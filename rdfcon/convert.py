"""convert.py

This module uses a conversion schema to process csv data into RDF.
"""

import csv
import logging
import re
from datetime import datetime
from functools import partial
from multiprocessing import Pool

import jinja2
from rdflib import Dataset, Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF
from tqdm import tqdm

from rdfcon.custom_functions import load_custom_functions
from rdfcon.namespace import NSM
from rdfcon.utils import (
    approx_size_of,
    compile_regex,
    count_rows,
    counter,
    get_uuid,
    replace_curly_terms,
)


def get_col_values(
    col: str,
    separator: str | None,
    regex: bool,
    as_iri: bool,
    datatype: URIRef,
    datestr: str | None,
    ns: URIRef | None,
    as_uuid: bool,
    ignore_case: bool,
    label: str | None,
    ttype: str | None,
) -> tuple[list[Literal | URIRef], Graph]:
    g = Graph()
    col_values = []
    if col.strip() == "":
        return col_values, g
    if separator:
        if regex:
            values = compile_regex(separator).split(col)
        else:
            values = col.split(separator)
    else:
        values = [col]
    for value in values:
        stripped = value.strip()
        if stripped == "":
            continue
        if as_iri:
            iri_str = stripped.strip("<>")
            if ns is None:
                try:
                    iri = URIRef(iri_str)
                    iri.n3()
                    col_values.append(iri)
                except Exception:
                    raise Exception(f"Could not interpret {iri_str} as an IRI")
            else:
                if ignore_case:
                    iri_str = iri_str.lower()
                if as_uuid:
                    iri_str = get_uuid(iri_str)
                try:
                    iri = URIRef(ns + iri_str)
                    iri.n3()
                    col_values.append(iri)
                except Exception:
                    raise Exception(
                        f"Could not interpret {iri_str} as an IRI using namespace {ns}"
                    )
            if label:
                g.add((iri, URIRef(label), Literal(value, datatype=datatype)))
            if ttype:
                g.add((iri, RDF.type, URIRef(ttype)))

        else:
            formatted_str = stripped
            if datestr:
                try:
                    dt = datetime.strptime(stripped, datestr)
                    formatted_str = dt.isoformat()
                except Exception:
                    logging.error(f"Could not parse {stripped} with datestr: {datestr}")
                    continue
            try:
                col_values.append(Literal(formatted_str, datatype=datatype))
            except ValueError as e:
                logging.error(f"Could not parse {value} as datatype {datatype}: {e}")

    return col_values, g


def warn_about_unused_columns(headers: list[str], spec: dict, filename: str) -> None:
    mapped_columns = set()
    if spec.get("identifier"):
        mapped_columns.add(spec["identifier"])
    if spec.get("columns"):
        [mapped_columns.add(str(column["column"])) for column in spec["columns"]]
    if spec.get("template"):
        for col in headers:
            if re.findall(rf"\{{.*{col}.*\}}", spec["template"]):
                mapped_columns.add(col)
    unmapped_columns = set(headers) - mapped_columns
    if unmapped_columns:
        logging.warning(
            f"{filename} contains {len(unmapped_columns)} unmapped columns: {unmapped_columns}"
        )
    return


def get_id_column(headers: list[str], spec: dict) -> int | None:
    if spec.get("identifier") is None:
        return None
    try:
        idcol = headers.index(spec["identifier"])
    except ValueError as e:
        raise ValueError(f"Column '{spec['identifier']}' does not exist: {e}")
    return idcol


def get_iri_for_row(row: list, idcol: int, ns: URIRef) -> URIRef | None:
    if idcol is None or row[idcol] == "":
        return None
    if ns:
        iri = ns[str(row[idcol])]
    else:
        try:
            iri = URIRef(row[idcol].strip("<>"))
            iri.n3()
        except Exception:
            raise Exception(f"Could not interpret {row[idcol]} as an IRI")
    return iri


def row_to_graph(headers: list[str], spec: dict, iri: URIRef, row: list) -> Graph:
    g = Graph()

    # type declarations
    if spec.get("types"):
        for type in spec["types"]:
            g.add((iri, RDF.type, type))

    # column conversions
    for coldef in spec.get("columns", []):
        col = headers.index(str(coldef["column"]))
        col_values, graph = get_col_values(
            col=row[col],
            separator=coldef["separator"],
            regex=coldef["regex"],
            datatype=coldef["datatype"],
            datestr=coldef["datestr"],
            as_iri=coldef["as_iri"],
            ns=coldef["namespace"],
            as_uuid=coldef["as_uuid"],
            ignore_case=coldef["ignore_case"],
            label=coldef["label"],
            ttype=coldef["type"],
        )
        for col_value in col_values:
            g.add((iri, coldef["predicate"], col_value))
        g += graph

    return g


def templated_expressions(
    headers: list[str],
    row: list,
    spec: dict,
    idcol: int,
) -> Graph:

    g = Graph()

    # escape double quotes in strings
    row = [cell.replace('"', r"\"") for cell in row]
    # escape new lines
    row = [cell.replace("\n", r"\n") for cell in row]
    r = {col: row[headers.index(col)] for col in headers}
    template_str = spec.get("prefixes", "") + replace_curly_terms(spec["template"])
    template = jinja2.Template(template_str)
    # add custom functions and python builtins to the template context
    custom_functions = load_custom_functions(spec.get("templateFunctions"))
    template.globals.update(custom_functions)
    template.globals.update(__builtins__)
    try:
        rendered = template.render(r=r, row=row, headers=headers)
    except Exception as e:
        raise Exception(f"Could not render the template string\n{template_str}: {e}")
    # remove datatypes from empty string literals to avoid parser warnings
    rendered = re.sub(r'""\^\^[\w:]+', '""', rendered)
    # replace empty IRIs with empty strings so they can be removed
    rendered = re.sub(r"<>", '""', rendered)
    # replace bare prefixes with a placeholder IRI so they can be removed
    rendered = re.sub(
        r"^(?!(?:@prefix|prefix))([^\n\"']*?)\b([\w-]+):(?=\s)",
        lambda m: m.group(1) + "<http://null>",
        rendered,
        flags=re.MULTILINE,
    )

    try:
        g += Graph().parse(data=rendered, format="turtle")
    except Exception as e:
        raise Exception(
            f"Could not parse rendered template expression\n{rendered}: {e}"
        )

    # remove empty literals from the graph
    empty_literals = g.query(
        "select ?s ?p ?o where { ?s ?p ?o . filter(str(?o) = '') }"
    )
    for s, p, o in empty_literals:
        g.remove((s, p, o))

    # remove null IRI placeholders
    null_triples = (triple for triple in g if URIRef("http://null") in triple)
    for triple in null_triples:
        g.remove(triple)

    # recursively remove empty blank nodes from the graph
    empty_bnode_query = "select ?o where { ?s ?p ?o . filter(isblank(?o)) . filter not exists { ?o ?x ?y } }"
    empty_bnodes = g.query(empty_bnode_query)
    while empty_bnodes:
        for o in empty_bnodes:
            g.remove((None, None, o))
            empty_bnodes = g.query(empty_bnode_query)

    return g


def process_row(
    row: list,
    idcol: int,
    headers: list,
    ns: Namespace,
    spec: dict,
) -> Graph:
    g = Graph()
    if spec.get("columns"):
        iri = get_iri_for_row(row, idcol, ns)
        g += row_to_graph(headers=headers, spec=spec, iri=iri, row=row)
    if spec.get("template"):
        g += templated_expressions(
            headers=headers,
            spec=spec,
            row=row,
            idcol=idcol,
        )
    return g


def convert(spec: dict, limit: int, processes: int) -> None:
    graph_name = spec.get("graph")
    d = Dataset()
    g = d.graph(graph_name)
    g.namespace_manager = NSM
    if graph_name:
        outfile = (spec["outdir"] / spec["infile"].with_suffix(".trig").name).resolve()
        format = "trig"
    else:
        outfile = (spec["outdir"] / spec["infile"].with_suffix(".ttl").name).resolve()
        format = "turtle"
    ns = Namespace(spec["namespace"]) if spec.get("namespace") else None
    total = count_rows(infile=spec["infile"]) - 1
    if limit <= 0 or total < limit:
        limit = total
    row_counter = counter()
    chunk_counter = counter()
    total_triples = 0
    total_size = 0
    with open(spec["infile"], "r", encoding=spec["encoding"]) as file:
        reader = csv.reader(file)
        headers = next(reader)
        warn_about_unused_columns(
            headers=headers, spec=spec, filename=spec["infile"].name
        )
        idcol = get_id_column(headers, spec)
        worker = partial(
            process_row,
            idcol=idcol,
            headers=headers,
            ns=ns,
            spec=spec,
        )
        with Pool(processes=processes) as pool:
            results = tqdm(
                pool.imap_unordered(worker, reader, chunksize=1),
                total=limit,
                initial=1,
            )
            for result in results:
                g += result
                i = next(row_counter)
                if i >= limit:
                    chunk = next(chunk_counter)
                    size = approx_size_of(g)
                    total_size += size
                    num_triples = len(g)
                    total_triples += num_triples
                    logging.info(
                        f"Serializing chunk {chunk}, ~ {size}Mb, {num_triples:,} {'quads' if graph_name else 'triples'}"
                    )
                    g.serialize(
                        destination=outfile.with_stem(f"{outfile.stem}-{chunk}"),
                        format=format,
                    )
                    break
                if spec.get("maxGraphSizeMb"):
                    if i % spec["sizeCheckFrequency"] == 0:
                        num_triples = len(g)
                        total_triples += num_triples
                        size = approx_size_of(g)
                        total_size += size
                        logging.info(
                            f"Current graph size ~ {size}Mb, {num_triples:,} {'quads' if graph_name else 'triples'}"
                        )
                        if size > spec["maxGraphSizeMb"]:
                            chunk = next(chunk_counter)
                            logging.info(
                                f"Serializing chunk {chunk}, ~ {size}Mb, {num_triples:,} {'quads' if graph_name else 'triples'}"
                            )
                            g.serialize(
                                destination=outfile.with_stem(
                                    f"{outfile.stem}-{chunk}"
                                ),
                                format=format,
                            )
                            del d
                            d = Dataset()
                            g = d.graph(graph_name)
                            g.namespace_manager = NSM
    logging.info(
        f"~ {total_size}Mb, {total_triples:,} {'quads' if graph_name else 'triples'} written to {spec['outdir']}"
    )
    return

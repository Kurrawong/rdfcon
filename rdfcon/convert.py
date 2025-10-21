"""convert.py

This module uses a conversion schema to process csv data into RDF.
"""

import csv
import logging
import re
from datetime import datetime
from functools import partial
from multiprocessing import Pool
from pathlib import Path

import jinja2
from rdflib import Dataset, Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF
from tqdm import tqdm

from rdfcon.namespace import NSM
from rdfcon.utils import (
    compile_regex,
    count_rows,
    generate_prefix_frontmatter,
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
    mapped_columns = [spec["identifier"]]
    if spec["columns"]:
        mapped_columns.extend([str(column["column"]) for column in spec["columns"]])
    if spec["template"]:
        mapped_columns.extend(re.findall(r"\{(.*?)\}", spec["template"]))
    unmapped_columns = [column for column in headers if column not in mapped_columns]
    if unmapped_columns:
        logging.warning(
            f"{filename} contains {len(unmapped_columns)} unmapped columns: {unmapped_columns}"
        )
    return


def get_id_column(headers: list[str], spec: dict) -> int:
    try:
        idcol = headers.index(spec["identifier"])
    except ValueError as e:
        raise ValueError(f"Column '{spec['identifier']}' does not exist: {e}")
    return idcol


def get_iri_for_row(row: list, idcol: int, ns: URIRef) -> URIRef | None:
    if row[idcol] == "":
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
    for coldef in spec["columns"]:
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
    headers: list[str], row: list, iri: URIRef, spec: dict, idcol: int
) -> Graph:

    g = Graph()
    if not spec["template"]:
        return g

    # escape double quotes in strings
    row = [cell.replace('"', r"\"") for cell in row]
    # escape new lines
    row = [cell.replace("\n", r"\n") for cell in row]
    prefixes = generate_prefix_frontmatter()
    template_str = prefixes + replace_curly_terms(spec["template"])
    template = jinja2.Template(template_str)
    rendered = template.render(row=row, headers=headers)
    # remove datatypes from empty string literals to avoid parser warnings
    rendered = re.sub(r'""\^\^[\w:]+', '""', rendered)
    try:
        g += Graph().parse(data=rendered, format="turtle")
    except Exception as e:
        raise Exception(f"Could not parse templated expression {template_str}: {e}")

    # remove empty literals from the graph
    empty_literals = g.query(
        "select ?s ?p ?o where { ?s ?p ?o . filter(str(?o) = '') }"
    )
    for s, p, o in empty_literals:
        g.remove((s, p, o))

    # recursively remove empty blank nodes from the graph
    empty_bnode_query = "select ?o where { ?s ?p ?o . filter(isblank(?o)) . filter not exists { ?o ?x ?y } }"
    empty_bnodes = g.query(empty_bnode_query)
    while empty_bnodes:
        for o in empty_bnodes:
            g.remove((None, None, o))
            empty_bnodes = g.query(empty_bnode_query)
    return g


def process_row(
    row: list, idcol: int, headers: list, ns: Namespace, spec: dict
) -> Graph:
    g = Graph()
    iri = get_iri_for_row(row, idcol, ns)
    if iri:
        g += row_to_graph(headers=headers, spec=spec, iri=iri, row=row)
        g += templated_expressions(
            headers=headers, spec=spec, iri=iri, row=row, idcol=idcol
        )
    return g


def convert(infile: Path, spec: dict, outdir: Path, limit: int) -> None:
    d = Dataset()
    graph_name = spec.get("graph")
    g = d.graph(graph_name)
    if graph_name:
        outfile = (outdir / infile.with_suffix(".trig").name).resolve()
        format = "trig"
    else:
        outfile = (outdir / infile.with_suffix(".ttl").name).resolve()
        format = "turtle"
    ns = Namespace(spec["namespace"]) if spec["namespace"] else None
    [g.bind(ns, uri) for ns, uri in NSM.namespaces()]
    total = count_rows(infile=infile) - 1
    with open(infile, "r") as file:
        reader = csv.reader(file)
        headers = next(reader)
        warn_about_unused_columns(headers=headers, spec=spec, filename=infile.name)
        idcol = get_id_column(headers, spec)
        worker = partial(process_row, idcol=idcol, headers=headers, ns=ns, spec=spec)
        with Pool() as pool:
            results = tqdm(pool.imap_unordered(worker, reader), total=total)
            for result in results:
                g += result
    g.serialize(destination=outfile, format=format)
    logging.info(
        f"{len(g)} {'quads' if graph_name else 'triples'} written to {outfile}"
    )
    return

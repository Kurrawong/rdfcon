"""convert.py

This module uses a conversion schema to process csv data into RDF.
"""

import csv
import logging
import re
import string
import uuid
from pathlib import Path

from rdflib import Dataset, Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF

from rdfcon.namespace import NSM

logger = logging.getLogger(__name__)


def get_col_values(
    col: str,
    separator: str | None,
    as_iri: bool,
    datatype: URIRef,
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
                    iri_str = str(uuid.uuid3(uuid.NAMESPACE_DNS, iri_str))
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
            try:
                col_values.append(Literal(value, datatype=datatype))
            except ValueError as e:
                logger.error(f"Could not parse {value} as datatype {datatype}: {e}")

    return col_values, g


def warn_about_unused_columns(headers: list[str], spec: dict, filename: str) -> None:
    mapped_columns = [spec["identifier"]]
    if spec["columns"]:
        mapped_columns.extend([str(column["column"]) for column in spec["columns"]])
    if spec["template"]:
        mapped_columns.extend(re.findall(r"\{(.*?)\}", spec["template"]))
    unmapped_columns = [column for column in headers if column not in mapped_columns]
    if unmapped_columns:
        logger.warning(
            f"WARNING: {filename} contains {len(unmapped_columns)} unmapped columns: {unmapped_columns}"
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
    for type in spec["types"]:
        g.add((iri, RDF.type, type))

    # column conversions
    for coldef in spec["columns"]:
        col = headers.index(str(coldef["column"]))
        col_values, graph = get_col_values(
            col=row[col],
            separator=coldef["separator"],
            datatype=coldef["datatype"],
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
    headers: list[str], row: list, iri: URIRef, spec: dict
) -> Graph:

    def as_uuid(value: str) -> str:
        new_uuid = str(uuid.uuid3(uuid.NAMESPACE_DNS, value))
        return new_uuid

    g = Graph()
    if not spec["template"]:
        return g

    # generate prefix front matter for template
    prefixes = ""
    for ns, uri in NSM.namespaces():
        prefixes += f"@prefix {ns}: <{uri}> .\n"

    vars = ""
    for col in headers:
        valid_colname = (
            set(col).intersection(set(string.punctuation + " ") - set("_")) == set()
        )
        if col == spec["identifier"]:
            value = iri.n3()
            vars += f"{col}='{value}',"
        elif valid_colname:
            value = (
                row[headers.index(col)]
                .replace('"', "")
                .replace("'", "")
                .replace("\n", " ")
            )
            vars += f"{col}='{value}',"
    try:
        formatted = eval(f"spec['template'].format({vars}).strip()")

    except Exception as e:
        raise Exception(
            f"Could not format templated expression {spec['template']}: {e}\n"
            f"vars string {vars}"
        )
    template = prefixes + formatted
    # remove datatypes from empty string literals to avoid parser warnings
    template = re.sub(r'""\^\^[\w:]+', '""', template)

    try:
        g += Graph().parse(data=template, format="turtle")
    except Exception as e:
        raise Exception(f"Could not parse templated expression {formatted}: {e}")

    # remove empty literals from the graph
    empty_literals = g.query(
        "select ?s ?p ?o where { ?s ?p ?o . filter(str(?o) = '') }"
    )
    for s, p, o in empty_literals:
        g.remove((s, p, o))

    # recursively remove empty blank nodes from the graph
    empty_bnodes = g.query(
        "select ?o where { ?s ?p ?o . filter(isblank(?o)) . filter not exists { ?o ?x ?y } }"
    )
    while empty_bnodes:
        for o in empty_bnodes:
            g.remove((None, None, o))
            empty_bnodes = g.query(
                "select ?o where { ?s ?p ?o . filter(isblank(?o)) . filter not exists { ?o ?x ?y } }"
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
    with open(infile, "r") as file:
        reader = csv.reader(file)
        headers = next(reader)
        warn_about_unused_columns(headers=headers, spec=spec, filename=infile.name)
        idcol = get_id_column(headers, spec)
        for i, row in enumerate(reader):
            print(f"processing row {i + 1}", end="\r", flush=True)
            if limit and i > limit:
                break
            iri = get_iri_for_row(row, idcol, ns)
            if not iri:
                continue
            g += row_to_graph(headers, spec, iri, row)
            g += templated_expressions(headers, row, iri, spec)
        print("done".ljust(100, " "))
    g.serialize(destination=outfile, format=format)
    logger.info(f"{len(g)} {'quads' if graph_name else 'triples'} written to {outfile}")
    return

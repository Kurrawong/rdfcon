"""utils.py

general utility functions to be used in other modules
"""

import csv
import functools
import logging
import re
import time
import uuid
from pathlib import Path

import cerberus
import yaml
from rdflib import URIRef

from rdfcon.namespace import NSM
from rdfcon.schemas import md_schema


def timer(func):
    @functools.wraps(func)
    def wrapped(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        end = time.time()
        logging.debug(f"{func.__name__} took {end - start:.4f} seconds")
        return result

    return wrapped


@functools.lru_cache(maxsize=128)
def generate_prefix_frontmatter() -> str:
    prefixes = ""
    for ns, uri in NSM.namespaces():
        prefixes += f"@prefix {ns}: <{uri}> .\n"
    return prefixes


@functools.lru_cache(maxsize=128)
def get_uuid(value: str) -> str:
    new_uuid = str(uuid.uuid3(uuid.NAMESPACE_DNS, value))
    return new_uuid


@functools.lru_cache(maxsize=128)
def compile_regex(pattern: str) -> re.Pattern:
    return re.compile(pattern=pattern)


@timer
def count_rows(infile: Path) -> int:
    with open(infile, "r") as f:
        return sum(1 for _ in csv.reader(f))


@timer
def parse_config_from_yaml(spec: Path) -> dict:
    with open(spec, "r") as file:
        try:
            parsed_spec = yaml.safe_load(file)
        except yaml.YAMLError as e:
            logging.error(f"Error loading {spec.name}: {e}")
    v = cerberus.Validator(md_schema)
    if not v.validate(parsed_spec):
        raise cerberus.DocumentError(f"Could not validate {spec.name}: {v.errors}")
    parsed_spec = v.normalized(parsed_spec)

    for prefix in parsed_spec["prefixes"]:
        for ns, uri in prefix.items():
            NSM.bind(ns, uri.strip("<>"))

    def resolve_uris(item):
        if isinstance(item, dict):
            for k, v in item.items():
                if not k == "template":
                    item[k] = resolve_uris(v)
            return item
        elif isinstance(item, list):
            for i in range(len(item)):
                item[i] = resolve_uris(item[i])
            return item
        elif isinstance(item, str):
            x = item.strip("<>")
            if x.startswith("http"):
                try:
                    item = URIRef(x)
                    item.n3()
                except Exception:
                    pass
            else:
                try:
                    item = NSM.expand_curie(x)
                except ValueError:
                    pass
            return item
        else:
            return item

    resolve_uris(parsed_spec)
    if parsed_spec["columns"]:
        assert parsed_spec[
            "identifier"
        ], "If column specs are given, you must specify the id column as the identifier"
    return parsed_spec


@functools.lru_cache(maxsize=128)
def replace_curly_terms(text) -> str:
    # Find and replace {something} with {row[headers.index('something')]}
    def repl(match):
        inner = match.group(1)
        return f"{{{{row[headers.index('{inner}')]}}}}"

    # Match text inside single curly braces, not including nested ones
    pattern = r"\{([^{}]+?)\}"
    return re.sub(pattern, repl, text)

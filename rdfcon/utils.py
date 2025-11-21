"""utils.py

general utility functions to be used in other modules
"""

import csv
import functools
import logging
import math
import pickle
import re
import time
import uuid
from copy import deepcopy
from pathlib import Path
from typing import Iterator

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
def get_uuid(value: str) -> str:
    new_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, value))
    return new_uuid


@functools.lru_cache(maxsize=128)
def compile_regex(pattern: str) -> re.Pattern:
    return re.compile(pattern=pattern)


@timer
def count_rows(infile: Path) -> int:
    with open(infile, "r") as f:
        return sum(1 for _ in csv.reader(f))


def resolve_path(path_str: str, spec_path: Path, directory: bool = False) -> Path:
    path = Path(path_str)
    if not path.is_absolute():
        path = spec_path.parent / path
    if not path.exists():
        raise FileNotFoundError(f"Could not find the file {path}")
    if not directory and path.is_dir():
        raise ValueError(f"{path} is a directory")
    elif directory and path.is_file():
        raise ValueError(f"{path} is a file")
    return path


def merge(base: dict, new: dict) -> dict:
    """Merge two dictionaries but smarter than .update"""
    merged = {}
    for k, new_value in new.items():
        old_value = base.get(k)
        if isinstance(old_value, dict) and isinstance(new_value, dict):
            merged[k] = merge(old_value, new_value)
        elif new_value:
            merged[k] = new_value
        elif old_value:
            merged[k] = old_value
    return merged


@timer
def parse_config_from_yaml(spec: Path, imported: bool = False) -> dict:
    logging.debug(f"Parsing config from {spec.name}")
    with open(spec, "r") as file:
        try:
            this_spec = yaml.safe_load(file)
        except yaml.YAMLError as e:
            logging.error(f"Error loading {spec.name}: {e}")

    if imported:
        schema = deepcopy(md_schema)
        schema["infile"]["required"] = False
    else:
        schema = md_schema
    v = cerberus.Validator(schema)
    if not v.validate(this_spec):
        raise cerberus.DocumentError(f"Could not validate {spec.name}: {v.errors}")
    this_spec = v.normalized(this_spec)

    merged_spec = {}
    if this_spec["imports"]:
        for item in this_spec["imports"]:
            subspec_path = resolve_path(item, spec)
            subspec = parse_config_from_yaml(subspec_path, imported=True)
            merged_spec = merge(base=merged_spec, new=subspec)
    merged_spec = merge(base=merged_spec, new=this_spec)

    if not imported:
        merged_spec["infile"] = resolve_path(
            path_str=merged_spec["infile"], spec_path=spec
        )
        merged_spec["outdir"] = resolve_path(
            path_str=merged_spec.get("outdir", ""),
            spec_path=spec,
            directory=True,
        )

    if merged_spec.get("prefixes") and not imported:
        for ns, uri in merged_spec["prefixes"].items():
            NSM.bind(ns, uri.strip("<>"))
        prefixes = ""
        for ns, uri in NSM.namespaces():
            prefixes += f"@prefix {ns}: <{uri}> .\n"
        merged_spec["prefixes"] = prefixes

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

    resolve_uris(merged_spec)
    if merged_spec.get("columns"):
        assert merged_spec[
            "identifier"
        ], "If column specs are given, you must specify the id column as the identifier"

    # resolve path to custom template functions
    if merged_spec.get("templateFunctions"):
        merged_spec["templateFunctions"] = resolve_path(
            merged_spec["templateFunctions"], spec
        )
    return merged_spec


@functools.lru_cache(maxsize=128)
def replace_curly_terms(text) -> str:
    # Find and replace {something} with {{ r['something'] }} except for Jinja tags
    def repl(match):
        inner = match.group(1)
        return f"{{{{ r['{inner}'] }}}}"

    # Match single curly braces that are NOT for Jinja-like {% ... %} tags
    pattern = r"(?<!\{)\{(?!%)([^{}]+?)(?<!%)\}(?!\})"
    return re.sub(pattern, repl, text)


def counter(start: int = 1, step: int = 1) -> Iterator[int]:
    i = start
    while True:
        yield i
        i += step
    return StopIteration


def approx_size_of(x: object) -> float:
    """Return the approximate size of an object in mebibytes

    Measures the length in bytes of the pickled object divided by 3*
    then converted to mebibytes.

    It is only approximate and can vary significantly depending on the
    structure of the object.

    *3 is arbritary but based on experience. mileage may vary.
    """
    p = pickle.dumps(x)
    bites = len(p)
    mebibytes = math.floor(bites / 3 / 1024 / 1024)
    return mebibytes

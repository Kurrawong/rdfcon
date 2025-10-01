"""utils.py

general utility functions to be used in other modules
"""

from pathlib import Path

import cerberus
import yaml
from logs import logger
from namespace import NSM
from rdflib import URIRef
from schemas import md_schema


def parse_config_from_yaml(spec: Path) -> dict:
    with open(spec, "r") as file:
        try:
            parsed_spec = yaml.safe_load(file)
        except yaml.YAMLError as e:
            logger.error(f"Error loading {spec.name}: {e}")
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
    return parsed_spec

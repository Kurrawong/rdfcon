"""schemas.py

This module defines a schema for the YAML conversion templates.
It is used to validate them before execution.

See: https://docs.python-cerberus.org/schemas.html
"""

md_schema = {
    "prefixes": {
        "type": "list",
        "schema": {
            "type": "dict",
            "keysrules": {"type": "string"},
            "valuesrules": {"type": "string", "regex": "^<http[s]?://.*>"},
        },
        "required": False,
    },
    "infile": {"type": "string", "required": True},
    "outdir": {"type": "string", "required": False},
    "graph": {"type": "string", "required": False},
    "namespace": {"type": "string", "default": None, "nullable": True},
    "identifier": {"type": "string", "required": True},
    "types": {
        "type": "list",
        "schema": {"type": "string"},
        "required": False,
    },
    "columns": {
        "type": "list",
        "default": None,
        "schema": {
            "type": "dict",
            "schema": {
                "column": {"type": "string", "required": True},
                "predicate": {"type": "string", "required": True},
                "datatype": {
                    "type": "string",
                    "default": "<http://www.w3.org/2001/XMLSchema#string>",
                },
                "datestr": {
                    "type": "string",
                    "default": None,
                    "nullable": True,
                    "regex": r"^(%[aAbBcdHIjmMpSUwWxXyYzZfGuvV]|[%\-\s:./,]+)+$",
                },
                "separator": {"type": "string", "default": None, "nullable": True},
                "regex": {
                    "type": "boolean",
                    "default": False,
                    "nullable": True,
                },
                "as_iri": {"type": "boolean", "default": False},
                "namespace": {"type": "string", "default": None, "nullable": True},
                "as_uuid": {"type": "boolean", "default": False},
                "ignore_case": {"type": "boolean", "default": False},
                "label": {"type": "string", "default": None, "nullable": True},
                "type": {"type": "string", "default": None, "nullable": True},
            },
        },
        "required": False,
    },
    "template": {"type": "string", "default": None, "nullable": True},
}

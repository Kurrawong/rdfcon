"""schemas.py

This module defines a schema for the YAML conversion templates.
It is used to validate them before execution.

See: https://docs.python-cerberus.org/schemas.html
"""

import locale

md_schema = {
    "imports": {
        "type": "list",
        "schema": {
            "type": "string",
        },
        "nullable": True,
        "required": False,
        "default": None,
    },
    "prefixes": {
        "type": "dict",
        "keysrules": {"type": "string"},
        "valuesrules": {"type": "string", "regex": "^<http[s]?://.*>"},
        "nullable": True,
        "default": None,
        "required": False,
    },
    "infile": {"type": "string", "required": True},
    "encoding": {
        "type": "string",
        "required": False,
        "default": locale.getpreferredencoding(),
    },
    "outdir": {"type": "string", "required": False},
    "maxGraphSizeMb": {
        "type": "integer",
        "required": False,
        "default": None,
        "nullable": True,
        "min": 1,
    },
    "sizeCheckFrequency": {
        "type": "integer",
        "required": False,
        "default": 30000,
        "min": 1,
    },
    "graph": {"type": "string", "required": False},
    "namespace": {
        "type": "string",
        "default": None,
        "required": False,
        "nullable": True,
    },
    "identifier": {
        "type": "string",
        "default": None,
        "required": False,
        "nullable": True,
    },
    "types": {
        "type": "list",
        "default": [],
        "schema": {"type": "string"},
        "required": False,
    },
    "columns": {
        "type": "list",
        "default": [],
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
    "templateFunctions": {
        "type": "string",
        "default": None,
        "nullable": True,
        "regex": r".*\.py$",
    },
    "template": {"type": "string", "default": None, "nullable": True},
}

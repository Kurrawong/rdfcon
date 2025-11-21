"""__main__.py

This module gathers command line arguments for rdfcon when
called from the command line.
"""

import argparse
import logging
import logging.config
import multiprocessing
import webbrowser
from importlib.metadata import version
from pathlib import Path
from pprint import pformat

from rdfcon.config.logs import logging_config
from rdfcon.convert import convert
from rdfcon.utils import parse_config_from_yaml


def get_spec(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Spec file could not be found at {path}")
    spec = parse_config_from_yaml(path)
    return spec


def main():
    parser = argparse.ArgumentParser(
        prog="convert.py",
        description="convert tabular data to RDF using a YAML specification file",
        add_help=True,
        allow_abbrev=True,
    )
    parser.add_argument("spec", nargs="?", help="YAML conversion specification file")
    parser.add_argument(
        "-n", "--limit", help="Max number of rows to process", default=0, type=int
    )
    parser.add_argument(
        "-p",
        "--processes",
        help="Maximum number of processes, defaults to number of CPU cores -1",
        dest="processes",
        default=multiprocessing.cpu_count() - 1,
        type=int,
    )
    parser.add_argument(
        "--ui",
        action="store_true",
        help="Open a browser based ui for creating spec files",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        help="increase output verbosity (use -v, -vv, -vvv, etc.)",
        action="count",
        dest="verbosity",
        default=0,
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"rdfcon {version('rdfcon')}",
        help="Show the version and exit.",
    )
    args = parser.parse_args()
    loglevel = max(logging.DEBUG, (logging.ERROR - (10 * args.verbosity)))
    logging_config["handlers"]["console"]["level"] = loglevel
    logging.config.dictConfig(logging_config)
    if not any([args.spec, args.ui]):
        parser.error("spec is required unless --ui is given")
    if all([args.spec, args.ui]):
        parser.error("illegal flag combination, only one of spec or --ui can be given")

    assert (
        0 < args.processes <= multiprocessing.cpu_count()
    ), "--processes must be between 1 and the number of available cpu cores"

    if args.ui:
        webbrowser.open(f"file:///{Path(__file__).parent / 'ui' / 'index.html'}")
        exit()
    spec_path = Path(args.spec)
    spec = get_spec(path=spec_path)

    logging.debug("Parsed conversion doc")
    logging.debug("-" * 80)
    logging.debug(pformat(spec))
    logging.debug("-" * 80)

    convert(
        spec=spec,
        limit=args.limit,
        processes=args.processes,
    )


if __name__ == "__main__":
    main()

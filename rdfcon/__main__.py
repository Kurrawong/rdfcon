"""__main__.py

This module gathers command line arguments for rdfcon when
called from the command line.
"""

import argparse
import logging
import logging.config
import webbrowser
from pathlib import Path

from rdfcon.config.logs import logging_config
from rdfcon.convert import convert
from rdfcon.utils import parse_config_from_yaml


def get_spec(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Spec file could not be found at {path}")
    spec = parse_config_from_yaml(path)
    return spec


def resolve_paths(default_dir: Path, spec: dict) -> tuple[Path]:
    if Path(spec["infile"]).is_absolute():
        infile = Path(spec["infile"])
    else:
        infile = Path((default_dir / spec["infile"]).resolve())
    if not infile.exists():
        raise FileNotFoundError(f"Data file {infile} could not be found")
    if not spec.get("outdir"):
        outdir = infile.parent
    elif Path(spec["outdir"]).is_absolute():
        outdir = Path(spec["outdir"])
    else:
        outdir = (default_dir / spec["outdir"]).resolve()

    return infile, outdir


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
        "--ui",
        action="store_true",
        help="Open a browser based ui for creating spec files",
    )
    parser.add_argument(
        "-v", "--verbose", help="more verbose logging", action="store_true"
    )
    args = parser.parse_args()
    if args.verbose:
        logging_config["handlers"]["console"]["level"] = "DEBUG"
    logging.config.dictConfig(logging_config)
    if not any([args.spec, args.ui]):
        parser.error("spec is required unless --ui is given")
    if all([args.spec, args.ui]):
        parser.error("illegal flag combination, only one of spec or --ui can be given")

    if args.ui:
        webbrowser.open(str(Path(__file__).parent / "ui" / "index.html"))
        exit()
    spec_path = Path(args.spec)
    spec = get_spec(path=spec_path)
    infile, outdir = resolve_paths(default_dir=spec_path.parent, spec=spec)

    logging.debug("Parsed conversion doc")
    logging.debug("-" * 80)
    logging.debug(__import__("pprint").pformat(spec))
    logging.debug("-" * 80)

    convert(infile=infile, spec=spec, outdir=outdir, limit=args.limit)


if __name__ == "__main__":
    main()

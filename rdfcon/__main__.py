"""__main__.py

This module gathers command line arguments for rdfcon when
called from the command line.
"""

import argparse
from pathlib import Path

from convert import convert
from logs import addFileHandler, logger
from utils import parse_config_from_yaml


def cli() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="convert.py",
        description="convert tabular data to RDF using a YAML specification file",
        add_help=True,
        allow_abbrev=True,
    )
    parser.add_argument("spec", help="YAML conversion specification file")
    parser.add_argument(
        "-n", "--limit", help="Max number of rows to process", default=0, type=int
    )
    args = parser.parse_args()
    return args


if __name__ == "__main__":
    args = cli()
    specpath = Path(args.spec)
    if not specpath.exists():
        raise FileNotFoundError(f"Spec file {specpath} could not be found")
    spec = parse_config_from_yaml(specpath)
    if Path(spec["infile"]).is_absolute():
        data = Path(spec["infile"])
    else:
        data = Path((specpath / spec["infile"]).resolve())
    if not data.exists():
        raise FileNotFoundError(f"Data file {data} could not be found")
    if not spec.get("outdir"):
        outdir = data.parent
    elif Path(spec["outdir"]).is_absolute():
        outdir = Path(spec["outdir"])
    else:
        outdir = (specpath / spec["outdir"]).resolve()

    logfile = outdir / data.with_suffix(".log").name
    addFileHandler(logfile)
    logger.info(f"using dataset configuration {specpath} for {data}")
    logger.info("-" * 80)
    logger.info(__import__("pprint").pformat(spec))
    logger.info("-" * 80)

    convert(data=data, spec=spec, outdir=outdir, limit=args.limit)

"""__main__.py

This module gathers command line arguments for rdfcon when
called from the command line.
"""

import argparse
import logging
import logging.config
from pathlib import Path

from config.logs import logging_config
from convert import convert
from utils import parse_config_from_yaml

logging.config.dictConfig(logging_config)
logger = logging.getLogger(__name__)


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


if __name__ == "__main__":
    args = cli()
    spec_path = Path(args.spec)
    spec = get_spec(path=spec_path)
    infile, outdir = resolve_paths(default_dir=spec_path.parent, spec=spec)

    logger.info(f"using dataset configuration {spec_path} for {infile}")
    logger.info("-" * 80)
    logger.info(__import__("pprint").pformat(spec))
    logger.info("-" * 80)

    convert(infile=infile, spec=spec, outdir=outdir, limit=args.limit)

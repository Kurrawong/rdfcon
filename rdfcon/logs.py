"""logs.py

This module sets up logging for use in the other modules.
It must be imported to take effect.
"""

import logging
from pathlib import Path

logger = logging.getLogger()
logger.setLevel(logging.INFO)
stream_handler = logging.StreamHandler()


class CustomFormatter(logging.Formatter):
    """Custom logging formatter to color the log level outputs."""

    # ANSI escape codes for colors
    GREY = "\x1b[38;21m"
    YELLOW = "\x1b[33;21m"
    RED = "\x1b[31;21m"
    RESET = "\x1b[0m"
    FORMAT = "%(asctime)s - %(levelname)-8s | %(message)s"

    FORMATS = {
        logging.INFO: GREY + FORMAT + RESET,
        logging.WARNING: YELLOW + FORMAT + RESET,
        logging.ERROR: RED + FORMAT + RESET,
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno, self.FORMAT)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


# Add the formatter to the stream handler
formatter = CustomFormatter()
stream_handler.setFormatter(formatter)

stream_handler.setLevel(logging.INFO)
logger.addHandler(stream_handler)


def addFileHandler(file: Path):
    if file.exists():
        file.unlink()
    if not file.parent.exists():
        file.parent.mkdir()
    file_handler = logging.FileHandler(file)
    file_handler.setLevel(logging.WARNING)
    logger.addHandler(file_handler)

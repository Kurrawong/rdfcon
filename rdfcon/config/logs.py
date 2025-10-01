import datetime
import logging
from pathlib import Path


class ColorFormatter(logging.Formatter):
    """Custom logging formatter to color the log level outputs."""

    grey = "\x1b[38;21m"
    yellow = "\x1b[33;21m"
    red = "\x1b[31;21m"
    reset = "\x1b[0m"
    format_str = "%(asctime)s - %(levelname)-8s | %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"
    formats = {
        logging.DEBUG: grey + format_str + reset,
        logging.WARNING: yellow + format_str + reset,
        logging.ERROR: red + format_str + reset,
        logging.CRITICAL: red + format_str + reset,
    }

    def format(self, record):
        fmt = self.formats.get(record.levelno, self.format_str)
        formatter = logging.Formatter(fmt=fmt, datefmt=self.datefmt)
        return formatter.format(record)


logging_config = {
    "version": 1,
    "root": {"level": "NOTSET", "handlers": ["console", "file"]},
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": "INFO",
            "formatter": "color",
        },
        "file": {
            "class": "logging.FileHandler",
            "level": "DEBUG",
            "formatter": "color",
            "filename": f"{Path.cwd()}/{datetime.date.today().isoformat()}.log",
        },
    },
    "formatters": {
        "color": {
            "()": "config.logs.ColorFormatter",
        }
    },
}

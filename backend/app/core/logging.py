from __future__ import annotations

import logging
import os


def configure_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler()
    if os.getenv("ENV", "production") != "development":
        try:
            from pythonjsonlogger import jsonlogger
            handler.setFormatter(
                jsonlogger.JsonFormatter("%(asctime)s %(levelname)s %(name)s %(message)s")
            )
        except ImportError:
            handler.setFormatter(
                logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
            )
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        )
    logging.root.setLevel(level)
    logging.root.handlers = [handler]


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)

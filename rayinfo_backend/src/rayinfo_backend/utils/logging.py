from __future__ import annotations

import logging

_LOG_FORMAT = "[%(asctime)s] %(levelname)s %(name)s: %(message)s"


def setup_logging(level: int = logging.INFO):
    logging.basicConfig(level=level, format=_LOG_FORMAT)
    return logging.getLogger("rayinfo")

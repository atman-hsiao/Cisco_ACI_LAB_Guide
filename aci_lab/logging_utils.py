from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path


def exception_logger(root: Path) -> logging.Logger:
    log_dir = root / "logs"
    log_dir.mkdir(exist_ok=True)
    logger = logging.getLogger("aci_lab")
    if not logger.handlers:
        logger.setLevel(logging.WARNING)
        path = log_dir / f"aci-lab-{datetime.now():%Y%m%d-%H%M%S}.log"
        handler = logging.FileHandler(path, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
    return logger


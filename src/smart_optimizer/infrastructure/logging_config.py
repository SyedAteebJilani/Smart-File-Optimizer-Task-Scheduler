from __future__ import annotations

import logging
from pathlib import Path


def configure_logging(data_dir: Path) -> logging.Logger:
    data_dir.mkdir(parents=True, exist_ok=True)
    log_path = data_dir / "smart_optimizer.log"
    logger = logging.getLogger("smart_optimizer")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s [%(threadName)s] %(name)s: %(message)s"
    )
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)
    return logger


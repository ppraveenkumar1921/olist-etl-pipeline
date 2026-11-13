import logging
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "raw"
PROCESSED_DIR = BASE_DIR / "data" / "processed"
LOG_DIR = BASE_DIR / "logs"


def get_logger(name: str) -> logging.Logger:
    LOG_DIR.mkdir(exist_ok=True)
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
        file_handler = logging.FileHandler(LOG_DIR / "pipeline.log", encoding="utf-8")
        file_handler.setFormatter(fmt)
        console = logging.StreamHandler()
        console.setFormatter(fmt)
        logger.addHandler(file_handler)
        logger.addHandler(console)
    return logger
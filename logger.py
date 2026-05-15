"""
Структурированное логирование для FRIDAY.
Пишет в файл + stdout. Ротация по размеру.
"""
import logging
import sys
from logging.handlers import RotatingFileHandler
from config import LOG_LEVEL, LOG_FILE


def setup_logger(name: str = "friday") -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))

    if logger.handlers:
        return logger

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Stdout
    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(fmt)
    logger.addHandler(stream)

    # Файл с ротацией (5 МБ, 3 файла)
    try:
        file_handler = RotatingFileHandler(
            LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
        )
        file_handler.setFormatter(fmt)
        logger.addHandler(file_handler)
    except Exception:
        pass  # Если файл недоступен — только stdout

    return logger


log = setup_logger()

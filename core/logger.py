"""
core/logger.py — Centralized logging configuration.

Single source of truth for logging across the entire project.
Every module imports get_logger() from here — nothing else.
"""

import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler

LOG_DIR = Path("logs")
LOG_FILE = LOG_DIR / "agent_app.log"


def setup_logging(log_level: str = "INFO") -> None:
    """
    Call once at app startup (cli.py and main.py).

    Sets up:
    - RotatingFileHandler → logs/agent_app.log (max 5MB, 3 backups)
    - StreamHandler → stdout (INFO and above)

    Format: [TIMESTAMP] [LEVEL] [module_name] message
    """
    LOG_DIR.mkdir(exist_ok=True)

    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(log_level.upper())

    # Prevent duplicate handlers on repeated calls
    if root.handlers:
        return

    # File handler — rotating, max 5MB per file, keep 3 backups
    fh = RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3)
    fh.setFormatter(fmt)

    # Console handler — INFO and above only
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)

    root.addHandler(fh)
    root.addHandler(ch)


def get_logger(name: str) -> logging.Logger:
    """Use this in every module: logger = get_logger(__name__)"""
    return logging.getLogger(name)

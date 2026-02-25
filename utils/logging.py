"""Logging configuration for MatchKit."""
import logging
import sys

from config.settings import settings


def setup_logging() -> None:
    """Configure application-wide logging.

    Call this once at application startup (e.g., in api/main.py lifespan).
    """
    log_level = logging.DEBUG if settings.debug else logging.INFO

    root = logging.getLogger()
    root.setLevel(log_level)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)

    if not root.handlers:
        root.addHandler(handler)

    # Quiet noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if settings.debug else logging.WARNING
    )
    logging.getLogger("apscheduler").setLevel(logging.INFO)

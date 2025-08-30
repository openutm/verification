"""
Logging utilities for the OpenUTM Verification Tool.
"""

from pathlib import Path

from loguru import logger


def setup_logging(output_dir: Path, base_filename: str, formats: list, debug: bool = False):
    """
    Configures logging to write to the console and optionally to a file.
    Returns the path to the log file if created, otherwise None.
    """
    console_level = "DEBUG" if debug else "INFO"
    log_file_path = None

    logger.remove()  # Remove default handler

    if "log" in formats:
        log_file_path = output_dir / f"{base_filename}.log"
        logger.add(
            log_file_path,
            level="DEBUG",
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} [{level}] - {message}",
        )

    logger.add(
        lambda msg: print(msg, end=""),
        level=console_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> [<level>{level}</level>] - <level>{message}</level>",
    )
    return log_file_path

import argparse
from datetime import datetime, timezone
from pathlib import Path

import yaml
from loguru import logger

from openutm_verification.config_models import AppConfig
from openutm_verification.runner import run_verification_scenarios


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


def main():
    """
    Main entry point for the verification script.
    """
    parser = argparse.ArgumentParser(description="Run OpenUTM Verification Scenarios.")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/default.yaml"),
        help="Path to the configuration file.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging on the console.",
    )
    args = parser.parse_args()

    with open(args.config, "r", encoding="utf-8") as f:
        config_data = yaml.safe_load(f)
    config = AppConfig(**config_data)

    output_dir = Path(config.reporting.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    run_timestamp = datetime.now(timezone.utc)
    base_filename = f"report_{run_timestamp.strftime('%Y-%m-%dT%H-%M-%SZ')}"
    log_file = setup_logging(output_dir, base_filename, config.reporting.formats, args.debug)

    # Run verification scenarios
    run_verification_scenarios(config, args.config)

    if log_file:
        logger.info(f"Log file saved to: {log_file}")


if __name__ == "__main__":
    main()

"""
Command Line Interface for OpenUTM Verification Tool.
"""

from datetime import datetime, timezone
from pathlib import Path

import yaml

from openutm_verification.cli.parser import create_parser
from openutm_verification.config_models import AppConfig, ConfigProxy
from openutm_verification.core import run_verification_scenarios
from openutm_verification.utils.logging import setup_logging


def main():
    """
    Main entry point for the verification script.
    """
    parser = create_parser()
    args = parser.parse_args()

    # Load configuration
    with open(args.config, "r", encoding="utf-8") as f:
        config_data = yaml.safe_load(f)
    config = AppConfig.model_validate(config_data)
    ConfigProxy.initialize(config)

    # Setup logging
    output_dir = Path(config.reporting.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    run_timestamp = datetime.now(timezone.utc)
    base_filename = f"report_{run_timestamp.strftime('%Y-%m-%dT%H-%M-%SZ')}"
    log_file = setup_logging(output_dir, base_filename, config.reporting.formats, args.debug)

    # Run verification scenarios
    run_verification_scenarios(config, args.config)

    if log_file:
        from loguru import logger

        logger.info(f"Log file saved to: {log_file}")


if __name__ == "__main__":
    main()

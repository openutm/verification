import argparse
import os
from datetime import datetime

import yaml
from loguru import logger

from openutm_verification.client import NoAuthCredentialsGetter, PassportCredentialsGetter
from openutm_verification.flight_blender_client import FlightBlenderClient
from tests.scenarios.test_f1_flow import run_f1_scenario
from tests.scenarios.test_f2_flow import run_f2_scenario
from tests.scenarios.test_f3_flow import run_f3_scenario


def setup_logging(output_dir, debug=False):
    """
    Configures logging to write to both the console and a file.
    """
    console_level = "DEBUG" if debug else "INFO"
    logger.remove()  # Remove default handler
    logger.add(
        os.path.join(output_dir, f"run_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"),
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} [{level}] - {message}",
    )
    logger.add(
        lambda msg: print(msg, end=""),
        level=console_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> [<level>{level}</level>] - <level>{message}</level>",
    )


SCENARIO_REGISTRY = {
    "F1_happy_path": run_f1_scenario,
    "F2_contingent_path": run_f2_scenario,
    "F3_non_conforming_path": run_f3_scenario,
}


def main():
    """
    Main entry point for the verification script.
    """
    parser = argparse.ArgumentParser(description="Run OpenUTM Verification Scenarios.")
    parser.add_argument(
        "--config",
        default="config/default.yaml",
        help="Path to the configuration file.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging on the console.",
    )
    args = parser.parse_args()

    # Load configuration
    with open(args.config, "r") as f:
        config = yaml.safe_load(f)

    # Create output directory
    output_dir = config.get("reporting", {}).get("output_dir", "reports")
    os.makedirs(output_dir, exist_ok=True)

    # Setup logging
    setup_logging(output_dir, args.debug)

    # Run verification
    logger.info("Starting verification run...")
    logger.info(f"Using configuration: {args.config}")
    logger.debug(f"Configuration details: {config}")

    # Get credentials
    auth_config = config.get("flight_blender", {}).get("auth", {})
    if auth_config.get("type") == "passport":
        auth_provider = PassportCredentialsGetter(
            client_id=auth_config.get("client_id"),
            client_secret=auth_config.get("client_secret"),
            audience=auth_config.get("audience"),
            token_url=auth_config.get("token_url"),
        )
    else:
        auth_provider = NoAuthCredentialsGetter()

    credentials = auth_provider.get_cached_credentials(audience="testflight.flightblender.com", scopes=["flightblender.write"])

    with FlightBlenderClient(
        base_url=config.get("flight_blender", {}).get("url"),
        credentials=credentials,
    ) as client:
        scenarios_to_run = config.get("scenarios", [])
        all_results = []
        if scenarios_to_run:
            logger.info(f"Found {len(scenarios_to_run)} scenarios to run.")
            for scenario_id in scenarios_to_run:
                if scenario_id in SCENARIO_REGISTRY:
                    logger.info("=" * 100)
                    logger.info(f"Running scenario: {scenario_id}")
                    scenario_func = SCENARIO_REGISTRY[scenario_id]
                    result = scenario_func(client)
                    all_results.append(result)
                    logger.info(f"Scenario {scenario_id} finished with status: {result['status']}")
                else:
                    logger.warning(f"Scenario '{scenario_id}' not found in registry.")
            logger.info("=" * 100)
        else:
            logger.warning("No scenarios found in the configuration.")

    logger.info("Verification run complete.")
    logger.info(f"Results: {all_results}")
    logger.info(f"Reports would be saved in: {output_dir}")


if __name__ == "__main__":
    main()

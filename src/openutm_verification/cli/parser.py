"""
CLI argument parser for the OpenUTM Verification Tool.
"""

import argparse
from pathlib import Path


def create_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser."""
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
    parser.add_argument(
        "-s",
        "--suite",
        type=str,
        action="append",
        help="Name of the test suite to run (overrides individual scenarios). Can be specified multiple times.",
    )
    parser.add_argument(
        "--server",
        action="store_true",
        help="Run in server mode (starts the API and Web UI).",
    )
    return parser

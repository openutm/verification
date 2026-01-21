import functools
import os
from pathlib import Path


@functools.cache
def get_docs_directory() -> Path:
    """
    Determines the directory containing documentation and images.
    """
    package_root = Path(__file__).parents[3]  # Dev location
    docs_dir = os.getenv("DOCS_PATH", str(package_root / "docs" / "scenarios"))
    return Path(docs_dir)


@functools.cache
def get_scenarios_directory() -> Path:
    """
    Determines the directory containing scenario definitions.
    """
    package_root = Path(__file__).parents[3]  # Dev location
    scenarios_dir = os.getenv("SCENARIOS_PATH", str(package_root / "scenarios"))
    return Path(scenarios_dir)

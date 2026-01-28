import functools
import os
from pathlib import Path


@functools.cache
def get_project_root() -> Path:
    """Returns the project root directory."""
    return Path(__file__).parents[3]


def relative_path(path: Path | str) -> str:
    """Convert an absolute path to a relative path from the project root for logging."""
    path = Path(path)
    try:
        return str(path.relative_to(get_project_root()))
    except ValueError:
        return str(path)


@functools.cache
def get_docs_directory() -> Path:
    """
    Determines the directory containing documentation and images.
    """
    package_root = get_project_root()
    docs_dir = os.getenv("DOCS_PATH", str(package_root / "docs" / "scenarios"))
    return Path(docs_dir)


@functools.cache
def get_scenarios_directory() -> Path:
    """
    Determines the directory containing scenario definitions.
    """
    package_root = get_project_root()
    scenarios_dir = os.getenv("SCENARIOS_PATH", str(package_root / "scenarios"))
    return Path(scenarios_dir)

import functools
import os
from pathlib import Path


@functools.cache
def get_docs_directory() -> Path:
    """
    Determines the directory containing documentation and images.

    Strategies:
    1. Installed package location: openutm_verification/docs/
    2. Development location: project_root/docs/
    """
    # 1. Try installed package location: src/openutm_verification/docs/scenarios/
    # This file is in src/openutm_verification/utils/
    package_root = Path(__file__).parent.parent
    docs_dir = os.getenv("DOCS_PATH", str(package_root / "docs" / "scenarios"))
    docs_dir = Path(docs_dir)

    if docs_dir.exists():
        return docs_dir

    # 2. Try development location: project_root/docs/scenarios/
    # src/openutm_verification/utils/ -> src/openutm_verification/ -> src/ -> root/ (4 levels)
    docs_dir = Path(__file__).parents[3] / "docs" / "scenarios"

    return docs_dir


@functools.cache
def get_scenarios_directory() -> Path:
    """
    Determines the directory containing scenario definitions.

    Strategies:
    1. Installed package location: openutm_verification/scenarios/
    2. Development location: project_root/scenarios/
    """
    # 1. Try installed package location: src/openutm_verification/scenarios/
    # This file is in src/openutm_verification/utils/
    package_root = Path(__file__).parent.parent
    scenarios_dir = os.getenv("SCENARIOS_PATH", str(package_root / "scenarios"))
    scenarios_dir = Path(scenarios_dir)

    if scenarios_dir.exists():
        return scenarios_dir

    # 2. Try development location: project_root/scenarios/
    # src/openutm_verification/utils/ -> src/openutm_verification/ -> src/ -> root/ (4 levels)
    scenarios_dir = Path(__file__).parents[3] / "scenarios"

    return scenarios_dir

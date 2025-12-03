from pathlib import Path


def get_docs_directory() -> Path | None:
    """
    Determines the directory containing documentation and images.

    Strategies:
    1. Installed package location: openutm_verification/docs/
    2. Development location: project_root/docs/
    """
    # 1. Try installed package location: src/openutm_verification/docs/scenarios/
    # This file is in src/openutm_verification/utils/
    package_root = Path(__file__).parent.parent
    docs_dir = package_root / "docs" / "scenarios"

    if docs_dir.exists():
        return docs_dir

    # 2. Try development location: project_root/docs/scenarios/
    # src/openutm_verification/utils/ -> src/openutm_verification/ -> src/ -> root/
    docs_dir = Path(__file__).parents[3] / "docs" / "scenarios"
    if docs_dir.exists():
        return docs_dir

    return None

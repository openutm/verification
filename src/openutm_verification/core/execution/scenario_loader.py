from pathlib import Path

import yaml

from openutm_verification.core.execution.definitions import ScenarioDefinition
from openutm_verification.utils.paths import get_scenarios_directory


def load_yaml_scenario_definition(scenario_id: str, base_dir: Path | None = None) -> ScenarioDefinition:
    """Load and validate a YAML scenario definition.

    Args:
        scenario_id: Scenario file stem (without extension).
        base_dir: Optional override directory; defaults to get_scenarios_directory().

    Raises:
        FileNotFoundError: if the YAML file does not exist.
        ValidationError: if the YAML content fails validation.
    """

    scenarios_dir = base_dir or get_scenarios_directory()
    scenario_path = scenarios_dir / f"{scenario_id}.yaml"
    if not scenario_path.exists():
        raise FileNotFoundError(f"Scenario YAML not found: {scenario_path}")

    with open(scenario_path, "r", encoding="utf-8") as f:
        scenario_data = yaml.safe_load(f)

    return ScenarioDefinition.model_validate(scenario_data)

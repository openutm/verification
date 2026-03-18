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
    scenario_path = (scenarios_dir / f"{scenario_id}.yaml").resolve()
    if not scenario_path.is_relative_to(scenarios_dir.resolve()):
        raise FileNotFoundError(f"Scenario YAML not found: {scenario_id}")
    if not scenario_path.exists():
        if "/" not in scenario_id:
            # Bare name: search subfolders for a matching file
            matches = list(scenarios_dir.rglob(f"{scenario_id}.yaml"))
            if len(matches) == 1:
                scenario_path = matches[0]
            elif len(matches) > 1:
                raise FileNotFoundError(f"Ambiguous scenario '{scenario_id}': found in multiple locations: {[str(m) for m in matches]}")
            else:
                raise FileNotFoundError(f"Scenario YAML not found: {scenario_id}")
        else:
            raise FileNotFoundError(f"Scenario YAML not found: {scenario_path}")

    with open(scenario_path, "r", encoding="utf-8") as f:
        scenario_data = yaml.safe_load(f)

    return ScenarioDefinition.model_validate(scenario_data)

"""Tests for UI group functionality."""

from openutm_verification.core.execution.definitions import ScenarioDefinition


def test_group_roundtrip():
    """Test that groups are correctly serialized and deserialized."""
    # Create scenario with groups
    scenario_data = {
        "name": "test_groups",
        "description": "Test scenario",
        "groups": {
            "process_data": {
                "description": "Process some data",
                "steps": [
                    {"id": "fetch", "step": "Fetch OpenSky Data"},
                    {"id": "submit", "step": "Submit Air Traffic", "arguments": {"observations": "${{ group.fetch.result }}"}},
                ],
            }
        },
        "steps": [{"step": "process_data", "loop": {"count": 3}}],
    }

    # Parse to model
    scenario = ScenarioDefinition.model_validate(scenario_data)

    # Verify structure
    assert "process_data" in scenario.groups
    assert scenario.groups["process_data"].description == "Process some data"
    assert len(scenario.groups["process_data"].steps) == 2
    assert scenario.groups["process_data"].steps[0].id == "fetch"
    assert scenario.groups["process_data"].steps[1].arguments["observations"] == "${{ group.fetch.result }}"

    # Verify the group is referenced in steps
    assert scenario.steps[0].step == "process_data"
    assert scenario.steps[0].loop.count == 3

    # Serialize back to dict
    serialized = scenario.model_dump()

    # Verify roundtrip
    assert serialized["groups"]["process_data"]["description"] == "Process some data"
    assert len(serialized["groups"]["process_data"]["steps"]) == 2
    assert serialized["steps"][0]["step"] == "process_data"
    assert serialized["steps"][0]["loop"]["count"] == 3


def test_group_with_condition():
    """Test that groups work with conditional execution."""
    scenario_data = {
        "name": "test",
        "groups": {"cleanup": {"steps": [{"id": "step1", "step": "Clean Up"}]}},
        "steps": [{"step": "cleanup", "if": "${{ always() }}"}],
    }

    scenario = ScenarioDefinition.model_validate(scenario_data)
    assert scenario.steps[0].if_condition == "${{ always() }}"


def test_multiple_group_references():
    """Test scenario that references the same group multiple times."""
    scenario_data = {
        "name": "test",
        "groups": {"fetch": {"steps": [{"id": "f", "step": "Fetch Data"}]}},
        "steps": [{"step": "fetch"}, {"step": "fetch", "if": "${{ success() }}"}, {"step": "fetch", "if": "${{ always() }}"}],
    }

    scenario = ScenarioDefinition.model_validate(scenario_data)
    assert len(scenario.steps) == 3
    assert all(s.step == "fetch" for s in scenario.steps)

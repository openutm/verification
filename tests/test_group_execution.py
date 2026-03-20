"""Tests for step group execution."""

import pytest
import yaml

from openutm_verification.core.execution.definitions import ScenarioDefinition


@pytest.mark.asyncio
async def test_group_definition_parsing():
    """Test that group definitions are correctly parsed from YAML."""
    yaml_content = """
name: test_groups
description: Test scenario with groups

groups:
  my_group:
    description: A test group
    steps:
      - id: step1
        step: Setup Flight Declaration
      - id: step2
        step: Wait X seconds
        arguments:
          duration: 1

steps:
  - step: my_group
"""

    data = yaml.safe_load(yaml_content)
    scenario = ScenarioDefinition.model_validate(data)

    # Verify groups are parsed
    assert "my_group" in scenario.groups
    assert scenario.groups["my_group"].description == "A test group"
    assert len(scenario.groups["my_group"].steps) == 2
    assert scenario.groups["my_group"].steps[0].id == "step1"
    assert scenario.groups["my_group"].steps[1].arguments["duration"] == 1


@pytest.mark.asyncio
async def test_group_with_loop():
    """Test that groups can be looped."""
    yaml_content = """
name: test_group_loop
description: Test scenario with looped groups

groups:
  fetch_data:
    steps:
      - id: fetch
        step: Stream Air Traffic
        arguments:
          provider: opensky
          target: flight_blender
      - id: wait
        step: Wait X seconds
        arguments:
          duration: 1

steps:
  - step: fetch_data
    loop:
      count: 3
"""

    data = yaml.safe_load(yaml_content)
    scenario = ScenarioDefinition.model_validate(data)

    # Verify group definition
    assert "fetch_data" in scenario.groups
    assert len(scenario.groups["fetch_data"].steps) == 2

    # Verify the step references the group with a loop
    assert scenario.steps[0].step == "fetch_data"
    assert scenario.steps[0].loop is not None
    assert scenario.steps[0].loop.count == 3


@pytest.mark.asyncio
async def test_group_references_within_group():
    """Test that steps within a group can reference other steps in the same group."""
    yaml_content = """
name: test_group_refs
description: Test scenario with group internal references

groups:
  process_data:
    steps:
      - id: stream
        step: Stream Air Traffic
        arguments:
          provider: opensky
          target: flight_blender
      - id: generate
        step: Generate Random Number
        arguments:
          min: 1
          max: 5
      - id: wait
        step: Wait X seconds
        arguments:
          duration: ${{ group.generate.result }}

steps:
  - step: process_data
"""

    data = yaml.safe_load(yaml_content)
    scenario = ScenarioDefinition.model_validate(data)

    # Verify group definition
    assert "process_data" in scenario.groups
    group = scenario.groups["process_data"]

    # Verify the submit step has correct arguments
    assert group.steps[2].arguments["duration"] == "${{ group.generate.result }}"


@pytest.mark.asyncio
async def test_multiple_groups():
    """Test scenario with multiple groups."""
    yaml_content = """
name: test_multiple_groups
description: Test scenario with multiple groups

groups:
  group1:
    description: First group
    steps:
      - id: step1
        step: Setup Flight Declaration

  group2:
    description: Second group
    steps:
      - id: step2
        step: Wait X seconds
        arguments:
          duration: 1

steps:
  - step: group1
  - step: group2
  - step: group1
    if: ${{ always() }}
"""

    data = yaml.safe_load(yaml_content)
    scenario = ScenarioDefinition.model_validate(data)

    # Verify both groups are defined
    assert "group1" in scenario.groups
    assert "group2" in scenario.groups
    assert scenario.groups["group1"].description == "First group"
    assert scenario.groups["group2"].description == "Second group"

    # Verify steps reference groups
    assert len(scenario.steps) == 3
    assert scenario.steps[0].step == "group1"
    assert scenario.steps[1].step == "group2"
    assert scenario.steps[2].step == "group1"
    assert scenario.steps[2].if_condition == "${{ always() }}"


@pytest.mark.asyncio
async def test_empty_groups_section():
    """Test that scenarios work without groups section."""
    yaml_content = """
name: test_no_groups
description: Test scenario without groups

steps:
  - step: Setup Flight Declaration
"""

    data = yaml.safe_load(yaml_content)
    scenario = ScenarioDefinition.model_validate(data)

    # Verify groups is empty dict
    assert scenario.groups == {}
    assert len(scenario.steps) == 1


@pytest.mark.asyncio
async def test_on_step_result_fail_parsing():
    """Test that on_step_result_fail is correctly parsed from YAML."""
    yaml_content = """
name: test_continue_on_fail
description: Test scenario with on_step_result_fail

steps:
  - step: Setup Flight Declaration
  - step: Validate Metrics
    on_step_result_fail: continue
  - step: Teardown Flight Declaration
"""

    data = yaml.safe_load(yaml_content)
    scenario = ScenarioDefinition.model_validate(data)

    assert scenario.steps[0].on_step_result_fail == "stop"  # default
    assert scenario.steps[1].on_step_result_fail == "continue"
    assert scenario.steps[2].on_step_result_fail == "stop"  # default


@pytest.mark.asyncio
async def test_on_step_result_fail_default():
    """Test that on_step_result_fail defaults to 'stop'."""
    yaml_content = """
name: test_default_fail_action
description: Test default on_step_result_fail

steps:
  - step: Setup Flight Declaration
"""

    data = yaml.safe_load(yaml_content)
    scenario = ScenarioDefinition.model_validate(data)
    assert scenario.steps[0].on_step_result_fail == "stop"


@pytest.mark.asyncio
async def test_on_step_result_fail_in_group():
    """Test that on_step_result_fail works inside groups."""
    yaml_content = """
name: test_continue_on_fail_group
description: Test scenario with on_step_result_fail inside a group

groups:
  my_group:
    steps:
      - step: Validate Metrics
        on_step_result_fail: continue
      - step: Teardown Flight Declaration

steps:
  - step: my_group
"""

    data = yaml.safe_load(yaml_content)
    scenario = ScenarioDefinition.model_validate(data)
    assert scenario.groups["my_group"].steps[0].on_step_result_fail == "continue"
    assert scenario.groups["my_group"].steps[1].on_step_result_fail == "stop"

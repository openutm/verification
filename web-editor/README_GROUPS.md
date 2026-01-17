<!-- Groups Support in Web Editor

## Overview

The web editor now fully supports step groups, allowing you to create reusable collections of steps that can be looped and referenced as a single unit.

## Features

### 1. Groups Management Panel

Located in the **Scenario Settings** right sidebar, the Groups Manager allows you to:

- **Create new groups**: Enter a group name and click the + button
- **Add descriptions**: Document what each group does
- **Manage steps**: Add, edit, and remove steps within each group
- **Expand/collapse**: Toggle to see group details

### 2. Group Step Definitions

Each step in a group has:
- **Step ID**: Unique identifier within the group (e.g., `fetch`, `submit`)
- **Step Name**: The operation to execute (e.g., "Fetch OpenSky Data")
- **Arguments**: Parameters for the operation, supporting internal group references

### 3. Internal Group References

Steps within a group can reference other steps in the same group:

```
observations: ${{ group.fetch.result }}
```

This reference syntax is supported in:
- **Argument Editor**: Click the link icon to create references
- **Reference Type Selector**: Toggle between `steps` (previous steps) and `group` (steps in current group)

### 4. Group References in Main Flow

In the main scenario flow:
- **Add group steps**: Drag operations onto the canvas or select from the step library
- **Reference groups**: Click on a step and select a group from the operation list
- **Loop groups**: Groups can be looped just like regular steps
  - Fixed count: `count: 5`
  - Iterate items: `items: [...]`
  - While condition: `while: loop.index < 10`
- **Conditional groups**: Groups can have conditions: `if: ${{ always() }}`

### 5. UI Indicators

- **Group Reference Badge**: When a step references a group, the properties panel shows a 📦 indicator
- **Reference Helper**: Shows the correct reference syntax: `${{ group.step_id.result }}`
- **No Parameters**: Group reference nodes don't show operation parameters

## Example Workflow

1. **Create a group** in the Groups Manager:
   - Name: `fetch_and_submit`
   - Add step 1: "Fetch OpenSky Data" (id: `fetch`)
   - Add step 2: "Submit Air Traffic" (id: `submit`)
   - Set submit's observations argument to: `${{ group.fetch.result }}`

2. **Use the group** in the main flow:
   - Add a step that references `fetch_and_submit`
   - Set it to loop with count 5
   - The group will execute all its steps 5 times

3. **Reference group results** in subsequent steps:
   - After the group, add "Process Results"
   - Reference the group's submit step: `${{ group.submit.result }}`
   - This will get the last iteration's result

## Exporting to YAML

When you save a scenario with groups, the YAML will include:

```yaml
name: my_scenario
groups:
  fetch_and_submit:
    description: Fetches and submits air traffic data
    steps:
      - id: fetch
        step: Fetch OpenSky Data
      - id: submit
        step: Submit Air Traffic
        arguments:
          observations: ${{ group.fetch.result }}
steps:
  - step: fetch_and_submit
    loop:
      count: 5
```

## Key Implementation Details

### Types Updated
- `ScenarioDefinition`: Added optional `groups` field
- `GroupDefinition`: New type for group definitions
- `GroupStepDefinition`: New type for steps within groups
- `NodeData`: Added `isGroupReference` flag

### Components Updated
- **GroupsManager.tsx**: New component for managing groups
- **ScenarioInfoPanel.tsx**: Integrated GroupsManager
- **PropertiesPanel.tsx**: Enhanced reference type selection (steps vs group)
- **scenarioConversion.ts**: Updated to parse/serialize groups

### Backend Integration
- Groups are parsed in `convertYamlToGraph()`
- Group references are detected and marked with `isGroupReference: true`
- `_resolve_ref()` in runner.py supports `group.step_id.result` syntax
- Group execution handled by `_execute_group()` and `_execute_loop_for_group()`

## Autosave

Groups are included in the autosave state:
- Stored in: `editor-autosave-groups`
- Restored on page refresh
- Cleared when scenario is saved to server

## Testing

- **Backend tests**: `tests/test_group_execution.py` (5 tests)
- **YAML roundtrip tests**: `tests/test_ui_groups.py` (3 tests)
- **Scenario execution**: All 12 YAML scenarios pass
- **Builds successfully**: Web editor builds without errors

-->

# YAML Scenarios

Scenarios are defined as YAML files in this folder. Python-based scenario modules have been removed; YAML is the single source of truth.

## Quick Start
- Create a new file in this directory with a `.yaml` extension.
- Provide `name`, optional `description`, and a list of `steps`.
- Each `step` references a registered operation by its display name and can provide `arguments`.

Example:

```yaml
name: sdsp_heartbeat
description: Runs the SDSP heartbeat scenario.

steps:
  - step: Generate UUID

  - id: start_session
    step: Start / Stop SDSP Session
    arguments:
      action: START
      session_id: ${{ steps.Generate UUID.result }}

  - step: Wait X seconds
    arguments:
      duration: 2

  - step: Verify SDSP Heartbeat
    arguments:
      session_id: ${{ steps.Generate UUID.result }}
      expected_heartbeat_interval_seconds: 1
      expected_heartbeat_count: 3

  - id: wait_verification
    step: Wait X seconds
    arguments:
      duration: 5

  - step: Start / Stop SDSP Session
    arguments:
      action: STOP
      session_id: ${{ steps.Generate UUID.result }}
```

## Step Groups (Reusable Step Collections)

Groups allow you to define reusable collections of steps that can be referenced multiple times or looped as a single unit.

### Defining Groups

Use the optional `groups` section to define named step collections:

```yaml
name: opensky_live_data
description: Fetch live flight data and submit to Flight Blender.

groups:
  fetch_and_submit_opensky:
    description: Fetches OpenSky data and submits it to Flight Blender
    steps:
      - id: fetch
        step: Fetch OpenSky Data

      - id: submit
        step: Submit Air Traffic
        arguments:
          observations: ${{ group.fetch.result }}

      - id: wait
        step: Wait X seconds
        arguments:
          duration: 3

steps:
  # Execute the group once
  - step: fetch_and_submit_opensky

  # Execute the group in a loop
  - step: fetch_and_submit_opensky
    loop:
      count: 5
```

### Group Features

- **Step References Within Groups**: Use `${{ group.<step_id>.result }}` to reference results from other steps within the same group execution.
- **Looping Groups**: Groups can be looped just like regular steps using `loop.count`, `loop.items`, or `loop.while`.
- **Group Reuse**: The same group can be referenced multiple times in the `steps` section.
- **Conditions on Groups**: Groups can have conditions (`if` field) just like regular steps.

### Example: Looped Group with Internal References

```yaml
groups:
  process_data:
    steps:
      - id: fetch
        step: Fetch Data

      - id: process
        step: Process Data
        arguments:
          data: ${{ group.fetch.result }}

      - id: submit
        step: Submit Results
        arguments:
          results: ${{ group.process.result }}

steps:
  - step: process_data
    loop:
      count: 3
```

## Referencing Prior Step Results
- Use the expression syntax: `${{ steps.<step_id_or_name>.result }}` to inject values from previous steps.
- Within groups, use: `${{ group.<step_id>.result }}` to reference other steps in the same group execution.
- Loop indices can be referenced with bracket notation: `steps.my_step[2].result`.
- Loop variables are available via `loop.index` and `loop.item` inside looped steps.

## Conditions & Status
- Default step condition: runs only if prior steps are `success()`.
- Available status strings: `success`, `failure`, `running`, `skipped`.
- You can use conditions like `always()`, `success()`, `failure()` and combined references (e.g., `steps.Upload Flight Declaration.status == 'success'`).

## Validation
To validate scenarios locally:

```bash
cd ..
python -m pytest tests/test_yaml_scenarios.py -q --tb=no
```

## Discovering Available Operations
The system exposes registered operations used in YAML (e.g., `Generate UUID`, `Wait X seconds`, `Start / Stop SDSP Session`). These are provided by clients and discovered at runtime. In the web editor, you can browse and insert these operations directly.

## Tips
- Keep `id` short and unique if you plan to reference a step later.
- Use `arguments` to pass parameters; file paths and IDs can be injected via references.
- Prefer bracket references when using loops to access specific iterations.
- Use groups to reduce repetition when the same sequence of steps needs to be executed multiple times or with loops.

# Implementing Async/Background Tasks in the UI

This guide outlines the implementation of asynchronous background tasks (like those in `test_sdsp_track.py`) using the OpenUTM Verification Web Editor and Backend.

## Status: Implemented

The core infrastructure for async/background tasks has been implemented in both the Frontend and Backend.

## 1. Client-Side Orchestration (Frontend)

The frontend now executes scenarios step-by-step, allowing for dynamic updates and handling of long-running processes.

### Key Components
-   **`useScenarioRunner.ts`**:
    -   Performs topological sort of the graph to determine execution order.
    -   Iterates through nodes and calls the backend API for each step individually.
    -   Supports `runInBackground` flag: If a node is configured to run in background, it passes `run_in_background=true` to the backend.
    -   Updates node status to `running` (blue border + spinner) before execution, and `success`/`failure` after completion.
    -   Handles `step_id` passing to ensure results are stored in the backend session context.

-   **UI Updates**:
    -   **Running State**: Nodes now show a spinner and blue border while executing.
    -   **Connection Status**: A "Connected/Disconnected" indicator in the top-right panel shows backend health.
    -   **Toolbox Refresh**: Automatically reloads available operations when the backend connects.

## 2. Backend Support for Background Tasks

The backend `SessionManager` has been updated to support "fire-and-forget" tasks and task joining.

### Implementation Details (`src/openutm_verification/server/runner.py`)

1.  **Background Execution**:
    -   When `run_in_background=True` is passed to `execute_single_step`:
        -   The method call is wrapped in `asyncio.create_task`.
        -   The task object is stored in `self.session_context["background_tasks"]` keyed by a UUID.
        -   Returns immediately with `{"task_id": <uuid>, "status": "running"}`.

2.  **`SessionManager.join_task`**:
    -   A special handling block in `_execute_step` intercepts calls to `SessionManager.join_task`.
    -   It retrieves the `task_id` from parameters (which can be a direct string or a reference to a previous step's result).
    -   It looks up the task in `session_context["background_tasks"]`.
    -   It `await`s the task completion and returns the result.

## 3. Usage Example (SDSP Track)

To create a scenario with async tasks (e.g., `sdsp_track`):

1.  **Start Task**: Add a node (e.g., `FlightBlenderClient.submit_simulated_air_traffic`).
    -   Set `Run in Background` to `true` (via properties panel or JSON).
2.  **Intermediate Steps**: Add other nodes (e.g., `CommonClient.wait`, `Verify Track`) that run while the background task is active.

### Example YAML (`scenarios/sdsp_track.yaml`)

```yaml
  - step: Submit Simulated Air Traffic
    arguments:
      observations: ${{ steps.Generate Simulated Air Traffic Data.result }}
    background: true

  # ... other steps running in parallel ...

  - step: Other step that needs to wait for BG task to finish.
    needs:
    - Submit Simulated Air Traffic
```

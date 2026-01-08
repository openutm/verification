# F1 Flow No Telemetry with User Input

## Overview

**Scenario Name:** `F1_flow_no_telemetry_with_user_input`
**Description:** This scenario validates a flight operation flow that requires manual user intervention to proceed. It activates a flight, pauses for user input, and then ends the operation, without submitting any telemetry data. This is useful for testing state transitions and operator interactions.

## Execution Flow

The scenario executes the following sequence of steps:

### 1. Setup Flight Declaration
- **Action:** Creates a flight declaration context.
- **Context:** Establishes the baseline for the flight operation.

### 2. Initial Wait
- **Step:** `Wait`
- **Action:** System pauses for **5 seconds**.
- **Context:** Simulates a pre-activation delay.

### 3. Activate Operation
- **Step:** `Update Operation State`
- **Action:** Transitions the flight operation state to **`ACTIVATED`**.

### 4. User Input Required
- **Step:** `Wait For User Input`
- **Action:** The simulation pauses and waits for the user to confirm continuation (e.g., "Press Enter to end the operation...").
- **Context:** Allows manual verification of the system state while the flight is active, or coordination with external events.

### 5. End Operation
- **Step:** `Update Operation State`
- **Action:** Transitions the flight operation state to **`ENDED`**.

### 6. Explicit Teardown
- **Step:** `Teardown Flight Declaration`
- **Action:** Explicitly invokes the teardown of the flight declaration to ensure no artifacts remain.

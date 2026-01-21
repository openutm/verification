# F5 Non-Conforming Path (Contingent Transition)

## Overview

**Scenario Name:** `F5_non_conforming_path`
**Description:** This scenario validates the complex state transition flow where a flight becomes **Non-Conforming** due to telemetry deviations and subsequently transitions to a **Contingent** state. It tests the system's ability to first detect non-conformance and then accept a contingency declaration for the same operation.

## Execution Flow

The scenario executes the following sequence of steps:

### 1. Setup Flight Declaration
- **Action:** Creates a flight declaration context.
- **Context:** Establishes the valid geometric boundaries for the flight.

### 2. Activate Operation
- **Step:** `Update Operation State`
- **Action:** Transitions the flight operation state to **`ACTIVATED`**.

### 3. Inject Non-Conforming Telemetry
- **Step:** `Submit Telemetry`
- **Action:** Streams simulated telemetry data for **20 seconds**.
- **Context:** The telemetry path breaches the declared volume, triggering a non-conformance event.

### 4. Verify Non-Conformance
- **Step:** `Check Operation State (Connected)`
- **Action:** Checks the operation state via active connection/polling.
- **Expectation:** The state must be **`NONCONFORMING`**.
- **Wait Duration:** **5 seconds**
    - Verifies that the system has correctly flagged the operation as non-conforming based on the uploaded telemetry.

### 5. Declare Contingency
- **Step:** `Update Operation State`
- **Action:** Transitions the flight operation state from `NONCONFORMING` to **`CONTINGENT`**.
- **Context:** Simulates the operator or system acknowledging the issue and moving to a contingency plan to resolve the violation.

### 6. End Operation
- **Step:** `Update Operation State`
- **Action:** Transitions the flight operation state to **`ENDED`**.
- **Purpose:** Closes the operation.

### 7. Explicit Teardown
- **Step:** `Teardown Flight Declaration`
- **Action:** Clean up resources.

# F3 Non-Conforming Path

## Overview

**Scenario Name:** `F3_non_conforming_path`
**Description:** This scenario verifies the system's ability to detect and handle **Non-Conforming** flights. It simulates an operation that activates normally but subsequently reports telemetry positions that deviate significantly from its declared flight plan (Operational Intent), expecting the system to automatically transition the operation state to `NONCONFORMING`.

## Execution Flow

The scenario executes the following sequence of steps:

### 1. Setup Flight Declaration
- **Action:** Creates a flight declaration context.
- **Context:** Establishes the valid geometric boundaries (volumes) for the flight.

### 2. Activate Operation
- **Step:** `Update Operation State`
- **Action:** Transitions the flight operation state to **`ACTIVATED`**.

### 3. Initial Wait
- **Step:** `Wait`
- **Duration:** **5 seconds**
- **Context:** Short delay to allow system state to settle before data transmission begins.

### 4. Inject Non-Conforming Telemetry
- **Step:** `Submit Telemetry`
- **Action:** Streams simulated telemetry data for **20 seconds**.
- **Context:** The telemetry path used in this scenario is designed to breach the conformance thresholds of the declared volumes.

### 5. Verify State Transition
- **Step:** `Check Operation State`
- **Action:** Polls the operation status.
- **Expectation:** The state must be **`NONCONFORMING`**.
- **Wait Duration:** **5 seconds**
    - Waits up to 5 seconds for the system to process the telemetry and flag the violation.

### 6. End Operation
- **Step:** `Update Operation State`
- **Action:** Transitions the flight operation state to **`ENDED`**.
- **Purpose:** Closes the operation.

### 7. Explicit Teardown
- **Step:** `Teardown Flight Declaration`
- **Action:** Clean up resources.

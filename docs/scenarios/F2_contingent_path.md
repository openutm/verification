# F2 Contingent Path

## Overview

**Scenario Name:** `F2_contingent_path`
**Description:** This scenario validates the system's handling of off-nominal flight conditions, specifically the transition to a **Contingent** state. It simulates a flight that activates normally but then encounters an issue requiring a state change before ending.

## Execution Flow

The scenario executes the following sequence of steps:

### 1. Setup Flight Declaration
- **Action:** Creates a flight declaration context.
- **Context:** Establishes the baseline for the flight operation.

### 2. Activate Operation
- **Step:** `Update Operation State`
- **Action:** Transitions the flight operation state to **`ACTIVATED`**.
- **Context:** The flight begins normal operations.

### 3. Normal Telemetry Stream
- **Step:** `Submit Telemetry`
- **Action:** Streams telemetry data for **10 seconds**.
- **Context:** Represents the initial phase of successful flight.

### 4. Contingency Declaration
- **Step:** `Update Operation State`
- **Action:** Transitions the flight operation state to **`CONTINGENT`**.
- **Duration:** **7 seconds**
    - The system holds this state for 7 seconds to simulate the duration of the contingent event or the time taken to resolve/acknowledge it.

### 5. End Operation
- **Step:** `Update Operation State`
- **Action:** Transitions the flight operation state to **`ENDED`**.
- **Purpose:** Closes the operation after the contingency is resolved or the flight is terminated.

### 6. Explicit Teardown
- **Step:** `Teardown Flight Declaration`
- **Action:** Explicitly invokes the teardown of the flight declaration to ensure no artifacts remain.

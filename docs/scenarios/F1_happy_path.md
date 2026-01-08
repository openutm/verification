# F1 Happy Path

## Overview

**Scenario Name:** `F1_happy_path`
**Description:** This scenario validates the "Happy Path" (nominal flow) for a flight operation. It simulates a completely successful flight life-cycle without any deviations, interruptions, or off-nominal conditions.

## Execution Flow

The scenario executes the following sequence of steps:

### 1. Setup Flight Declaration
- **Action:** Creates a flight declaration context (uploading necessary declaration and trajectory validation).
- **Context:** Establishes the baseline for the flight operation.

### 2. Activate Operation
- **Step:** `Update Operation State`
- **Action:** Transitions the flight operation state to **`ACTIVATED`**.
- **Context:** Signals that the flight is ready to commence or has commenced.

### 3. Submit Telemetry
- **Step:** `Submit Telemetry`
- **Action:** Streams telemetry data for the flight.
- **Duration:** **30 seconds**
    - The system submits position updates securely for a half-minute duration to simulate active flight tracking.

### 4. End Operation
- **Step:** `Update Operation State`
- **Action:** Transitions the flight operation state to **`ENDED`**.
- **Purpose:** Normally completes the flight operation.

### 5. Explicit Teardown
- **Step:** `Teardown Flight Declaration`
- **Action:** Explicitly invokes the teardown of the flight declaration to ensure no artifacts remain.

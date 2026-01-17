# Add Flight Declaration via Operational Intent

## Overview

**Scenario Name:** `add_flight_declaration_via_operational_intent`
**Description:** This scenario validates the workflow for creating a flight declaration through the submission of an Operational Intent. It verifies that the system correctly initializes a declaration from an intent, handles state transitions, and manages the operational lifecycle.

## Execution Flow

The scenario executes the following sequence of steps:

### 1. Setup Flight Declaration via Operational Intent
- **Action:** Submits a Flight Declaration via the Operational Intent interface.
- **Context:** Unlike the standard upload, this tests the specific path of deriving a declaration from a full operational intent submission.
- **Outcome:** A valid flight declaration is established in the system.

### 2. Activate Operation
- **Step:** `Update Operation State`
- **Action:** Transitions the flight operation state to **`ACTIVATED`**.
- **Wait Duration:** **5 seconds**
    - The system pauses for 5 seconds post-activation to ensure state propagation.

### 3. Operational Wait
- **Step:** `Wait`
- **Action:** System idle wait.
- **Duration:** **10 seconds**
    - Simulates the duration of the flight operation. Note that unlike the standard `add_flight_declaration` scenario, this test does not explicitly submit telemetry distinct from the intent.

### 4. End Operation
- **Step:** `Update Operation State`
- **Action:** Transitions the flight operation state to **`ENDED`**.
- **Purpose:** Formally closes the operational intent and associated declaration.

### 5. Teardown
- **Step:** Cleanup
- **Action:** Automatically tears down the created resources upon scenario completion.
- **Result:** Initializes system cleanup for the operational intent and declaration.

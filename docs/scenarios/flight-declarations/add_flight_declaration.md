# Add Flight Declaration Scenario

## Overview

**Scenario Name:** `add_flight_declaration`
**Description:** This scenario validates the complete lifecycle of a flight declaration, from submission to activation, telemetry transmission, and cleanup. It verifies that the system correctly parses flight declarations, accepts state transitions, and processes telemetry updates.

## Execution Flow

The scenario executes the following sequence of steps:

### 1. Setup Flight Declaration
- **Action:** Uploads a flight declaration JSON file to Flight Blender.
- **Verification:** Ensures the declaration is successfully parsed and approved by the system.
- **Outcome:** A new `flight_declaration_id` is created and stored in the execution context.

### 2. Activate Operation
- **Step:** `Update Operation State`
- **Action:** Transitions the flight operation state to **`ACTIVATED`**.
- **Wait Duration:** **20 seconds**
    - The system waits for 20 seconds after the state update to simulate pre-flight checks or operational delays.

### 3. Submit Telemetry
- **Step:** `Submit Telemetry`
- **Action:** Streams simulated telemetry data (position, altitude, velocity) for the activated flight.
- **Duration:** **30 seconds**
    - Telemetry points are submitted sequentially to the data ingest endpoint.
- **Verification:** Validates that the system accepts the telemetry stream without errors.

### 4. End Operation
- **Step:** `Update Operation State` (ID: `update_state_ended`)
- **Action:** Transitions the flight operation state to **`ENDED`**.
- **Purpose:** Formally closes the flight operation, indicating the flight has completed.

### 5. Teardown
- **Step:** `Teardown Flight Declaration`
- **Action:** Clean up resources (e.g., flight declaration, associated geo-fences).
- **Result:** Ensures the system returns to a clean state after the test.

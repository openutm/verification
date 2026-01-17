# OpenUTM Simulated Air Traffic Data

## Overview

**Scenario Name:** `openutm_sim_air_traffic_data`
**Description:** This scenario verifies the integration between the simulated air traffic generator and Flight Blender. It generates simulated air traffic observations and submits them to the backend to ensure they are correctly ingested.

## Execution Flow

The scenario executes the following sequence of steps:

### 1. Generate Simulated Air Traffic
- **Step:** `AirTrafficClient.generate_simulated_air_traffic_data`
- **Action:** Generates a set of simulated flight observations (e.g., positions, velocities) representing local air traffic.
- **Context:** Unlike live tracking, this uses internal simulation logic/templates to create predictable traffic patterns for testing.

### 2. Submit Traffic Data
- **Step:** `FlightBlenderClient.submit_simulated_air_traffic`
- **Action:** Submits the generated observations to Flight Blender's air traffic data feed.
- **Verification:** Ensures the API accepts the payload (typically a bulk submission of observations).

### 3. Completion
- **Action:** The scenario completes successfully upon meaningful submission callback.

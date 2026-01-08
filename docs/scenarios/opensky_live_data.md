# OpenSky Live Data

## Overview

**Scenario Name:** `opensky_live_data`
**Description:** This scenario tests the integration with live data sources by fetching real-time flight positions from OpenSky Network and submitting them to Flight Blender. It verifies that the system can ingest and process live air traffic streams.

## Execution Flow

The scenario executes the following sequence of steps:

### 1. Iterative Data Fetch & Submission
- **Loop:** Runs for **5 iterations**.
- **Wait:** Pauses for **3 seconds** between iterations.

#### Step A: Fetch Live Data
- **Step:** `OpenSkyClient.fetch_data`
- **Action:** Queries the OpenSky API to retrieve current state vectors for aircraft in the configured bounding box.
- **Context:** Provides a "real-world" dataset for system verification.

#### Step B: Submit Traffic Data
- **Step:** `FlightBlenderClient.submit_air_traffic`
- **Action:** Submits the retrieved observations to Flight Blender.
- **Condition:** Executed only if valid observations are returned from OpenSky.
- **Verification:** Ensures the backend accepts the external data format.

### 2. Completion
- **Action:** The scenario completes after all iterations are finished.

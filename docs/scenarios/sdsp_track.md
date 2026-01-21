# SDSP Track Verification

## Overview

**Scenario Name:** `sdsp_track`
**Description:** This scenario validates the tracking capability of Supplemental Data Service Providers (SDSP). It verifies that Flight Blender can successfully establish a session, ingest simulated air traffic tracks concurrently, and monitor the reception of track updates at a specified frequency.

## Execution Flow

The scenario executes the following sequence of steps:

### 1. Start SDSP Session
- **Step:** `Start/Stop SDSP Session (START)`
- **Action:** Initiates a new SDSP session with a unique UUID.
- **Context:** Signals the beginning of a data provision session.

### 2. Generate and Submit Air Traffic
- **Step:** `Generate Simulated Air Traffic Data`
- **Action:** Generates simulated flight observations.
- **Step:** `Submit Simulated Air Traffic` (Background Task)
- **Action:** Starts submitting the generated observations to Flight Blender in a background process.
- **Context:** Simulates a live feed of aircraft tracking data being pushed to the system.

### 3. Initial Wait
- **Step:** `Wait`
- **Duration:** **2 seconds**
- **Context:** Allows the data stream to initialize and reach the system.

### 4. Verify Track Reception
- **Step:** `Initialize Verify SDSP Track`
- **Action:** Configures the verification logic to listen for track updates.
- **Parameters:**
    - **Interval:** 1 second
    - **Expected Count:** 3 track updates
- **Verification:** Ensures the system correctly processes and counts the incoming track data associated with the session.

### 5. Operational Wait
- **Step:** `Wait`
- **Duration:** **5 seconds**
- **Context:** Provides the time window for the verification logic to confirm the track count.

### 6. Stop SDSP Session
- **Step:** `Start/Stop SDSP Session (STOP)`
- **Action:** Terminates the SDSP session.
- **Purpose:** Cleanly closes the connection.

### 7. Task Completion
- **Action:** Waits for the background air traffic submission task to complete fully before finishing the scenario.

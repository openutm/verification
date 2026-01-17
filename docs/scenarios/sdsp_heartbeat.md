# SDSP Heartbeat

## Overview

**Scenario Name:** `sdsp_heartbeat`
**Description:** This scenario validates the heartbeat mechanism for Supplemental Data Service Providers (SDSP). It ensures that Flight Blender can successfully establish a session, monitor heartbeat signals at a specified frequency, and gracefully terminate the session.

## Execution Flow

The scenario executes the following sequence of steps:

### 1. Start SDSP Session
- **Step:** `Start/Stop SDSP Session (START)`
- **Action:** Initiates a new SDSP session with a unique UUID.
- **Context:** Signals the beginning of a data provision session.

### 2. Initial Wait
- **Step:** `Wait`
- **Duration:** **2 seconds**
- **Context:** Allows the session initialization to propagate.

### 3. Verify Heartbeat
- **Step:** `Initialize Verify SDSP Heartbeat`
- **Action:** Configures the verification logic to listen for heartbeats.
- **Parameters:**
    - **Interval:** 1 second
    - **Expected Count:** 3 heartbeats
- **Verification:** Ensures the system detects the ongoing liveness of the SDSP connection.

### 4. Operational Wait
- **Step:** `Wait`
- **Duration:** **5 seconds**
- **Context:** Provides the time window for the heartbeat verification to collect data and confirm the count.

### 5. Stop SDSP Session
- **Step:** `Start/Stop SDSP Session (STOP)`
- **Action:** Terminates the SDSP session.
- **Purpose:** Cleanly closes the connection.

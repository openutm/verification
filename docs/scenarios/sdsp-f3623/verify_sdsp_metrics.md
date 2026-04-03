# SDSP Metrics Verification

## Overview

**Scenario Name:** `verify_sdsp_metrics`

**Description:** This scenario validates that the metrics related to Supplemental Data Service Providers (SDSP) are correctly recorded and reported by Flight Blender. It ensures that the system accurately tracks the number of active SDSP sessions, the volume of data ingested, and the frequency of updates received.

## Execution Flow
The scenario executes the following sequence of steps:
1. **Generate Bayesian Simulation Air Traffic Data** - Create synthetic air traffic data streams that mimic real-world SDSP inputs, including various flight parameters and metadata.
2. **Fetch Session IDs for Bayesian Simulation** - Retrieve the session identifiers for the generated air traffic data to track and correlate metrics accurately throughout the test.
3. **Submit Simulated Air Traffic** - Ingest the generated air traffic data into Flight Blender, ensuring that the system processes the data as it would in a live environment.
4. **Start SDSP Session** - Initiate and terminate SDSP sessions to simulate real-world usage patterns, allowing for the measurement of session-related metrics such as active session count and data volume.
5. **Verify Reported Metrics in Flight Blender** - Check the Flight Blender dashboard and logs to confirm that the metrics for active SDSP sessions, data volume, and update frequency are accurately reported based on the actions performed in the previous steps.
5. **Stop SDSP Session** - Terminate the SDSP sessions to ensure that the system correctly updates the metrics to reflect the cessation of data streams and session activity.


## Expected Outcomes
- The metrics for active SDSP sessions should reflect the correct count based on the number of sessions started and stopped.
- The data volume metric should accurately represent the total amount of data ingested from the SDSP sources.
- The update frequency metric should show the correct number of updates received from the SDSP sources over the test duration.
- All metrics should be reported correctly in the Flight Blender dashboard and logs, confirming that the system is functioning as expected in handling SDSP data streams.

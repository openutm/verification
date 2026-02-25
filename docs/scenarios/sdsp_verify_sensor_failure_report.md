# SDSP Sensor Failure Report Verification

## Overview
**Scenario Name:** `sdsp_verify_sensor_failure_report`
**Description:* This scenario tests the ability of Flight Blender to retrieve and report sensor failure notifications from Supplemental Data Service Providers (SDSP). It ensures that when a sensor failure occurs, the system correctly captures and displays the relevant information in the dashboard.
## Execution Flow
The scenario executes the following sequence of steps:
1. **Simulate Sensor Failure** - Trigger a sensor failure event in the SDSP environment to create a realistic test case for the system's response to such incidents.
2. **List Sensor Failure Notifications from SDSP** - Use the Flight Blender client to retrieve the list of sensor failure notifications from the SDSP, ensuring that the system can access and display this critical information.
3. **Verify Sensor Failure Notification Details** - Check the details of the retrieved sensor failure notifications to confirm that they contain accurate and relevant information about the failure, such as the sensor ID, failure type, timestamp, and any associated metadata.

__TODO:__
4. **Check Dashboard for Sensor Failure Alerts** - Verify that the Flight Blender dashboard correctly displays alerts or notifications related to the sensor failure, ensuring that users are informed of such events in a timely manner.

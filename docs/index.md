# OpenUTM Verification Scenarios

## Overview

This section documents the various test scenarios used to verify UTM functionality.

## Scenario Format

All scenarios are defined as YAML files and executed via the runner. See the [scenarios/README.md](scenarios/README.md) for the YAML schema, references, and examples.

## Scenarios

### DAA (Detect and Avoid)
* [DAA Scenario Authoring Guide](daa_scenario_authoring_guide.md)

### Flight Declarations
* [Add Flight Declaration](scenarios/flight-declarations/add_flight_declaration.md)
* [Add Flight Declaration (via Operational Intent)](scenarios/flight-declarations/add_flight_declaration_via_operational_intent.md)

### Basic Scenarios
* [F1 Happy Path](scenarios/standard-scenarios/F1_happy_path.md)
* [F2 Contingent Path](scenarios/standard-scenarios/F2_contingent_path.md)
* [F3 Non Conforming Path](scenarios/standard-scenarios/F3_non_conforming_path.md)
* [F5 Non Conforming Path](scenarios/standard-scenarios/F5_non_conforming_path.md)

### Geo Fence Scenarios
* [Geo Fence Upload](scenarios/geo-fence/geo_fence_upload.md)

## Air Traffic Simulation Scenarios
* [Opensky Live Data](scenarios/airtraffic-simulations/opensky_live_data.md)
* [OpenUTM Sim Air Traffic Data](scenarios/airtraffic-simulations/openutm_sim_air_traffic_data.md)

## SDSP Scenarios
* [SDSP Heartbeat](scenarios/sdsp-f3623/sdsp_heartbeat.md)
* [SDSP Track](scenarios/sdsp-f3623/sdsp_track.md)
* [SDSP Sensor Failure](scenarios/sdsp-f3623/sdsp_verify_sensor_failure_report.md)
* [SDSP Metrics](scenarios/sdsp-f3623/verify_sdsp_metrics.md)

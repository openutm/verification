# OpenUTM Simulated Air Traffic Data

## Overview

**Scenario Name:** `openutm_sim_air_traffic_data`
**Description:** This scenario verifies the integration between the simulated air traffic generator and Flight Blender. It generates simulated air traffic observations and submits them to the backend to ensure they are correctly ingested.

## Execution Flow

The scenario executes the following sequence of steps:

### 1. Stream Air Traffic
- **Step:** `Stream Air Traffic`
- **Arguments:** `provider: geojson`, `target: flight_blender`
- **Action:** Generates simulated flight observations using the GeoJSON provider and submits them to Flight Blender's air traffic data feed.
- **Context:** Uses internal simulation logic/templates to create predictable traffic patterns for testing.
- **Verification:** Ensures observations are generated and the API accepts the payload.

### 2. Completion
- **Action:** The scenario completes successfully upon meaningful submission callback.

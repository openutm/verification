# DAA Scenario Authoring Guide

End-to-end workflow for creating, running, and verifying ASTM F3442 DAA scenarios in the Edmonton area.

## Existing scenarios

| ID | Ownships | Intruders | Geometry |
|----|----------|-----------|----------|
| A1 | 1 | 1 | Head-on |
| A2 | 1 | 1 | Crossing |
| A3 | 1 | 1 | Overtake |
| B1 | 1 | 2 | Simultaneous |
| B2 | 1 | 2 | Staggered |
| B3 | 1 | 5 | Swarm |
| C1 | 2 | 1 | Shared intruder |
| C2 | 3 | 4 | Multi-ownship multi-intruder |
| Cap100 | 100 | 10 | 10×10 grid, BlueSky defined-path intruders |

## Files per scenario

Every scenario needs these files in the repo. Replace `<tag>` with a short identifier (e.g. `d1_diverging`).

| File | Path | Purpose |
|------|------|---------|
| Flight declaration | `config/edmonton/flight_declaration_<tag>.json` | Ownship bounding box |
| Ownship trajectory | `config/edmonton/trajectory_<tag>_ownship.json` | GeoJSON LineString path |
| BlueSky scenario | `config/edmonton/bluesky_<tag>.scn` | Intruder aircraft definitions |
| Scenario YAML | `scenarios/daa_<tag>_cooperative.yaml` | Orchestration + verification |

Multi-ownship scenarios use per-ownship files: `flight_declaration_<tag>_alpha.json`, `trajectory_<tag>_alpha.json`, etc.

**Large scenarios (>20 ownships):** use a subfolder under `config/edmonton/` to keep data files organized. For example, `config/edmonton/cap100/` contains all 200 data files for the 100-ownship scenario (trajectory + declaration per ownship) plus the BlueSky `.scn` file.

---

## Step 1: Create the flight declaration

A bounding box that encloses the ownship trajectory and encounter area.

```json
{
  "minx": -113.6100,
  "miny": 53.5100,
  "maxx": -113.5400,
  "maxy": 53.5300
}
```

Coordinates are in the Edmonton suburban area (~53.52°N, -113.57°W). Add margin around the ownship path to cover intruder approach.

## Step 2: Create the ownship trajectory

A GeoJSON FeatureCollection with a single LineString. **Minimum 300m total length** — use a loiter rectangle for hovering ownships.

**Linear path** (Cat A/B — ownship flies a straight line):

```json
{
  "type": "FeatureCollection",
  "features": [{
    "type": "Feature",
    "properties": {},
    "geometry": {
      "type": "LineString",
      "coordinates": [
        [-113.6000, 53.5200],
        [-113.5960, 53.5200],
        [-113.5920, 53.5200],
        [-113.5880, 53.5200],
        [-113.5840, 53.5200],
        [-113.5800, 53.5200],
        [-113.5760, 53.5200],
        [-113.5720, 53.5200],
        [-113.5680, 53.5200],
        [-113.5640, 53.5200],
        [-113.5600, 53.5200]
      ]
    }
  }]
}
```

**Loiter rectangle** (Cat C — ownship hovers in a small box):

```json
{
  "type": "FeatureCollection",
  "features": [{
    "type": "Feature",
    "properties": {},
    "geometry": {
      "type": "LineString",
      "coordinates": [
        [-113.5378, 53.5219],
        [-113.5358, 53.5219],
        [-113.5358, 53.5207],
        [-113.5378, 53.5207],
        [-113.5378, 53.5219],
        [-113.5358, 53.5219],
        [-113.5358, 53.5207],
        [-113.5378, 53.5207],
        [-113.5378, 53.5219]
      ]
    }
  }]
}
```

## Step 3: Create the BlueSky scenario

Defines intruder aircraft. Format:

```
# Header comment describing the scenario
00:00:00.00>POLY <AREA_NAME> <lat1>,<lon1> <lat2>,<lon2> <lat3>,<lon3> <lat4>,<lon4>
00:00:00.00>COLOR <AREA_NAME> 0,255,0
00:00:00.00>TRAILS ON
00:00:00.00>RESO OFF
00:00:00.00>RTF 10
00:00:00.00>PAN <center_lat>,<center_lon>
00:00:00.00>-

# CRE <callsign>,<type>,<lat>,<lon>,<heading>,<alt_ft>,<speed_kts>
00:00:00.00>CRE INTD1,C172,53.5200,-113.5500,270,400,87
00:00:00.00>INTD1 ADDWPT 53.5200,-113.5750
00:00:00.00>INTD1 ADDWPT 53.5200,-113.6000

# Stagger additional intruders with time offsets
00:00:20.00>CRE INTD2,P28A,53.4900,-113.5700,045,380,70
00:00:20.00>INTD2 ADDWPT 53.5200,-113.5750

00:02:00.00>HOLD
```

Key rules:
- Callsign = ICAO identifier used in incident logs (e.g. `INTD1`)
- Aircraft types: `C172` (Cessna), `P28A` (Piper), `B206` (Bell 206), `C150` (ultralight)
- Altitude in feet; speed in knots
- `HOLD` time must exceed the encounter window
- Stagger `CRE` timestamps for staggered-arrival scenarios

## Step 4: Create the scenario YAML

### Single-ownship skeleton (Categories A/B)

```yaml
name: daa_<tag>_cooperative
description: >
  ASTM F3442 Category <X> - <geometry description>.
  <One sentence on what this scenario verifies.>

steps:
  - step: Check AMQP Connection
  - step: Cleanup Flight Declarations
  - step: Setup Flight Declaration
    arguments:
      flight_declaration_path: config/edmonton/flight_declaration_<tag>.json
      trajectory_path: config/edmonton/trajectory_<tag>_ownship.json
  - step: Start AMQP Queue Monitor
    arguments:
      routing_key: ${{ steps.Setup Flight Declaration.result.id }}
      duration: 160                     # > telemetry + BlueSky duration
    background: true
  - step: Update Operation State
    arguments:
      state: ACTIVATED
  - id: generate_traffic
    step: Generate BlueSky Simulation Air Traffic Data
    arguments:
      config_path: config/edmonton/bluesky_<tag>.scn
      duration: 130                     # > encounter window
  - step: Submit Simulated Air Traffic
    arguments:
      observations: ${{ steps.generate_traffic.result }}
    background: true
  - step: Wait X seconds
    arguments:
      duration: 5
  - step: Submit Telemetry
    arguments:
      duration: 120                     # covers full encounter + resolution
    background: true
  - id: update_state_ended
    step: Update Operation State
    arguments:
      state: ENDED
    needs:
      - Submit Telemetry
      - Submit Simulated Air Traffic
  - step: Stop AMQP Queue Monitor
    needs:
      - update_state_ended
  - id: get_daa_active_alerts
    step: Get Active DAA Alerts
  - id: get_daa_incident_logs
    step: Get DAA Incident Logs
    arguments:
      start_date: ${{ steps.Setup Flight Declaration.result.start_datetime }}
  - step: Get AMQP Messages
    arguments:
      routing_key_filter: ${{ steps.Setup Flight Declaration.result.id }}

  # --- Verification ---
  - step: Verify DAA ASTM F3442 API Compliance
    arguments:
      incident_logs: ${{ steps.get_daa_incident_logs.result }}
      active_alerts: ${{ steps.get_daa_active_alerts.result }}
      min_incident_logs: 1
      require_alert_events: true
      require_periodic_updates: true
  - step: Verify DAA Encounter Criteria
    arguments:
      incident_logs: ${{ steps.get_daa_incident_logs.result }}
      active_alerts: ${{ steps.get_daa_active_alerts.result }}
      expected_alert_levels: [1, 2, 3]  # ADVISORY, CAUTION, WARNING
      expected_geometry: head_on         # head_on | crossing | overtake | any
      max_1hz_gap_seconds: 3.0
```

### Multi-ownship skeleton (Category C)

Differences: `Setup Multiple Flight Declarations With Paths`, per-ownship activation/telemetry, `routing_key: "#"`, shared-intruder verification.

```yaml
name: daa_<tag>_cooperative
description: >
  ASTM F3442 Category C - <multi-ownship description>.

steps:
  - step: Check AMQP Connection
  - step: Cleanup Flight Declarations
  - id: setup_declarations
    step: Setup Multiple Flight Declarations With Paths
    arguments:
      declaration_paths:
        - config/edmonton/flight_declaration_<tag>_alpha.json
        - config/edmonton/flight_declaration_<tag>_bravo.json
      duration_minutes: 60
  - step: Start AMQP Queue Monitor
    arguments:
      routing_key: "#"
      duration: 250
    background: true

  # Activate each ownship
  - id: activate_alpha
    step: Update Operation State of declaration
    arguments:
      declaration_id: ${{ steps.setup_declarations.result.declarations[0].id }}
      state: ACTIVATED
  - id: activate_bravo
    step: Update Operation State of declaration
    arguments:
      declaration_id: ${{ steps.setup_declarations.result.declarations[1].id }}
      state: ACTIVATED

  # Intruder traffic
  - id: generate_traffic
    step: Generate BlueSky Simulation Air Traffic Data
    arguments:
      config_path: config/edmonton/bluesky_<tag>.scn
      duration: 210
  - step: Submit Simulated Air Traffic
    arguments:
      observations: ${{ steps.generate_traffic.result }}
    background: true
  - step: Wait X seconds
    arguments:
      duration: 5

  # Per-ownship telemetry
  - id: generate_alpha_telemetry
    step: Generate Telemetry
    arguments:
      config_path: config/edmonton/trajectory_<tag>_alpha.json
      duration: 180
      reference_time: ${{ steps.setup_declarations.result.declarations[0].start_datetime }}
  - id: generate_bravo_telemetry
    step: Generate Telemetry
    arguments:
      config_path: config/edmonton/trajectory_<tag>_bravo.json
      duration: 180
      reference_time: ${{ steps.setup_declarations.result.declarations[1].start_datetime }}
  - id: submit_alpha_telemetry
    step: Submit Telemetry For Declaration
    arguments:
      declaration_id: ${{ steps.setup_declarations.result.declarations[0].id }}
      states: ${{ steps.generate_alpha_telemetry.result }}
      duration: 180
    background: true
  - id: submit_bravo_telemetry
    step: Submit Telemetry For Declaration
    arguments:
      declaration_id: ${{ steps.setup_declarations.result.declarations[1].id }}
      states: ${{ steps.generate_bravo_telemetry.result }}
      duration: 180
    background: true

  # End all declarations
  - id: end_alpha
    step: Update Operation State of declaration
    arguments:
      declaration_id: ${{ steps.setup_declarations.result.declarations[0].id }}
      state: ENDED
    needs: [submit_alpha_telemetry, submit_bravo_telemetry, Submit Simulated Air Traffic]
  - id: end_bravo
    step: Update Operation State of declaration
    arguments:
      declaration_id: ${{ steps.setup_declarations.result.declarations[1].id }}
      state: ENDED
    needs: [submit_alpha_telemetry, submit_bravo_telemetry, Submit Simulated Air Traffic]

  - step: Stop AMQP Queue Monitor
    needs: [end_alpha, end_bravo]
  - id: get_active_alerts
    step: Get Active DAA Alerts
  - id: get_incident_logs
    step: Get DAA Incident Logs
    arguments:
      start_date: ${{ steps.setup_declarations.result.declarations[0].start_datetime }}
  - step: Get AMQP Messages
    arguments:
      routing_key_filter: "#"

  # --- Verification ---
  - step: Verify DAA ASTM F3442 API Compliance
    arguments:
      incident_logs: ${{ steps.get_incident_logs.result }}
      active_alerts: ${{ steps.get_active_alerts.result }}
      min_incident_logs: 4
      require_alert_events: true
      require_periodic_updates: true
  - step: Verify DAA Encounter Criteria
    arguments:
      incident_logs: ${{ steps.get_incident_logs.result }}
      active_alerts: ${{ steps.get_active_alerts.result }}
      expected_alert_levels: [1]
      expected_geometry: any
      require_escalation: false
      max_1hz_gap_seconds: 4.0
  - step: Verify DAA Shared Intruder Independence
    arguments:
      incident_logs: ${{ steps.get_incident_logs.result }}
      expected_intruder_icao: <SHARED_INTRUDER_ICAO>
      expected_alert_count: 2
      min_distinct_range_m: 25.0
      min_distinct_initial_cpa_seconds: 10.0
```

---

## Step 5: Create a dev config and run

Create a one-scenario config in `config/local/` (gitignored):

```yaml
# config/local/daa_dev_<tag>.yaml
suites:
  daa_dev:
    scenarios:
      - name: daa_<tag>_cooperative
```

Run:

```bash
./scripts/iterate_daa.sh --config config/local/daa_dev_<tag>.yaml --suite daa_dev
```

Or with a Flight Blender rebuild first:

```bash
./scripts/iterate_daa.sh --rebuild --config config/local/daa_dev_<tag>.yaml --suite daa_dev
```

The script runs the scenario and displays the report summary automatically.

## Step 6: Verify results

### Quick pass/fail check

```bash
./scripts/iterate_daa.sh --latest
# or
python3 debug/scenario/parse_report.py --quiet
```

### Detailed diagnostics

```bash
python3 debug/scenario/parse_report.py --verbose
python3 debug/scenario/summarize_incidents.py --scenario daa_<tag>
python3 debug/scenario/analyze_alert_pair.py --scenario daa_<tag> --icao <INTRUDER_ICAO>
```

### Geometry / timing debugging

```bash
python3 debug/scenario/check_3d_distances.py --scenario daa_<tag> --icao <INTRUDER_ICAO>
python3 debug/scenario/analyze_bearings.py --scenario daa_<tag>
python3 debug/scenario/check_timestamps.py --scenario daa_<tag>
```

All tools default to the latest report. Pass a report directory as a positional arg for a specific run.

---

## System constraints (must-know)

| Constraint | Detail |
|------------|--------|
| **Predictive alerting** | Alert level is based on predicted min separation over 30s horizon, not current range. Alerts fire while aircraft are still far apart. |
| **Current-level semantics** | `current_level` reflects current threat (not peak). Alerts de-escalate: WARNING → CAUTION → ADVISORY → resolved. |
| **Ownship cadence** | Simulator advances at `0.004` path-fraction per state → effective speed = `trajectory_length_m × 0.004` m/s. A 2700m trajectory gives ~11 m/s; a 5000m trajectory gives ~20 m/s. Account for ownship movement when designing crossing/overtake geometry. |
| **Min trajectory length** | 300m. Use loiter rectangles for hover scenarios. |
| **BlueSky speed** | Performance models may override requested speed significantly. Observed: P28A requested 97 kts → actual ~150 kts (77 m/s); SR22 requested 117 kts → actual ~136 kts (70 m/s). Always check `intruder_speed_mps` from incident logs and design geometry based on observed speed. |
| **1Hz logging jitter** | Celery Beat scheduling has inherent jitter. Start with loose thresholds: 2-3s (1 intruder), 3-5s (multi). |

## Vertical offset guide

Vertical separation is AND-gated with horizontal. Use altitude offset to control max alert level.

| Target max level | Vertical offset from ownship |
|------------------|------------------------------|
| WARNING (3) | ≤ 30m |
| CAUTION (2) | 35–70m |
| ADVISORY (1) | 80–110m |
| No alerts | > 115m |

These are design heuristics. Predictive alerting can shift the observed max level by ±1 (e.g., a 90m offset designed for ADVISORY-only may reach CAUTION). Use margins ≥20m above each threshold boundary.

## Duration sizing

Size four durations together:

| Duration | Rule of thumb |
|----------|---------------|
| Telemetry (`Submit Telemetry`) | Must cover CPA + post-CPA resolution |
| BlueSky (`Generate ... duration`) | ≥ telemetry duration + 10s |
| AMQP monitor | ≥ BlueSky duration + 30s |
| BlueSky HOLD time | ≥ BlueSky generation duration |

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Alert starts at WARNING immediately | Increase initial intruder separation |
| Only one alert level appears | Increase starting separation or encounter duration |
| No logs after early phase | Increase telemetry and AMQP durations |
| CAUTION-only intruder reaches WARNING | Increase vertical offset margin |
| 1Hz check fails | Inspect actual gap; relax `max_1hz_gap_seconds` |
| Shared-intruder independence fails | Increase ownship separation; ensure loiter boxes don't overlap |

## Iteration loop (automated)

```
1. Create/edit config files (declaration, trajectory, .scn, YAML)
2. Run:  ./scripts/iterate_daa.sh --config config/local/daa_dev_<tag>.yaml --suite daa_dev
3. Check: python3 debug/scenario/parse_report.py --quiet
4. If FAIL → inspect with debug tools → adjust geometry/timing → go to 2
5. If PASS → add scenario to config/default.yaml astm_f3442 suite
```

## Related files

- [daa_integration_testing_learnings.md](daa_integration_testing_learnings.md) — background and design rationale
- [debug/scenario/README.md](../debug/scenario/README.md) — debug tools reference
- [scenarios/README.md](../scenarios/README.md) — all scenario descriptions

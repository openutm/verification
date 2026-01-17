# Configuration Editor Implementation

## Overview
A configuration editor has been added to the Scenario Settings panel in the web-editor, allowing users to modify configuration settings directly in the UI without manually editing YAML files.

## Features

### Configurable Settings
The configuration editor provides expandable sections for three main configuration areas:

#### 1. **Flight Blender Configuration**
- **URL**: Flight Blender deployment endpoint (e.g., `http://localhost:8000`)
- **Auth Type**: Authentication method (`none` or `passport`)
- **Auth Fields** (conditionally shown for passport):
  - Client ID
  - Client Secret
  - Token Endpoint
  - Passport Base URL
- **Audience**: OAuth token audience
- **Scopes**: List of required scopes (comma-separated)

#### 2. **Data Files Configuration**
- **Trajectory**: Path to trajectory JSON file
- **Flight Declaration**: Path to flight declaration JSON file
- **Flight Declaration via Operational Intent**: Path to operational intent flight declaration
- **Geo Fence**: Path to geo-fence configuration

#### 3. **Air Traffic Simulator Settings**
- **Number of Aircraft**: Integer field (1-100)
- **Simulation Duration**: Duration in seconds (1-3600)
- **Single or Multiple Sensors**: Dropdown selector
- **Sensor IDs**: Comma-separated list of sensor identifiers

## Implementation Details

### New Files
- **`src/components/ScenarioEditor/ConfigEditor.tsx`**: Main configuration editor component
  - Collapsible sections for each configuration category
  - Form inputs for all configuration fields
  - Real-time validation and state management

### Modified Files

#### Type Definitions (`src/types/scenario.ts`)
- Added `FlightBlenderAuth` interface
- Added `FlightBlenderConfig` interface
- Added `DataFilesConfig` interface
- Added `AirTrafficSimulatorSettings` interface
- Added `ScenarioConfig` interface

#### Components
- **`ScenarioEditor.tsx`**:
  - Added config state management with autosave support
  - Default configuration values
  - Config persists to sessionStorage when dirty
  - Loads config from autosave on restoration

- **`ScenarioInfoPanel.tsx`**:
  - Imported and integrated `ConfigEditor` component
  - Added config prop to component signature
  - Added `onUpdateConfig` callback handler
  - ConfigEditor displays below description field

- **`ScenarioList.tsx`**:
  - Updated `onLoadScenario` callback signature to accept optional config
  - Passes config from loaded scenarios to parent

#### Hooks
- **`useScenarioFile.ts`**:
  - Added `currentScenarioConfig` parameter
  - Passes config to `convertGraphToYaml` when saving

#### Utilities
- **`scenarioConversion.ts`**:
  - `convertYamlToGraph`: Now returns config if present in scenario
  - `convertGraphToYaml`: Accepts and includes config in output

#### Tests
- **`useScenarioFile.test.ts`**: Updated all test cases to include config parameter

#### Styling
- **`SidebarPanel.module.css`**: Added styles for config sections
  - `.configSection`: Container for collapsible sections
  - `.configSectionHeader`: Button styling with icon alignment

## State Management

### Autosave Integration
The configuration is automatically saved to sessionStorage along with other scenario data:
```typescript
- editor-autosave-config: Configuration state as JSON
```

### Flow
1. User modifies configuration in the UI
2. `onUpdateConfig` sets state and marks scenario as dirty
3. Dirty state triggers autosave (debounced at 500ms)
4. Configuration is persisted to sessionStorage
5. On page reload, configuration is restored from autosave

## User Experience

### Collapsible Sections
- Each configuration category is collapsible for better UI organization
- Default expanded state: Flight Blender section
- User can toggle sections independently
- State is maintained during the editing session

### Form Validation
- Number fields have min/max constraints
- Sensor IDs are parsed as comma-separated values
- Scopes are automatically parsed from comma-separated input

### Integration
- Configuration editor seamlessly integrates with existing scenario editor
- Configuration changes trigger the same dirty state as step changes
- Configuration is saved alongside scenario steps when saving to server

## Usage

1. Open the Scenario Settings panel (right sidebar)
2. Scroll down to find the CONFIGURATION section
3. Click section headers to expand/collapse
4. Modify configuration fields as needed
5. Changes are automatically saved to autosave
6. When saving the scenario, configuration is included in the YAML file

## API Compatibility

Scenarios saved with configuration will now include a `config` field in the YAML format:
```yaml
name: my_scenario
description: My scenario description
config:
  flight_blender:
    url: "http://localhost:8000"
    auth:
      type: "none"
      audience: "testflight.flightblender.com"
      scopes: ["flightblender.write", "flightblender.read"]
  data_files:
    trajectory: "config/bern/trajectory_f1.json"
    flight_declaration: "config/bern/flight_declaration.json"
  air_traffic_simulator_settings:
    number_of_aircraft: 3
    simulation_duration: 10
    single_or_multiple_sensors: "multiple"
    sensor_ids:
      - "a0b7d47e5eac45dc8cbaf47e6fe0e558"
steps:
  - step: "Create Flight"
    arguments: {}
```

## Default Configuration
When creating a new scenario, default configuration values are provided:
- Flight Blender: `http://localhost:8000` with "none" auth
- Audience: `testflight.flightblender.com`
- Data Files: Bern configuration files
- Air Traffic Simulator: 3 aircraft, 10 seconds duration, multiple sensors

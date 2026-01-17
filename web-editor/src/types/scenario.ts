export interface OperationParam {
    name: string;
    type: string;
    default?: unknown;
    options?: { name: string; value: unknown }[];
    isEnum?: boolean;
}

export interface Operation {
    id: string;
    name: string;
    description: string;
    parameters: OperationParam[];
    category?: string;
}

export interface NodeData extends Record<string, unknown> {
    label: string;
    stepId?: string;
    operationId?: string;
    description?: string;
    parameters?: OperationParam[];
    status?: 'success' | 'failure' | 'error' | 'running';
    result?: unknown;
    runInBackground?: boolean;
    onShowResult?: (result: unknown) => void;
}

export interface ScenarioStep {
    id?: string;
    step: string;
    arguments: Record<string, unknown>;
    needs?: string[];
    background?: boolean;
    description?: string;
}

export interface ScenarioDefinition {
    name: string;
    description?: string;
    steps: ScenarioStep[];
}

export interface StepResult {
    id: string;
    status: 'success' | 'failure' | 'error';
    result: unknown;
    error?: string;
}

export interface ScenarioExecutionResult {
    results: StepResult[];
    status: string;
    duration: number;
}

export interface FlightBlenderAuth {
    type: string;
    client_id?: string;
    client_secret?: string;
    token_endpoint?: string;
    passport_base_url?: string;
    audience?: string;
    scopes?: string[];
}

export interface FlightBlenderConfig {
    url: string;
    auth: FlightBlenderAuth;
}

export interface DataFilesConfig {
    trajectory?: string;
    flight_declaration?: string;
    flight_declaration_via_operational_intent?: string;
    geo_fence?: string;
}

export interface AirTrafficSimulatorSettings {
    number_of_aircraft?: number;
    simulation_duration?: number;
    single_or_multiple_sensors?: string;
    sensor_ids?: string[];
}

export interface ScenarioConfig {
    flight_blender: FlightBlenderConfig;
    data_files: DataFilesConfig;
    air_traffic_simulator_settings: AirTrafficSimulatorSettings;
}

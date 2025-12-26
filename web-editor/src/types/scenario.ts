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
    operationId?: string;
    description?: string;
    parameters?: OperationParam[];
    status?: 'success' | 'failure' | 'error' | 'running';
    result?: unknown;
    runInBackground?: boolean;
}

export interface ScenarioStep {
    id: string;
    name: string;
    parameters: Record<string, unknown>;
    run_in_background?: boolean;
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

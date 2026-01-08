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

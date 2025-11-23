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
    functionName: string;
    className: string;
    description: string;
    parameters: OperationParam[];
}

export interface NodeData extends Record<string, unknown> {
    label: string;
    operationId?: string;
    className?: string;
    functionName?: string;
    description?: string;
    parameters?: OperationParam[];
    status?: 'success' | 'failure' | 'error';
    result?: unknown;
    onShowResult?: (result: unknown) => void;
}

export interface ScenarioStep {
    id: string;
    className: string;
    functionName: string;
    parameters: Record<string, unknown>;
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

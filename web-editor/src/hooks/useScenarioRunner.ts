import { useState, useCallback } from 'react';
import type { Node, Edge } from '@xyflow/react';
import type { NodeData } from '../types/scenario';

export const useScenarioRunner = () => {
    const [isRunning, setIsRunning] = useState(false);

    const runScenario = useCallback(async (
        nodes: Node<NodeData>[],
        edges: Edge[],
        onStepComplete?: (result: { id: string; status: 'success' | 'failure' | 'error'; result?: unknown }) => void,
        onStepStart?: (nodeId: string) => void
    ) => {
        if (nodes.length === 0) return null;

        // Simple topological sort / path following
        const incomingEdges = new Set(edges.map(e => e.target));
        const startNodes = nodes.filter(n => !incomingEdges.has(n.id));

        if (startNodes.length === 0) {
            alert("Cycle detected or no start node found.");
            return null;
        }

        setIsRunning(true);

        const sortedNodes: Node<NodeData>[] = [];
        const queue = [...startNodes];
        const visited = new Set<string>();

        while (queue.length > 0) {
            const node = queue.shift()!;
            if (visited.has(node.id)) continue;
            visited.add(node.id);
            sortedNodes.push(node);

            const outgoing = edges.filter(e => e.source === node.id);
            for (const edge of outgoing) {
                const targetNode = nodes.find(n => n.id === edge.target);
                if (targetNode) {
                    queue.push(targetNode);
                }
            }
        }

        const steps = sortedNodes.filter(node => node.data.operationId); // Filter out nodes without operationId

        try {
            // 1. Reset Session
            await fetch('http://localhost:8989/session/reset', { method: 'POST' });

            const results: { id: string; status: string; result?: unknown; error?: unknown }[] = [];

            // 2. Execute steps one by one
            for (const node of steps) {
                if (onStepStart) {
                    onStepStart(node.id);
                }

                const params = (node.data.parameters || []).reduce((acc, param) => {
                    if (param.default !== undefined && param.default !== null && param.default !== '') {
                        acc[param.name] = param.default;
                    }
                    return acc;
                }, {} as Record<string, unknown>);

                let className = node.data.className as string;
                let functionName = node.data.functionName as string;

                if ((!className || !functionName) && typeof node.data.operationId === 'string') {
                    const parts = node.data.operationId.split('.');
                    if (parts.length === 2) {
                        [className, functionName] = parts;
                    }
                }

                // Construct URL with query param for background execution
                const url = new URL(`http://localhost:8989/api/${className}/${functionName}`);
                if (node.data.runInBackground) {
                    url.searchParams.append('run_in_background', 'true');
                }
                url.searchParams.append('step_id', node.id);

                console.log(`Executing step ${node.id}: ${className}.${functionName}`, params);

                const response = await fetch(url.toString(), {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(params)
                });

                if (!response.ok) {
                    const errorText = await response.text();
                    throw new Error(`Step ${className}.${functionName} failed: ${response.status} ${errorText}`);
                }

                const result = await response.json();

                // Add ID to result to match expected format
                const stepResult = {
                    id: node.id,
                    status: result.status || 'success',
                    result: result.result || result,
                    error: result.error
                };
                results.push(stepResult);

                if (onStepComplete) {
                    onStepComplete(stepResult as { id: string; status: 'success' | 'failure' | 'error'; result?: unknown });
                }

                // If error, stop execution
                if (stepResult.status === 'error' || stepResult.status === 'failure') {
                    console.error(`Step ${node.id} failed`, stepResult);
                    break;
                }
            }

            return { results, status: 'completed', duration: 0 };

        } catch (error) {
            console.error('Error running scenario:', error);
            alert(`Failed to run scenario: ${error}`);
            return null;
        } finally {
            setIsRunning(false);
        }
    }, []);

    return { isRunning, runScenario };
};

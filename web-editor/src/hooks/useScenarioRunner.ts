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
            await fetch('/session/reset', { method: 'POST' });

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

                const stepDefinition = {
                    id: node.id,
                    step: node.data.label, // The backend expects 'step', not 'name'
                    arguments: params,     // The backend expects 'arguments', not 'parameters'
                    background: !!node.data.runInBackground // The backend expects 'background', not 'run_in_background'
                };

                console.log(`Executing step ${node.id}: ${node.data.label}`, stepDefinition);

                const response = await fetch('/api/step', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(stepDefinition)
                });

                if (!response.ok) {
                    const errorText = await response.text();
                    throw new Error(`Step ${node.data.label} failed: ${response.status} ${errorText}`);
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

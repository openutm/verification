import { useState, useCallback } from 'react';
import type { Node, Edge } from '@xyflow/react';
import type { NodeData, ScenarioStep, ScenarioExecutionResult } from '../types/scenario';

export const useScenarioRunner = () => {
    const [isRunning, setIsRunning] = useState(false);

    const runScenario = useCallback(async (nodes: Node<NodeData>[], edges: Edge[]) => {
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

        const steps: ScenarioStep[] = sortedNodes
            .filter(node => node.data.operationId) // Filter out nodes without operationId (like Start node)
            .map(node => {
                const params = (node.data.parameters || []).reduce((acc, param) => {
                    if (param.default !== undefined && param.default !== null && param.default !== '') {
                        acc[param.name] = param.default;
                    }
                    return acc;
                }, {} as Record<string, unknown>);

                let className = node.data.className as string;
                let functionName = node.data.functionName as string;

                // Fallback to parsing operationId if className/functionName are missing
                if ((!className || !functionName) && typeof node.data.operationId === 'string') {
                    const parts = node.data.operationId.split('.');
                    if (parts.length === 2) {
                        [className, functionName] = parts;
                    }
                }

                return {
                    id: node.id,
                    className,
                    functionName,
                    parameters: params
                };
            });

        try {
            console.log('Sending scenario steps:', steps);
            const response = await fetch('http://localhost:8989/run-scenario', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ steps })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const result: ScenarioExecutionResult = await response.json();
            return result;

        } catch (error) {
            console.error('Error running scenario:', error);
            alert('Failed to run scenario. Is the backend server running?');
            return null;
        } finally {
            setIsRunning(false);
        }
    }, []);

    return { isRunning, runScenario };
};

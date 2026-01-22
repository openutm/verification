import { useState, useCallback, useRef } from 'react';
import type { Node, Edge } from '@xyflow/react';
import type { GroupDefinition, NodeData, Operation, ScenarioConfig } from '../types/scenario';
import { convertGraphToYaml } from '../utils/scenarioConversion';

export const useScenarioRunner = () => {
    const [isRunning, setIsRunning] = useState(false);
    const eventSourceRef = useRef<EventSource | null>(null);

    const stopScenario = useCallback(async () => {
        try {
            // Close the EventSource connection first
            if (eventSourceRef.current) {
                eventSourceRef.current.close();
                eventSourceRef.current = null;
            }

            const response = await fetch('/stop-scenario', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
            });
            if (!response.ok) {
                console.error('Failed to stop scenario:', response.statusText);
            }
        } catch (error) {
            console.error('Error stopping scenario:', error);
        } finally {
            setIsRunning(false);
        }
    }, []);

    const runScenario = useCallback(async (
        nodes: Node<NodeData>[],
        edges: Edge[],
        scenarioName: string,
        onStepComplete?: (result: { id: string; status: 'success' | 'failure' | 'error' | 'skipped' | 'running' | 'waiting'; result?: unknown }) => void,
        onStepStart?: (nodeId: string) => void,
        config?: ScenarioConfig,
        operations: Operation[] = [],
        groups?: Record<string, GroupDefinition>,
        description: string = 'Run from Web UI'
    ) => {
        if (nodes.length === 0) return null;

        // Filter out visual/dependency edges (dotted lines)
        const sequenceEdges = edges.filter(e => e.style?.strokeDasharray !== '5 5');

        // Simple topological sort / path following
        const incomingEdges = new Set(sequenceEdges.map(e => e.target));
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

            const outgoing = sequenceEdges.filter(e => e.source === node.id);
            for (const edge of outgoing) {
                const targetNode = nodes.find(n => n.id === edge.target);
                if (targetNode) {
                    queue.push(targetNode);
                }
            }
        }

        const runnableNodes = sortedNodes.filter(node => node.data.operationId); // Filter out nodes without operationId

        try {
            // 1. Reset Session and apply configuration
            const resetPayload: { config?: ScenarioConfig } = {};
            if (config) {
                resetPayload.config = config;
            }

            const resetResponse = await fetch('/session/reset', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(resetPayload)
            });

            if (!resetResponse.ok) {
                throw new Error(`Failed to initialize session: ${resetResponse.statusText}`);
            }

            const results: { id: string; status: string; result?: unknown; error?: unknown }[] = [];

            if (onStepStart) {
                runnableNodes.forEach(node => onStepStart(node.id));
            }

            const scenarioPayload = convertGraphToYaml(
                nodes,
                edges,
                operations,
                scenarioName,
                description,
                undefined,
                groups
            );

            const response = await fetch('/run-scenario-async', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(scenarioPayload)
            });

            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`Scenario run failed: ${response.status} ${errorText}`);
            }

            const seenResults = new Map<string, string>();

            const handleStepResult = (result: { id?: string; status?: string; result?: unknown; error?: unknown; error_message?: string; logs?: string[] }) => {
                if (!result?.id) {
                    return;
                }
                const nextStatus = result.status || 'success';
                const previousStatus = seenResults.get(result.id);
                if (previousStatus === nextStatus) {
                    return;
                }
                seenResults.set(result.id, nextStatus);
                const stepResult = {
                    id: result.id,
                    status: nextStatus,
                    result: result.result || result,
                    error: result.error_message || result.error,
                    logs: result.logs || []
                };
                results.push(stepResult);
                if (onStepComplete) {
                    onStepComplete(stepResult as { id: string; status: 'success' | 'failure' | 'error' | 'skipped' | 'running' | 'waiting'; result?: unknown; logs?: string[] });
                }
            };

            await new Promise<void>((resolve, reject) => {
                const source = new EventSource(`/run-scenario-events`);
                eventSourceRef.current = source;

                source.onmessage = (event) => {
                    try {
                        const data = JSON.parse(event.data) as { id?: string; status?: string; result?: unknown; error?: unknown; error_message?: string; logs?: string[] };
                        handleStepResult(data);
                    } catch (err) {
                        source.close();
                        eventSourceRef.current = null;
                        reject(err);
                    }
                };

                source.addEventListener('done', (event) => {
                    try {
                        const payload = JSON.parse((event as MessageEvent).data) as { status?: string; error?: string };
                        source.close();
                        eventSourceRef.current = null;
                        if (payload.status === 'error') {
                            reject(new Error(payload.error || 'Scenario run failed'));
                            return;
                        }
                        resolve();
                    } catch (err) {
                        source.close();
                        eventSourceRef.current = null;
                        reject(err);
                    }
                });

                source.onerror = () => {
                    source.close();
                    eventSourceRef.current = null;
                    reject(new Error('Scenario event stream failed'));
                };
            });

            // 3. Generate Report
            try {
                console.log("Generating report...");
                const reportRes = await fetch('/session/generate-report', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ scenario_name: scenarioName })
                });
                if (!reportRes.ok) {
                    console.error("Failed to generate report:", await reportRes.text());
                } else {
                    console.log("Report generated successfully");
                }
            } catch (e) {
                console.error("Error calling generate report endpoint:", e);
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

    return { isRunning, runScenario, stopScenario };
};

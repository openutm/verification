import { useCallback } from 'react';
import type { Node, Edge } from '@xyflow/react';
import type { NodeData, Operation } from '../types/scenario';
import { convertGraphToYaml } from '../utils/scenarioConversion';

export const useScenarioFile = (
    nodes: Node<NodeData>[],
    edges: Edge[],
    operations: Operation[]
) => {
    const handleSaveToServer = useCallback(async () => {
        const scenarioName = prompt("Enter scenario name (e.g. my_scenario):", "new_scenario");
        if (!scenarioName) return;

        const scenario = convertGraphToYaml(nodes, edges, operations);

        try {
            const response = await fetch(`/api/scenarios/${scenarioName}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(scenario),
            });

            if (!response.ok) {
                throw new Error(`Server error: ${response.statusText}`);
            }

            const result = await response.json();
            alert(result.message || "Scenario saved successfully!");
        } catch (error) {
            console.error('Error saving scenario:', error);
            alert('Failed to save scenario to server.');
        }
    }, [nodes, edges]);

    // handleLoadYAML is not needed anymore as we load from the sidebar list
    // but we keep handleFileChange if we want to support local file loading as a fallback?
    // The user said "We don't need to handle YAML files locally".
    // So I will remove local file handling.

    return { handleSaveToServer };
};

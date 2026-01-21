import { useCallback } from 'react';
import type { Node, Edge } from '@xyflow/react';
import type { NodeData, Operation, ScenarioConfig, GroupDefinition } from '../types/scenario';
import { convertGraphToYaml } from '../utils/scenarioConversion';

export const useScenarioFile = (
    nodes: Node<NodeData>[],
    edges: Edge[],
    operations: Operation[],
    currentScenarioName: string | null,
    setCurrentScenarioName: (name: string) => void,
    currentScenarioDescription: string,
    currentScenarioConfig: ScenarioConfig,
    currentScenarioGroups?: Record<string, GroupDefinition>,
    onScenarioSaved?: () => void,
    onSaveSuccess?: () => void
) => {
    const handleSaveToServer = useCallback(async () => {
        let scenarioName = currentScenarioName;

        if (!scenarioName) {
            scenarioName = prompt("Enter scenario name (e.g. my_scenario):", "new_scenario");
            if (!scenarioName) return;
        }

        const scenario = convertGraphToYaml(nodes, edges, operations, scenarioName, currentScenarioDescription, currentScenarioConfig, currentScenarioGroups);

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
            setCurrentScenarioName(scenarioName);
            onScenarioSaved?.();
            onSaveSuccess?.();
        } catch (error) {
            console.error('Error saving scenario:', error);
            alert('Failed to save scenario to server.');
        }
    }, [nodes, edges, operations, currentScenarioName, setCurrentScenarioName, currentScenarioDescription, currentScenarioConfig, currentScenarioGroups, onScenarioSaved, onSaveSuccess]);

    const handleSaveAs = useCallback(async () => {
        const defaultName = currentScenarioName || "new_scenario";
        const scenarioName = prompt("Enter new scenario name:", defaultName);
        if (!scenarioName) return;

        const scenario = convertGraphToYaml(nodes, edges, operations, scenarioName, currentScenarioDescription, currentScenarioConfig, currentScenarioGroups);

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
            setCurrentScenarioName(scenarioName);
            onScenarioSaved?.();
            onSaveSuccess?.();
        } catch (error) {
            console.error('Error saving scenario:', error);
            alert('Failed to save scenario to server.');
        }
    }, [nodes, edges, operations, currentScenarioName, setCurrentScenarioName, currentScenarioDescription, currentScenarioConfig, currentScenarioGroups, onScenarioSaved, onSaveSuccess]);

    return { handleSaveToServer, handleSaveAs };
};

import type { Node, Edge } from '@xyflow/react';
import type { Operation, ScenarioDefinition, ScenarioStep, NodeData } from '../types/scenario';

export const convertYamlToGraph = (
    scenario: ScenarioDefinition,
    operations: Operation[]
): { nodes: Node<NodeData>[]; edges: Edge[] } => {
    const nodes: Node<NodeData>[] = [];
    const edges: Edge[] = [];

    let yPos = 0;
    const xPos = 250;
    const gap = 150;
    const usedIds = new Set<string>();

    scenario.steps.forEach((step, index) => {
        const operation = operations.find(op => op.name === step.step);
        if (!operation) {
            console.warn(`Operation ${step.step} not found`);
            return;
        }

        let nodeId = step.id;

        if (!nodeId) {
            // Use the step name as is for the ID
            nodeId = step.step;
        }

        // Ensure uniqueness (in case the provided ID was already used)
        if (usedIds.has(nodeId)) {
             nodeId = `node_${index}_${Date.now()}`;
        }

        usedIds.add(nodeId);

        // Map arguments to parameters
        const parameters = operation.parameters.map(param => ({
            ...param,
            default: step.arguments?.[param.name] ?? param.default
        }));

        const node: Node<NodeData> = {
            id: nodeId,
            type: 'custom',
            position: { x: xPos, y: yPos },
            data: {
                label: step.step,
                operationId: operation.id,
                description: step.description || operation.description,
                parameters: parameters,
                runInBackground: step.background
            }
        };

        nodes.push(node);
        yPos += gap;

        if (index > 0) {
            const prevNode = nodes[index - 1];
            edges.push({
                id: `e_${prevNode.id}-${nodeId}`,
                source: prevNode.id,
                target: nodeId,
                type: 'smoothstep'
            });
        }
    });

    return { nodes, edges };
};

export const convertGraphToYaml = (
    nodes: Node<NodeData>[],
    edges: Edge[],
    operations: Operation[] = []
): ScenarioDefinition => {
    // Sort nodes based on edges to determine order
    const targetIds = new Set(edges.map(e => e.target));
    const roots = nodes.filter(n => !targetIds.has(n.id));

    // If multiple roots, sort by y position
    roots.sort((a, b) => a.position.y - b.position.y);

    const sortedNodes: Node<NodeData>[] = [];
    const visited = new Set<string>();

    const visit = (node: Node<NodeData>) => {
        if (visited.has(node.id)) return;
        visited.add(node.id);
        sortedNodes.push(node);

        // Find outgoing edges
        const outgoing = edges
            .filter(e => e.source === node.id)
            .map(e => nodes.find(n => n.id === e.target))
            .filter((n): n is Node<NodeData> => !!n);

        // Sort outgoing by y position
        outgoing.sort((a, b) => a.position.y - b.position.y);

        outgoing.forEach(visit);
    };

    roots.forEach(visit);

    // Handle disconnected nodes
    nodes.forEach(node => {
        if (!visited.has(node.id)) {
            sortedNodes.push(node);
        }
    });

    const steps: ScenarioStep[] = sortedNodes.map(node => {
        const operation = operations.find(op => op.id === node.data.operationId);
        const args: Record<string, unknown> = {};

        node.data.parameters?.forEach(param => {
            const currentValue = param.default;

            // Skip null values
            if (currentValue === null) return;

            // Skip undefined values
            if (currentValue === undefined) return;

            // Skip default values if operation is available
            if (operation) {
                const originalParam = operation.parameters.find(p => p.name === param.name);
                if (originalParam && originalParam.default === currentValue) {
                    return;
                }
            }

            args[param.name] = currentValue;
        });

        const step: ScenarioStep = {
            step: node.data.label,
            arguments: args,
        };

        // Don't save IDs to keep YAML clean
        // if (node.id && !node.id.startsWith('node_')) {
        //     step.id = node.id;
        // }

        // Description is not saved to YAML to keep it clean
        // if (node.data.description) {
        //     step.description = node.data.description;
        // }

        if (node.data.runInBackground) {
            step.background = true;
        }

        return step;
    });

    return {
        name: "Exported Scenario",
        description: "Exported from OpenUTM Scenario Designer",
        steps
    };
};

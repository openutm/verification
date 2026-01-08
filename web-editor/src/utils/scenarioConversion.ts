import { type Node, type Edge, MarkerType } from '@xyflow/react';
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
                stepId: step.id,
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
                type: 'smoothstep',
                animated: true,
                style: { stroke: 'var(--accent-primary)', strokeWidth: 1 },
                markerEnd: { type: MarkerType.ArrowClosed, color: 'var(--accent-primary)' }
            });
        }

        // Add visual connection for Join Background Task
        if (step.step === "Join Background Task" && step.arguments?.['task_id']) {
            const targetLabel = step.arguments['task_id'];
            // Find the node with this label
            const backgroundNode = nodes.find(n => n.data.label === targetLabel);

            if (backgroundNode) {
                edges.push({
                    id: `e${backgroundNode.id}-${nodeId}`,
                    source: backgroundNode.id,
                    target: nodeId,
                    type: 'smoothstep',
                    selectable: false,
                    style: { strokeDasharray: '5 5' }
                });
            }
        }
    });

    return { nodes, edges };
};

export const convertGraphToYaml = (
    nodes: Node<NodeData>[],
    edges: Edge[],
    operations: Operation[] = [],
    name: string = "Exported Scenario",
    description: string = "Exported from OpenUTM Scenario Designer"
): ScenarioDefinition => {
    // Filter out visual/dependency edges (dotted lines)
    const sequenceEdges = edges.filter(e => e.style?.strokeDasharray !== '5 5');

    // Sort nodes based on edges to determine order
    const targetIds = new Set(sequenceEdges.map(e => e.target));
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
        const outgoing = sequenceEdges
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

            // Transform reference object to string format expected by backend
            if (typeof currentValue === 'object' && currentValue !== null && '$ref' in currentValue) {
                const ref = (currentValue as { $ref: string }).$ref;
                const parts = ref.split('.');
                const stepName = parts[0];
                const fieldPath = parts.slice(1).join('.');
                args[param.name] = `\${{ steps.${stepName}.result.${fieldPath} }}`;
                return;
            }

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

        if (node.data.stepId && node.data.stepId.trim() !== '') {
            step.id = node.data.stepId;
        }

        // Don't save IDs to keep YAML clean
        // if (node.id && !node.id.startsWith('node_')) {
        //     step.id = node.id;
        // }

        // Description is saved if it differs from the default operation description
        if (node.data.description && (!operation || node.data.description !== operation.description)) {
            step.description = node.data.description;
        }

        if (node.data.runInBackground) {
            step.background = true;
        }

        return step;
    });

    return {
        name: name,
        description: description,
        steps
    };
};

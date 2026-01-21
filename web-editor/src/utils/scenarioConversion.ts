import { type Node, type Edge, MarkerType } from '@xyflow/react';
import { createWaitEdge } from './edgeStyles';
import type { Operation, ScenarioDefinition, ScenarioStep, NodeData, ScenarioConfig, GroupDefinition } from '../types/scenario';

export const convertYamlToGraph = (
    scenario: ScenarioDefinition,
    operations: Operation[]
): { nodes: Node<NodeData>[]; edges: Edge[]; config?: ScenarioConfig } => {
    const nodes: Node<NodeData>[] = [];
    const edges: Edge[] = [];

    let yPos = 0;
    const xPos = 250;
    const gap = 150;
    const groupContainerGap = 200; // Extra space for group containers
    const usedIds = new Set<string>();
    const groupStepMap = new Map<string, string[]>(); // Maps group container ID to its step IDs
    const stepIdToNodeId = new Map<string, string>();
    let lastSequenceNodeId: string | null = null;

    scenario.steps.forEach((step, index) => {

        // Check if this is a group reference
        const isGroupReference = scenario.groups && step.step in scenario.groups;
        const operation = isGroupReference ? null : operations.find(op => op.name === step.step);

        if (!isGroupReference && !operation) {
            console.warn(`Operation ${step.step} not found`);
            return;
        }

        let nodeId = step.id;

        if (!nodeId) {
            nodeId = step.step;
        }

        if (usedIds.has(nodeId)) {
            nodeId = `node_${index}_${Date.now()}`;
        }

        usedIds.add(nodeId);
        const stepIdForMap = step.id || step.step;

        if (isGroupReference) {
            // Expand group into visual container with its steps
            const group = scenario.groups![step.step];
            const groupContainerId = `group_${nodeId}`;
            const groupStepIds: string[] = [];

            // Determine container styling based on modifiers
            let containerBorder = '2px solid var(--accent-primary)';
            let containerBackground = 'rgba(100, 150, 200, 0.05)';

            if (step.loop && step.if) {
                containerBorder = '3px double #a855f7'; // Purple double border for both
                containerBackground = 'rgba(168, 85, 247, 0.08)';
            } else if (step.loop) {
                containerBorder = '3px solid #a855f7'; // Purple for loop
                containerBackground = 'rgba(168, 85, 247, 0.05)';
            } else if (step.if) {
                containerBorder = '3px solid #22c55e'; // Green for condition
                containerBackground = 'rgba(34, 197, 94, 0.05)';
            }

            // Add container node
            const containerNode: Node<NodeData> = {
                id: groupContainerId,
                type: 'custom',
                position: { x: xPos - 50, y: yPos },
                data: {
                    label: `📦 ${step.step}`,
                    stepId: step.id,
                    description: group.description || `Group containing ${group.steps.length} steps`,
                    parameters: [],
                    runInBackground: step.background,
                    ifCondition: step.if,
                    loop: step.loop,
                    isGroupReference: true,
                    isGroupContainer: true
                },
                style: {
                    background: containerBackground,
                    border: containerBorder,
                    borderRadius: '12px',
                    padding: '20px',
                    minWidth: '600px',
                    minHeight: `${Math.max(150, group.steps.length * 120 + 80)}px`
                }
            };
            nodes.push(containerNode);

            stepIdToNodeId.set(stepIdForMap, groupContainerId);

            let groupInternalYPos = yPos + 60;
            let prevGroupStepNode: Node<NodeData> | null = null;

            // Add steps inside the group
            group.steps.forEach((groupStep, stepIndex) => {
                const groupStepId = `${groupContainerId}_step_${stepIndex}`;
                groupStepIds.push(groupStepId);

                const groupOperation = operations.find(op => op.name === groupStep.step);

                const groupParameters = (groupOperation?.parameters || []).map(param => ({
                    ...param,
                    default: groupStep.arguments?.[param.name] ?? param.default
                }));

                const groupStepNode: Node<NodeData> = {
                    id: groupStepId,
                    type: 'custom',
                    parentId: groupContainerId,
                    position: { x: 80, y: groupInternalYPos - yPos }, // Relative to parent
                    data: {
                        label: groupStep.step,
                        stepId: groupStep.id || groupStep.step,
                        operationId: groupOperation?.id,
                        description: groupStep.description || groupOperation?.description || '',
                        parameters: groupParameters
                    }
                };

                nodes.push(groupStepNode);

                stepIdToNodeId.set(groupStep.id || groupStep.step, groupStepId);

                // Connect group steps to each other
                if (prevGroupStepNode) {
                    edges.push({
                        id: `e_${prevGroupStepNode.id}-${groupStepId}`,
                        source: prevGroupStepNode.id,
                        target: groupStepId,
                        type: 'smoothstep',
                        animated: true,
                        style: { stroke: 'var(--accent-primary)', strokeWidth: 1 },
                        markerEnd: { type: MarkerType.ArrowClosed, color: 'var(--accent-primary)' }
                    });
                }

                prevGroupStepNode = groupStepNode;
                groupInternalYPos += gap;
            });

            groupStepMap.set(groupContainerId, groupStepIds);
            yPos += groupContainerGap;
            // Track for sequence connection
            const currentNodeId = groupContainerId;
            if (lastSequenceNodeId && lastSequenceNodeId !== currentNodeId) {
                edges.push({
                    id: `e_${lastSequenceNodeId}-${currentNodeId}`,
                    source: lastSequenceNodeId,
                    target: currentNodeId,
                    type: 'smoothstep',
                    animated: true,
                    style: { stroke: 'var(--accent-primary)', strokeWidth: 1 },
                    markerEnd: { type: MarkerType.ArrowClosed, color: 'var(--accent-primary)' }
                });
            }
            lastSequenceNodeId = currentNodeId;
        } else {
            // Regular step
            const parameters = (operation?.parameters || []).map(param => ({
                ...param,
                default: step.arguments?.[param.name] ?? param.default
            }));

            const needsListRaw = step.needs || [];
            const needsList = needsListRaw
                .map(depId => stepIdToNodeId.get(depId) || depId)
                .filter((v): v is string => !!v);

            const node: Node<NodeData> = {
                id: nodeId,
                type: 'custom',
                position: { x: xPos, y: yPos },
                data: {
                    label: step.step,
                    stepId: step.id,
                    operationId: operation?.id,
                    description: step.description || operation?.description || '',
                    parameters: parameters,
                    runInBackground: step.background,
                    ifCondition: step.if,
                    loop: step.loop,
                    needs: needsList,
                    isGroupReference: false
                }
            };

            nodes.push(node);
            stepIdToNodeId.set(stepIdForMap, nodeId);
            yPos += gap;
            const currentNodeId = nodeId;
            if (lastSequenceNodeId && lastSequenceNodeId !== currentNodeId) {
                edges.push({
                    id: `e_${lastSequenceNodeId}-${currentNodeId}`,
                    source: lastSequenceNodeId,
                    target: currentNodeId,
                    type: 'smoothstep',
                    animated: true,
                    style: { stroke: 'var(--accent-primary)', strokeWidth: 1 },
                    markerEnd: { type: MarkerType.ArrowClosed, color: 'var(--accent-primary)' }
                });
            }
            lastSequenceNodeId = currentNodeId;
        }

        // Render dependency edges for needs (dotted)
        const currentId = isGroupReference ? `group_${nodeId}` : nodeId;
        const needsForStep = isGroupReference
            ? (step.needs || [])
            : ((nodes.find(n => n.id === nodeId)?.data?.needs as string[] | undefined) || (step.needs || []));
        needsForStep.forEach(depId => {
            const sourceNodeId = stepIdToNodeId.get(depId) || depId || nodes.find(n => n.data.stepId === depId || n.data.label === depId)?.id;
            if (!sourceNodeId) return;
            edges.push(createWaitEdge(sourceNodeId, currentId));
        });
    });

    const result: { nodes: Node<NodeData>[]; edges: Edge[]; config?: ScenarioConfig } = { nodes, edges };

    if ('config' in scenario) {
        result.config = scenario.config as ScenarioConfig;
    }

    return result;
};

export const convertGraphToYaml = (
    nodes: Node<NodeData>[],
    edges: Edge[],
    operations: Operation[] = [],
    name: string = "Exported Scenario",
    description: string = "Exported from OpenUTM Scenario Designer",
    config?: ScenarioConfig,
    groups?: Record<string, GroupDefinition>
): ScenarioDefinition & { config?: ScenarioConfig } => {
    // Filter out visual/dependency edges (dotted lines)
    const sequenceEdges = edges.filter(e => e.style?.strokeDasharray !== '5 5');
    const dependencyEdges = edges.filter(e => e.style?.strokeDasharray === '5 5');

    // Identify group containers (nodes that are group references)
    const groupContainerIds = new Set(nodes.filter(n => n.data.isGroupContainer).map(n => n.id));

    // Filter out nodes that are inside group containers (they have a parentId that is a group container)
    const topLevelNodes = nodes.filter(n => !n.parentId || !groupContainerIds.has(n.parentId));

    // Sort nodes based on edges to determine order
    const targetIds = new Set(sequenceEdges.map(e => e.target).filter(id => topLevelNodes.some(n => n.id === id)));
    const roots = topLevelNodes.filter(n => !targetIds.has(n.id));

    // If multiple roots, sort by y position
    roots.sort((a, b) => a.position.y - b.position.y);

    const sortedNodes: Node<NodeData>[] = [];
    const visited = new Set<string>();

    const visit = (node: Node<NodeData>) => {
        if (visited.has(node.id)) return;
        visited.add(node.id);
        sortedNodes.push(node);

        // Find outgoing edges (only to top-level nodes)
        const outgoing = sequenceEdges
            .filter(e => e.source === node.id)
            .map(e => topLevelNodes.find(n => n.id === e.target))
            .filter((n): n is Node<NodeData> => !!n);

        // Sort outgoing by y position
        outgoing.sort((a, b) => a.position.y - b.position.y);

        outgoing.forEach(visit);
    };

    roots.forEach(visit);

    // Handle disconnected nodes
    topLevelNodes.forEach(node => {
        if (!visited.has(node.id)) {
            sortedNodes.push(node);
        }
    });

    const steps: ScenarioStep[] = sortedNodes.map(node => {
        const isGroupReference = node.data.isGroupReference;

        if (isGroupReference) {
            // For group references, extract the group name from the label (remove 📦 emoji if present)
            const groupName = node.data.label.replace(/^📦\s*/, '').trim();
            const step: ScenarioStep = {
                step: groupName,
                arguments: {},
            };

            if (node.data.stepId && node.data.stepId.trim() !== '') {
                step.id = node.data.stepId;
            }

            if (node.data.ifCondition && node.data.ifCondition.trim() !== '') {
                step.if = node.data.ifCondition;
            }

            if (node.data.loop) {
                step.loop = node.data.loop;
            }

            return step;
        }

        // Regular operation step
        const operation = operations.find(op => op.id === node.data.operationId);
        const args: Record<string, unknown> = {};

        node.data.parameters?.forEach(param => {
            const currentValue = param.default;

            // Skip null values
            if (currentValue === null) return;

            // Skip undefined values
            if (currentValue === undefined) return;

            // Transform reference object to string format expected by backend
            if (typeof currentValue === 'object' && '$ref' in currentValue) {
                const ref = (currentValue as { $ref: string }).$ref;
                const parts = ref.split('.');

                // Handle both steps.step_id.result and group.step_id.result references
                if (parts[0] === 'steps' || parts[0] === 'group') {
                    const stepName = parts[1];
                    // Field path comes after 'result', e.g., group.fetch.result.id -> fieldPath = 'id'
                    const fieldPath = parts.length > 3 ? parts.slice(3).join('.') : '';
                    const refType = 'steps';
                    if (fieldPath) {
                        args[param.name] = `\${{ ${refType}.${stepName}.result.${fieldPath} }}`;
                    } else {
                        args[param.name] = `\${{ ${refType}.${stepName}.result }}`;
                    }
                } else {
                    // Legacy support
                    const stepName = parts[0];
                    const fieldPath = parts.slice(1).join('.');
                    args[param.name] = `\${{ steps.${stepName}.result.${fieldPath} }}`;
                }
                return;
            }

            // Skip default values if operation is available
            if (operation) {
                const originalParam = operation.parameters.find(p => p.name === param.name);
                if (originalParam?.default === currentValue) {
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

        if (node.data.description && (!operation || node.data.description !== operation.description)) {
            step.description = node.data.description;
        }

        if (node.data.runInBackground) {
            step.background = true;
        }

        if (node.data.ifCondition && node.data.ifCondition.trim() !== '') {
            step.if = node.data.ifCondition;
        }

        if (node.data.loop) {
            step.loop = node.data.loop;
        }

        // Dependencies (needs) come from dotted edges into this node
        const deps = dependencyEdges
            .filter(e => e.target === node.id)
            .map(e => {
                const sourceNode = nodes.find(n => n.id === e.source);
                return sourceNode?.data.stepId || sourceNode?.id;
            })
            .filter((v): v is string => !!v);
        if (deps.length > 0) {
            step.needs = Array.from(new Set(deps));
        }

        return step;
    });

    const result: ScenarioDefinition & { config?: ScenarioConfig } = {
        name: name,
        description: description,
        steps
    };

    // Include groups if provided
    if (groups && Object.keys(groups).length > 0) {
        result.groups = groups;
    }

    // Include config if provided
    if (config) {
        result.config = config;
    }

    return result;
};

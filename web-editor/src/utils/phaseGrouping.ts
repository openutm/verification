import type { Node, Edge } from '@xyflow/react';
import type { NodeData } from '../types/scenario';
import { getPhaseColor, PHASE_LABELS, PHASE_ORDER } from './phaseColors';
import { GROUP_CONFIG, getGroupHeight } from './layoutConfig';
import { getLayoutedElements } from '../hooks/useScenarioGraph';

/**
 * Resolve phases for untagged nodes: if an untagged node sits between
 * two nodes that share the same phase, it inherits that phase.
 */
const resolvePhases = (
    topLevelSteps: Node<NodeData>[],
    sequenceEdges: Edge[],
): Map<string, string> => {
    const predecessorMap = new Map<string, string>();
    const successorMap = new Map<string, string>();
    for (const e of sequenceEdges) {
        predecessorMap.set(e.target, e.source);
        successorMap.set(e.source, e.target);
    }

    const topLevelById = new Map(topLevelSteps.map(n => [n.id, n]));
    const resolvedPhase = new Map<string, string>();
    for (const node of topLevelSteps) {
        if (node.data.phase) {
            resolvedPhase.set(node.id, node.data.phase as string);
        }
    }

    for (const node of topLevelSteps) {
        if (resolvedPhase.has(node.id)) continue;

        // Walk backwards to find nearest tagged predecessor
        let predPhase: string | undefined;
        let cur = node.id;
        while (predecessorMap.has(cur)) {
            cur = predecessorMap.get(cur)!;
            const phase = resolvedPhase.get(cur) ?? (topLevelById.get(cur)?.data.phase as string | undefined);
            if (phase) { predPhase = phase; break; }
        }

        // Walk forwards to find nearest tagged successor
        let succPhase: string | undefined;
        cur = node.id;
        while (successorMap.has(cur)) {
            cur = successorMap.get(cur)!;
            const phase = resolvedPhase.get(cur) ?? (topLevelById.get(cur)?.data.phase as string | undefined);
            if (phase) { succPhase = phase; break; }
        }

        if (predPhase && predPhase === succPhase) {
            resolvedPhase.set(node.id, predPhase);
        }
    }

    return resolvedPhase;
};

/**
 * Build synthetic edges between phase containers and untagged top-level nodes
 * so dagre stacks everything vertically.
 */
const buildSyntheticEdges = (
    sequenceEdges: Edge[],
    nodeToContainer: Map<string, string>,
    newNodes: Node<NodeData>[],
): Edge[] => {
    const containerEdges: Edge[] = [];
    const added = new Set<string>();

    const addEdge = (source: string, target: string) => {
        const key = `${source}->${target}`;
        if (added.has(key)) return;
        added.add(key);
        containerEdges.push({
            id: `phase_edge_${source}_${target}`,
            source,
            target,
            type: 'default',
        });
    };

    const topLevelIds = new Set(newNodes.filter(n => !n.parentId).map(n => n.id));

    for (const edge of sequenceEdges) {
        const srcContainer = nodeToContainer.get(edge.source);
        const tgtContainer = nodeToContainer.get(edge.target);
        const srcIsTopLevel = !srcContainer && topLevelIds.has(edge.source);
        const tgtIsTopLevel = !tgtContainer && topLevelIds.has(edge.target);

        if (srcContainer && tgtContainer && srcContainer !== tgtContainer) {
            addEdge(srcContainer, tgtContainer);
        } else if (srcIsTopLevel && tgtContainer) {
            addEdge(edge.source, tgtContainer);
        } else if (srcContainer && tgtIsTopLevel) {
            addEdge(srcContainer, edge.target);
        }
    }

    return containerEdges;
};

/** Apply phase grouping to a flat list of nodes, returning grouped + layouted nodes. */
export const applyPhaseGrouping = (flatNodes: Node<NodeData>[], currentEdges: Edge[]): Node<NodeData>[] => {
    const topLevelSteps = flatNodes.filter(
        n => !n.data.isGroupContainer && !n.data.isPhaseContainer && !n.parentId
    );

    const sequenceEdges = currentEdges.filter(e => e.style?.strokeDasharray !== '5 5');
    const resolvedPhase = resolvePhases(topLevelSteps, sequenceEdges);

    // Group nodes by resolved phase
    const phaseMap = new Map<string, Node<NodeData>[]>();
    const noPhaseNodes: Node<NodeData>[] = [];
    for (const node of topLevelSteps) {
        const phase = resolvedPhase.get(node.id);
        if (phase) {
            if (!phaseMap.has(phase)) phaseMap.set(phase, []);
            phaseMap.get(phase)!.push(node);
        } else {
            noPhaseNodes.push(node);
        }
    }

    if (phaseMap.size === 0) return flatNodes;

    // Existing user-created group containers and their children stay unchanged
    const existingContainers = flatNodes.filter(
        n => (n.data.isGroupContainer && !n.data.isPhaseContainer) ||
             (n.parentId && flatNodes.some(p => p.id === n.parentId && p.data.isGroupContainer && !p.data.isPhaseContainer))
    );

    const newNodes: Node<NodeData>[] = [...existingContainers, ...noPhaseNodes];

    const sortedPhases = [...phaseMap.keys()].sort(
        (a, b) => (PHASE_ORDER.indexOf(a) === -1 ? 999 : PHASE_ORDER.indexOf(a)) -
                  (PHASE_ORDER.indexOf(b) === -1 ? 999 : PHASE_ORDER.indexOf(b))
    );

    const nodeToContainer = new Map<string, string>();

    for (const phase of sortedPhases) {
        const phaseNodes = phaseMap.get(phase)!;
        const containerId = `phase_container_${phase}`;
        const colors = getPhaseColor(phase);
        const label = PHASE_LABELS[phase] || phase;
        const containerHeight = getGroupHeight(phaseNodes.length);

        const containerNode: Node<NodeData> = {
            id: containerId,
            type: 'custom',
            position: { x: 0, y: 0 },
            data: {
                label: `✈ ${label}`,
                description: `Flight phase: ${label}`,
                parameters: [],
                isGroupContainer: true,
                isPhaseContainer: true,
                phase: phase,
            },
            style: {
                background: colors.bg,
                border: `2px solid ${colors.border}`,
                borderRadius: '12px',
                padding: '20px',
                minWidth: `${GROUP_CONFIG.width}px`,
                minHeight: `${containerHeight}px`,
                width: `${GROUP_CONFIG.width}px`,
                height: `${containerHeight}px`,
            },
        };
        newNodes.push(containerNode);

        phaseNodes.forEach((node, idx) => {
            nodeToContainer.set(node.id, containerId);
            newNodes.push({
                ...node,
                parentId: containerId,
                position: {
                    x: 80,
                    y: GROUP_CONFIG.paddingTop + idx * (80 + 40),
                },
            });
        });
    }

    const syntheticEdges = buildSyntheticEdges(sequenceEdges, nodeToContainer, newNodes);
    const allEdgesForLayout = [...currentEdges, ...syntheticEdges];
    const { nodes: layoutedNodes } = getLayoutedElements(newNodes, allEdgesForLayout, 'TB');
    return layoutedNodes;
};

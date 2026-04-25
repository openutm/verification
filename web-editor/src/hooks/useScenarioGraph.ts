import { useCallback, useState } from 'react';
import {
    useNodesState,
    useEdgesState,
    addEdge,
    type Connection,
    type Edge,
    type Node,
    type ReactFlowInstance,
} from '@xyflow/react';
import dagre from '@dagrejs/dagre';
import type { Operation, NodeData } from '../types/scenario';
import { LAYOUT_CONFIG, COMMON_NODE_DEFAULTS, COMMON_EDGE_OPTIONS, getGroupHeight, GROUP_CONFIG } from '../utils/layoutConfig';

export const getLayoutedElements = (nodes: Node<NodeData>[], edges: Edge[], direction = LAYOUT_CONFIG.direction) => {
    const dagreGraph = new dagre.graphlib.Graph();
    dagreGraph.setDefaultEdgeLabel(() => ({}));
    dagreGraph.setGraph({ rankdir: direction, nodesep: LAYOUT_CONFIG.nodeSep, ranksep: LAYOUT_CONFIG.rankSep });

    // Identify container IDs so we can exclude their children from dagre
    const containerIds = new Set(nodes.filter(n => n.data.isGroupContainer).map(n => n.id));

    // Pre-compute child counts for containers
    const childCounts = new Map<string, number>();
    for (const id of containerIds) {
        childCounts.set(id, nodes.filter(n => n.parentId === id).length);
    }

    for (const node of nodes) {
        // Skip children of containers — they will be positioned relative to parent
        if (node.parentId && containerIds.has(node.parentId)) continue;

        let width = LAYOUT_CONFIG.nodeWidth;
        let height = LAYOUT_CONFIG.nodeHeight;

        if (node.data.isGroupContainer) {
            height = getGroupHeight(childCounts.get(node.id) ?? 0);
            width = GROUP_CONFIG.width;
        }

        dagreGraph.setNode(node.id, { width, height });
    }

    // Only add edges between nodes that are in the dagre graph
    for (const edge of edges) {
        if (dagreGraph.hasNode(edge.source) && dagreGraph.hasNode(edge.target)) {
            dagreGraph.setEdge(edge.source, edge.target);
        }
    }

    dagre.layout(dagreGraph);

    const layoutedNodes = nodes.map((node) => {
        // Children of containers keep their relative positions
        if (node.parentId && containerIds.has(node.parentId)) {
            return { ...node, ...COMMON_NODE_DEFAULTS };
        }

        const nodeWithPosition = dagreGraph.node(node.id);
        const isContainer = node.data.isGroupContainer;
        const w = isContainer ? GROUP_CONFIG.width : LAYOUT_CONFIG.nodeWidth;
        const h = isContainer ? getGroupHeight(childCounts.get(node.id) ?? 0) : LAYOUT_CONFIG.nodeHeight;
        return {
            ...node,
            ...COMMON_NODE_DEFAULTS,
            position: {
                x: nodeWithPosition.x - w / 2,
                y: nodeWithPosition.y - h / 2,
            },
        };
    });

    return { nodes: layoutedNodes, edges: edges.map(edge => ({ ...edge, type: COMMON_EDGE_OPTIONS.type })) };
};

export const generateNodeId = (nodes: Node<NodeData>[], baseName: string) => {
    const slug = baseName.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '');
    let counter = 1;
    let newId = `${slug}_${counter}`;
    while (nodes.some(n => n.id === newId)) {
        counter++;
        newId = `${slug}_${counter}`;
    }
    return newId;
};

export const useScenarioGraph = (initialNodesParams: Node<NodeData>[] = [], initialEdgesParams: Edge[] = []) => {

    const [nodes, setNodes, onNodesChange] = useNodesState<Node<NodeData>>(initialNodesParams);
    const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>(initialEdgesParams);
    const [reactFlowInstance, setReactFlowInstance] = useState<ReactFlowInstance<Node<NodeData>, Edge> | null>(null);

    const onGraphDragStart = useCallback(() => {
        // Placeholder for future drag handling
    }, []);

    const onGraphDragStop = useCallback(() => {
        // Placeholder for future drag handling
    }, []);

    const onConnect = useCallback(
        (params: Connection) => {
            // Enforce 0 or 1 next/previous step constraint
            const sourceHasOutgoing = edges.some(e => e.source === params.source && e.style?.strokeDasharray !== '5 5');
            const targetHasIncoming = edges.some(e => e.target === params.target && e.style?.strokeDasharray !== '5 5');

            if (sourceHasOutgoing) {
                alert("A step can only have one next step.");
                return;
            }

            if (targetHasIncoming) {
                alert("A step can only have one previous step.");
                return;
            }

            setEdges((eds) => addEdge({
                ...params,
                ...COMMON_EDGE_OPTIONS
            }, eds));
        },
        [edges, setEdges],
    );

    const onDrop = useCallback(
        (event: React.DragEvent, operations: Operation[]) => {
            event.preventDefault();

            const type = event.dataTransfer.getData('application/reactflow');
            const opId = event.dataTransfer.getData('application/reactflow/id');

            if (!type || !reactFlowInstance) {
                return;
            }

            const position = reactFlowInstance.screenToFlowPosition({
                x: event.clientX,
                y: event.clientY,
            });

            const operation = operations.find(op => op.id === opId);

            setNodes((nds) => {
                const newId = generateNodeId(nds, type);
                const newNode: Node<NodeData> = {
                    id: newId,
                    type: 'custom',
                    position,
                    data: {
                        label: type,
                        operationId: opId,
                        category: operation?.category,
                        description: operation?.description,
                        phase: operation?.phase,
                        parameters: operation?.parameters ? JSON.parse(JSON.stringify(operation.parameters)) : [], // Deep copy parameters
                    },
                };
                return nds.concat(newNode);
            });
        },
        [reactFlowInstance, setNodes],
    );

    const onLayout = useCallback(() => {
        const { nodes: layoutedNodes, edges: layoutedEdges } = getLayoutedElements(
            nodes,
            edges,
            'TB'
        );

        setNodes([...layoutedNodes]);
        setEdges([...layoutedEdges]);

        globalThis.requestAnimationFrame(() => {
            reactFlowInstance?.fitView({ padding: 0.2, duration: 400 });
        });
    }, [nodes, edges, setNodes, setEdges, reactFlowInstance]);

    const clearGraph = useCallback(() => {
        setNodes([]);
        setEdges([]);
        sessionStorage.removeItem('scenario-nodes');
        sessionStorage.removeItem('scenario-edges');
    }, [setNodes, setEdges]);

    return {
        nodes,
        edges,
        setNodes,
        setEdges,
        onNodesChange,
        onEdgesChange,
        onConnect,
        onDrop,
        onLayout,
        clearGraph,
        reactFlowInstance,
        setReactFlowInstance,
        onGraphDragStart,
        onGraphDragStop,
    };
};

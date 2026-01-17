import { useCallback, useState } from 'react';
import {
    useNodesState,
    useEdgesState,
    addEdge,
    type Connection,
    type Edge,
    type Node,
    type ReactFlowInstance,
    MarkerType,
} from '@xyflow/react';
import dagre from '@dagrejs/dagre';
import type { Operation, NodeData } from '../types/scenario';

const nodeWidth = 180;
const nodeHeight = 80;

const getLayoutedElements = (nodes: Node<NodeData>[], edges: Edge[], direction = 'TB') => {
    const dagreGraph = new dagre.graphlib.Graph();
    dagreGraph.setDefaultEdgeLabel(() => ({}));
    dagreGraph.setGraph({ rankdir: direction, nodesep: 50, ranksep: 100 });

    for (const node of nodes) {
        dagreGraph.setNode(node.id, { width: nodeWidth, height: nodeHeight });
    }

    for (const edge of edges) {
        dagreGraph.setEdge(edge.source, edge.target);
    }

    dagre.layout(dagreGraph);

    const layoutedNodes = nodes.map((node) => {
        const nodeWithPosition = dagreGraph.node(node.id);
        return {
            ...node,
            position: {
                x: nodeWithPosition.x - nodeWidth / 2,
                y: nodeWithPosition.y - nodeHeight / 2,
            },
        };
    });

    return { nodes: layoutedNodes, edges };
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
                animated: true,
                style: { stroke: 'var(--accent-primary)', strokeWidth: 1 },
                markerEnd: { type: MarkerType.ArrowClosed, color: 'var(--accent-primary)' }
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
                        description: operation?.description,
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

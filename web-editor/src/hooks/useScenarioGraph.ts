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

let id = 0;
const getId = () => `dndnode_${id++}`;

export const useScenarioGraph = () => {
    const [nodes, setNodes, onNodesChange] = useNodesState<Node<NodeData>>([]);
    const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
    const [reactFlowInstance, setReactFlowInstance] = useState<ReactFlowInstance<Node<NodeData>, Edge> | null>(null);

    const onConnect = useCallback(
        (params: Connection) => setEdges((eds) => addEdge({
            ...params,
            animated: true,
            style: { stroke: 'var(--accent-primary)', strokeWidth: 1 },
            markerEnd: { type: MarkerType.ArrowClosed, color: 'var(--accent-primary)' }
        }, eds)),
        [setEdges],
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

            const newNode: Node<NodeData> = {
                id: getId(),
                type: 'custom',
                position,
                data: {
                    label: type,
                    operationId: opId,
                    className: operation?.className,
                    functionName: operation?.functionName,
                    description: operation?.description,
                    parameters: operation?.parameters ? JSON.parse(JSON.stringify(operation.parameters)) : [], // Deep copy parameters
                },
            };

            setNodes((nds) => nds.concat(newNode));
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
    };
};

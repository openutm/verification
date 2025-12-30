import React, { useCallback, useState, useEffect, useRef, useMemo } from 'react';
import {
    ReactFlow,
    Controls,
    Background,
    BackgroundVariant,
    Panel,
    ReactFlowProvider,
    type Node,
    type Edge,
    type NodeTypes,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import layoutStyles from '../styles/EditorLayout.module.css';
import type { Operation, OperationParam, NodeData } from '../types/scenario';

import { CustomNode } from './ScenarioEditor/CustomNode';
import { Toolbox } from './ScenarioEditor/Toolbox';
import { ScenarioList } from './ScenarioEditor/ScenarioList';
import { PropertiesPanel } from './ScenarioEditor/PropertiesPanel';
import { BottomPanel } from './ScenarioEditor/BottomPanel';
import { Header } from './ScenarioEditor/Header';

import { useScenarioGraph, generateNodeId } from '../hooks/useScenarioGraph';
import { useScenarioRunner } from '../hooks/useScenarioRunner';
import { useScenarioFile } from '../hooks/useScenarioFile';

const nodeTypes: NodeTypes = {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    custom: CustomNode as any,
};

// Helper function moved outside component to avoid recreation
const updateParameterInList = (params: OperationParam[], paramName: string, value: unknown) => {
    return params.map((param) =>
        param.name === paramName ? { ...param, default: value } : param
    );
};

// Memoize child components to prevent unnecessary re-renders
const MemoizedToolbox = React.memo(Toolbox);
const MemoizedPropertiesPanel = React.memo(PropertiesPanel);
const MemoizedBottomPanel = React.memo(BottomPanel);
const MemoizedHeader = React.memo(Header);

const ScenarioEditorContent = () => {
    const reactFlowWrapper = useRef<HTMLDivElement>(null);
    const [theme, setTheme] = useState<'light' | 'dark'>(() => {
        if (typeof window !== 'undefined') {
            const saved = sessionStorage.getItem('editor-theme');
            if (saved === 'light' || saved === 'dark') return saved;
        }
        return 'light';
    });
    const [selectedNode, setSelectedNode] = useState<Node<NodeData> | null>(null);
    const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);
    const [operations, setOperations] = useState<Operation[]>([]);
    const [isConnected, setIsConnected] = useState(false);

    useEffect(() => {
        const checkHealth = async () => {
            try {
                const res = await fetch('/health');
                if (res.ok) {
                    setIsConnected(true);
                } else {
                    setIsConnected(false);
                }
            } catch {
                setIsConnected(false);
            }
        };

        checkHealth();
        const interval = setInterval(checkHealth, 5000);
        return () => clearInterval(interval);
    }, []);

    useEffect(() => {
        if (isConnected) {
            fetch('/operations')
                .then(res => res.json())
                .then(data => setOperations(data))
                .catch(err => console.error('Failed to fetch operations:', err));
        }
    }, [isConnected]);

    const {
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
        setReactFlowInstance,
        reactFlowInstance,
        onGraphDragStart,
        onGraphDragStop
    } = useScenarioGraph();

    // Refs to keep track of latest nodes/edges without triggering re-renders in callbacks
    const nodesRef = useRef(nodes);
    const edgesRef = useRef(edges);

    useEffect(() => {
        nodesRef.current = nodes;
        edgesRef.current = edges;
    }, [nodes, edges]);

    const { isRunning, runScenario } = useScenarioRunner();
    const { handleSaveToServer } = useScenarioFile(
        nodes,
        edges,
        operations
    );

    const loadScenarioFromYaml = useCallback((newNodes: Node<NodeData>[], newEdges: Edge[]) => {
        setNodes(newNodes);
        setEdges(newEdges);
        setTimeout(() => reactFlowInstance?.fitView({ padding: 0.2, duration: 400 }), 100);
    }, [setNodes, setEdges, reactFlowInstance]);

    useEffect(() => {
        document.documentElement.dataset.theme = theme;
        sessionStorage.setItem('editor-theme', theme);
    }, [theme]);

    // Update edge styles when selection changes
    useEffect(() => {
        setEdges(eds => eds.map(edge => ({
            ...edge,
            style: {
                ...edge.style,
                stroke: edge.id === selectedEdgeId ? 'var(--success)' : 'var(--accent-primary)',
                strokeWidth: edge.id === selectedEdgeId ? 2 : 1
            }
        })));
    }, [selectedEdgeId, setEdges]);

    const toggleTheme = useCallback(() => {
        setTheme(prev => prev === 'light' ? 'dark' : 'light');
    }, []);

    const onNodeClick = useCallback((_event: React.MouseEvent, node: Node) => {
        setSelectedNode(node as Node<NodeData>);
        setSelectedEdgeId(null);
    }, []);

    const onNodeDragStart = useCallback((_event: React.MouseEvent, node: Node) => {
        setSelectedNode(node as Node<NodeData>);
        setSelectedEdgeId(null);
        onGraphDragStart();
    }, [onGraphDragStart]);

    const onNodeDragStop = useCallback(() => {
        onGraphDragStop();
    }, [onGraphDragStop]);

    const onPaneClick = useCallback(() => {
        setSelectedNode(null);
        setSelectedEdgeId(null);
    }, []);

    const onEdgeClick = useCallback((_event: React.MouseEvent, edge: Edge) => {
        setSelectedEdgeId(edge.id);
        setSelectedNode(null);
    }, []);

    const onDragOver = useCallback((event: React.DragEvent) => {
        event.preventDefault();
        event.dataTransfer.dropEffect = 'move';
    }, []);

    const handleDrop = useCallback((event: React.DragEvent) => {
        onDrop(event, operations);
    }, [onDrop, operations]);

    const handleClear = useCallback(() => {
        if (globalThis.confirm('Are you sure you want to clear the current scenario? All unsaved changes will be lost.')) {
            clearGraph();
            setSelectedNode(null);
            setSelectedEdgeId(null);
        }
    }, [clearGraph]);

    const updateNodesWithResults = useCallback((currentNodes: Node<NodeData>[], results: { id: string; status: 'success' | 'failure' | 'error'; result?: unknown }[]) => {
        return currentNodes.map(node => {
            const stepResult = results.find((r) => r.id === node.id);
            if (stepResult) {
                return {
                    ...node,
                    data: {
                        ...node.data,
                        status: stepResult.status,
                        result: stepResult.result,
                    }
                };
            }
            return node;
        });
    }, []);

    const handleRun = useCallback(async () => {
        // Clear previous results/errors from the UI immediately
        setNodes((nds) => nds.map(node => ({
            ...node,
            data: {
                ...node.data,
                status: undefined,
                result: undefined
            }
        })));

        // Use getNodes/getEdges from instance to ensure we have the latest state
        // Fallback to refs if instance not ready
        const currentNodes = reactFlowInstance ? reactFlowInstance.getNodes() : nodesRef.current;
        const currentEdges = reactFlowInstance ? reactFlowInstance.getEdges() : edgesRef.current;

        // Pass a callback to update nodes incrementally
        const onStepComplete = (stepResult: { id: string; status: 'success' | 'failure' | 'error'; result?: unknown }) => {
            setNodes((nds) => {
                const updatedNodes = updateNodesWithResults(nds, [stepResult]);

                // Check if this was a Join Background Task step
                const completedNode = updatedNodes.find(n => n.id === stepResult.id);
                if (completedNode && completedNode.data.label === "Join Background Task" && stepResult.status === 'success') {
                    // Find the task_id parameter
                    const taskIdParam = completedNode.data.parameters?.find(p => p.name === "task_id");
                    const taskIdValue = taskIdParam?.default;

                    // If it's a reference, extract the node ID
                    if (taskIdValue && typeof taskIdValue === 'object' && '$ref' in taskIdValue) {
                        const ref = (taskIdValue as { $ref: string }).$ref;
                        // Assuming ref format is "nodeId.task_id"
                        const targetNodeId = ref.split('.')[0];

                        // Update the target node with the result
                        return updatedNodes.map(node => {
                            if (node.id === targetNodeId) {
                                return {
                                    ...node,
                                    data: {
                                        ...node.data,
                                        status: 'success', // Or inherit status from result?
                                        result: stepResult.result
                                    }
                                };
                            }
                            return node;
                        });
                    } else if (typeof taskIdValue === 'string') {
                        // If it's a string, it's likely the label of the background node
                        const targetNode = updatedNodes.find(n => n.data.label === taskIdValue);
                        if (targetNode) {
                            return updatedNodes.map(node => {
                                if (node.id === targetNode.id) {
                                    return {
                                        ...node,
                                        data: {
                                            ...node.data,
                                            status: 'success',
                                            result: stepResult.result
                                        }
                                    };
                                }
                                return node;
                            });
                        }
                    }
                }

                return updatedNodes;
            });
        };

        const onStepStart = (nodeId: string) => {
            setNodes((nds) => nds.map(node => {
                if (node.id === nodeId) {
                    return {
                        ...node,
                        data: {
                            ...node.data,
                            status: 'running'
                        }
                    };
                }
                return node;
            }));
        };

        await runScenario(currentNodes, currentEdges, onStepComplete, onStepStart);
    }, [runScenario, setNodes, updateNodesWithResults, reactFlowInstance]);

    const updateNodeParameter = useCallback((nodeId: string, paramName: string, value: unknown) => {
        setNodes((nds) => {
            // Special handling for Join Background Task -> task_id
            // If we are updating task_id, we might need to create/update an edge
            if (paramName === 'task_id' && typeof value === 'string') {
                const targetNode = nds.find(n => n.id === nodeId);
                if (targetNode && targetNode.data.label === "Join Background Task") {
                    // Find the source node by label (value)
                    const sourceNode = nds.find(n => n.data.label === value);

                    // Update edges: Remove existing background connection edges to this node
                    setEdges(eds => {
                        // Keep regular sequence edges (where source is NOT a background node)
                        const filtered = eds.filter(e => {
                            if (e.target !== nodeId) return true;
                            const edgeSourceNode = nds.find(n => n.id === e.source);
                            // If source is background node, remove it (we are replacing it)
                            // If source is NOT background node, keep it (it's the sequence flow)
                            return !edgeSourceNode?.data?.runInBackground;
                        });

                        if (sourceNode) {
                            return [
                                ...filtered,
                                {
                                    id: `e${sourceNode.id}-${nodeId}`,
                                    source: sourceNode.id,
                                    target: nodeId,
                                    type: 'smoothstep',
                                    selectable: false,
                                    style: { strokeDasharray: '5 5' }
                                }
                            ];
                        }
                        return filtered;
                    });
                }
            }

            return nds.map((node) => {
                if (node.id === nodeId) {
                    const updatedParameters = updateParameterInList(
                        (node.data.parameters || []),
                        paramName,
                        value
                    );
                    return {
                        ...node,
                        data: { ...node.data, parameters: updatedParameters },
                    };
                }
                return node;
            });
        });

        setSelectedNode((prev) => {
            if (!prev || prev.id !== nodeId) return prev;
            const updatedParameters = updateParameterInList(
                (prev.data.parameters || []),
                paramName,
                value
            );
            return {
                ...prev,
                data: { ...prev.data, parameters: updatedParameters },
            };
        });
    }, [setNodes, setEdges]);

    const updateNodeRunInBackground = useCallback((nodeId: string, value: boolean) => {
        const joinOp = operations.find(op => op.name === "Join Background Task");
        const shouldCreateJoinNode = value && !!joinOp;
        const newNodeId = shouldCreateJoinNode && joinOp ? generateNodeId(nodes, joinOp.name) : null;

        setNodes((nds) => {
            const updatedNodes = nds.map((node) => {
                if (node.id === nodeId) {
                    return {
                        ...node,
                        data: { ...node.data, runInBackground: value },
                    };
                }
                return node;
            });

            if (shouldCreateJoinNode && newNodeId && joinOp) {
                // Create a new node
                const newNode: Node<NodeData> = {
                    id: newNodeId,
                    type: 'custom',
                    position: { x: 0, y: 0 }, // Position will be adjusted by layout or user
                    data: {
                        label: joinOp.name,
                        operationId: joinOp.name, // Using name as ID based on runner.py
                        description: joinOp.description,
                        parameters: joinOp.parameters.map(p => ({
                            ...p,
                            default: p.name === 'task_id' ? { $ref: `${nodeId}.id` } : p.default
                        }))
                    }
                };

                // Place it near the original node if possible
                const originalNode = nds.find(n => n.id === nodeId);
                if (originalNode) {
                    newNode.position = {
                        x: originalNode.position.x,
                        y: originalNode.position.y + 150
                    };
                }

                return [...updatedNodes, newNode];
            }

            return updatedNodes;
        });

        if (shouldCreateJoinNode && newNodeId) {
            setEdges((eds) => [
                ...eds,
                {
                    id: `e${nodeId}-${newNodeId}`,
                    source: nodeId,
                    target: newNodeId,
                }
            ]);
        }

        setSelectedNode((prev) => {
            if (!prev || prev.id !== nodeId) return prev;
            return {
                ...prev,
                data: { ...prev.data, runInBackground: value },
            };
        });
    }, [setNodes, setEdges, operations, nodes]);

    const getConnectedSourceNodes = useCallback((targetNodeId: string) => {
        const sourceNodeIds = new Set(edges
            .filter(edge => edge.target === targetNodeId)
            .map(edge => edge.source));
        return nodes.filter(node => sourceNodeIds.has(node.id));
    }, [edges, nodes]);

    const connectedNodes = useMemo(() =>
        selectedNode ? getConnectedSourceNodes(selectedNode.id) : [],
        [selectedNode, getConnectedSourceNodes]
    );

    return (
        <div className={layoutStyles.editorContainer} style={{ height: '100vh', width: '100%' }}>
            <MemoizedHeader
                theme={theme}
                toggleTheme={toggleTheme}
                onLayout={onLayout}
                onClear={handleClear}
                onSave={handleSaveToServer}
                onRun={handleRun}
                isRunning={isRunning}
            />

            <div className={layoutStyles.workspace}>
                <MemoizedToolbox operations={operations}>
                    <ScenarioList onLoadScenario={loadScenarioFromYaml} operations={operations} />
                </MemoizedToolbox>

                <div className={layoutStyles.centerPane}>
                    <div className={layoutStyles.graphContainer} ref={reactFlowWrapper}>
                        <ReactFlow<Node<NodeData>, Edge>
                            nodes={nodes}
                            edges={edges}
                            nodeTypes={nodeTypes}
                            onNodesChange={onNodesChange}
                            onEdgesChange={onEdgesChange}
                            onConnect={onConnect}
                            onInit={setReactFlowInstance}
                            onDrop={handleDrop}
                            onDragOver={onDragOver}
                            onNodeClick={onNodeClick}
                            onNodeDragStart={onNodeDragStart}
                            onNodeDragStop={onNodeDragStop}
                            onPaneClick={onPaneClick}
                            onEdgeClick={onEdgeClick}
                            fitView
                            className={theme === 'dark' ? "dark-flow" : ""}
                            colorMode={theme}
                        >
                            <Controls style={{ backgroundColor: 'var(--rf-bg)', borderColor: 'var(--border-color)', fill: 'var(--text-primary)' }} />
                            <Background variant={BackgroundVariant.Dots} gap={12} size={1} color="var(--border-color)" />
                            <Panel position="top-right">
                                <div style={{ display: 'flex', gap: '10px', padding: '10px' }}>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '5px', fontSize: '12px', color: 'var(--text-secondary)' }}>
                                        <div style={{ width: '10px', height: '10px', borderRadius: '50%', backgroundColor: isConnected ? 'var(--success)' : 'var(--danger)' }}></div>
                                        {isConnected ? 'Connected' : 'Disconnected'}
                                    </div>
                                </div>
                            </Panel>
                        </ReactFlow>
                    </div>

                    {selectedNode && (
                        <MemoizedBottomPanel
                            selectedNode={selectedNode}
                            onClose={() => setSelectedNode(null)}
                        />
                    )}
                </div>

                {selectedNode && (
                    <MemoizedPropertiesPanel
                        selectedNode={selectedNode}
                        connectedNodes={connectedNodes}
                        allNodes={nodes}
                        onClose={() => setSelectedNode(null)}
                        onUpdateParameter={updateNodeParameter}
                        onUpdateRunInBackground={updateNodeRunInBackground}
                    />
                )}
            </div>
        </div>
    );
};

export default function ScenarioEditor() {
    return (
        <ReactFlowProvider>
            <ScenarioEditorContent />
        </ReactFlowProvider>
    );
}

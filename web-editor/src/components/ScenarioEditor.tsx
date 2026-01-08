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
import { ScenarioInfoPanel } from './ScenarioEditor/ScenarioInfoPanel';

import { useScenarioGraph, generateNodeId } from '../hooks/useScenarioGraph';
import { useScenarioRunner } from '../hooks/useScenarioRunner';
import { useScenarioFile } from '../hooks/useScenarioFile';
import { convertYamlToGraph } from '../utils/scenarioConversion';

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
const MemoizedScenarioInfoPanel = React.memo(ScenarioInfoPanel);
const MemoizedBottomPanel = React.memo(BottomPanel);
const MemoizedHeader = React.memo(Header);

const ScenarioEditorContent = () => {
    // Synchronously read autosave state for lazy initialization
    const [initialState] = useState(() => {
        if (typeof window === 'undefined') return { nodes: [], edges: [], desc: "", isDirty: false, isRestored: false };

        const savedIsDirty = sessionStorage.getItem('editor-is-dirty') === 'true';
        if (savedIsDirty) {
             try {
                const nodes = JSON.parse(sessionStorage.getItem('editor-autosave-nodes') || '[]');
                const edges = JSON.parse(sessionStorage.getItem('editor-autosave-edges') || '[]');
                const desc = sessionStorage.getItem('editor-autosave-description') || "";
                return { nodes, edges, desc, isDirty: true, isRestored: true };
             } catch (e) {
                 console.error("Failed to parse autosave data", e);
             }
        }
        return { nodes: [], edges: [], desc: "", isDirty: false, isRestored: false };
    });

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
    const [currentScenarioName, setCurrentScenarioName] = useState<string | null>(() => {
        if (typeof window !== 'undefined') {
            return sessionStorage.getItem('currentScenarioName');
        }
        return null;
    });
    const [currentScenarioDescription, setCurrentScenarioDescription] = useState<string>(initialState.desc);
    const [scenarioListRefreshKey, setScenarioListRefreshKey] = useState(0);
    const [isDirty, setIsDirty] = useState(initialState.isDirty);

    const incrementScenarioListRefreshKey = useCallback(() => {
        setScenarioListRefreshKey(prev => prev + 1);
    }, []);

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
    } = useScenarioGraph(initialState.nodes, initialState.edges);

    // Refs to keep track of latest nodes/edges without triggering re-renders in callbacks
    const nodesRef = useRef(nodes);
    const edgesRef = useRef(edges);

    useEffect(() => {
        nodesRef.current = nodes;
        edgesRef.current = edges;
    }, [nodes, edges]);

    const { isRunning, runScenario } = useScenarioRunner();
    const { handleSaveToServer, handleSaveAs } = useScenarioFile(
        nodes,
        edges,
        operations,
        currentScenarioName,
        setCurrentScenarioName,
        currentScenarioDescription,
        incrementScenarioListRefreshKey,
        () => setIsDirty(false)
    );

    const loadScenarioFromYaml = useCallback((newNodes: Node<NodeData>[], newEdges: Edge[]) => {
        setNodes(newNodes);
        setEdges(newEdges);
        setIsDirty(false);
        setTimeout(() => reactFlowInstance?.fitView({ padding: 0.2, duration: 400 }), 100);
    }, [setNodes, setEdges, reactFlowInstance]);

    useEffect(() => {
        // Also load description from the ScenarioList load if possible,
        // but for now the list only loads scenarios by name.
        // We might want to clear description if we can't load it?
    }, [loadScenarioFromYaml]);

    useEffect(() => {
        if (currentScenarioName) {
            sessionStorage.setItem('currentScenarioName', currentScenarioName);
        } else {
            sessionStorage.removeItem('currentScenarioName');
        }
    }, [currentScenarioName]);

    // Autosave dirty state
    useEffect(() => {
        const saveState = () => {
            if (isDirty) {
                sessionStorage.setItem('editor-is-dirty', 'true');
                sessionStorage.setItem('editor-autosave-nodes', JSON.stringify(nodes));
                sessionStorage.setItem('editor-autosave-edges', JSON.stringify(edges));
                sessionStorage.setItem('editor-autosave-description', currentScenarioDescription);
            } else {
                sessionStorage.removeItem('editor-is-dirty');
                sessionStorage.removeItem('editor-autosave-nodes');
                sessionStorage.removeItem('editor-autosave-edges');
                sessionStorage.removeItem('editor-autosave-description');
            }
        };

        // Debounce save to avoid performance impact
        const timeoutId = setTimeout(saveState, 500);
        return () => clearTimeout(timeoutId);
    }, [isDirty, nodes, edges, currentScenarioDescription]);

    // Load saved scenario on mount (refresh) if available
    const [isRestored, setIsRestored] = useState(initialState.isRestored);

    // Fallback to server load on mount if not restored from autosave
    useEffect(() => {
        if (isRestored) return;

        // Fallback to server load if not dirty or autosave failed
        if (operations.length > 0 && currentScenarioName && nodes.length === 0) {
            fetch(`/api/scenarios/${currentScenarioName}`)
                .then(res => res.json())
                .then(scenario => {
                    const { nodes: newNodes, edges: newEdges } = convertYamlToGraph(scenario, operations);
                    loadScenarioFromYaml(newNodes, newEdges);
                    setCurrentScenarioDescription(scenario.description || "");
                    setIsRestored(true);
                })
                .catch(err => {
                    console.error('Failed to restore scenario:', err);
                    setIsRestored(true);
                });
        }
    }, [operations, currentScenarioName, nodes.length, loadScenarioFromYaml, isRestored]);

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
        setIsDirty(true);
        onDrop(event, operations);
    }, [onDrop, operations]);

    const handleNew = useCallback(() => {
        if (!isDirty || globalThis.confirm('Create new scenario? Any unsaved changes will be lost.')) {
            clearGraph();
            setSelectedNode(null);
            setSelectedEdgeId(null);
            setCurrentScenarioName(null);
            setCurrentScenarioDescription("");
            setIsDirty(false);
        }
    }, [clearGraph, isDirty]);

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
        setIsDirty(true);
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
        setIsDirty(true);
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

    const updateNodeStepId = useCallback((nodeId: string, stepId: string) => {
        setIsDirty(true);
        setNodes((nds) => {
            return nds.map((node) => {
                if (node.id === nodeId) {
                    return {
                        ...node,
                        data: { ...node.data, stepId: stepId },
                    };
                }
                return node;
            });
        });

        setSelectedNode((prev) => {
            if (!prev || prev.id !== nodeId) return prev;
            return {
                ...prev,
                data: { ...prev.data, stepId: stepId },
            };
        });
    }, [setNodes]);

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
                onNew={handleNew}
                onSave={handleSaveToServer}
                onSaveAs={handleSaveAs}
                onRun={handleRun}
                isRunning={isRunning}
            />

            <div className={layoutStyles.workspace}>
                <MemoizedToolbox operations={operations}>
                    <ScenarioList
                        onLoadScenario={loadScenarioFromYaml}
                        operations={operations}
                        currentScenarioName={currentScenarioName}
                        onSelectScenario={setCurrentScenarioName}
                        refreshKey={scenarioListRefreshKey}
                        onLoadDescription={setCurrentScenarioDescription}
                    />
                </MemoizedToolbox>

                <div className={layoutStyles.centerPane}>
                    <div className={layoutStyles.graphContainer} ref={reactFlowWrapper}>
                        <ReactFlow<Node<NodeData>, Edge>
                            nodes={nodes}
                            edges={edges}
                            nodeTypes={nodeTypes}
                            onNodesChange={(changes) => {
                                // Only mark dirty if relevant changes occur (add, remove, reset, position drag end?)
                                // simple 'position' change fires on every mouse move, we might want to be less aggressive or just accept it.
                                // But selection changes also fire onNodesChange.
                                const isRelevantChange = changes.some(c => c.type !== 'select' && c.type !== 'dimensions');
                                if (isRelevantChange) setIsDirty(true);
                                onNodesChange(changes);
                            }}
                            onEdgesChange={(changes) => {
                                // Selection changes fire onEdgesChange too
                                const isRelevantChange = changes.some(c => c.type !== 'select');
                                if (isRelevantChange) setIsDirty(true);
                                onEdgesChange(changes);
                            }}
                            onConnect={(connection) => {
                                setIsDirty(true);
                                onConnect(connection);
                            }}
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
                                    {currentScenarioName && (
                                        <div style={{ display: 'flex', alignItems: 'center', fontWeight: '500', color: 'var(--text-primary)', backgroundColor: 'var(--bg-secondary)', padding: '2px 8px', borderRadius: '4px', border: '1px solid var(--border-color)' }}>
                                            {currentScenarioName}{isDirty && <span style={{ marginLeft: '4px', color: 'var(--accent-primary)' }}>*</span>}
                                        </div>
                                    )}
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

                {selectedNode ? (
                    <MemoizedPropertiesPanel
                        selectedNode={selectedNode}
                        connectedNodes={connectedNodes}
                        allNodes={nodes}
                        onClose={() => setSelectedNode(null)}
                        onUpdateParameter={updateNodeParameter}
                        onUpdateRunInBackground={updateNodeRunInBackground}
                        onUpdateStepId={updateNodeStepId}
                    />
                ) : (
                    <MemoizedScenarioInfoPanel
                        name={currentScenarioName}
                        description={currentScenarioDescription}
                        onUpdateName={(name) => {
                            setCurrentScenarioName(name);
                            setIsDirty(true);
                        }}
                        onUpdateDescription={(desc) => {
                            setCurrentScenarioDescription(desc);
                            setIsDirty(true);
                        }}
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

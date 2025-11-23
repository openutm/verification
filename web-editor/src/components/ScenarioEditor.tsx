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
import operationsData from '../data/operations.json';
import type { Operation, OperationParam, NodeData } from '../types/scenario';

import { CustomNode } from './ScenarioEditor/CustomNode';
import { Toolbox } from './ScenarioEditor/Toolbox';
import { PropertiesPanel } from './ScenarioEditor/PropertiesPanel';
import { ResultPanel } from './ScenarioEditor/ResultPanel';
import { Header } from './ScenarioEditor/Header';

import { useScenarioGraph } from '../hooks/useScenarioGraph';
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
const MemoizedResultPanel = React.memo(ResultPanel);
const MemoizedHeader = React.memo(Header);

const ScenarioEditorContent = () => {
    const reactFlowWrapper = useRef<HTMLDivElement>(null);
    const [theme, setTheme] = useState<'light' | 'dark'>('light');
    const [selectedNode, setSelectedNode] = useState<Node<NodeData> | null>(null);
    const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);
    const [resultToDisplay, setResultToDisplay] = useState<unknown>(null);

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
        reactFlowInstance
    } = useScenarioGraph();

    // Refs to keep track of latest nodes/edges without triggering re-renders in callbacks
    const nodesRef = useRef(nodes);
    const edgesRef = useRef(edges);

    useEffect(() => {
        nodesRef.current = nodes;
        edgesRef.current = edges;
    }, [nodes, edges]);

    const { isRunning, runScenario } = useScenarioRunner();
    const { fileInputRef, handleExportJSON, handleLoadJSON, handleFileChange } = useScenarioFile(
        nodes,
        edges,
        setNodes,
        setEdges,
        reactFlowInstance
    );

    useEffect(() => {
        document.documentElement.dataset.theme = theme;
    }, [theme]);

    // Update edge styles when selection changes
    useEffect(() => {
        setEdges(eds => eds.map(edge => ({
            ...edge,
            style: {
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
        setResultToDisplay(null);
    }, []);

    const onNodeDragStart = useCallback((_event: React.MouseEvent, node: Node) => {
        setSelectedNode(node as Node<NodeData>);
        setSelectedEdgeId(null);
        setResultToDisplay(null);
    }, []);

    const onPaneClick = useCallback(() => {
        setSelectedNode(null);
        setSelectedEdgeId(null);
        setResultToDisplay(null);
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
        onDrop(event, operationsData as Operation[]);
    }, [onDrop]);

    const handleClear = useCallback(() => {
        if (globalThis.confirm('Are you sure you want to clear the current scenario? All unsaved changes will be lost.')) {
            clearGraph();
            setSelectedNode(null);
            setSelectedEdgeId(null);
            setResultToDisplay(null);
        }
    }, [clearGraph]);

    const handleShowResult = useCallback((res: unknown) => {
        setResultToDisplay(res);
    }, []);

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
                        onShowResult: handleShowResult
                    }
                };
            }
            return node;
        });
    }, [handleShowResult]);

    const handleRun = useCallback(async () => {
        // Clear previous results/errors from the UI immediately
        setResultToDisplay(null);
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

        const result = await runScenario(currentNodes, currentEdges);
        if (result?.results) {
            setNodes((nds) => updateNodesWithResults(nds, result.results));
        }
    }, [runScenario, setNodes, updateNodesWithResults, reactFlowInstance, setResultToDisplay]);

    const updateNodeParameter = useCallback((nodeId: string, paramName: string, value: unknown) => {
        setNodes((nds) =>
            nds.map((node) => {
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
            })
        );

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

    // Inject onShowResult handler into nodes whenever they change or are loaded
    // This is a bit of a hack to ensure the callback is present after serialization/deserialization
    // Ideally, we wouldn't store functions in node data.
    useEffect(() => {
        setNodes(nds => nds.map(node => {
            if (!node.data.onShowResult) {
                return {
                    ...node,
                    data: {
                        ...node.data,
                        onShowResult: handleShowResult
                    }
                };
            }
            return node;
        }));
    }, [setNodes, nodes.length, handleShowResult]); // Only run when node count changes (added/loaded)

    return (
        <div className={layoutStyles.editorContainer} style={{ height: '100vh', width: '100%' }}>
            <MemoizedHeader
                theme={theme}
                toggleTheme={toggleTheme}
                onLayout={onLayout}
                onClear={handleClear}
                onLoad={handleLoadJSON}
                onExport={handleExportJSON}
                onRun={handleRun}
                isRunning={isRunning}
                fileInputRef={fileInputRef as React.RefObject<HTMLInputElement>}
                onFileChange={handleFileChange}
            />

            <div className={layoutStyles.workspace}>
                <MemoizedToolbox />

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
                                    <div style={{ width: '10px', height: '10px', borderRadius: '50%', backgroundColor: 'var(--success)' }}></div>
                                    Connected
                                </div>
                            </div>
                        </Panel>
                    </ReactFlow>
                </div>

                {resultToDisplay !== null && resultToDisplay !== undefined && (
                    <MemoizedResultPanel
                        result={resultToDisplay}
                        onClose={() => setResultToDisplay(null)}
                    />
                )}

                {selectedNode && !resultToDisplay && (
                    <MemoizedPropertiesPanel
                        selectedNode={selectedNode}
                        connectedNodes={connectedNodes}
                        onClose={() => setSelectedNode(null)}
                        onUpdateParameter={updateNodeParameter}
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

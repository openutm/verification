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
    type OnSelectionChangeParams,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import layoutStyles from '../styles/EditorLayout.module.css';
import type { Operation, OperationParam, NodeData, ScenarioConfig, GroupDefinition } from '../types/scenario';

import { CustomNode } from './ScenarioEditor/CustomNode';
import { Toolbox } from './ScenarioEditor/Toolbox';
import { ScenarioList } from './ScenarioEditor/ScenarioList';
import { PropertiesPanel } from './ScenarioEditor/PropertiesPanel';
import { BottomPanel } from './ScenarioEditor/BottomPanel';
import { Header } from './ScenarioEditor/Header';
import { ScenarioInfoPanel } from './ScenarioEditor/ScenarioInfoPanel';

import { useScenarioGraph } from '../hooks/useScenarioGraph';
import { useScenarioRunner } from '../hooks/useScenarioRunner';
import { useScenarioFile } from '../hooks/useScenarioFile';
import { convertGraphToYaml, convertYamlToGraph } from '../utils/scenarioConversion';
import { createWaitEdge } from '../utils/edgeStyles';

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
    // Default configuration
    const getDefaultConfig = (): ScenarioConfig => ({
        flight_blender: {
            url: "http://localhost:8000",
            auth: {
                type: "none",
                audience: "testflight.flightblender.com",
                scopes: ["flightblender.write", "flightblender.read"]
            }
        },
        data_files: {
            trajectory: "config/bern/trajectory_f1.json",
            flight_declaration: "config/bern/flight_declaration.json",
            flight_declaration_via_operational_intent: "config/bern/flight_declaration_via_operational_intent.json"
        },
        air_traffic_simulator_settings: {
            number_of_aircraft: 3,
            simulation_duration: 10,
            single_or_multiple_sensors: "multiple",
            sensor_ids: ["a0b7d47e5eac45dc8cbaf47e6fe0e558"]
        },
        blue_sky_air_traffic_simulator_settings: {
            number_of_aircraft: 3,
            simulation_duration_seconds: 30,
            single_or_multiple_sensors: "multiple",
            sensor_ids: ["562e6297036a4adebb4848afcd1ede90"]
        }
    });

    const groupPadding = 40;

    // Synchronously read autosave state for lazy initialization
    const [initialState] = useState(() => {
        if (typeof window === 'undefined') return { nodes: [], edges: [], desc: "", config: getDefaultConfig(), groups: {}, isDirty: false, isRestored: false };

        const savedIsDirty = sessionStorage.getItem('editor-is-dirty') === 'true';
        const savedScenarioName = sessionStorage.getItem('editor-autosave-scenario-name');
        const currentScenarioName = sessionStorage.getItem('currentScenarioName');

        if (savedIsDirty && savedScenarioName === currentScenarioName) {
             try {
                const nodes = JSON.parse(sessionStorage.getItem('editor-autosave-nodes') || '[]');
                const edges = JSON.parse(sessionStorage.getItem('editor-autosave-edges') || '[]');
                const desc = sessionStorage.getItem('editor-autosave-description') || "";
                const config = JSON.parse(sessionStorage.getItem('editor-autosave-config') || JSON.stringify(getDefaultConfig()));
                const groups = JSON.parse(sessionStorage.getItem('editor-autosave-groups') || '{}');
                return { nodes, edges, desc, config, groups, isDirty: true, isRestored: true };
             } catch (e) {
                 console.error("Failed to parse autosave data", e);
             }
        }
        return { nodes: [], edges: [], desc: "", config: getDefaultConfig(), groups: {}, isDirty: false, isRestored: false };
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
    const [selectedNodes, setSelectedNodes] = useState<Node<NodeData>[]>([]);
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
    const [currentScenarioConfig, setCurrentScenarioConfig] = useState<ScenarioConfig>(initialState.config);
    const [currentScenarioGroups, setCurrentScenarioGroups] = useState<Record<string, GroupDefinition>>(initialState.groups || {});
    const [scenarioListRefreshKey, setScenarioListRefreshKey] = useState(0);
    const [isDirty, setIsDirty] = useState(initialState.isDirty);
    const [reportError, setReportError] = useState<{ title: string; message: string } | null>(null);

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

    const { isRunning, runScenario, stopScenario } = useScenarioRunner();
    const { handleSaveToServer, handleSaveAs } = useScenarioFile(
        nodes,
        edges,
        operations,
        currentScenarioName,
        setCurrentScenarioName,
        currentScenarioDescription,
        currentScenarioConfig,
        currentScenarioGroups,
        incrementScenarioListRefreshKey,
        () => setIsDirty(false)
    );

    const loadScenarioFromYaml = useCallback((newNodes: Node<NodeData>[], newEdges: Edge[], newConfig?: ScenarioConfig, newGroups?: Record<string, GroupDefinition>, newDescription?: string) => {
        setNodes(newNodes);
        setEdges(newEdges);
        if (newConfig) {
            setCurrentScenarioConfig(newConfig);
        }
        // Always set groups to the new scenario's groups (or empty object if none provided)
        setCurrentScenarioGroups(newGroups || {});
        if (typeof newDescription === 'string') {
            setCurrentScenarioDescription(newDescription);
        }
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
                sessionStorage.setItem('editor-autosave-config', JSON.stringify(currentScenarioConfig));
                sessionStorage.setItem('editor-autosave-groups', JSON.stringify(currentScenarioGroups));
                // Save the scenario name to verify autosave is for the correct scenario
                if (currentScenarioName) {
                    sessionStorage.setItem('editor-autosave-scenario-name', currentScenarioName);
                }
            } else {
                sessionStorage.removeItem('editor-is-dirty');
                sessionStorage.removeItem('editor-autosave-nodes');
                sessionStorage.removeItem('editor-autosave-edges');
                sessionStorage.removeItem('editor-autosave-description');
                sessionStorage.removeItem('editor-autosave-config');
                sessionStorage.removeItem('editor-autosave-groups');
                sessionStorage.removeItem('editor-autosave-scenario-name');
            }
        };

        // Debounce save to avoid performance impact
        const timeoutId = setTimeout(saveState, 500);
        return () => clearTimeout(timeoutId);
    }, [isDirty, nodes, edges, currentScenarioDescription, currentScenarioConfig, currentScenarioGroups, currentScenarioName]);

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
                    const { nodes: newNodes, edges: newEdges, config } = convertYamlToGraph(scenario, operations);
                    loadScenarioFromYaml(newNodes, newEdges, config, scenario.groups);
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

    const onNodeDragStop = useCallback((_event: React.MouseEvent, node: Node<NodeData>) => {
        onGraphDragStop();

        // Only auto-attach when the node is free-floating (no edges) and not itself a group
        const hasEdges = edgesRef.current.some(e => e.source === node.id || e.target === node.id);
        if (hasEdges || node.data?.isGroupContainer || node.data?.isGroupReference) return;

        // Compute absolute position (child nodes store positions relative to parent)
        const getAbsolutePosition = (n: Node<NodeData>): { x: number; y: number } => {
            let x = n.position.x;
            let y = n.position.y;
            if (n.parentId) {
                const parent = nodesRef.current.find(p => p.id === n.parentId);
                if (parent) {
                    const parentPos = getAbsolutePosition(parent);
                    x += parentPos.x;
                    y += parentPos.y;
                }
            }
            return { x, y };
        };

        const nodeAbs = getAbsolutePosition(node);

        const parseSize = (value: unknown, fallback: number) => {
            if (typeof value === 'number') return value;
            if (typeof value === 'string') {
                const num = parseFloat(value);
                return Number.isFinite(num) ? num : fallback;
            }
            return fallback;
        };

        // Find the first group container that encloses the drop point
        const targetGroup = nodesRef.current.find(g => {
            if (!g.data?.isGroupContainer) return false;
            const width = parseSize(g.style?.minWidth, 400);
            const height = parseSize(g.style?.minHeight, 200);
            const gx = g.position.x;
            const gy = g.position.y;
            return nodeAbs.x >= gx && nodeAbs.x <= gx + width && nodeAbs.y >= gy && nodeAbs.y <= gy + height;
        });

        if (!targetGroup || targetGroup.id === node.parentId) return;

        const gx = targetGroup.position.x;
        const gy = targetGroup.position.y;
        const relativePos = {
            x: nodeAbs.x - gx,
            y: nodeAbs.y - gy,
        };

        setNodes(prev => prev.map(n => {
            if (n.id === node.id) {
                return {
                    ...n,
                    parentId: targetGroup.id,
                    position: relativePos,
                };
            }
            if (n.id === targetGroup.id) {
                const width = parseSize(n.style?.minWidth, 400);
                const height = parseSize(n.style?.minHeight, 200);
                const neededW = Math.max(width, relativePos.x + groupPadding);
                const neededH = Math.max(height, relativePos.y + groupPadding);
                return {
                    ...n,
                    style: {
                        ...n.style,
                        minWidth: `${neededW}px`,
                        minHeight: `${neededH}px`,
                    }
                };
            }
            return n;
        }));
        setIsDirty(true);
    }, [onGraphDragStop, setNodes, groupPadding]);

    const onPaneClick = useCallback(() => {
        setSelectedNode(null);
        setSelectedEdgeId(null);
    }, []);

    const onEdgeClick = useCallback((_event: React.MouseEvent, edge: Edge) => {
        setSelectedEdgeId(edge.id);
        setSelectedNode(null);
    }, []);

    const onSelectionChange = useCallback((params: OnSelectionChangeParams) => {
        const nodesSel = (params.nodes || []) as Node<NodeData>[];
        setSelectedNodes(nodesSel);

        if (nodesSel.length === 1) {
            setSelectedNode(nodesSel[0]);
        } else {
            setSelectedNode(null);
        }
    }, []);

    const clampChildPositionChanges = useCallback((changes: Parameters<typeof onNodesChange>[0]) => {
        return changes.map(change => {
            if (change.type !== 'position' || !('position' in change) || !change.position) return change;
            const node = nodesRef.current.find(n => n.id === change.id);
            if (!node?.parentId) return change;
            const clampedX = Math.max(groupPadding, change.position.x);
            const clampedY = Math.max(groupPadding, change.position.y);
            if (clampedX === change.position.x && clampedY === change.position.y) return change;
            return { ...change, position: { x: clampedX, y: clampedY } };
        });
    }, [groupPadding]);

    const expandParentForChildren = useCallback((changes: Parameters<typeof onNodesChange>[0]) => {
        const sizeUpdates: Record<string, { minWidth: number; minHeight: number }> = {};

        const parseSize = (value: unknown, fallback: number) => {
            if (typeof value === 'number') return value;
            if (typeof value === 'string') {
                const num = parseFloat(value);
                return Number.isFinite(num) ? num : fallback;
            }
            return fallback;
        };

        changes.forEach(change => {
            if (change.type !== 'position' || !('position' in change) || !change.position) return;
            const node = nodesRef.current.find(n => n.id === change.id);
            if (!node?.parentId) return;
            const parent = nodesRef.current.find(n => n.id === node.parentId);
            if (!parent) return;

            const currentMinW = parseSize(parent.style?.minWidth, 400);
            const currentMinH = parseSize(parent.style?.minHeight, 200);
            const neededW = Math.max(currentMinW, change.position.x + groupPadding);
            const neededH = Math.max(currentMinH, change.position.y + groupPadding);

            if (neededW !== currentMinW || neededH !== currentMinH) {
                const prev = sizeUpdates[parent.id];
                sizeUpdates[parent.id] = {
                    minWidth: prev ? Math.max(prev.minWidth, neededW) : neededW,
                    minHeight: prev ? Math.max(prev.minHeight, neededH) : neededH,
                };
            }
        });

        if (Object.keys(sizeUpdates).length > 0) {
            setNodes(prev => prev.map(n => {
                const update = sizeUpdates[n.id];
                if (!update) return n;
                return {
                    ...n,
                    style: {
                        ...n.style,
                        minWidth: `${update.minWidth}px`,
                        minHeight: `${update.minHeight}px`,
                    }
                };
            }));
        }
    }, [setNodes]);

    const ungroupSelectedNode = useCallback(() => {
        if (!selectedNode?.data.isGroupContainer) return;
        const groupId = selectedNode.id;
        const groupName = selectedNode.data.label.replace(/^📦\s*/, '').trim();

        // Prefer unwrapping existing child nodes to avoid duplication
        const childNodes = nodes.filter(n => n.parentId === groupId);
        const childIds = new Set(childNodes.map(n => n.id));
        const childInternalEdges = edges.filter(e => childIds.has(e.source) && childIds.has(e.target));

        let unwrapNodes: Node<NodeData>[] = [];
        let internalEdges: Edge[] = childInternalEdges;

        if (childNodes.length > 0) {
            // Convert child positions to absolute and drop parentId
            unwrapNodes = childNodes.map(n => ({
                ...n,
                parentId: undefined,
                position: {
                    x: n.position.x + selectedNode.position.x,
                    y: n.position.y + selectedNode.position.y,
                },
                selected: false,
            }));
        } else {
            // Fall back to rebuilding from group definition if children missing
            const groupDef = currentScenarioGroups[groupName];
            if (!groupDef) return;

            const tempScenario = {
                name: 'temp',
                description: '',
                steps: groupDef.steps,
            } as unknown as Parameters<typeof convertYamlToGraph>[0];

            const { nodes: groupNodes, edges: groupEdges } = convertYamlToGraph(tempScenario, operations);
            const offsetX = selectedNode.position.x + 50;
            const offsetY = selectedNode.position.y + 50;

            unwrapNodes = groupNodes.map(n => ({
                ...n,
                position: {
                    x: n.position.x + offsetX,
                    y: n.position.y + offsetY,
                },
                selected: false,
            }));
            internalEdges = groupEdges as Edge[];
        }

        // Identify roots and leaves for rewiring
        const incomingCount: Record<string, number> = {};
        const outgoingCount: Record<string, number> = {};
        internalEdges.forEach(e => {
            incomingCount[e.target] = (incomingCount[e.target] || 0) + 1;
            outgoingCount[e.source] = (outgoingCount[e.source] || 0) + 1;
        });
        const roots = unwrapNodes.filter(n => !incomingCount[n.id]);
        const leaves = unwrapNodes.filter(n => !outgoingCount[n.id]);

        // External edges
        const incomingEdges = edges.filter(e => e.target === groupId && e.style?.strokeDasharray !== '5 5');
        const outgoingEdges = edges.filter(e => e.source === groupId && e.style?.strokeDasharray !== '5 5');

        // Remove group container and any existing children
        const remainingNodes = nodes.filter(n => n.id !== groupId && n.parentId !== groupId);
        const remainingEdges = edges.filter(e => e.source !== groupId && e.target !== groupId && !childIds.has(e.source) && !childIds.has(e.target));

        const rewiredIncoming: Edge[] = incomingEdges.flatMap(e => roots.map(root => ({
            ...e,
            id: `e_${e.source}-${root.id}`,
            target: root.id,
        })));

        const rewiredOutgoing: Edge[] = outgoingEdges.flatMap(e => leaves.map(leaf => ({
            ...e,
            id: `e_${leaf.id}-${e.target}`,
            source: leaf.id,
        })));

        const nodesAfterUngroup = [...remainingNodes, ...unwrapNodes];
        setNodes(nodesAfterUngroup);
        setEdges([...remainingEdges, ...internalEdges, ...rewiredIncoming, ...rewiredOutgoing]);
        setCurrentScenarioGroups(prev => {
            const next = { ...prev };
            delete next[groupName];
            return next;
        });
        setSelectedNode(null);
        setSelectedNodes([]);
        setIsDirty(true);
    }, [selectedNode, currentScenarioGroups, operations, edges, nodes, setNodes, setEdges, setCurrentScenarioGroups]);

    const groupSelectedNodes = useCallback(() => {
        if (selectedNodes.length < 2) return;

        const selectedIds = new Set(selectedNodes.map(n => n.id));

        // Keep only sequence edges (non dotted) fully inside selection
        const internalEdges = edges.filter(e => selectedIds.has(e.source) && selectedIds.has(e.target) && e.style?.strokeDasharray !== '5 5');

        // Build steps from the selected subgraph using existing converter
        const tempScenario = convertGraphToYaml(selectedNodes, internalEdges, operations, 'temp', 'temp');
        const groupSteps = tempScenario.steps || [];
        if (groupSteps.length === 0) return;

        const defaultName = `group_${Date.now()}`;
        const groupName = window.prompt('Name this group', defaultName);
        if (!groupName) return;

        // Compute placement of new group node near selection
        const minX = Math.min(...selectedNodes.map(n => n.position.x));
        const minY = Math.min(...selectedNodes.map(n => n.position.y));
        const maxX = Math.max(...selectedNodes.map(n => n.position.x));
        const maxY = Math.max(...selectedNodes.map(n => n.position.y));
        const containerMinWidth = Math.max(400, (maxX - minX) + groupPadding * 3);
        const containerMinHeight = Math.max(200, (maxY - minY) + groupPadding * 3);
        const groupNodeId = `group_${groupName}`;

        // Rewire external edges to group roots/leaves (not to container) so flow stays intact
        const incomingEdges = edges.filter(e => !selectedIds.has(e.source) && selectedIds.has(e.target) && e.style?.strokeDasharray !== '5 5');
        const outgoingEdges = edges.filter(e => selectedIds.has(e.source) && !selectedIds.has(e.target) && e.style?.strokeDasharray !== '5 5');

        // Identify roots and leaves within the selection
        const incomingCount: Record<string, number> = {};
        const outgoingCount: Record<string, number> = {};
        internalEdges.forEach(e => {
            incomingCount[e.target] = (incomingCount[e.target] || 0) + 1;
            outgoingCount[e.source] = (outgoingCount[e.source] || 0) + 1;
        });
        const roots = selectedNodes.filter(n => !incomingCount[n.id]);
        const leaves = selectedNodes.filter(n => !outgoingCount[n.id]);

        // Base edges: those fully outside selection
        const rewiredEdges: Edge[] = edges.filter(e => !selectedIds.has(e.source) && !selectedIds.has(e.target));

        // Add incoming edges mapped to all roots
        rewiredEdges.push(
            ...incomingEdges.flatMap(e => roots.map(root => ({ ...e, id: `e_${e.source}-${root.id}`, target: root.id })))
        );

        // Add outgoing edges mapped from all leaves
        rewiredEdges.push(
            ...outgoingEdges.flatMap(e => leaves.map(leaf => ({ ...e, id: `e_${leaf.id}-${e.target}`, source: leaf.id })))
        );

        // Keep internal edges so child steps remain connected
        rewiredEdges.push(...internalEdges);

        // Create container node
        const groupNode: Node<NodeData> = {
            id: groupNodeId,
            type: 'custom',
            position: { x: minX - 50, y: minY - 50 },
            data: {
                label: `📦 ${groupName}`,
                description: `Group created from selection (${groupSteps.length} steps)`,
                isGroupContainer: true,
                isGroupReference: true,
            },
            style: {
                background: 'rgba(100, 150, 200, 0.05)',
                border: '2px solid var(--accent-primary)',
                borderRadius: '12px',
                padding: `${groupPadding}px`,
                boxShadow: 'inset 0 0 0 1px var(--border-color)',
                minWidth: `${containerMinWidth}px`,
                minHeight: `${containerMinHeight}px`
            }
        };

        // Re-parent selected nodes as children of the group container so they stay visible
        const childNodes = selectedNodes.map(n => ({
            ...n,
            parentId: groupNodeId,
            position: {
                x: n.position.x - (minX - 50),
                y: n.position.y - (minY - 50),
            },
            selected: false,
        }));

        const remainingNodes = nodes.filter(n => !selectedIds.has(n.id));
        const nodesAfterGroup = [...remainingNodes, groupNode, ...childNodes];

        setNodes(nodesAfterGroup);
        setEdges(rewiredEdges);
        setCurrentScenarioGroups(prev => ({
            ...prev,
            [groupName]: {
                description: 'Group created from selection',
                steps: groupSteps as GroupDefinition['steps']
            }
        }));
        setSelectedNodes([]);
        setSelectedNode(null);
        setIsDirty(true);
    }, [selectedNodes, edges, operations, nodes, setNodes, setEdges, setCurrentScenarioGroups]);

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

    const updateNodesWithResults = useCallback((currentNodes: Node<NodeData>[], results: { id: string; status: 'success' | 'failure' | 'error' | 'skipped' | 'running' | 'waiting'; result?: unknown; logs?: string[] }[]) => {
        return currentNodes.map(node => {
            const stepId = node.data.stepId || node.id;
            const stepName = node.data.label;
            const hasCustomStepId = !!node.data.stepId?.trim();
            const stepResult = results.find((r) =>
                r.id === stepId ||
                r.id === node.id ||
                r.id?.endsWith(`.${stepId}`) ||
                (!hasCustomStepId && (r.id === stepName || r.id?.endsWith(`.${stepName}`)))
            );
            if (stepResult) {
                return {
                    ...node,
                    data: {
                        ...node.data,
                        status: stepResult.status,
                        result: stepResult.result,
                        logs: stepResult.logs,
                    }
                };
            }
            return node;
        });
    }, []);

    const handleOpenReport = useCallback(async () => {
        const scenarioParam = currentScenarioName ? `?scenario=${encodeURIComponent(currentScenarioName)}` : '';
        const url = `/api/reports/latest${scenarioParam}`;

        // Strategy: Open "about:blank" first, then navigate.
        const newWindow = window.open('', '_blank');

        if (!newWindow) {
            setReportError({ title: "Popup Blocked", message: "Please allow popups for this site to view reports." });
            return;
        }

        // Set a loading title or message
        newWindow.document.title = "Loading Report...";
        newWindow.document.body.innerHTML = '<div style="font-family:sans-serif;padding:20px;">Finding latest report...</div>';

        try {
            const res = await fetch(url);
            if (res.ok) {
                // If it's a redirect, res.url is the final destination.
                // If the backend returns 200 OK directly, res.url is the served content url.
                newWindow.location.href = res.url;
            } else {
                newWindow.close();
                // Get error details from JSON if possible
                let message = "Unable to find the report.";
                try {
                    const errorData = await res.json();
                    if (errorData.detail) message = errorData.detail;
                } catch { /* ignore JSON parse error */ }

                setReportError({ title: "Report Not Found", message });
            }
        } catch {
            newWindow?.close();
            setReportError({ title: "Connection Error", message: "Failed to connect to the server." });
        }
    }, [currentScenarioName]);

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
        const onStepComplete = (stepResult: { id: string; status: 'success' | 'failure' | 'error' | 'skipped' | 'running' | 'waiting'; result?: unknown }) => {
            setNodes((nds) => updateNodesWithResults(nds, [stepResult]));
        };

        const onStepStart = (nodeId: string) => {
            setNodes((nds) => nds.map(node => {
                if (node.id === nodeId) {
                    return {
                        ...node,
                        data: {
                            ...node.data,
                            status: 'waiting'
                        }
                    };
                }
                return node;
            }));
        };

        await runScenario(
            currentNodes,
            currentEdges,
            currentScenarioName || "Interactive Session",
            onStepComplete,
            onStepStart,
            currentScenarioConfig,
            operations,
            currentScenarioGroups,
            currentScenarioDescription
        );
    }, [
        runScenario,
        currentScenarioName,
        currentScenarioConfig,
        currentScenarioGroups,
        currentScenarioDescription,
        operations,
        setNodes,
        updateNodesWithResults,
        reactFlowInstance
    ]);

    const updateNodeParameter = useCallback((nodeId: string, paramName: string, value: unknown) => {
        setIsDirty(true);
        setNodes((nds) => {
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
    }, [setNodes]);

    const updateNodeRunInBackground = useCallback((nodeId: string, value: boolean) => {
        setIsDirty(true);
        setNodes((nds) => nds.map((node) => (
            node.id === nodeId
                ? { ...node, data: { ...node.data, runInBackground: value } }
                : node
        )));

        setSelectedNode((prev) => {
            if (!prev || prev.id !== nodeId) return prev;
            return {
                ...prev,
                data: { ...prev.data, runInBackground: value },
            };
        });
    }, [setNodes]);

    const updateNodeNeeds = useCallback((nodeId: string, needs: string[]) => {
        setIsDirty(true);
        const cleanedNeeds = needs.filter(Boolean);

        setNodes((nds) => nds.map((node) => (
            node.id === nodeId
                ? { ...node, data: { ...node.data, needs: cleanedNeeds } }
                : node
        )));

        setEdges((eds) => {
            const base = eds.filter(e => !(e.target === nodeId && e.style?.strokeDasharray === '5 5'));
            const newEdges: Edge[] = cleanedNeeds
                .map(depId => {
                    const sourceExists = nodesRef.current.find(n => n.id === depId);
                    if (!sourceExists) return null;
                    return createWaitEdge(depId, nodeId);
                })
                .filter((e): e is Edge => !!e);
            return [...base, ...newEdges];
        });

        setSelectedNode((prev) => {
            if (!prev || prev.id !== nodeId) return prev;
            return {
                ...prev,
                data: { ...prev.data, needs: cleanedNeeds },
            };
        });
    }, [setNodes, setEdges]);

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

    const updateNodeIfCondition = useCallback((nodeId: string, condition: string) => {
        setIsDirty(true);
        setNodes((nds) => {
            return nds.map((node) => {
                if (node.id === nodeId) {
                    return {
                        ...node,
                        data: { ...node.data, ifCondition: condition },
                    };
                }
                return node;
            });
        });

        setSelectedNode((prev) => {
            if (!prev || prev.id !== nodeId) return prev;
            return {
                ...prev,
                data: { ...prev.data, ifCondition: condition },
            };
        });
    }, [setNodes]);

    const updateNodeLoop = useCallback((nodeId: string, loopConfig: NodeData['loop']) => {
        setIsDirty(true);
        setNodes((nds) => {
            return nds.map((node) => {
                if (node.id === nodeId) {
                    return {
                        ...node,
                        data: { ...node.data, loop: loopConfig },
                    };
                }
                return node;
            });
        });

        setSelectedNode((prev) => {
            if (!prev || prev.id !== nodeId) return prev;
            return {
                ...prev,
                data: { ...prev.data, loop: loopConfig },
            };
        });
    }, [setNodes]);

    const updateGroupDescription = useCallback((groupName: string, newDescription: string) => {
        setIsDirty(true);
        // Update in state
        setCurrentScenarioGroups(prev => ({
            ...prev,
            [groupName]: {
                ...prev[groupName],
                description: newDescription
            }
        }));
        // Also update the container node data
        setNodes((nds) => {
            return nds.map((node) => {
                if (node.data.isGroupContainer && node.data.label.includes(groupName)) {
                    return {
                        ...node,
                        data: { ...node.data, description: newDescription }
                    };
                }
                return node;
            });
        });
        setSelectedNode((prev) => {
            if (!prev || !prev.data.isGroupContainer) return prev;
            if (prev.data.label.includes(groupName)) {
                return {
                    ...prev,
                    data: { ...prev.data, description: newDescription }
                };
            }
            return prev;
        });
    }, [setNodes]);

    const getConnectedSourceNodes = useCallback((targetNodeId: string) => {
        const sourceNodeIds = new Set(edges
            .filter(edge => edge.target === targetNodeId && edge.style?.strokeDasharray !== '5 5')
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
                onStop={stopScenario}
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
                    />
                </MemoizedToolbox>

                <div className={layoutStyles.centerPane}>
                    <div className={layoutStyles.graphContainer} ref={reactFlowWrapper}>
                        <ReactFlow<Node<NodeData>, Edge>
                            nodes={nodes}
                            edges={edges}
                            nodeTypes={nodeTypes}
                            onNodesChange={(changes) => {
                                const boundedChanges = clampChildPositionChanges(changes);
                                expandParentForChildren(boundedChanges);
                                // Only mark dirty if relevant changes occur (add, remove, reset, position drag end?)
                                // simple 'position' change fires on every mouse move, we might want to be less aggressive or just accept it.
                                // But selection changes also fire onNodesChange.
                                const isRelevantChange = boundedChanges.some(c => c.type !== 'select' && c.type !== 'dimensions');
                                if (isRelevantChange) setIsDirty(true);
                                onNodesChange(boundedChanges);
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
                            onSelectionChange={onSelectionChange}
                            fitView
                            className={theme === 'dark' ? "dark-flow" : ""}
                            colorMode={theme}
                        >
                            <Controls style={{ backgroundColor: 'var(--rf-bg)', borderColor: 'var(--border-color)', fill: 'var(--text-primary)' }} />
                            <Background variant={BackgroundVariant.Dots} gap={12} size={1} color="var(--border-color)" />
                            <Panel position="top-right">
                                <div style={{ display: 'flex', gap: '10px', padding: '10px', alignItems: 'center' }}>
                                    {currentScenarioName && (
                                        <div style={{ display: 'flex', alignItems: 'center', fontWeight: '500', color: 'var(--text-primary)', backgroundColor: 'var(--bg-secondary)', padding: '2px 8px', borderRadius: '4px', border: '1px solid var(--border-color)' }}>
                                            {currentScenarioName}{isDirty && <span style={{ marginLeft: '4px', color: 'var(--accent-primary)' }}>*</span>}
                                        </div>
                                    )}
                                    {selectedNodes.length >= 2 && (
                                        <button
                                            onClick={groupSelectedNodes}
                                            style={{
                                                padding: '6px 12px',
                                                borderRadius: '6px',
                                                border: '1px solid var(--accent-primary)',
                                                backgroundColor: 'var(--accent-primary)',
                                                color: '#fff',
                                                cursor: 'pointer',
                                                fontWeight: 600,
                                            }}
                                            title="Group selected nodes"
                                        >
                                            Group Selection
                                        </button>
                                    )}
                                    {selectedNode?.data.isGroupContainer && (
                                        <button
                                            onClick={ungroupSelectedNode}
                                            style={{
                                                padding: '6px 12px',
                                                borderRadius: '6px',
                                                border: '1px solid var(--accent-primary)',
                                                backgroundColor: 'transparent',
                                                color: 'var(--accent-primary)',
                                                cursor: 'pointer',
                                                fontWeight: 600,
                                            }}
                                            title="Ungroup selected group"
                                        >
                                            Ungroup
                                        </button>
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
                        onUpdateNeeds={updateNodeNeeds}
                        onUpdateStepId={updateNodeStepId}
                        onUpdateIfCondition={updateNodeIfCondition}
                        onUpdateLoop={updateNodeLoop}
                        onUpdateGroupDescription={updateGroupDescription}
                    />
                ) : (
                    <MemoizedScenarioInfoPanel
                        name={currentScenarioName}
                        description={currentScenarioDescription}
                        config={currentScenarioConfig}
                        onUpdateName={(name) => {
                            setCurrentScenarioName(name);
                            setIsDirty(true);
                        }}
                        onUpdateDescription={(desc) => {
                            setCurrentScenarioDescription(desc);
                            setIsDirty(true);
                        }}
                        onUpdateConfig={(config) => {
                            setCurrentScenarioConfig(config);
                            setIsDirty(true);
                        }}
                        onOpenReport={handleOpenReport}
                    />
                )}
            </div>
            {reportError && (
                <div style={{
                    position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
                    backgroundColor: 'rgba(0, 0, 0, 0.5)', zIndex: 2000,
                    display: 'flex', justifyContent: 'center', alignItems: 'center'
                }}>
                    <div style={{
                        backgroundColor: 'var(--bg-primary)',
                        color: 'var(--text-primary)',
                        padding: '24px', borderRadius: '8px',
                        maxWidth: '400px', width: '100%',
                        boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
                        border: '1px solid var(--border-color)'
                    }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                            <h3 style={{ margin: 0, fontSize: '18px', fontWeight: 600 }}>{reportError.title}</h3>
                            <button
                                onClick={() => setReportError(null)}
                                style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-secondary)' }}
                            >
                                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                            </button>
                        </div>
                        <p style={{ margin: '0 0 20px', lineHeight: '1.5', color: 'var(--text-secondary)' }}>
                            {reportError.message}
                        </p>
                        <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                            <button
                                onClick={() => setReportError(null)}
                                style={{
                                    padding: '8px 16px', borderRadius: '4px',
                                    backgroundColor: 'var(--accent-primary)', color: 'white',
                                    border: 'none', cursor: 'pointer', fontWeight: 500
                                }}
                            >
                                Close
                            </button>
                        </div>
                    </div>
                </div>
            )}
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

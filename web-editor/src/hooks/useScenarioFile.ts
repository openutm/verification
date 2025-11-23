import { useCallback, useRef } from 'react';
import type { Node, Edge, ReactFlowInstance } from '@xyflow/react';
import type { NodeData } from '../types/scenario';

export const useScenarioFile = (
    nodes: Node<NodeData>[],
    edges: Edge[],
    setNodes: (nodes: Node<NodeData>[]) => void,
    setEdges: (edges: Edge[]) => void,
    reactFlowInstance: ReactFlowInstance<Node<NodeData>, Edge> | null
) => {
    const fileInputRef = useRef<HTMLInputElement>(null);

    const handleExportJSON = useCallback(() => {
        // Remove style and width from nodes to keep export clean
        const cleanNodes = nodes.map((node) => {
            // eslint-disable-next-line @typescript-eslint/no-unused-vars
            const { style, ...rest } = node;
            // eslint-disable-next-line @typescript-eslint/no-unused-vars
            const { width: _width, ...data } = rest.data as { width?: number;[key: string]: unknown };
            return {
                ...rest,
                data,
            };
        });

        const flowData = {
            nodes: cleanNodes,
            edges,
            viewport: reactFlowInstance?.getViewport() || { x: 0, y: 0, zoom: 1 },
        };

        const dataStr = JSON.stringify(flowData, null, 2);
        const dataBlob = new Blob([dataStr], { type: 'application/json' });
        const url = URL.createObjectURL(dataBlob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `scenario_${new Date().toISOString().replaceAll(/[:.]/g, '-')}.json`;
        document.body.appendChild(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(url);
    }, [nodes, edges, reactFlowInstance]);

    const handleLoadJSON = useCallback(() => {
        fileInputRef.current?.click();
    }, []);

    const handleFileChange = useCallback(async (event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0];
        if (!file) return;

        try {
            const content = await file.text();
            const flowData = JSON.parse(content);

            if (flowData.nodes) {
                // Apply custom node type to imported nodes
                const nodesWithStyle = flowData.nodes.map((node: Node<NodeData>) => ({
                    ...node,
                    type: 'custom',
                    style: undefined, // Remove hardcoded style
                    data: {
                        ...node.data,
                    }
                }));
                setNodes(nodesWithStyle);
            }
            if (flowData.edges) {
                setEdges(flowData.edges);
            }
            if (flowData.viewport && reactFlowInstance) {
                reactFlowInstance.setViewport(flowData.viewport);
            }
        } catch (error) {
            console.error('Error parsing JSON file:', error);
            alert('Error loading file. Please ensure it is a valid JSON scenario file.');
        }

        // Reset file input to allow loading the same file again
        if (event.target) {
            event.target.value = '';
        }
    }, [setNodes, setEdges, reactFlowInstance]);

    return { fileInputRef, handleExportJSON, handleLoadJSON, handleFileChange };
};

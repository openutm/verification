import { renderHook } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { useScenarioGraph } from '../useScenarioGraph';
import { ReactFlowProvider } from '@xyflow/react';
import React from 'react';

// Mock dagre
vi.mock('@dagrejs/dagre', () => ({
    default: {
        graphlib: {
            Graph: class {
                setDefaultEdgeLabel() { return; }
                setGraph() { return; }
                setNode() { return; }
                setEdge() { return; }
                node() { return { x: 0, y: 0 }; }
            }
        },
        layout: vi.fn()
    }
}));

describe('useScenarioGraph', () => {
    const wrapper = ({ children }: { children: React.ReactNode }) => (
        <ReactFlowProvider>{children}</ReactFlowProvider>
    );

    it('initializes with empty nodes and edges', () => {
        const { result } = renderHook(() => useScenarioGraph(), { wrapper });
        expect(result.current.nodes).toEqual([]);
        expect(result.current.edges).toEqual([]);
    });

    it('returns required functions', () => {
        const { result } = renderHook(() => useScenarioGraph(), { wrapper });
        expect(result.current.onNodesChange).toBeDefined();
        expect(result.current.onEdgesChange).toBeDefined();
        expect(result.current.onConnect).toBeDefined();
        expect(result.current.onDrop).toBeDefined();
        expect(result.current.onLayout).toBeDefined();
        expect(result.current.clearGraph).toBeDefined();
    });
});

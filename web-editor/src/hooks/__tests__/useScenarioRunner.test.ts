import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach, type Mock } from 'vitest';
import { useScenarioRunner } from '../useScenarioRunner';
import type { Node, Edge } from '@xyflow/react';
import type { NodeData } from '../../types/scenario';

describe('useScenarioRunner', () => {
    beforeEach(() => {
        globalThis.fetch = vi.fn();
        globalThis.alert = vi.fn();
    });

    afterEach(() => {
        vi.restoreAllMocks();
    });

    it('initializes with isRunning false', () => {
        const { result } = renderHook(() => useScenarioRunner());
        expect(result.current.isRunning).toBe(false);
    });

    it('runs scenario successfully', async () => {
        const mockResult = { success: true, logs: [] };
        (globalThis.fetch as Mock).mockResolvedValue({
            ok: true,
            json: async () => mockResult
        });

        const { result } = renderHook(() => useScenarioRunner());

        const nodes: Node<NodeData>[] = [
            { id: '1', position: { x: 0, y: 0 }, data: { label: 'Node 1', operationId: 'Class.method', className: 'Class', functionName: 'method', parameters: [] } }
        ];
        const edges: Edge[] = [];

        let executionResult;
        await act(async () => {
            executionResult = await result.current.runScenario(nodes, edges);
        });

        expect(executionResult).toEqual(mockResult);
        expect(globalThis.fetch).toHaveBeenCalledWith('http://localhost:8989/run-scenario', expect.any(Object));
        expect(result.current.isRunning).toBe(false);
    });

    it('handles fetch error', async () => {
        (globalThis.fetch as Mock).mockRejectedValue(new Error('Network error'));

        const { result } = renderHook(() => useScenarioRunner());

        const nodes: Node<NodeData>[] = [
            { id: '1', position: { x: 0, y: 0 }, data: { label: 'Node 1', operationId: 'Class.method', className: 'Class', functionName: 'method', parameters: [] } }
        ];
        const edges: Edge[] = [];

        let executionResult;
        await act(async () => {
            executionResult = await result.current.runScenario(nodes, edges);
        });

        expect(executionResult).toBeNull();
        expect(globalThis.alert).toHaveBeenCalled();
        expect(result.current.isRunning).toBe(false);
    });

    it('handles empty nodes', async () => {
        const { result } = renderHook(() => useScenarioRunner());

        let executionResult;
        await act(async () => {
            executionResult = await result.current.runScenario([], []);
        });

        expect(executionResult).toBeNull();
        expect(globalThis.fetch).not.toHaveBeenCalled();
    });
});

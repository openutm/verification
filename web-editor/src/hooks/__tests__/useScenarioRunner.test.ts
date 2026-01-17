import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach, type Mock } from 'vitest';
import { useScenarioRunner } from '../useScenarioRunner';
import type { Node, Edge } from '@xyflow/react';
import type { NodeData, ScenarioConfig } from '../../types/scenario';

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
            executionResult = await result.current.runScenario(nodes, edges, 'Test Scenario');
        });

        const expectedResult = {
            results: [{
                id: '1',
                status: 'success',
                result: mockResult,
                error: undefined
            }],
            status: 'completed',
            duration: 0
        };

        expect(executionResult).toEqual(expectedResult);
        expect(globalThis.fetch).toHaveBeenCalledWith('/session/reset', expect.any(Object));
        expect(globalThis.fetch).toHaveBeenCalledWith('/api/step', expect.any(Object));
        expect(result.current.isRunning).toBe(false);
    });

    it('runs scenario with config', async () => {
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
        const config: ScenarioConfig = {
            flight_blender: {
                url: "http://localhost:8000",
                auth: { type: "none", audience: "test", scopes: [] }
            },
            data_files: {},
            air_traffic_simulator_settings: {}
        };

        await act(async () => {
            await result.current.runScenario(nodes, edges, 'Test Scenario', undefined, undefined, config);
        });

        expect(globalThis.fetch).toHaveBeenCalledWith('/session/reset', expect.objectContaining({
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        }));
        const resetCall = (globalThis.fetch as Mock).mock.calls.find(call => call[0] === '/session/reset');
        if (resetCall) {
            const body = JSON.parse(resetCall[1].body);
            expect(body.config).toEqual(config);
        }
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
            executionResult = await result.current.runScenario(nodes, edges, 'Test Scenario');
        });

        expect(executionResult).toBeNull();
        expect(globalThis.alert).toHaveBeenCalled();
        expect(result.current.isRunning).toBe(false);
    });

    it('handles empty nodes', async () => {
        const { result } = renderHook(() => useScenarioRunner());

        let executionResult;
        await act(async () => {
            executionResult = await result.current.runScenario([], [], 'Test Scenario');
        });

        expect(executionResult).toBeNull();
        expect(globalThis.fetch).not.toHaveBeenCalled();
    });
});

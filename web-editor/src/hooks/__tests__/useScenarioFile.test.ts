import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { useScenarioFile } from '../useScenarioFile';
import type { Node, Edge } from '@xyflow/react';
import type { NodeData } from '../../types/scenario';

describe('useScenarioFile', () => {
    const mockNodes: Node<NodeData>[] = [
        { id: '1', position: { x: 0, y: 0 }, data: { label: 'Node 1' } }
    ];
    const mockEdges: Edge[] = [];
    const mockSetCurrentScenarioName = vi.fn();

    beforeEach(() => {
        globalThis.fetch = vi.fn();
        globalThis.prompt = vi.fn();
        globalThis.alert = vi.fn();
        mockSetCurrentScenarioName.mockClear();
    });

    afterEach(() => {
        vi.restoreAllMocks();
    });

    it('saves scenario to server successfully', async () => {
        const { result } = renderHook(() => useScenarioFile(mockNodes, mockEdges, [], null, mockSetCurrentScenarioName, ""));

        vi.mocked(globalThis.prompt).mockReturnValue('test_scenario');
        vi.mocked(globalThis.fetch).mockResolvedValue({
            ok: true,
            json: async () => ({ message: 'Saved' }),
        } as Response);

        await act(async () => {
            await result.current.handleSaveToServer();
        });

        expect(globalThis.prompt).toHaveBeenCalled();
        expect(globalThis.fetch).toHaveBeenCalledWith('/api/scenarios/test_scenario', expect.objectContaining({
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
        }));
        expect(globalThis.alert).toHaveBeenCalledWith('Saved');
        expect(mockSetCurrentScenarioName).toHaveBeenCalledWith('test_scenario');
    });

    it('handles save error', async () => {
        const { result } = renderHook(() => useScenarioFile(mockNodes, mockEdges, [], null, mockSetCurrentScenarioName, ""));

        vi.mocked(globalThis.prompt).mockReturnValue('test_scenario');
        vi.mocked(globalThis.fetch).mockResolvedValue({
            ok: false,
            statusText: 'Internal Server Error',
        } as Response);

        await act(async () => {
            await result.current.handleSaveToServer();
        });

        expect(globalThis.alert).toHaveBeenCalledWith('Failed to save scenario to server.');
    });

    it('does nothing if prompt is cancelled', async () => {
        const { result } = renderHook(() => useScenarioFile(mockNodes, mockEdges, [], null, mockSetCurrentScenarioName, ""));

        vi.mocked(globalThis.prompt).mockReturnValue(null);

        await act(async () => {
            await result.current.handleSaveToServer();
        });

        expect(globalThis.fetch).not.toHaveBeenCalled();
    });

    it('uses existing scenario name if provided', async () => {
        const { result } = renderHook(() => useScenarioFile(mockNodes, mockEdges, [], 'existing_scenario', mockSetCurrentScenarioName, ""));

        vi.mocked(globalThis.fetch).mockResolvedValue({
            ok: true,
            json: async () => ({ message: 'Saved' }),
        } as Response);

        await act(async () => {
            await result.current.handleSaveToServer();
        });

        expect(globalThis.prompt).not.toHaveBeenCalled();
        expect(globalThis.fetch).toHaveBeenCalledWith('/api/scenarios/existing_scenario', expect.objectContaining({
            method: 'POST',
        }));
        expect(mockSetCurrentScenarioName).toHaveBeenCalledWith('existing_scenario');
    });
});

import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { useScenarioFile } from '../useScenarioFile';
import type { Node, Edge, ReactFlowInstance } from '@xyflow/react';
import type { NodeData } from '../../types/scenario';

describe('useScenarioFile', () => {
    const mockNodes: Node<NodeData>[] = [
        { id: '1', position: { x: 0, y: 0 }, data: { label: 'Node 1' } }
    ];
    const mockEdges: Edge[] = [];
    const setNodes = vi.fn();
    const setEdges = vi.fn();
    const mockReactFlowInstance = {
        getViewport: vi.fn().mockReturnValue({ x: 0, y: 0, zoom: 1 }),
    } as unknown as ReactFlowInstance<Node<NodeData>, Edge>;

    beforeEach(() => {
        globalThis.URL.createObjectURL = vi.fn();
        globalThis.URL.revokeObjectURL = vi.fn();
    });

    afterEach(() => {
        vi.restoreAllMocks();
    });

    it('exports JSON correctly', () => {
        const { result } = renderHook(() => useScenarioFile(mockNodes, mockEdges, setNodes, setEdges, mockReactFlowInstance));

        // Mock document.createElement and click
        const mockLink = {
            href: '',
            download: '',
            click: vi.fn(),
            remove: vi.fn(),
        };
        const createElementSpy = vi.spyOn(document, 'createElement').mockReturnValue(mockLink as unknown as HTMLAnchorElement);
        const appendChildSpy = vi.spyOn(document.body, 'appendChild').mockImplementation(() => mockLink as unknown as HTMLAnchorElement);

        act(() => {
            result.current.handleExportJSON();
        });

        expect(createElementSpy).toHaveBeenCalledWith('a');
        expect(appendChildSpy).toHaveBeenCalled();
        expect(mockLink.click).toHaveBeenCalled();
        expect(mockLink.remove).toHaveBeenCalled();
        expect(globalThis.URL.createObjectURL).toHaveBeenCalled();
    });

    it('loads JSON correctly', async () => {
        const { result } = renderHook(() => useScenarioFile(mockNodes, mockEdges, setNodes, setEdges, mockReactFlowInstance));

        const mockInput = {
            click: vi.fn(),
        };

        const fileInputRef = result.current.fileInputRef;
        // eslint-disable-next-line @typescript-eslint/ban-ts-comment
        // @ts-expect-error
        fileInputRef.current = mockInput;

        act(() => {
            result.current.handleLoadJSON();
        });

        expect(mockInput.click).toHaveBeenCalled();
    });

    it('handles file change', async () => {
        const { result } = renderHook(() => useScenarioFile(mockNodes, mockEdges, setNodes, setEdges, mockReactFlowInstance));

        const fileContent = JSON.stringify({
            nodes: [{ id: '2', position: { x: 10, y: 10 }, data: { label: 'Node 2' } }],
            edges: []
        });
        const file = new File([fileContent], 'scenario.json', { type: 'application/json' });
        // Mock text() method which might be missing in jsdom/node File implementation
        file.text = vi.fn().mockResolvedValue(fileContent);

        const event = {
            target: {
                files: [file]
            }
        } as unknown as React.ChangeEvent<HTMLInputElement>;

        await act(async () => {
            await result.current.handleFileChange(event);
        });

        expect(setNodes).toHaveBeenCalledWith(expect.arrayContaining([
            expect.objectContaining({ id: '2' })
        ]));
        expect(setEdges).toHaveBeenCalledWith([]);
    });
});

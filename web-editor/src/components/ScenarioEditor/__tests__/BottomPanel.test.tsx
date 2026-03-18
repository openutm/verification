import { render, screen, fireEvent, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { BottomPanel } from '../BottomPanel';
import type { Node } from '@xyflow/react';
import type { NodeData } from '../../../types/scenario';

vi.mock('../../../hooks/useBottomPanelResize', () => ({
    useBottomPanelResize: () => ({
        panelHeight: 300,
        isResizing: false,
        startResizing: vi.fn(),
    }),
}));

const makeNode = (overrides: Partial<NodeData> = {}): Node<NodeData> => ({
    id: '1',
    position: { x: 0, y: 0 },
    data: {
        label: 'Test Step',
        status: 'success',
        parameters: [],
        ...overrides,
    },
});

describe('BottomPanel', () => {
    let writeTextMock: ReturnType<typeof vi.fn>;

    beforeEach(() => {
        vi.useFakeTimers();
        writeTextMock = vi.fn().mockResolvedValue(undefined);
        Object.assign(navigator, {
            clipboard: { writeText: writeTextMock },
        });
    });

    afterEach(() => {
        vi.useRealTimers();
        vi.restoreAllMocks();
    });

    it('returns null when selectedNode is null', () => {
        const { container } = render(<BottomPanel selectedNode={null} onClose={vi.fn()} />);
        expect(container.innerHTML).toBe('');
    });

    it('shows copy button when output data exists', () => {
        const node = makeNode({ result: { foo: 'bar' } });
        render(<BottomPanel selectedNode={node} onClose={vi.fn()} />);
        expect(screen.getByLabelText('Copy to clipboard')).toBeInTheDocument();
    });

    it('hides copy button when no result on output tab', () => {
        const node = makeNode({ result: undefined });
        render(<BottomPanel selectedNode={node} onClose={vi.fn()} />);
        expect(screen.queryByLabelText('Copy to clipboard')).not.toBeInTheDocument();
    });

    it('shows copy button for falsy but defined result (e.g. 0)', () => {
        const node = makeNode({ result: 0 });
        render(<BottomPanel selectedNode={node} onClose={vi.fn()} />);
        expect(screen.getByLabelText('Copy to clipboard')).toBeInTheDocument();
    });

    it('copies output JSON to clipboard', async () => {
        const node = makeNode({ result: { key: 'value' } });
        render(<BottomPanel selectedNode={node} onClose={vi.fn()} />);

        await act(async () => {
            fireEvent.click(screen.getByLabelText('Copy to clipboard'));
        });

        expect(writeTextMock).toHaveBeenCalledWith(JSON.stringify({ key: 'value' }, null, 2));
    });

    it('copies filtered logs to clipboard on logs tab', async () => {
        const node = makeNode({
            result: {
                logs: [
                    '12:00 | INFO | info message',
                    '12:01 | ERROR | error message',
                ],
            },
        });
        render(<BottomPanel selectedNode={node} onClose={vi.fn()} />);

        fireEvent.click(screen.getByText('Logs (2)'));

        // Filter to ERROR only
        const select = screen.getByDisplayValue('All Levels');
        fireEvent.change(select, { target: { value: 'ERROR' } });

        await act(async () => {
            fireEvent.click(screen.getByLabelText('Copy to clipboard'));
        });

        expect(writeTextMock).toHaveBeenCalledWith('12:01 | ERROR | error message');
    });

    it('shows "Copied!" feedback and resets after 2 seconds', async () => {
        const node = makeNode({ result: { data: 1 } });
        render(<BottomPanel selectedNode={node} onClose={vi.fn()} />);

        await act(async () => {
            fireEvent.click(screen.getByLabelText('Copy to clipboard'));
        });

        expect(screen.getByText('Copied!')).toBeInTheDocument();

        act(() => {
            vi.advanceTimersByTime(2000);
        });

        expect(screen.queryByText('Copied!')).not.toBeInTheDocument();
        expect(screen.getByText('Copy')).toBeInTheDocument();
    });
});

import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { CustomNode } from '../CustomNode';
import { ReactFlowProvider } from '@xyflow/react';
import type { NodeData } from '../../../types/scenario';

describe('CustomNode', () => {
    const mockData: NodeData = {
        label: 'Test Node',
        status: 'success',
        result: { success: true },
        onShowResult: vi.fn(),
    };

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const defaultProps: any = {
        id: '1',
        data: mockData,
        type: 'custom',
        selected: false,
        zIndex: 0,
        isConnectable: true,
        positionAbsoluteX: 0,
        positionAbsoluteY: 0,
        dragging: false,
        dragHandle: undefined,
        parentId: undefined,
        width: 100,
        height: 50,
        sourcePosition: undefined,
        targetPosition: undefined,
    };

    const wrapper = ({ children }: { children: React.ReactNode }) => (
        <ReactFlowProvider>{children}</ReactFlowProvider>
    );

    it('renders label', () => {
        render(<CustomNode {...defaultProps} />, { wrapper });
        expect(screen.getByText('Test Node')).toBeInTheDocument();
    });

    it('renders success status icon', () => {
        render(<CustomNode {...defaultProps} />, { wrapper });
        // Check for CheckCircle icon (or button containing it)
        const button = screen.getByTitle('Click to view results');
        expect(button).toBeInTheDocument();
    });

    it('calls onShowResult when status icon is clicked', () => {
        render(<CustomNode {...defaultProps} />, { wrapper });
        const button = screen.getByTitle('Click to view results');
        fireEvent.click(button);
        expect(mockData.onShowResult).toHaveBeenCalledWith(mockData.result);
    });

    it('renders failure status', () => {
        const failureProps = {
            ...defaultProps,
            data: { ...mockData, status: 'failure' as const }
        };
        render(<CustomNode {...failureProps} />, { wrapper });
        const button = screen.getByTitle('Click to view results');
        expect(button).toBeInTheDocument();
        // We could check for color or specific icon if we could query by icon
    });

    it('applies selected style', () => {
        const selectedProps = {
            ...defaultProps,
            selected: true
        };
        const { container } = render(<CustomNode {...selectedProps} />, { wrapper });
        const nodeElement = container.firstChild as HTMLElement;
        expect(nodeElement.style.borderColor).toBe('var(--accent-primary)');
        expect(nodeElement.style.boxShadow).toBe('0 0 0 1px var(--accent-primary)');
    });
});

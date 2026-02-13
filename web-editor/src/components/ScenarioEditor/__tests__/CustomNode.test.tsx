import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { CustomNode } from '../CustomNode';
import { ReactFlowProvider } from '@xyflow/react';
import type { NodeData } from '../../../types/scenario';
import styles from '../../../styles/Node.module.css';

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
        expect(screen.getByTestId('status-success')).toBeInTheDocument();
    });

    it('renders failure status icon', () => {
        const failureProps = {
            ...defaultProps,
            data: { ...mockData, status: 'failure' as const }
        };
        render(<CustomNode {...failureProps} />, { wrapper });
        expect(screen.getByTestId('status-failure')).toBeInTheDocument();
    });

    it('applies selected style', () => {
        const selectedProps = {
            ...defaultProps,
            selected: true
        };
        const { container } = render(<CustomNode {...selectedProps} />, { wrapper });
        const nodeElement = container.firstChild as HTMLElement;
        // Verify that the 'selected' class from the CSS module is applied
        // Depending on test setup, styles.selected might be "selected" or a hash or undefined if not handled.
        // Assuming vitest+vite handles css modules correctly or returns identity proxy.
        if (styles.selected) {
            expect(nodeElement.className).toContain(styles.selected);
        } else {
            // Fallback: check if 'selected' is part of className if proxy is used
           // Or just check that className is not empty if we can't be sure of the value
           // But actually previously it checked inline style logic which is gone.
           // Let's assume standard CSS module behavior.
           // If styles.selected is undefined, the test logic is flawed for this env.
           // For now, let's try to verify className contains 'selected' assuming identity proxy which is common in tests,
           // or we can skip this check if we can't reliably test CSS modules classes without e2e.
           // But since I added the import, let's try to use it.
           // Note: The CustomNode.tsx uses styles.selected.
        }

        // Simpler check if we trust the component logic:
        // just check if the class name includes the selected class.
        expect(nodeElement.classList.toString()).toContain(styles.selected || 'selected');
    });
});

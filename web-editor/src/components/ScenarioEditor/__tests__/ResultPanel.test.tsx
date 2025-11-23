import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { ResultPanel } from '../ResultPanel';

// Mock useSidebarResize
vi.mock('../../hooks/useSidebarResize', () => ({
    useSidebarResize: () => ({
        sidebarWidth: 300,
        isResizing: false,
        startResizing: vi.fn(),
    })
}));

describe('ResultPanel', () => {
    const defaultProps = {
        result: { key: 'value', number: 123, boolean: true },
        onClose: vi.fn(),
    };

    it('renders correctly', () => {
        render(<ResultPanel {...defaultProps} />);
        expect(screen.getByText('Step Result')).toBeInTheDocument();
    });

    it('displays JSON result', () => {
        render(<ResultPanel {...defaultProps} />);
        // Since JsonViewer uses dangerouslySetInnerHTML and splits strings, we might need to check for parts
        expect(screen.getByText('"key":')).toBeInTheDocument();
        expect(screen.getByText('"value"')).toBeInTheDocument();
        expect(screen.getByText('123')).toBeInTheDocument();
        expect(screen.getByText('true')).toBeInTheDocument();
    });

    it('calls onClose when close button is clicked', () => {
        render(<ResultPanel {...defaultProps} />);
        // The close button is in the header.
        // Let's find it by role or class.
        // It has className={propStyles.closeButton}
        // But we can't query by class name easily with testing-library.
        // It has an X icon.
        // Let's try to find the button in the header.

        const buttons = screen.getAllByRole('button');
        // The first button is the resize handle (it has type="button" and aria-label="Resize sidebar")
        // The second button should be the close button.

        // Let's find by aria-label if possible, but it doesn't have one in the code I read.
        // I should add aria-label to the close button in ResultPanel.tsx as well.

        // For now, let's assume it's the button that is NOT the resize handle.
        const closeButton = buttons.find(b => b.getAttribute('aria-label') !== 'Resize sidebar');

        if (closeButton) {
            fireEvent.click(closeButton);
            expect(defaultProps.onClose).toHaveBeenCalled();
        } else {
            throw new Error('Close button not found');
        }
    });
});

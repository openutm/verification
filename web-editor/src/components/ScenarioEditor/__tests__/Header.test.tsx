import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { Header } from '../Header';

describe('Header', () => {
    const defaultProps = {
        theme: 'light' as const,
        toggleTheme: vi.fn(),
        onLayout: vi.fn(),
        onClear: vi.fn(),
        onSave: vi.fn(),
        onRun: vi.fn(),
        isRunning: false,
    };

    it('renders correctly', () => {
        render(<Header {...defaultProps} />);
        expect(screen.getByText('OpenUTM Scenario Designer')).toBeInTheDocument();
    });

    it('calls toggleTheme when theme button is clicked', () => {
        render(<Header {...defaultProps} />);
        const themeButton = screen.getByTitle('Switch to dark mode');
        fireEvent.click(themeButton);
        expect(defaultProps.toggleTheme).toHaveBeenCalled();
    });

    it('calls onLayout when Auto Layout button is clicked', () => {
        render(<Header {...defaultProps} />);
        const layoutButton = screen.getByText('Auto Layout');
        fireEvent.click(layoutButton);
        expect(defaultProps.onLayout).toHaveBeenCalled();
    });

    it('calls onClear when Clear button is clicked', () => {
        render(<Header {...defaultProps} />);
        const clearButton = screen.getByText('Clear');
        fireEvent.click(clearButton);
        expect(defaultProps.onClear).toHaveBeenCalled();
    });

    it('calls onSave when Save button is clicked', () => {
        render(<Header {...defaultProps} />);
        const saveButton = screen.getByText('Save');
        fireEvent.click(saveButton);
        expect(defaultProps.onSave).toHaveBeenCalled();
    });

    it('calls onRun when Run button is clicked', () => {
        render(<Header {...defaultProps} />);
        const runButton = screen.getByText('Run Scenario');
        fireEvent.click(runButton);
        expect(defaultProps.onRun).toHaveBeenCalled();
    });

    it('shows loading state when isRunning is true', () => {
        render(<Header {...defaultProps} isRunning={true} />);
        const runButton = screen.getByText('Run Scenario');
        expect(runButton).toBeDisabled();
    });
});

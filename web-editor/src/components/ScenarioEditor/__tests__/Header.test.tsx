import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { Header } from '../Header';
import React from 'react';

describe('Header', () => {
    const defaultProps = {
        theme: 'light' as const,
        toggleTheme: vi.fn(),
        onLayout: vi.fn(),
        onClear: vi.fn(),
        onLoad: vi.fn(),
        onExport: vi.fn(),
        onRun: vi.fn(),
        isRunning: false,
        fileInputRef: React.createRef<HTMLInputElement>() as React.RefObject<HTMLInputElement>,
        onFileChange: vi.fn(),
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

    it('calls onLoad when Load Scenario button is clicked', () => {
        render(<Header {...defaultProps} />);
        const loadButton = screen.getByText('Load Scenario');
        fireEvent.click(loadButton);
        expect(defaultProps.onLoad).toHaveBeenCalled();
    });

    it('calls onExport when Save Scenario button is clicked', () => {
        render(<Header {...defaultProps} />);
        const exportButton = screen.getByText('Export');
        fireEvent.click(exportButton);
        expect(defaultProps.onExport).toHaveBeenCalled();
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

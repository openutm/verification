import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { Toolbox } from '../Toolbox';

// Mock the operations data
vi.mock('../../../data/operations.json', () => ({
    default: [
        {
            id: 'op1',
            name: 'Operation 1',
            className: 'ClassA',
            functionName: 'op1',
            description: 'Docstring A',
            parameters: []
        },
        {
            id: 'op2',
            name: 'Operation 2',
            className: 'ClassA',
            functionName: 'op2',
            description: 'Docstring B',
            parameters: []
        },
        {
            id: 'op3',
            name: 'Operation 3',
            className: 'ClassB',
            functionName: 'op3',
            description: 'Docstring C',
            parameters: []
        }
    ]
}));

describe('Toolbox', () => {
    it('renders correctly', () => {
        render(<Toolbox />);
        expect(screen.getByText('ClassA')).toBeInTheDocument();
        expect(screen.getByText('ClassB')).toBeInTheDocument();
    });

    it('displays operations under groups', () => {
        render(<Toolbox />);
        expect(screen.getByText('Operation 1')).toBeInTheDocument();
        expect(screen.getByText('Operation 2')).toBeInTheDocument();
        expect(screen.getByText('Operation 3')).toBeInTheDocument();
    });

    it('collapses and expands groups', () => {
        render(<Toolbox />);
        const groupHeader = screen.getByText('ClassA');

        // Initially expanded
        expect(screen.getByText('Operation 1')).toBeVisible();

        // Click to collapse
        fireEvent.click(groupHeader);
        expect(screen.queryByText('Operation 1')).not.toBeInTheDocument();

        // Click to expand
        fireEvent.click(groupHeader);
        expect(screen.getByText('Operation 1')).toBeVisible();
    });

    it('sets data transfer on drag start', () => {
        render(<Toolbox />);
        const operationItem = screen.getByText('Operation 1');

        const dataTransfer = {
            setData: vi.fn(),
        };

        fireEvent.dragStart(operationItem, { dataTransfer });

        expect(dataTransfer.setData).toHaveBeenCalledWith('application/reactflow', 'Operation 1');
        expect(dataTransfer.setData).toHaveBeenCalledWith('application/reactflow/id', 'op1');
    });
});

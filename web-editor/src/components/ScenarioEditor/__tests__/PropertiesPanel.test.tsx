import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { PropertiesPanel } from '../PropertiesPanel';
import type { Node } from '@xyflow/react';
import type { NodeData } from '../../../types/scenario';

describe('PropertiesPanel', () => {
    const mockNode: Node<NodeData> = {
        id: '1',
        position: { x: 0, y: 0 },
        data: {
            label: 'Test Node',
            description: 'Test docstring',
            parameters: [
                { name: 'arg1', type: 'string', default: 'value1' },
                { name: 'arg2', type: 'int', default: 123 }
            ]
        }
    };

    const defaultProps = {
        selectedNode: mockNode,
        connectedNodes: [],
        allNodes: [],
        onClose: vi.fn(),
        onUpdateParameter: vi.fn(),
        onUpdateRunInBackground: vi.fn(),
    };

    it('renders correctly', () => {
        render(<PropertiesPanel {...defaultProps} />);
        expect(screen.getByText('Test Node')).toBeInTheDocument();
        expect(screen.getByText('Test docstring')).toBeInTheDocument();
    });

    it('calls onClose when close button is clicked', () => {
        render(<PropertiesPanel {...defaultProps} />);
        const buttons = screen.getAllByRole('button');
        fireEvent.click(buttons[0]);
        expect(defaultProps.onClose).toHaveBeenCalled();
    });

    it('displays parameters', () => {
        render(<PropertiesPanel {...defaultProps} />);
        expect(screen.getByText('arg1')).toBeInTheDocument();
        expect(screen.getByDisplayValue('value1')).toBeInTheDocument();
        expect(screen.getByText('arg2')).toBeInTheDocument();
        expect(screen.getByDisplayValue('123')).toBeInTheDocument();
    });

    it('calls onUpdateParameter when input changes', () => {
        render(<PropertiesPanel {...defaultProps} />);
        const input = screen.getByDisplayValue('value1');
        fireEvent.change(input, { target: { value: 'newValue' } });
        expect(defaultProps.onUpdateParameter).toHaveBeenCalledWith('1', 'arg1', 'newValue');
    });
});

import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import ScenarioEditor from '../ScenarioEditor';
import { ReactFlowProvider } from '@xyflow/react';

// Mock child components to simplify testing
vi.mock('../ScenarioEditor/Header', () => ({
    Header: () => <div data-testid="header">Header</div>
}));
vi.mock('../ScenarioEditor/Toolbox', () => ({
    Toolbox: () => <div data-testid="toolbox">Toolbox</div>
}));
vi.mock('../ScenarioEditor/PropertiesPanel', () => ({
    PropertiesPanel: () => <div data-testid="properties-panel">PropertiesPanel</div>
}));
vi.mock('../ScenarioEditor/ResultPanel', () => ({
    ResultPanel: () => <div data-testid="result-panel">ResultPanel</div>
}));

// Mock hooks
vi.mock('../hooks/useScenarioGraph', () => ({
    useScenarioGraph: () => ({
        nodes: [],
        edges: [],
        setNodes: vi.fn(),
        setEdges: vi.fn(),
        onNodesChange: vi.fn(),
        onEdgesChange: vi.fn(),
        onConnect: vi.fn(),
        onDrop: vi.fn(),
        onLayout: vi.fn(),
        clearGraph: vi.fn(),
        reactFlowInstance: {},
        setReactFlowInstance: vi.fn(),
    })
}));

vi.mock('../hooks/useScenarioRunner', () => ({
    useScenarioRunner: () => ({
        isRunning: false,
        runScenario: vi.fn(),
    })
}));

vi.mock('../hooks/useScenarioFile', () => ({
    useScenarioFile: () => ({
        handleExportJSON: vi.fn(),
        handleLoadJSON: vi.fn(),
        handleFileChange: vi.fn(),
        fileInputRef: { current: null },
    })
}));

// Mock ReactFlow
vi.mock('@xyflow/react', async () => {
    const actual = await vi.importActual('@xyflow/react');
    return {
        ...actual,
        ReactFlow: ({ children }: { children: React.ReactNode }) => <div data-testid="react-flow">{children}</div>,
        Controls: () => <div data-testid="controls">Controls</div>,
        Background: () => <div data-testid="background">Background</div>,
        Panel: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
    };
});

describe('ScenarioEditor', () => {
    it('renders correctly', () => {
        render(
            <ReactFlowProvider>
                <ScenarioEditor />
            </ReactFlowProvider>
        );

        expect(screen.getByTestId('header')).toBeInTheDocument();
        expect(screen.getByTestId('toolbox')).toBeInTheDocument();
        expect(screen.getByTestId('react-flow')).toBeInTheDocument();
    });
});

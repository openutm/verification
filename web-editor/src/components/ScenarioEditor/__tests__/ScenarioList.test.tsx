import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { ScenarioList } from '../ScenarioList';

// Mock convertYamlToGraph so we don't need real operations
vi.mock('../../../utils/scenarioConversion', () => ({
    convertYamlToGraph: vi.fn(() => ({ nodes: [], edges: [], config: undefined })),
}));

const mockOnLoadScenario = vi.fn();
const mockOnSelectScenario = vi.fn();

const defaultProps = {
    onLoadScenario: mockOnLoadScenario,
    operations: [],
    currentScenarioName: null,
    onSelectScenario: mockOnSelectScenario,
};

function mockFetchResponses(scenarios: string[], suites: Record<string, string[]> | null) {
    vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
        const urlStr = typeof url === 'string' ? url : url.toString();
        if (urlStr === '/api/scenarios') {
            return Promise.resolve({
                json: () => Promise.resolve(scenarios),
            } as Response);
        }
        if (urlStr === '/api/suites') {
            if (suites === null) {
                return Promise.reject(new Error('Network error'));
            }
            return Promise.resolve({
                json: () => Promise.resolve(suites),
            } as Response);
        }
        // For individual scenario loads
        return Promise.resolve({
            json: () => Promise.resolve({ name: 'test', steps: [] }),
        } as Response);
    });
}

describe('ScenarioList', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    afterEach(() => {
        vi.restoreAllMocks();
    });

    it('renders grouped suites from a suite map', async () => {
        mockFetchResponses(
            ['scenario_a', 'scenario_b', 'scenario_c'],
            {
                alpha_suite: ['scenario_a', 'scenario_b'],
                beta_suite: ['scenario_c'],
            },
        );

        render(<ScenarioList {...defaultProps} />);

        await waitFor(() => {
            expect(screen.getByText('Alpha Suite')).toBeInTheDocument();
            expect(screen.getByText('Beta Suite')).toBeInTheDocument();
        });

        // Scenarios should be visible under their groups
        expect(screen.getByText('Scenario A')).toBeInTheDocument();
        expect(screen.getByText('Scenario B')).toBeInTheDocument();
        expect(screen.getByText('Scenario C')).toBeInTheDocument();
    });

    it('renders ungrouped scenarios under "Other Scenarios"', async () => {
        mockFetchResponses(
            ['grouped_one', 'orphan_scenario'],
            {
                my_suite: ['grouped_one'],
            },
        );

        render(<ScenarioList {...defaultProps} />);

        await waitFor(() => {
            expect(screen.getByText('My Suite')).toBeInTheDocument();
            expect(screen.getByText('Other Scenarios')).toBeInTheDocument();
        });

        expect(screen.getByText('Grouped One')).toBeInTheDocument();
        expect(screen.getByText('Orphan Scenario')).toBeInTheDocument();
    });

    it('falls back to flat list when /api/suites fails', async () => {
        mockFetchResponses(['scenario_x', 'scenario_y'], null);

        render(<ScenarioList {...defaultProps} />);

        await waitFor(() => {
            expect(screen.getByText('Scenario X')).toBeInTheDocument();
            expect(screen.getByText('Scenario Y')).toBeInTheDocument();
        });

        // No suite group headers should appear
        expect(screen.queryByRole('button', { name: /suite/i })).not.toBeInTheDocument();
    });

    it('toggles collapse/expand on suite header click', async () => {
        mockFetchResponses(
            ['scenario_a', 'scenario_b'],
            { test_suite: ['scenario_a', 'scenario_b'] },
        );

        render(<ScenarioList {...defaultProps} />);

        await waitFor(() => {
            expect(screen.getByText('Test Suite')).toBeInTheDocument();
        });

        // Initially expanded
        expect(screen.getByText('Scenario A')).toBeVisible();
        const header = screen.getByText('Test Suite').closest('button')!;
        expect(header).toHaveAttribute('aria-expanded', 'true');

        // Click to collapse
        fireEvent.click(header);
        expect(screen.queryByText('Scenario A')).not.toBeInTheDocument();
        expect(header).toHaveAttribute('aria-expanded', 'false');

        // Click to expand again
        fireEvent.click(header);
        expect(screen.getByText('Scenario A')).toBeVisible();
        expect(header).toHaveAttribute('aria-expanded', 'true');
    });

    it('sorts suite names deterministically', async () => {
        mockFetchResponses(
            ['s1', 's2', 's3'],
            {
                zulu_suite: ['s1'],
                alpha_suite: ['s2'],
                mike_suite: ['s3'],
            },
        );

        render(<ScenarioList {...defaultProps} />);

        await waitFor(() => {
            expect(screen.getByText('Alpha Suite')).toBeInTheDocument();
        });

        const headers = screen.getAllByRole('button').filter(
            (btn) => btn.classList.contains('groupHeader') || btn.getAttribute('aria-expanded') !== null,
        );
        const labels = headers.map((h) => h.textContent?.replace(/\d+$/, '').trim());
        expect(labels).toEqual(['Alpha Suite', 'Mike Suite', 'Zulu Suite']);
    });

    it('shows "No scenarios found" when there are none', async () => {
        mockFetchResponses([], {});

        render(<ScenarioList {...defaultProps} />);

        await waitFor(() => {
            expect(screen.getByText('No scenarios found')).toBeInTheDocument();
        });
    });
});

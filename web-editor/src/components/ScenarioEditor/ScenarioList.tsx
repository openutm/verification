import { useState, useEffect, useMemo } from 'react';
import { FileText, MessageCircleQuestionMark, ChevronDown, ChevronRight, FolderOpen } from 'lucide-react';
import styles from '../../styles/Toolbox.module.css';
import type { Operation, ScenarioDefinition, NodeData, ScenarioConfig } from '../../types/scenario';
import type { Node, Edge } from '@xyflow/react';
import { convertYamlToGraph } from '../../utils/scenarioConversion';

interface ScenarioListProps {
    onLoadScenario: (nodes: Node<NodeData>[], edges: Edge[], config?: ScenarioConfig, groups?: ScenarioDefinition['groups'], description?: string) => void;
    operations: Operation[];
    currentScenarioName: string | null;
    onSelectScenario: (name: string) => void;
    refreshKey?: number;
}

type SuiteMap = Record<string, string[]>;

export const ScenarioList = ({ onLoadScenario, operations, currentScenarioName, onSelectScenario, refreshKey = 0 }: ScenarioListProps) => {
    const [scenarios, setScenarios] = useState<string[]>([]);
    const [suites, setSuites] = useState<SuiteMap>({});
    const [loading, setLoading] = useState(false);
    const [activeSuite, setActiveSuite] = useState<string | null>(null);
    const [filterText, setFilterText] = useState('');

    useEffect(() => {
        const fetchScenarios = async (): Promise<string[]> => {
            const res = await fetch('/api/scenarios');
            if (!res.ok) return [];
            const data: unknown = await res.json();
            return Array.isArray(data) && data.every(item => typeof item === 'string') ? data : [];
        };

        const fetchSuites = async (): Promise<SuiteMap> => {
            const res = await fetch('/api/suites');
            if (!res.ok) return {};
            const data: unknown = await res.json();
            if (typeof data !== 'object' || data === null || Array.isArray(data)) return {};
            const result: SuiteMap = {};
            for (const [key, value] of Object.entries(data as Record<string, unknown>)) {
                if (Array.isArray(value) && value.every(item => typeof item === 'string')) {
                    result[key] = value;
                }
            }
            return result;
        };

        Promise.all([
            fetchScenarios(),
            fetchSuites().catch(() => ({} as SuiteMap)),
        ]).then(([scenarioList, suiteMap]) => {
            setScenarios(scenarioList.sort());
            setSuites(suiteMap);

            // Open the suite containing the currently loaded scenario, if any
            if (currentScenarioName) {
                const matchingSuite = Object.entries(suiteMap).find(([, items]) =>
                    items.includes(currentScenarioName)
                );
                if (matchingSuite) setActiveSuite(matchingSuite[0]);
            }
        }).catch(err => console.error('Failed to load scenarios:', err));
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [refreshKey]);

    const hasSuites = Object.keys(suites).length > 0;

    const folderGroups = useMemo(() => {
        const map: Record<string, string[]> = {};
        for (const scenario of scenarios) {
            const parts = scenario.split('/');
            const folder = parts.length > 1 ? parts.slice(0, -1).join('/') : '';
            if (!map[folder]) map[folder] = [];
            map[folder].push(scenario);
        }
        return Object.entries(map).sort(([a], [b]) => {
            if (a === '') return -1;
            if (b === '') return 1;
            return a.localeCompare(b);
        });
    }, [scenarios]);

    const groupedScenarios = useMemo(() => {
        const suiteNames = Object.keys(suites).sort((a, b) => a.localeCompare(b));
        const scenarioSet = new Set(scenarios);
        const assigned = new Set(suiteNames.flatMap(s => suites[s]));
        const ungrouped = scenarios.filter(s => !assigned.has(s));

        const groups: { suite: string; label: string; items: string[] }[] = [];
        for (const suite of suiteNames) {
            const items = suites[suite]
                .filter(name => scenarioSet.has(name))
                .slice()
                .sort((a, b) => a.localeCompare(b));
            if (items.length > 0) {
                groups.push({
                    suite,
                    label: suite.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
                    items,
                });
            }
        }
        if (ungrouped.length > 0) {
            groups.push({ suite: '__ungrouped__', label: 'Other Scenarios', items: ungrouped.sort() });
        }
        return groups;
    }, [scenarios, suites]);

    const handleLoad = async (filename: string) => {
        if (loading) return;
        setLoading(true);
        try {
            const res = await fetch(`/api/scenarios/${filename}`);
            const scenario: ScenarioDefinition = await res.json();
            const { nodes, edges, config } = convertYamlToGraph(scenario, operations);
            onLoadScenario(nodes, edges, config, scenario.groups, scenario.description);
            onSelectScenario(filename);
        } catch (err) {
            console.error('Failed to load scenario:', err);
            alert('Failed to load scenario');
        } finally {
            setLoading(false);
        }
    };

    const renderScenarioItem = (name: string, suiteLabel?: string) => {
        const displayName = name.split('/').pop() ?? name;
        const isActive = name === currentScenarioName;
        return (
            <button
                key={name}
                type="button"
                className={`${styles.listItem} ${isActive ? styles.listItemActive : ''}`}
                onClick={() => handleLoad(name)}
                title={name}
                disabled={loading}
                style={{ opacity: loading ? 0.5 : 1, cursor: loading ? 'not-allowed' : 'pointer' }}
            >
                <FileText size={14} style={{ marginTop: 2 }} color={isActive ? 'var(--accent-primary)' : '#8b949e'} />
                <div style={{ minWidth: 0 }}>
                    <div>{displayName.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}</div>
                    {suiteLabel && (
                        <div style={{ fontSize: '11px', color: 'var(--text-tertiary)', marginTop: '2px' }}>
                            {suiteLabel}
                        </div>
                    )}
                </div>
            </button>
        );
    };

    const filter = filterText.toLowerCase().trim();

    // When filter is active, show flat list across all groups with suite label
    const filteredItems = useMemo(() => {
        if (!filter) return null;
        const results: { name: string; suiteLabel: string }[] = [];
        if (hasSuites) {
            for (const { label, items } of groupedScenarios) {
                for (const name of items) {
                    const displayName = (name.split('/').pop() ?? name).replace(/_/g, ' ');
                    if (displayName.toLowerCase().includes(filter) || name.toLowerCase().includes(filter)) {
                        results.push({ name, suiteLabel: label });
                    }
                }
            }
        } else {
            for (const scenario of scenarios) {
                const displayName = (scenario.split('/').pop() ?? scenario).replace(/_/g, ' ');
                if (displayName.toLowerCase().includes(filter) || scenario.toLowerCase().includes(filter)) {
                    results.push({ name: scenario, suiteLabel: '' });
                }
            }
        }
        return results;
    }, [filter, hasSuites, groupedScenarios, scenarios]);

    return (
        <div>
            <div style={{ padding: '8px 8px 0' }}>
                <input
                    className={styles.searchInput}
                    type="text"
                    placeholder="Search scenarios…"
                    value={filterText}
                    onChange={e => setFilterText(e.target.value)}
                />
            </div>

            <div className={styles.groupContent} style={{ padding: '8px' }}>
                {!filter && (
                    <div style={{ color: '#666', fontSize: '12px', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <MessageCircleQuestionMark size={14} color="#666" />
                        {hasSuites ? 'Grouped by test suite' : 'Pre-built scenarios'}
                    </div>
                )}

                {filteredItems ? (
                    // Flat filtered list
                    filteredItems.length > 0
                        ? filteredItems.map(({ name, suiteLabel }) => renderScenarioItem(name, suiteLabel || undefined))
                        : <div style={{ padding: '8px', color: '#666', fontSize: '12px' }}>No matches</div>
                ) : hasSuites ? (
                    // Accordion grouped by suite
                    groupedScenarios.map(({ suite, label, items }) => {
                        const isOpen = activeSuite === suite;
                        return (
                            <div key={suite} style={{ marginBottom: '2px' }}>
                                <button
                                    type="button"
                                    className={styles.groupHeader}
                                    onClick={() => setActiveSuite(isOpen ? null : suite)}
                                    aria-expanded={isOpen}
                                    style={{ padding: '6px 4px', marginTop: 2, marginBottom: 2, background: 'none', border: 'none', width: '100%' }}
                                >
                                    {isOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                                    <FolderOpen size={14} />
                                    {label}
                                    <span style={{ marginLeft: 'auto', fontSize: '11px', fontWeight: 400, opacity: 0.7 }}>
                                        {items.length}
                                    </span>
                                </button>
                                {isOpen && (
                                    <div style={{ paddingLeft: '8px', display: 'flex', flexDirection: 'column', gap: '2px' }}>
                                        {items.map(name => renderScenarioItem(name))}
                                    </div>
                                )}
                            </div>
                        );
                    })
                ) : folderGroups.some(([folder]) => folder !== '') ? (
                    // Accordion grouped by folder
                    folderGroups.map(([folder, items]) => {
                        const key = `__folder__${folder}`;
                        const isOpen = activeSuite === key;
                        const label = folder === ''
                            ? 'Root'
                            : folder.replace(/\//g, ' / ').replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
                        return folder === '' ? (
                            <div key="root" style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                                {items.map(name => renderScenarioItem(name))}
                            </div>
                        ) : (
                            <div key={folder} style={{ marginBottom: '2px' }}>
                                <button
                                    type="button"
                                    className={styles.groupHeader}
                                    onClick={() => setActiveSuite(isOpen ? null : key)}
                                    aria-expanded={isOpen}
                                    style={{ padding: '6px 4px', marginTop: 2, marginBottom: 2, background: 'none', border: 'none', width: '100%' }}
                                >
                                    {isOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                                    <FolderOpen size={14} />
                                    {label}
                                    <span style={{ marginLeft: 'auto', fontSize: '11px', fontWeight: 400, opacity: 0.7 }}>
                                        {items.length}
                                    </span>
                                </button>
                                {isOpen && (
                                    <div style={{ paddingLeft: '8px', display: 'flex', flexDirection: 'column', gap: '2px' }}>
                                        {items.map(name => renderScenarioItem(name))}
                                    </div>
                                )}
                            </div>
                        );
                    })
                ) : (
                    // Flat list (no grouping)
                    scenarios.map(name => renderScenarioItem(name))
                )}

                {scenarios.length === 0 && !filter && (
                    <div style={{ padding: '8px', color: '#666', fontSize: '12px' }}>No scenarios found</div>
                )}
            </div>
        </div>
    );
};

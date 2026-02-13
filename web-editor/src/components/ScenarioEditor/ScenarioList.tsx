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
    const [collapsedSuites, setCollapsedSuites] = useState<Set<string>>(new Set());

    useEffect(() => {
        Promise.all([
            fetch('/api/scenarios').then(res => res.json()),
            fetch('/api/suites').then(res => res.json()).catch(() => ({})),
        ]).then(([scenarioList, suiteMap]: [string[], SuiteMap]) => {
            setScenarios(scenarioList.sort());
            setSuites(suiteMap);
        }).catch(err => console.error('Failed to load scenarios:', err));
    }, [refreshKey]);

    const hasSuites = Object.keys(suites).length > 0;

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

    const toggleSuite = (suite: string) => {
        setCollapsedSuites(prev => {
            const next = new Set(prev);
            if (next.has(suite)) next.delete(suite);
            else next.add(suite);
            return next;
        });
    };

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

    const renderScenarioItem = (name: string) => (
        <div
            key={name}
            className={styles.nodeItem}
            onClick={() => handleLoad(name)}
            role="button"
            tabIndex={0}
            title={name}
            style={{
                cursor: 'pointer',
                opacity: loading ? 0.5 : 1,
                borderColor: name === currentScenarioName ? 'var(--accent-primary)' : 'var(--border-color)',
                backgroundColor: name === currentScenarioName ? 'var(--bg-secondary)' : 'var(--bg-primary)'
            }}
        >
            <FileText size={16} color={name === currentScenarioName ? "var(--accent-primary)" : "#8b949e"} />
            <span>{name.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}</span>
        </div>
    );

    return (
        <div>
            <div className={styles.groupContent}>
                <div style={{ padding: '8px', color: '#666', fontSize: '12px', marginBottom: '8px' }}>
                    <MessageCircleQuestionMark size={16} style={{ marginRight: '8px', color: '#666' }} />
                    Pre-built scenarios grouped by test suite
                </div>

                {hasSuites ? (
                    groupedScenarios.map(({ suite, label, items }) => {
                        const isCollapsed = collapsedSuites.has(suite);
                        return (
                            <div key={suite} style={{ marginBottom: '4px' }}>
                                <button
                                    type="button"
                                    className={styles.groupHeader}
                                    onClick={() => toggleSuite(suite)}
                                    aria-expanded={!isCollapsed}
                                    style={{ padding: '6px 4px', marginTop: 4, marginBottom: 4, background: 'none', border: 'none', width: '100%' }}
                                >
                                    {isCollapsed ? <ChevronRight size={14} /> : <ChevronDown size={14} />}
                                    <FolderOpen size={14} />
                                    {label}
                                    <span style={{ marginLeft: 'auto', fontSize: '11px', fontWeight: 400, opacity: 0.7 }}>
                                        {items.length}
                                    </span>
                                </button>
                                {!isCollapsed && (
                                    <div style={{ paddingLeft: '8px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                                        {items.map(renderScenarioItem)}
                                    </div>
                                )}
                            </div>
                        );
                    })
                ) : (
                    scenarios.map(renderScenarioItem)
                )}

                {scenarios.length === 0 && (
                    <div style={{ padding: '8px', color: '#666', fontSize: '12px' }}>
                        No scenarios found
                    </div>
                )}
            </div>
        </div>
    );
};

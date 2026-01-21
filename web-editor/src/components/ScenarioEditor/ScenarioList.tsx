import { useState, useEffect } from 'react';
import { FileText } from 'lucide-react';
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

export const ScenarioList = ({ onLoadScenario, operations, currentScenarioName, onSelectScenario, refreshKey = 0 }: ScenarioListProps) => {
    const [scenarios, setScenarios] = useState<string[]>([]);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        fetch('/api/scenarios')
            .then(res => res.json())
            .then((data: string[]) => setScenarios(data.sort()))
            .catch(err => console.error('Failed to load scenarios:', err));
    }, [refreshKey]);

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

    return (
        <div>

            <div className={styles.groupContent}>
                {scenarios.map(name => (
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
                ))}
                {scenarios.length === 0 && (
                    <div style={{ padding: '8px', color: '#666', fontSize: '12px' }}>
                        No scenarios found
                    </div>
                )}
            </div>
        </div>
    );
};

import { useState, useEffect } from 'react';
import { FileText } from 'lucide-react';
import styles from '../../styles/Toolbox.module.css';
import type { Operation, ScenarioDefinition, NodeData } from '../../types/scenario';
import type { Node, Edge } from '@xyflow/react';
import { convertYamlToGraph } from '../../utils/scenarioConversion';

interface ScenarioListProps {
    onLoadScenario: (nodes: Node<NodeData>[], edges: Edge[]) => void;
    operations: Operation[];
}

export const ScenarioList = ({ onLoadScenario, operations }: ScenarioListProps) => {
    const [scenarios, setScenarios] = useState<string[]>([]);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        fetch('/api/scenarios')
            .then(res => res.json())
            .then(data => setScenarios(data))
            .catch(err => console.error('Failed to load scenarios:', err));
    }, []);

    const handleLoad = async (filename: string) => {
        if (loading) return;
        setLoading(true);
        try {
            const res = await fetch(`/api/scenarios/${filename}`);
            const scenario: ScenarioDefinition = await res.json();

            const { nodes, edges } = convertYamlToGraph(scenario, operations);

            onLoadScenario(nodes, edges);
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
                        style={{ cursor: 'pointer', opacity: loading ? 0.5 : 1 }}
                    >
                        <FileText size={16} color="#8b949e" />
                        <span>{name}</span>
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

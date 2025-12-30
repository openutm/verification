import { useState, useEffect } from 'react';
import { FileText } from 'lucide-react';
import styles from '../../styles/Toolbox.module.css';
import type { Operation, ScenarioDefinition, NodeData } from '../../types/scenario';
import type { Node, Edge } from '@xyflow/react';

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

            const nodes: Node<NodeData>[] = [];
            const edges: Edge[] = [];

            let yPos = 0;
            const xPos = 250;
            const gap = 150;

            // Note: We assume sequential execution based on the list order
            // since 'needs' was removed.
            scenario.steps.forEach((step, index) => {
                // Find operation by name (which matches 'step' in YAML)
                const operation = operations.find(op => op.name === step.step);
                if (!operation) {
                    console.warn(`Operation ${step.step} not found`);
                    return;
                }

                const nodeId = step.id || step.step;

                // Map arguments to parameters
                const parameters = operation.parameters.map(param => ({
                    ...param,
                    default: step.arguments?.[param.name] ?? param.default
                }));

                const node: Node<NodeData> = {
                    id: nodeId,
                    type: 'custom',
                    position: { x: xPos, y: yPos },
                    data: {
                        label: step.step,
                        operationId: operation.id,
                        description: step.description || operation.description,
                        parameters: parameters,
                        runInBackground: step.background
                    }
                };

                nodes.push(node);
                yPos += gap;

                // Create edge from previous node
                if (index > 0) {
                    const prevNode = nodes[index - 1];
                    edges.push({
                        id: `e_${prevNode.id}-${nodeId}`,
                        source: prevNode.id,
                        target: nodeId,
                        type: 'smoothstep'
                    });
                }
            });

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

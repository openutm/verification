
import { Handle, Position, type NodeProps, type Node } from '@xyflow/react';
import { Box, CheckCircle, XCircle, AlertTriangle, Loader2, MinusCircle } from 'lucide-react';
import styles from '../../styles/Node.module.css';
import type { NodeData } from '../../types/scenario';

export const CustomNode = ({ data, selected }: NodeProps<Node<NodeData>>) => {
    const statusClass = data.status === 'success' ? styles.statusSuccess :
        (data.status === 'failure' || data.status === 'error') ? styles.statusError :
            data.status === 'running' ? styles.statusRunning :
                data.status === 'skipped' ? styles.statusSkipped : '';
    const selectedClass = selected ? styles.selected : '';

    return (
        <div className={`${styles.customNode} ${statusClass} ${selectedClass}`}>
            <Handle type="target" position={Position.Top} style={{ background: 'var(--rf-handle)' }} />
            <div className={styles.customNodeHeader}>
                <Box size={16} className={styles.icon} />
                <span>{data.label}</span>
                {data.status && (
                    <div className={styles.statusIndicator}>
                        {data.status === 'success' && (
                            <div
                                className={styles.statusButton}
                                title="Success"
                                onClick={(e) => {
                                    e.stopPropagation();
                                    data.onShowResult?.(data.result);
                                }}
                            >
                                <CheckCircle size={16} color="var(--success)" />
                            </div>
                        )}
                        {data.status === 'failure' && (
                            <div
                                className={styles.statusButton}
                                title="Failure"
                                onClick={(e) => {
                                    e.stopPropagation();
                                    data.onShowResult?.(data.result);
                                }}
                            >
                                <XCircle size={16} color="var(--danger)" />
                            </div>
                        )}
                        {data.status === 'error' && (
                            <div
                                className={styles.statusButton}
                                title="Error"
                                onClick={(e) => {
                                    e.stopPropagation();
                                    data.onShowResult?.(data.result);
                                }}
                            >
                                <AlertTriangle size={16} color="var(--danger)" />
                            </div>
                        )}
                        {data.status === 'running' && (
                            <Loader2 size={16} className={styles.spinner} color="var(--accent-primary)" />
                        )}
                        {data.status === 'skipped' && (
                            <div
                                className={styles.statusButton}
                                title="Skipped"
                                onClick={(e) => {
                                    e.stopPropagation();
                                    data.onShowResult?.(data.result);
                                }}
                            >
                                <MinusCircle size={16} color="var(--text-tertiary)" />
                            </div>
                        )}
                    </div>
                )}
            </div>
            <Handle type="source" position={Position.Bottom} style={{ background: 'var(--rf-handle)' }} />
        </div>
    );
};

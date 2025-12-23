
import { Handle, Position, type NodeProps, type Node } from '@xyflow/react';
import { Box, CheckCircle, XCircle, AlertTriangle, Loader2 } from 'lucide-react';
import styles from '../../styles/Node.module.css';
import type { NodeData } from '../../types/scenario';

export const CustomNode = ({ data, selected }: NodeProps<Node<NodeData>>) => {
    const statusClass = data.status === 'success' ? styles.statusSuccess :
        (data.status === 'failure' || data.status === 'error') ? styles.statusError :
            data.status === 'running' ? styles.statusRunning : '';
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
                            <button
                                className={styles.statusButton}
                                onClick={(e) => {
                                    e.stopPropagation();
                                    data.onShowResult?.(data.result);
                                }}
                                title="Click to view results"
                                type="button"
                            >
                                <CheckCircle size={16} color="var(--success)" />
                            </button>
                        )}
                        {data.status === 'failure' && (
                            <button
                                className={styles.statusButton}
                                onClick={(e) => {
                                    e.stopPropagation();
                                    data.onShowResult?.(data.result);
                                }}
                                title="Click to view results"
                                type="button"
                            >
                                <XCircle size={16} color="var(--danger)" />
                            </button>
                        )}
                        {data.status === 'error' && (
                            <button
                                className={styles.statusButton}
                                onClick={(e) => {
                                    e.stopPropagation();
                                    data.onShowResult?.(data.result);
                                }}
                                title="Click to view results"
                                type="button"
                            >
                                <AlertTriangle size={16} color="var(--danger)" />
                            </button>
                        )}
                        {data.status === 'running' && (
                            <Loader2 size={16} className={styles.spinner} color="var(--accent-primary)" />
                        )}
                    </div>
                )}
            </div>
            <Handle type="source" position={Position.Bottom} style={{ background: 'var(--rf-handle)' }} />
        </div>
    );
};

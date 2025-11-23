
import { Handle, Position, type NodeProps, type Node } from '@xyflow/react';
import { Box, CheckCircle, XCircle, AlertTriangle } from 'lucide-react';
import styles from '../../styles/Node.module.css';
import type { NodeData } from '../../types/scenario';

export const CustomNode = ({ data, selected }: NodeProps<Node<NodeData>>) => {
    const statusClass = data.status === 'success' ? styles.statusSuccess :
        (data.status === 'failure' || data.status === 'error') ? styles.statusError : '';
    const selectedClass = selected ? styles.selected : '';

    return (
        <div className={`${styles.customNode} ${statusClass} ${selectedClass}`}>
            <Handle type="target" position={Position.Top} style={{ background: 'var(--rf-handle)' }} />
            <div className={styles.customNodeHeader}>
                <Box size={16} className={styles.icon} />
                <span>{data.label}</span>
                {data.status && (
                    <button
                        className={styles.statusButton}
                        onClick={(e) => {
                            e.stopPropagation();
                            data.onShowResult?.(data.result);
                        }}
                        title="Click to view results"
                        type="button"
                    >
                        {data.status === 'success' && <CheckCircle size={16} color="var(--success)" />}
                        {data.status === 'failure' && <XCircle size={16} color="var(--danger)" />}
                        {data.status === 'error' && <AlertTriangle size={16} color="var(--danger)" />}
                    </button>
                )}
            </div>
            <Handle type="source" position={Position.Bottom} style={{ background: 'var(--rf-handle)' }} />
        </div>
    );
};

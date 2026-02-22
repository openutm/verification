
import { Handle, Position, type NodeProps, type Node } from '@xyflow/react';
import { Box, CheckCircle, XCircle, AlertTriangle, Loader2, MinusCircle, RotateCw, GitBranch, Timer, Hourglass } from 'lucide-react';
import styles from '../../styles/Node.module.css';
import type { NodeData } from '../../types/scenario';

export const CustomNode = ({ data, selected }: NodeProps<Node<NodeData>>) => {
    const isGroupContainer = data.isGroupContainer;

    let statusClass = '';
    if (data.status === 'success') {
        statusClass = styles.statusSuccess;
    } else if (data.status === 'failure' || data.status === 'error') {
        statusClass = styles.statusError;
    } else if (data.status === 'running') {
        statusClass = styles.statusRunning;
    } else if (data.status === 'waiting') {
        statusClass = styles.statusWaiting;
    } else if (data.status === 'skipped') {
        statusClass = styles.statusSkipped;
    }

    const selectedClass = selected ? styles.selected : '';

    // Render group containers with label and badges overlay
    if (isGroupContainer) {
        return (
            <div className={`${styles.groupContainerLabel} ${selectedClass}`}>
                <div className={styles.groupLabelContent}>
                    <span>{data.label}</span>
                    <div className={styles.modifierBadges}>
                        {data.runInBackground && (
                            <div className={styles.backgroundBadge} title="Runs in background">
                                <Timer size={14} />
                                <span>bg</span>
                            </div>
                        )}
                        {data.ifCondition && data.ifCondition.trim() !== '' && (
                            <div className={styles.conditionBadge} title={`Condition: ${data.ifCondition}`}>
                                <GitBranch size={14} />
                                <span>if</span>
                            </div>
                        )}
                        {data.loop && (
                            <div className={styles.loopBadge} title={`Loop: ${JSON.stringify(data.loop)}`}>
                                <RotateCw size={14} />
                                <span>loop</span>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className={`${styles.customNode} ${statusClass} ${selectedClass}`}>
            <Handle type="target" position={Position.Top} style={{ background: 'var(--rf-handle)' }} />
            <div className={styles.customNodeHeader}>
                <Box size={16} className={styles.icon} />
                <span>{data.label}</span>
                <div className={styles.modifierBadges}>
                    {data.runInBackground && (
                        <div className={styles.backgroundBadge} title="Runs in background">
                            <Timer size={14} />
                            <span>bg</span>
                        </div>
                    )}
                    {data.ifCondition && data.ifCondition.trim() !== '' && (
                        <div className={styles.conditionBadge} title={`Condition: ${data.ifCondition}`}>
                            <GitBranch size={14} />
                            <span>if</span>
                        </div>
                    )}
                    {data.loop && (
                        <div className={styles.loopBadge} title={`Loop: ${JSON.stringify(data.loop)}`}>
                            <RotateCw size={14} />
                            <span>loop</span>
                        </div>
                    )}
                </div>
                {data.status && (
                    <div className={styles.statusIndicator} data-testid={`status-${data.status}`}>
                        {data.status === 'success' && (
                            <CheckCircle size={16} color="var(--success)" />
                        )}
                        {data.status === 'failure' && (
                            <XCircle size={16} color="var(--danger)" />
                        )}
                        {data.status === 'error' && (
                            <AlertTriangle size={16} color="var(--danger)" />
                        )}
                        {data.status === 'running' && (
                            <Loader2 size={16} className={styles.spinner} color="var(--accent-primary)" />
                        )}
                        {data.status === 'waiting' && (
                            <Hourglass size={16} color="var(--warning)" />
                        )}
                        {data.status === 'skipped' && (
                            <MinusCircle size={16} color="var(--text-tertiary)" />
                        )}
                    </div>
                )}
            </div>
            <Handle type="source" position={Position.Bottom} style={{ background: 'var(--rf-handle)' }} />
        </div>
    );
};

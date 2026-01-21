
import { Handle, Position, type NodeProps, type Node } from '@xyflow/react';
import { Box, CheckCircle, XCircle, AlertTriangle, Loader2, MinusCircle, RotateCw, GitBranch, Timer } from 'lucide-react';
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

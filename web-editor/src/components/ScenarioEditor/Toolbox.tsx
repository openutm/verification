import { useState, useMemo } from 'react';
import { ChevronDown, ChevronRight, Box } from 'lucide-react';
import styles from '../../styles/Toolbox.module.css';
import { getPhaseColor, PHASE_LABELS, PHASE_ORDER } from '../../utils/phaseColors';
import layoutStyles from '../../styles/EditorLayout.module.css';
import type { Operation } from '../../types/scenario';

type GroupBy = 'client' | 'phase';

const ToolboxGroup = ({ title, ops, badge }: { title: string, ops: Operation[], badge?: { code: string } }) => {
    const [isExpanded, setIsExpanded] = useState(true);

    return (
        <div>
            <button
                className={styles.groupHeader}
                onClick={() => setIsExpanded(!isExpanded)}
                style={{ width: '100%', border: 'none', background: 'none', textAlign: 'left', cursor: 'pointer' }}
                type="button"
            >
                {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                {badge && (
                    <span
                        className={styles.phaseBadge}
                        style={{
                            backgroundColor: getPhaseColor(badge.code).bg,
                            color: getPhaseColor(badge.code).text,
                            border: `1px solid ${getPhaseColor(badge.code).border}`,
                        }}
                    >{PHASE_LABELS[badge.code] || badge.code}</span>
                )}
                {title}
            </button>
            {isExpanded && (
                <div className={styles.groupContent}>
                    {ops.map((op) => (
                        <div
                            key={op.id}
                            className={styles.nodeItem}
                            title={op.phase ? `${op.name} [${op.phase}]` : op.name}
                            onDragStart={(event) => {
                                event.dataTransfer.setData('application/reactflow', op.name);
                                event.dataTransfer.setData('application/reactflow/id', op.id);
                            }}
                            draggable
                            role="button"
                            tabIndex={0}
                        >
                            <Box size={16} color="#8b949e" />
                            <div className={styles.nodeItemContent}>
                                <span>{op.name}</span>
                                {op.phase && (
                                    <span
                                        className={styles.phaseBadge}
                                        style={{
                                            backgroundColor: getPhaseColor(op.phase).bg,
                                            color: getPhaseColor(op.phase).text,
                                            border: `1px solid ${getPhaseColor(op.phase).border}`,
                                        }}
                                    >{PHASE_LABELS[op.phase] || op.phase}</span>
                                )}
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
};

export const Toolbox = ({ operations, children }: { operations: Operation[], children?: React.ReactNode }) => {
    const [activeTab, setActiveTab] = useState<'toolbox' | 'scenarios'>('scenarios');
    const [groupBy, setGroupBy] = useState<GroupBy>('client');

    const groupedByClient = useMemo(() => {
        const grouped = operations.reduce((acc, op) => {
            const groupName = op.category || 'General';
            if (!acc[groupName]) {
                acc[groupName] = [];
            }
            acc[groupName].push(op);
            return acc;
        }, {} as Record<string, Operation[]>);

        const sortedKeys = Object.keys(grouped).sort((a, b) => a.localeCompare(b));
        for (const key of sortedKeys) {
            grouped[key].sort((a, b) => a.name.localeCompare(b.name));
        }
        return { grouped, sortedKeys };
    }, [operations]);

    const groupedByPhase = useMemo(() => {
        const grouped = operations.reduce((acc, op) => {
            const phase = op.phase || '_none';
            if (!acc[phase]) {
                acc[phase] = [];
            }
            acc[phase].push(op);
            return acc;
        }, {} as Record<string, Operation[]>);

        // Sort keys: known phases in flight order, then unknown, then _none last
        const sortedKeys = Object.keys(grouped).sort((a, b) => {
            const ai = PHASE_ORDER.indexOf(a);
            const bi = PHASE_ORDER.indexOf(b);
            if (a === '_none') return 1;
            if (b === '_none') return -1;
            if (ai >= 0 && bi >= 0) return ai - bi;
            if (ai >= 0) return -1;
            if (bi >= 0) return 1;
            return a.localeCompare(b);
        });

        for (const key of sortedKeys) {
            grouped[key].sort((a, b) => a.name.localeCompare(b.name));
        }
        return { grouped, sortedKeys };
    }, [operations]);

    return (
        <aside className={layoutStyles.sidebar}>
            <div className={styles.tabContainer}>
                <button
                    className={`${styles.tabButton} ${activeTab === 'scenarios' ? styles.activeTab : ''}`}
                    onClick={() => setActiveTab('scenarios')}
                >
                    Scenarios
                </button>
                <button
                    className={`${styles.tabButton} ${activeTab === 'toolbox' ? styles.activeTab : ''}`}
                    onClick={() => setActiveTab('toolbox')}
                >
                    Toolbox
                </button>
            </div>

            <div className={styles.nodeList}>
                {activeTab === 'toolbox' ? (
                    <>
                        <div className={styles.groupByToggle}>
                            <span className={styles.groupByLabel}>Group by</span>
                            <button
                                className={`${styles.toggleOption} ${groupBy === 'client' ? styles.toggleActive : ''}`}
                                onClick={() => setGroupBy('client')}
                            >Client</button>
                            <button
                                className={`${styles.toggleOption} ${groupBy === 'phase' ? styles.toggleActive : ''}`}
                                onClick={() => setGroupBy('phase')}
                            >Phase</button>
                        </div>
                        {groupBy === 'client'
                            ? groupedByClient.sortedKeys.map(category => (
                                <ToolboxGroup key={category} title={category} ops={groupedByClient.grouped[category]} />
                            ))
                            : groupedByPhase.sortedKeys.map(phase => (
                                <ToolboxGroup
                                    key={phase}
                                    title={phase === '_none' ? 'No Phase' : (PHASE_LABELS[phase] || phase)}
                                    ops={groupedByPhase.grouped[phase]}
                                    badge={phase !== '_none' ? { code: phase } : undefined}
                                />
                            ))
                        }
                    </>
                ) : (
                    children
                )}
            </div>
        </aside>
    );
};

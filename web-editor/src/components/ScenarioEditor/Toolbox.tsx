import { useState, useMemo } from 'react';
import { ChevronDown, ChevronRight, ChevronLeft, Box } from 'lucide-react';
import styles from '../../styles/Toolbox.module.css';
import { getPhaseColor, PHASE_LABELS, PHASE_ORDER } from '../../utils/phaseColors';
import layoutStyles from '../../styles/EditorLayout.module.css';
import type { Operation } from '../../types/scenario';

type GroupBy = 'client' | 'phase';

const ToolboxGroup = ({
    title,
    ops,
    badge,
    forceExpanded,
}: {
    title: string;
    ops: Operation[];
    badge?: { code: string };
    forceExpanded?: boolean;
}) => {
    const [isExpanded, setIsExpanded] = useState(false);
    const expanded = forceExpanded ?? isExpanded;

    return (
        <div>
            <button
                className={styles.groupHeader}
                onClick={() => setIsExpanded(!isExpanded)}
                style={{ width: '100%', border: 'none', background: 'none', textAlign: 'left', cursor: 'pointer' }}
                type="button"
            >
                {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
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
                <span style={{ marginLeft: 'auto', fontSize: '11px', fontWeight: 400, opacity: 0.7 }}>
                    {ops.length}
                </span>
            </button>
            {expanded && (
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
                            <Box size={16} color="#8b949e" style={{ flexShrink: 0 }} />
                            <div className={styles.nodeItemContent}>
                                <span style={{ whiteSpace: 'normal', wordBreak: 'break-word' }}>{op.name}</span>
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

interface ToolboxProps {
    operations: Operation[];
    children?: React.ReactNode;
    isCollapsed?: boolean;
    onToggleCollapse?: () => void;
}

export const Toolbox = ({ operations, children, isCollapsed = false, onToggleCollapse }: ToolboxProps) => {
    const [activeTab, setActiveTab] = useState<'toolbox' | 'scenarios'>('scenarios');
    const [groupBy, setGroupBy] = useState<GroupBy>('client');
    const [filterText, setFilterText] = useState('');

    const groupedByClient = useMemo(() => {
        const grouped = operations.reduce((acc, op) => {
            const groupName = op.category || 'General';
            if (!acc[groupName]) acc[groupName] = [];
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
            if (!acc[phase]) acc[phase] = [];
            acc[phase].push(op);
            return acc;
        }, {} as Record<string, Operation[]>);

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

    const filter = filterText.toLowerCase().trim();

    const filteredByClient = useMemo(() => {
        if (!filter) return groupedByClient;
        const grouped: Record<string, Operation[]> = {};
        for (const key of groupedByClient.sortedKeys) {
            const ops = groupedByClient.grouped[key].filter(op => op.name.toLowerCase().includes(filter));
            if (ops.length > 0) grouped[key] = ops;
        }
        return { grouped, sortedKeys: Object.keys(grouped).sort((a, b) => a.localeCompare(b)) };
    }, [groupedByClient, filter]);

    const filteredByPhase = useMemo(() => {
        if (!filter) return groupedByPhase;
        const grouped: Record<string, Operation[]> = {};
        for (const key of groupedByPhase.sortedKeys) {
            const ops = groupedByPhase.grouped[key].filter(op => op.name.toLowerCase().includes(filter));
            if (ops.length > 0) grouped[key] = ops;
        }
        return { grouped, sortedKeys: Object.keys(grouped) };
    }, [groupedByPhase, filter]);

    const sidebarClass = `${layoutStyles.sidebar}${isCollapsed ? ` ${layoutStyles.sidebarCollapsed}` : ''}`;

    if (isCollapsed) {
        return (
            <aside className={sidebarClass}>
                <button
                    type="button"
                    onClick={onToggleCollapse}
                    title="Expand sidebar"
                    style={{
                        width: '32px',
                        height: '48px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        background: 'none',
                        border: 'none',
                        cursor: 'pointer',
                        color: 'var(--text-secondary)',
                    }}
                >
                    <ChevronRight size={16} />
                </button>
            </aside>
        );
    }

    const activeGroups = groupBy === 'client' ? filteredByClient : filteredByPhase;

    return (
        <aside className={sidebarClass}>
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
                <button
                    type="button"
                    onClick={onToggleCollapse}
                    title="Collapse sidebar"
                    style={{
                        padding: '0 10px',
                        background: 'none',
                        border: 'none',
                        cursor: 'pointer',
                        color: 'var(--text-secondary)',
                        display: 'flex',
                        alignItems: 'center',
                    }}
                >
                    <ChevronLeft size={16} />
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
                        <input
                            className={styles.searchInput}
                            type="text"
                            placeholder="Search operations…"
                            value={filterText}
                            onChange={e => setFilterText(e.target.value)}
                        />
                        {groupBy === 'client'
                            ? activeGroups.sortedKeys.map(category => (
                                <ToolboxGroup
                                    key={category}
                                    title={category}
                                    ops={(activeGroups as typeof filteredByClient).grouped[category]}
                                    forceExpanded={filter.length > 0 ? true : undefined}
                                />
                            ))
                            : activeGroups.sortedKeys.map(phase => (
                                <ToolboxGroup
                                    key={phase}
                                    title={phase === '_none' ? 'No Phase' : (PHASE_LABELS[phase] || phase)}
                                    ops={(activeGroups as typeof filteredByPhase).grouped[phase]}
                                    badge={phase !== '_none' ? { code: phase } : undefined}
                                    forceExpanded={filter.length > 0 ? true : undefined}
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

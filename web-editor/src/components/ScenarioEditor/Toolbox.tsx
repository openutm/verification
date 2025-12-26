import { useState, useMemo } from 'react';
import { ChevronDown, ChevronRight, Box } from 'lucide-react';
import styles from '../../styles/Toolbox.module.css';
import layoutStyles from '../../styles/EditorLayout.module.css';
import type { Operation } from '../../types/scenario';

const ToolboxGroup = ({ title, ops }: { title: string, ops: Operation[] }) => {
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
                {title}
            </button>
            {isExpanded && (
                <div className={styles.groupContent}>
                    {ops.map((op) => (
                        <div
                            key={op.id}
                            className={styles.nodeItem}
                            onDragStart={(event) => {
                                event.dataTransfer.setData('application/reactflow', op.name);
                                event.dataTransfer.setData('application/reactflow/id', op.id);
                            }}
                            draggable
                            role="button"
                            tabIndex={0}
                        >
                            <Box size={16} color="#8b949e" />
                            <span>{op.name}</span>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
};

export const Toolbox = ({ operations }: { operations: Operation[] }) => {
    const groupedOperations = useMemo(() => {
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

    return (
        <aside className={layoutStyles.sidebar}>
            <div className={layoutStyles.sidebarHeader}>
                Toolbox
            </div>
            <div className={styles.nodeList}>
                {groupedOperations.sortedKeys.map(category => (
                    <ToolboxGroup
                        key={category}
                        title={category}
                        ops={groupedOperations.grouped[category]}
                    />
                ))}
            </div>
        </aside>
    );
};

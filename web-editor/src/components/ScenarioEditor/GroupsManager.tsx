import React, { useState } from 'react';
import { Plus, Trash2, ChevronDown, ChevronUp } from 'lucide-react';
import styles from '../../styles/SidebarPanel.module.css';
import type { GroupDefinition, GroupStepDefinition } from '../../types/scenario';

interface GroupsManagerProps {
    groups: Record<string, GroupDefinition>;
    onGroupsChange: (groups: Record<string, GroupDefinition>) => void;
}

export const GroupsManager: React.FC<GroupsManagerProps> = ({ groups, onGroupsChange }) => {
    const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());
    const [newGroupName, setNewGroupName] = useState('');

    const toggleGroupExpanded = (groupName: string) => {
        const newExpanded = new Set(expandedGroups);
        if (newExpanded.has(groupName)) {
            newExpanded.delete(groupName);
        } else {
            newExpanded.add(groupName);
        }
        setExpandedGroups(newExpanded);
    };

    const addGroup = () => {
        if (!newGroupName.trim()) return;
        if (newGroupName in groups) {
            alert('Group already exists');
            return;
        }

        const updated = {
            ...groups,
            [newGroupName]: {
                description: '',
                steps: []
            }
        };
        onGroupsChange(updated);
        setNewGroupName('');
    };

    const deleteGroup = (groupName: string) => {
        if (confirm(`Delete group "${groupName}"? This cannot be undone.`)) {
            const updated = { ...groups };
            delete updated[groupName];
            onGroupsChange(updated);
        }
    };

    const updateGroupDescription = (groupName: string, description: string) => {
        const updated = {
            ...groups,
            [groupName]: {
                ...groups[groupName],
                description
            }
        };
        onGroupsChange(updated);
    };

    const addStepToGroup = (groupName: string) => {
        const newStep: GroupStepDefinition = {
            id: `step_${Date.now()}`,
            step: 'Select Operation',
            arguments: {}
        };

        const updated = {
            ...groups,
            [groupName]: {
                ...groups[groupName],
                steps: [...(groups[groupName].steps || []), newStep]
            }
        };
        onGroupsChange(updated);
    };

    const updateGroupStep = (groupName: string, stepIndex: number, step: GroupStepDefinition) => {
        const updated = {
            ...groups,
            [groupName]: {
                ...groups[groupName],
                steps: groups[groupName].steps.map((s, i) => i === stepIndex ? step : s)
            }
        };
        onGroupsChange(updated);
    };

    const deleteGroupStep = (groupName: string, stepIndex: number) => {
        const updated = {
            ...groups,
            [groupName]: {
                ...groups[groupName],
                steps: groups[groupName].steps.filter((_, i) => i !== stepIndex)
            }
        };
        onGroupsChange(updated);
    };

    return (
        <div className={styles.panel}>
            <div style={{ borderBottom: '1px solid var(--border-color)', paddingBottom: '12px', marginBottom: '16px' }}>
                <h3 style={{ marginBottom: '12px' }}>Step Groups</h3>
                <div style={{ display: 'flex', gap: '8px', marginBottom: '12px' }}>
                    <input
                        type="text"
                        className={styles.paramInput}
                        placeholder="New group name"
                        value={newGroupName}
                        onChange={(e) => setNewGroupName(e.target.value)}
                        onKeyDown={(e) => {
                            if (e.key === 'Enter') {
                                addGroup();
                            }
                        }}
                        style={{ flex: 1 }}
                    />
                    <button
                        onClick={addGroup}
                        className={styles.actionButton}
                        style={{ padding: '6px 12px', backgroundColor: 'var(--accent-primary)' }}
                        title="Add new group"
                    >
                        <Plus size={16} />
                    </button>
                </div>
                <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                    Groups are reusable collections of steps that can be looped and referenced as a single unit.
                </div>
            </div>

            <div style={{ maxHeight: '600px', overflowY: 'auto' }}>
                {Object.entries(groups).length === 0 ? (
                    <div style={{ fontSize: '12px', color: 'var(--text-secondary)', padding: '16px', textAlign: 'center' }}>
                        No groups defined yet. Create one to get started!
                    </div>
                ) : (
                    Object.entries(groups).map(([groupName, group]) => (
                        <div
                            key={groupName}
                            style={{
                                marginBottom: '12px',
                                border: '1px solid var(--border-color)',
                                borderRadius: '4px',
                                overflow: 'hidden',
                                backgroundColor: 'var(--bg-secondary)'
                            }}
                        >
                            <div
                                style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'space-between',
                                    padding: '12px',
                                    cursor: 'pointer',
                                    backgroundColor: 'var(--bg-hover)',
                                    borderBottom: expandedGroups.has(groupName) ? '1px solid var(--border-color)' : 'none'
                                }}
                                onClick={() => toggleGroupExpanded(groupName)}
                            >
                                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flex: 1 }}>
                                    {expandedGroups.has(groupName) ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                                    <code style={{ fontWeight: 600, fontSize: '13px', wordBreak: 'break-all' }}>
                                        {groupName}
                                    </code>
                                    <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                                        ({group.steps.length} steps)
                                    </span>
                                </div>
                                <div
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        deleteGroup(groupName);
                                    }}
                                    style={{
                                        cursor: 'pointer',
                                        padding: '4px',
                                        borderRadius: '4px',
                                        transition: 'background-color 0.2s'
                                    }}
                                    onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'var(--accent-danger)')}
                                    onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
                                    title="Delete group"
                                >
                                    <Trash2 size={16} style={{ color: 'var(--accent-danger)' }} />
                                </div>
                            </div>

                            {expandedGroups.has(groupName) && (
                                <div style={{ padding: '12px' }}>
                                    <div className={styles.paramItem}>
                                        <label style={{ fontSize: '12px', fontWeight: 600, marginBottom: '4px', display: 'block' }}>
                                            Description
                                        </label>
                                        <textarea
                                            value={group.description || ''}
                                            onChange={(e) => updateGroupDescription(groupName, e.target.value)}
                                            className={styles.paramInput}
                                            placeholder="What does this group do?"
                                            rows={2}
                                            style={{ fontFamily: 'inherit' }}
                                        />
                                    </div>

                                    <div style={{ marginTop: '12px' }}>
                                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                                            <label style={{ fontSize: '12px', fontWeight: 600 }}>Steps in Group</label>
                                            <button
                                                onClick={() => addStepToGroup(groupName)}
                                                className={styles.actionButton}
                                                style={{
                                                    padding: '4px 8px',
                                                    fontSize: '12px',
                                                    backgroundColor: 'var(--accent-primary)',
                                                    display: 'flex',
                                                    alignItems: 'center',
                                                    gap: '4px'
                                                }}
                                                title="Add step to group"
                                            >
                                                <Plus size={14} /> Add Step
                                            </button>
                                        </div>

                                        {group.steps.length === 0 ? (
                                            <div style={{ fontSize: '11px', color: 'var(--text-secondary)', padding: '8px', textAlign: 'center' }}>
                                                No steps in this group yet
                                            </div>
                                        ) : (
                                            group.steps.map((step, stepIndex) => (
                                                <div
                                                    key={stepIndex}
                                                    style={{
                                                        marginBottom: '8px',
                                                        padding: '8px',
                                                        backgroundColor: 'var(--bg-primary)',
                                                        border: '1px solid var(--border-color)',
                                                        borderRadius: '4px'
                                                    }}
                                                >
                                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '8px' }}>
                                                        <div style={{ flex: 1 }}>
                                                            <input
                                                                type="text"
                                                                placeholder="Step ID"
                                                                value={step.id || ''}
                                                                onChange={(e) =>
                                                                    updateGroupStep(groupName, stepIndex, { ...step, id: e.target.value })
                                                                }
                                                                className={styles.paramInput}
                                                                style={{ fontSize: '11px', marginBottom: '4px' }}
                                                            />
                                                            <input
                                                                type="text"
                                                                placeholder="Step name (operation)"
                                                                value={step.step}
                                                                onChange={(e) =>
                                                                    updateGroupStep(groupName, stepIndex, { ...step, step: e.target.value })
                                                                }
                                                                className={styles.paramInput}
                                                                style={{ fontSize: '11px' }}
                                                            />
                                                        </div>
                                                        <button
                                                            onClick={() => deleteGroupStep(groupName, stepIndex)}
                                                            className={styles.actionButton}
                                                            style={{ padding: '4px', color: 'var(--accent-danger)' }}
                                                            title="Delete step from group"
                                                        >
                                                            <Trash2 size={14} />
                                                        </button>
                                                    </div>
                                                </div>
                                            ))
                                        )}
                                    </div>
                                </div>
                            )}
                        </div>
                    ))
                )}
            </div>
        </div>
    );
};

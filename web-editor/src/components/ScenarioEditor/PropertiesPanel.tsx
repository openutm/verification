import React, { useState, useMemo } from 'react';
import { X, Link as LinkIcon, Unlink } from 'lucide-react';
import type { Node } from '@xyflow/react';
import layoutStyles from '../../styles/EditorLayout.module.css';
import styles from '../../styles/SidebarPanel.module.css';
import type { NodeData } from '../../types/scenario';
import { useSidebarResize } from '../../hooks/useSidebarResize';

const DocstringViewer = ({ text }: { text: string }) => {
    const [expanded, setExpanded] = useState(false);

    if (!text) return <div className={styles.docstring}>No description available.</div>;

    const sectionRegex = /(Args:|Returns:|Raises:)/;
    const parts = text.split(sectionRegex);

    const mainDesc = parts[0].trim();
    const sections: React.ReactNode[] = [];

    for (let i = 1; i < parts.length; i += 2) {
        const title = parts[i];
        const content = parts[i + 1];
        sections.push(
            <div key={i} className={styles.docSection}>
                <strong>{title}</strong>
                <pre className={styles.docContent}>{content.trim()}</pre>
            </div>
        );
    }

    return (
        <div className={styles.docstring}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
                <div className={styles.docSummary} style={{ marginBottom: 0 }}>
                    {expanded ? mainDesc : mainDesc.slice(0, 120) + (mainDesc.length > 120 ? '…' : '')}
                </div>
                <button
                    className={styles.iconButton}
                    type="button"
                    onClick={() => setExpanded(prev => !prev)}
                    aria-expanded={expanded}
                >
                    {expanded ? 'Hide' : 'Show'}
                </button>
            </div>
            {expanded && sections}
            {!expanded && sections.length > 0 && (
                <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                    (Args/Returns hidden)
                </div>
            )}
        </div>
    );
};

interface PropertiesPanelProps {
    selectedNode: Node<NodeData>;
    connectedNodes: Node<NodeData>[];
    allNodes: Node<NodeData>[];
    onClose: () => void;
    onUpdateParameter: (nodeId: string, paramName: string, value: unknown) => void;
    onUpdateRunInBackground: (nodeId: string, value: boolean) => void;
    onUpdateStepId: (nodeId: string, stepId: string) => void;
    onUpdateIfCondition: (nodeId: string, condition: string) => void;
    onUpdateLoop: (nodeId: string, loopConfig: { count?: number; items?: unknown[]; while?: string } | undefined) => void;
    onUpdateNeeds: (nodeId: string, needs: string[]) => void;
    onUpdateGroupDescription?: (groupName: string, description: string) => void;
}

const parseRefString = (value: unknown) => {
    if (typeof value !== 'string') return null;
    const match = value.match(/^\$\{\{\s*steps\.([^.]+)\.result(?:\.(.*))?\s*\}\}$/);
    if (!match) return null;
    return {
        stepId: match[1],
        fieldPath: match[2] ? match[2].trim() : ''
    };
};

export const PropertiesPanel = ({ selectedNode, connectedNodes, allNodes, onClose, onUpdateParameter, onUpdateRunInBackground, onUpdateStepId, onUpdateIfCondition, onUpdateLoop, onUpdateNeeds, onUpdateGroupDescription }: PropertiesPanelProps) => {
    const { sidebarWidth: width, isResizing, startResizing } = useSidebarResize(480, 300, 800);

    // Compute loop type from node data
    const computedLoopType = useMemo<'none' | 'count' | 'items' | 'while'>(() => {
        if (!selectedNode.data.loop) return 'none';
        if (selectedNode.data.loop.count !== undefined) return 'count';
        if (selectedNode.data.loop.items !== undefined) return 'items';
        if (selectedNode.data.loop.while !== undefined) return 'while';
        return 'none';
    }, [selectedNode.data.loop]);

    const [loopType, setLoopType] = useState<'none' | 'count' | 'items' | 'while'>(computedLoopType);

    // Sync loopType state with computed value when node changes
    if (loopType !== computedLoopType) {
        setLoopType(computedLoopType);
    }

    const formatParamValue = (value: unknown): string => {
        if (value === null || value === undefined) {
            return '';
        }
        if (typeof value === 'object' && value !== null && '$ref' in value) {
            return (value as { $ref: string }).$ref;
        }
        if (typeof value === 'string') {
            return value;
        }
        if (typeof value === 'number' || typeof value === 'boolean') {
            return String(value);
        }
        if (typeof value === 'bigint') {
            return value.toString();
        }
        if (typeof value === 'symbol') {
            return value.toString();
        }
        return JSON.stringify(value);
    };

    return (
        <aside className={layoutStyles.rightSidebar} style={{ width, position: 'relative' }}>
            <div
                onMouseDown={(e) => {
                    e.preventDefault();
                    startResizing();
                }}
                style={{
                    position: 'absolute',
                    left: 0,
                    top: 0,
                    bottom: 0,
                    width: '5px',
                    cursor: 'col-resize',
                    zIndex: 100,
                    backgroundColor: isResizing ? 'var(--accent-primary)' : 'transparent',
                }}
                title="Drag to resize"
            />
            <div className={styles.panel}>
                <div className={layoutStyles.sidebarHeader}>
                    Properties
                    {' '}
                    <button
                        onClick={onClose}
                        className={styles.closeButton}
                        type="button"
                    >
                        <X size={16} />
                    </button>
                </div>
                <div className={styles.content}>
                    <h3>{selectedNode.data.label}</h3>
                    <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginBottom: '12px' }}>
                        <div style={{ fontFamily: 'monospace' }}>Node ID: {selectedNode.id}</div>
                    </div>

                    <div className={styles.paramItem}>
                        <label>Step ID (Optional)</label>
                        <input
                            type="text"
                            className={styles.paramInput}
                            value={selectedNode.data.stepId || ''}
                            onChange={(e) => onUpdateStepId(selectedNode.id, e.target.value)}
                            placeholder={selectedNode.data.label}
                        />
                         <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                            Uniquely identify this step in the YAML. Explicitly set this if you have multiple steps with the same name.
                        </div>
                    </div>

                    <DocstringViewer text={selectedNode.data.description || ''} />

                    <div className={styles.paramItem} style={{ marginTop: '10px', borderTop: '1px solid var(--border-color)', paddingTop: '10px' }}>
                        <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                            <input
                                type="checkbox"
                                checked={!!selectedNode.data.runInBackground}
                                onChange={(e) => onUpdateRunInBackground(selectedNode.id, e.target.checked)}
                            />
                            Run in Background
                        </label>
                        <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                            If checked, this step will run asynchronously. Use the Needs list below to wait for background tasks.
                        </div>
                    </div>

                    <div className={styles.paramItem} style={{ marginTop: '10px', borderTop: '1px solid var(--border-color)', paddingTop: '10px' }}>
                        <label>Needs (wait for background tasks)</label>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', maxHeight: '180px', overflowY: 'auto', padding: '6px', border: '1px solid var(--border-color)', borderRadius: '6px' }}>
                            {allNodes
                                .filter(n => n.data.runInBackground && n.id !== selectedNode.id)
                                .map(n => {
                                    const label = n.data.stepId || n.data.label;
                                    const checked = (selectedNode.data.needs || []).includes(n.id);
                                    return (
                                        <label key={n.id} style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                                            <input
                                                type="checkbox"
                                                checked={checked}
                                                onChange={(e) => {
                                                    const current = new Set(selectedNode.data.needs || []);
                                                    if (e.target.checked) {
                                                        current.add(n.id);
                                                    } else {
                                                        current.delete(n.id);
                                                    }
                                                    onUpdateNeeds(selectedNode.id, Array.from(current));
                                                }}
                                            />
                                            <span>{label}</span>
                                        </label>
                                    );
                                })}
                            {allNodes.filter(n => n.data.runInBackground && n.id !== selectedNode.id).length === 0 && (
                                <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>No background tasks available.</div>
                            )}
                        </div>
                        <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                            Check background steps to wait on. Uncheck to remove. Holds execution until those tasks complete.
                        </div>
                    </div>

                    <div className={styles.paramItem} style={{ marginTop: '10px', borderTop: '1px solid var(--border-color)', paddingTop: '10px' }}>
                        <label>If Condition</label>
                        <input
                            type="text"
                            className={styles.paramInput}
                            value={selectedNode.data.ifCondition || ''}
                            onChange={(e) => onUpdateIfCondition(selectedNode.id, e.target.value)}
                            placeholder="e.g., success() or steps.step1.status == 'pass'"
                        />
                        <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                            Conditional expression (GitHub Actions-style). Examples:<br/>
                            • <code style={{ fontSize: '10px' }}>success()</code> - run if previous step succeeded<br/>
                            • <code style={{ fontSize: '10px' }}>failure()</code> - run if previous step failed<br/>
                            • <code style={{ fontSize: '10px' }}>always()</code> - always run<br/>
                            • <code style={{ fontSize: '10px' }}>steps.step1.status == 'pass'</code> - check specific step
                        </div>
                    </div>

                    <div className={styles.paramItem} style={{ marginTop: '10px', borderTop: '1px solid var(--border-color)', paddingTop: '10px' }}>
                        <label>Loop Configuration</label>
                        <select
                            className={styles.paramInput}
                            value={loopType}
                            onChange={(e) => {
                                const newType = e.target.value as typeof loopType;
                                setLoopType(newType);
                                if (newType === 'none') {
                                    onUpdateLoop(selectedNode.id, undefined);
                                } else if (newType === 'count') {
                                    onUpdateLoop(selectedNode.id, { count: 1 });
                                } else if (newType === 'items') {
                                    onUpdateLoop(selectedNode.id, { items: [] });
                                } else if (newType === 'while') {
                                    onUpdateLoop(selectedNode.id, { while: '' });
                                }
                            }}
                            style={{ marginBottom: '8px' }}
                        >
                            <option value="none">No Loop</option>
                            <option value="count">Fixed Count</option>
                            <option value="items">Iterate Items</option>
                            <option value="while">While Condition</option>
                        </select>

                        {loopType === 'count' && (
                            <>
                                <input
                                    type="number"
                                    className={styles.paramInput}
                                    value={selectedNode.data.loop?.count || 1}
                                    onChange={(e) => onUpdateLoop(selectedNode.id, { count: parseInt(e.target.value) || 1 })}
                                    placeholder="Number of iterations"
                                    min="1"
                                />
                                <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                                    Repeat this step N times. Access iteration with <code style={{ fontSize: '10px' }}>loop.index</code>
                                </div>
                            </>
                        )}

                        {loopType === 'items' && (
                            <>
                                <textarea
                                    className={styles.paramInput}
                                    value={selectedNode.data.loop?.items ? JSON.stringify(selectedNode.data.loop.items) : '[]'}
                                    onChange={(e) => {
                                        try {
                                            const items = JSON.parse(e.target.value);
                                            onUpdateLoop(selectedNode.id, { items });
                                        } catch {
                                            // Invalid JSON, ignore
                                        }
                                    }}
                                    placeholder='["item1", "item2", "item3"]'
                                    rows={3}
                                    style={{ fontFamily: 'monospace', fontSize: '12px' }}
                                />
                                <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                                    JSON array of items. Access current item with <code style={{ fontSize: '10px' }}>loop.item</code>
                                </div>
                            </>
                        )}

                        {loopType === 'while' && (
                            <>
                                <input
                                    type="text"
                                    className={styles.paramInput}
                                    value={selectedNode.data.loop?.while || ''}
                                    onChange={(e) => onUpdateLoop(selectedNode.id, { while: e.target.value })}
                                    placeholder="loop.index < 10"
                                />
                                <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                                    Continue while condition is true. Max 100 iterations. Use <code style={{ fontSize: '10px' }}>loop.index</code>
                                </div>
                            </>
                        )}
                    </div>

                    <h4>Parameters</h4>
                    {selectedNode.data.isGroupReference || selectedNode.data.isGroupContainer ? (
                        <>
                            <div style={{
                                padding: '12px',
                                backgroundColor: 'var(--bg-hover)',
                                borderRadius: '4px',
                                border: '1px solid var(--accent-primary)',
                                marginBottom: '12px'
                            }}>
                                <div style={{ fontSize: '13px', fontWeight: 600, marginBottom: '8px', color: 'var(--accent-primary)' }}>
                                    📦 Step Group {selectedNode.data.isGroupContainer ? 'Container' : 'Reference'}
                                </div>
                                <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '8px' }}>
                                    This step references a group defined in the Groups panel. The group contains multiple steps that will execute together.
                                </div>
                                <div style={{ fontSize: '11px', color: 'var(--text-secondary)', padding: '8px', backgroundColor: 'var(--bg-primary)', borderRadius: '4px', fontFamily: 'monospace' }}>
                                    Steps within this group can reference each other using: <code>{'${{ group.step_id.result }}'}</code>
                                </div>
                            </div>
                            {(selectedNode.data.isGroupContainer || selectedNode.data.isGroupReference) && onUpdateGroupDescription && (
                                <div className={styles.paramItem} style={{ marginBottom: '12px' }}>
                                    <label>Group Description</label>
                                    <textarea
                                        className={styles.paramInput}
                                        value={selectedNode.data.description || ''}
                                        onChange={(e) => {
                                            const groupName = selectedNode.data.label.replace('📦 ', '').trim();
                                            onUpdateGroupDescription(groupName, e.target.value);
                                        }}
                                        placeholder="Describe what this group of steps does..."
                                        rows={3}
                                        style={{ fontFamily: 'inherit', fontSize: '12px' }}
                                    />
                                    <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                                        Optionally describe the purpose of this group.
                                    </div>
                                </div>
                            )}
                        </>
                    ) : (selectedNode.data.parameters || []).length > 0 ? (
                        (selectedNode.data.parameters || []).map(param => {
                            const refData = (typeof param.default === 'object' && param.default !== null && '$ref' in param.default)
                                ? (() => {
                                    const refValue = (param.default as { $ref: string }).$ref;
                                    const parts = refValue.split('.');
                                    if (parts[0] !== 'steps') return null;
                                    const stepId = parts[1] || '';
                                    const fieldPathParts = parts.slice(2);
                                    if (fieldPathParts[0] === 'result') {
                                        fieldPathParts.shift();
                                    }
                                    const fieldPath = fieldPathParts.join('.') || '';
                                    return { stepId, fieldPath };
                                })()
                                : parseRefString(param.default);

                            const isLinked = !!refData;

                            const resolvedStepId = refData ? (() => {
                                const found = allNodes.find(n => n.id === refData.stepId || n.data.label === refData.stepId || n.data.stepId === refData.stepId);
                                return found?.data.stepId || found?.id || refData.stepId;
                            })() : '';

                            return (
                                <div key={param.name} className={styles.paramItem}>
                                    <div style={{ display: 'flex', alignItems: 'center', marginBottom: '4px', gap: '8px' }}>
                                        <button
                                            className={styles.iconButton}
                                            onClick={() => {
                                                if (isLinked) {
                                                    onUpdateParameter(selectedNode.id, param.name, '');
                                                } else {
                                                    if (connectedNodes.length > 0) {
                                                        const sourceStepId = connectedNodes[0].data.stepId || connectedNodes[0].id;
                                                        onUpdateParameter(selectedNode.id, param.name, { $ref: `steps.${sourceStepId}.result` });
                                                    } else {
                                                        alert("Connect a node to this step first to link parameters.");
                                                    }
                                                }
                                            }}
                                            title={isLinked ? "Unlink parameter" : "Link to output from previous step"}
                                            type="button"
                                        >
                                            {isLinked ? <Unlink size={14} /> : <LinkIcon size={14} />}
                                        </button>
                                        <label style={{ flex: 1 }}>{param.name} <span className={styles.paramType}>({param.type})</span></label>
                                    </div>

                                    {isLinked && refData ? (
                                        <div style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
                                            <div className={styles.paramInput} style={{ padding: '8px 12px', color: 'var(--text-secondary)' }}>
                                                Reference from steps
                                            </div>
                                            <select
                                                className={styles.paramInput}
                                                value={resolvedStepId}
                                                onChange={(e) => {
                                                    const sourceId = e.target.value;
                                                    const fieldPath = refData.fieldPath;
                                                    onUpdateParameter(
                                                        selectedNode.id,
                                                        param.name,
                                                        { $ref: `steps.${sourceId}.result${fieldPath ? '.' + fieldPath : ''}` }
                                                    );
                                                }}
                                            >
                                                {connectedNodes.map(node => (
                                                    <option key={node.id} value={node.data.stepId || node.id}>
                                                        {node.data.label} ({node.data.stepId || node.id})
                                                    </option>
                                                ))}
                                                {!connectedNodes.find(n => (n.data.stepId || n.id) === resolvedStepId) && resolvedStepId && (
                                                    <option value={resolvedStepId}>
                                                        {allNodes.find(n => n.id === resolvedStepId || n.data.stepId === resolvedStepId)?.data.label || resolvedStepId} (Disconnected)
                                                    </option>
                                                )}
                                            </select>
                                            <input
                                                type="text"
                                                placeholder="Field path (e.g. id, result.id)"
                                                className={styles.paramInput}
                                                value={refData.fieldPath}
                                                onChange={(e) => {
                                                    const fieldPath = e.target.value;
                                                    const sourceId = resolvedStepId || refData.stepId;
                                                    onUpdateParameter(
                                                        selectedNode.id,
                                                        param.name,
                                                        { $ref: `steps.${sourceId}.result${fieldPath ? '.' + fieldPath : ''}` }
                                                    );
                                                }}
                                            />
                                            <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                                                {(() => {
                                                    const refDisplay = '${{ steps.'
                                                        + refData.stepId
                                                        + `.result${refData.fieldPath ? '.' + refData.fieldPath : ''} }}`;
                                                    return `Reference: ${refDisplay}`;
                                                })()}
                                            </div>
                                        </div>
                                    ) : (
                                        param.isEnum && param.options ? (
                                            <select
                                                className={styles.paramInput}
                                                value={formatParamValue(param.default)}
                                                onChange={(e) => {
                                                    const inputValue = e.target.value;
                                                    let value: unknown = undefined;
                                                    if (inputValue !== '') {
                                                        const numValue = Number(inputValue);
                                                        value = Number.isNaN(numValue) ? inputValue : numValue;
                                                    }
                                                    onUpdateParameter(selectedNode.id, param.name, value);
                                                }}
                                            >
                                                <option value="">Select...</option>
                                                {param.options.map(opt => (
                                                    <option key={String(opt.value)} value={String(opt.value)}>
                                                        {opt.name} ({String(opt.value)})
                                                    </option>
                                                ))}
                                            </select>
                                        ) : (
                                            <input
                                                type="text"
                                                placeholder="Value..."
                                                className={styles.paramInput}
                                                value={formatParamValue(param.default)}
                                                onChange={(e) => {
                                                    const inputValue = e.target.value;
                                                    let value: unknown = undefined;
                                                    if (inputValue !== '') {
                                                        const numValue = Number(inputValue);
                                                        value = Number.isNaN(numValue) ? inputValue : numValue;
                                                    }
                                                    onUpdateParameter(selectedNode.id, param.name, value);
                                                }}
                                            />
                                        )
                                    )}
                                </div>
                            );
                        })
                    ) : (
                        <p style={{ fontSize: '12px', fontStyle: 'italic' }}>No parameters required.</p>
                    )}
                </div>
            </div>
        </aside>
    );
};

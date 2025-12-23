import React from 'react';
import { X, Link as LinkIcon, Unlink } from 'lucide-react';
import type { Node } from '@xyflow/react';
import layoutStyles from '../../styles/EditorLayout.module.css';
import styles from '../../styles/SidebarPanel.module.css';
import type { NodeData } from '../../types/scenario';

const DocstringViewer = ({ text }: { text: string }) => {
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
            <div className={styles.docSummary}>{mainDesc}</div>
            {sections}
        </div>
    );
};

interface PropertiesPanelProps {
    selectedNode: Node<NodeData>;
    connectedNodes: Node<NodeData>[];
    onClose: () => void;
    onUpdateParameter: (nodeId: string, paramName: string, value: unknown) => void;
    onUpdateRunInBackground: (nodeId: string, value: boolean) => void;
}

export const PropertiesPanel = ({ selectedNode, connectedNodes, onClose, onUpdateParameter, onUpdateRunInBackground }: PropertiesPanelProps) => {
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
        <aside className={layoutStyles.rightSidebar}>
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
                            If checked, this step will run asynchronously. Use SystemClient.join_task to wait for it later.
                        </div>
                    </div>

                    <h4>Parameters</h4>
                    {(selectedNode.data.parameters || []).length > 0 ? (
                        (selectedNode.data.parameters || []).map(param => {
                            const isLinked = typeof param.default === 'object' && param.default !== null && '$ref' in param.default;

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
                                                        onUpdateParameter(selectedNode.id, param.name, { $ref: `${connectedNodes[0].id}.` });
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

                                    {isLinked ? (
                                        <div style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
                                            <select
                                                className={styles.paramInput}
                                                value={(param.default as { $ref: string }).$ref.split('.')[0]}
                                                onChange={(e) => {
                                                    const sourceId = e.target.value;
                                                    const currentRef = (param.default as { $ref: string }).$ref;
                                                    const parts = currentRef.split('.');
                                                    const fieldPath = parts.slice(1).join('.');
                                                    onUpdateParameter(selectedNode.id, param.name, { $ref: `${sourceId}.${fieldPath}` });
                                                }}
                                            >
                                                {connectedNodes.map(node => (
                                                    <option key={node.id} value={node.id}>
                                                        {node.data.label} ({node.id})
                                                    </option>
                                                ))}
                                            </select>
                                            <input
                                                type="text"
                                                placeholder="Field path (e.g. id, result.id)"
                                                className={styles.paramInput}
                                                value={(param.default as { $ref: string }).$ref.split('.').slice(1).join('.')}
                                                onChange={(e) => {
                                                    const fieldPath = e.target.value;
                                                    const currentRef = (param.default as { $ref: string }).$ref;
                                                    const sourceId = currentRef.split('.')[0];
                                                    onUpdateParameter(selectedNode.id, param.name, { $ref: `${sourceId}.${fieldPath}` });
                                                }}
                                            />
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
                            )
                        })
                    ) : (
                        <p style={{ fontSize: '12px', fontStyle: 'italic' }}>No parameters required.</p>
                    )}
                </div>
            </div>
        </aside>
    );
};

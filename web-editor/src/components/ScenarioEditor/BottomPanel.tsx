import { useState, useMemo } from 'react';
import { X } from 'lucide-react';
import layoutStyles from '../../styles/EditorLayout.module.css';
import panelStyles from '../../styles/SidebarPanel.module.css';
import styles from '../../styles/BottomPanel.module.css';
import { useBottomPanelResize } from '../../hooks/useBottomPanelResize';
import type { Node } from '@xyflow/react';
import type { NodeData } from '../../types/scenario';

const JsonViewer = ({ data }: { data: unknown }) => {
    const jsonString = JSON.stringify(data, null, 2);

    const html = jsonString.replace(/("[^"]*":?|\btrue\b|\bfalse\b|\bnull\b|-?\d+(?:\.\d+)?)/g, (match) => {
        let cls = styles.jsonNumber;
        if (match.startsWith('"')) {
            if (match.endsWith(':')) {
                cls = styles.jsonKey;
            } else {
                cls = styles.jsonString;
            }
        } else if (/true|false/.test(match)) {
            cls = styles.jsonBoolean;
        } else if (/null/.test(match)) {
            cls = styles.jsonNull;
        }
        return `<span class="${cls}">${match}</span>`;
    });

    return <div className={styles.jsonContainer} dangerouslySetInnerHTML={{ __html: html }} />;
};

const parseLog = (log: string) => {
    const parts = log.split(' | ');
    if (parts.length >= 3) {
        return {
            time: parts[0],
            level: parts[1].trim(),
            message: parts.slice(2).join(' | ')
        };
    }
    return { time: '', level: 'UNKNOWN', message: log };
};

interface BottomPanelProps {
    selectedNode: Node<NodeData> | null;
    onClose: () => void;
}

export const BottomPanel = ({ selectedNode, onClose }: BottomPanelProps) => {
    const { panelHeight, isResizing, startResizing } = useBottomPanelResize();
    const [activeTab, setActiveTab] = useState<'output' | 'logs'>('output');
    const [logLevel, setLogLevel] = useState<string>('ALL');

    const result = selectedNode?.data?.result;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const logs = (result as any)?.logs as string[] | undefined;

    const filteredLogs = useMemo(() => {
        if (!logs) return [];
        if (logLevel === 'ALL') return logs;
        return logs.filter(log => {
            const { level } = parseLog(log);
            return level === logLevel;
        });
    }, [logs, logLevel]);

    if (!selectedNode) return null;

    const { status, label } = selectedNode.data;

    return (
        <div className={layoutStyles.bottomPanel} style={{ height: panelHeight, position: 'relative' }}>
            <button
                className={`${styles.resizeHandle} ${isResizing ? styles.resizeHandleActive : ''}`}
                onMouseDown={startResizing}
                aria-label="Resize panel"
                type="button"
            />
            <div className={panelStyles.panel} style={{ height: '100%' }}>
                <div className={layoutStyles.sidebarHeader}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                        <span>{label} - Results</span>
                        {status && (
                            <span style={{
                                fontSize: '10px',
                                padding: '2px 6px',
                                borderRadius: '4px',
                                backgroundColor: status === 'success' ? 'var(--success-bg)' : status === 'failure' ? 'var(--danger-bg)' : 'var(--bg-secondary)',
                                color: status === 'success' ? 'var(--success)' : status === 'failure' ? 'var(--danger)' : 'var(--text-secondary)',
                                border: '1px solid currentColor'
                            }}>
                                {status.toUpperCase()}
                            </span>
                        )}
                    </div>
                    <button
                        onClick={onClose}
                        className={panelStyles.closeButton}
                        aria-label="Close panel"
                    >
                        <X size={16} />
                    </button>
                </div>

                <div className={styles.tabContainer}>
                    <button
                        className={`${styles.tab} ${activeTab === 'output' ? styles.activeTab : ''}`}
                        onClick={() => setActiveTab('output')}
                    >
                        Output Data
                    </button>
                    <button
                        className={`${styles.tab} ${activeTab === 'logs' ? styles.activeTab : ''}`}
                        onClick={() => setActiveTab('logs')}
                    >
                        Logs {logs && logs.length > 0 && `(${logs.length})`}
                    </button>
                </div>

                <div className={styles.content}>
                    {result ? (
                        <div className={styles.tabContent}>
                            {activeTab === 'output' && (
                                <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                                    <JsonViewer data={result} />
                                </div>
                            )}

                            {activeTab === 'logs' && (
                                <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                                    <div className={styles.toolbar}>
                                        <select
                                            className={styles.filterSelect}
                                            value={logLevel}
                                            onChange={(e) => setLogLevel(e.target.value)}
                                        >
                                            <option value="ALL">All Levels</option>
                                            <option value="INFO">INFO</option>
                                            <option value="WARNING">WARNING</option>
                                            <option value="ERROR">ERROR</option>
                                            <option value="DEBUG">DEBUG</option>
                                        </select>
                                        <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                                            {filteredLogs.length} lines
                                        </span>
                                    </div>
                                    {filteredLogs.length > 0 ? (
                                        <div className={styles.jsonContainer} style={{ fontSize: '12px' }}>
                                            {filteredLogs.map((log, i) => (
                                                <div key={i} style={{ borderBottom: '1px solid var(--border-color)', padding: '2px 0' }}>{log}</div>
                                            ))}
                                        </div>
                                    ) : (
                                        <div style={{ color: 'var(--text-secondary)', fontStyle: 'italic' }}>
                                            No logs available.
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>
                    ) : (
                        <div style={{ padding: '16px', color: 'var(--text-secondary)', fontStyle: 'italic' }}>
                            No results available for this step. Run the scenario to generate results.
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

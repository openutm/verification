import React, { useState, useEffect, useCallback } from 'react';
import { X, FileText, Info, BookOpen } from 'lucide-react';
import layoutStyles from '../../styles/EditorLayout.module.css';
import styles from '../../styles/SidebarPanel.module.css';
import { DocumentationModal } from './DocumentationModal';
import { ConfigEditor } from './ConfigEditor';
import type { ScenarioConfig } from '../../types/scenario';

interface ScenarioInfoPanelProps {
    name: string | null;
    description: string;
    config: ScenarioConfig;
    onUpdateName: (name: string) => void;
    onUpdateDescription: (description: string) => void;
    onUpdateConfig: (config: ScenarioConfig) => void;
    onOpenReport: () => void;
    onClose?: () => void;
}

export const ScenarioInfoPanel = ({ name, description, config, onUpdateName, onUpdateDescription, onUpdateConfig, onOpenReport, onClose }: ScenarioInfoPanelProps) => {
    const [width, setWidth] = useState(480);
    const [isResizing, setIsResizing] = useState(false);
    const [isDocsOpen, setIsDocsOpen] = useState(false);

    const startResizing = useCallback((mouseDownEvent: React.MouseEvent) => {
        mouseDownEvent.preventDefault();
        setIsResizing(true);
    }, []);

    const stopResizing = useCallback(() => {
        setIsResizing(false);
    }, []);

    const resize = useCallback(
        (mouseMoveEvent: MouseEvent) => {
            if (isResizing) {
                const newWidth = window.innerWidth - mouseMoveEvent.clientX;
                if (newWidth > 300 && newWidth < 800) {
                    setWidth(newWidth);
                }
            }
        },
        [isResizing]
    );

    useEffect(() => {
        window.addEventListener("mousemove", resize);
        window.addEventListener("mouseup", stopResizing);
        return () => {
            window.removeEventListener("mousemove", resize);
            window.removeEventListener("mouseup", stopResizing);
        };
    }, [resize, stopResizing]);

    return (
        <aside className={layoutStyles.rightSidebar} style={{ width, position: 'relative' }}>
            <div
                onMouseDown={startResizing}
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
                    Scenario Settings
                    {onClose && (
                        <button
                            onClick={onClose}
                            className={styles.closeButton}
                            type="button"
                        >
                            <X size={16} />
                        </button>
                    )}
                </div>
                <div className={styles.content}>
                    <div className={styles.paramItem}>
                        <label style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <FileText size={16} />
                            Scenario Name
                        </label>
                        <input
                            type="text"
                            className={styles.paramInput}
                            value={name || ''}
                            onChange={(e) => onUpdateName(e.target.value)}
                            placeholder="e.g. valid_flight_auth"
                        />
                        <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                            Currently saving as: <strong>{name || "new_scenario"}.yaml</strong>
                        </div>
                    </div>

                    <div className={styles.paramItem}>
                        <label style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <Info size={16} />
                            Description
                        </label>
                        <textarea
                            className={styles.paramInput}
                            value={description}
                            onChange={(e) => onUpdateDescription(e.target.value)}
                            rows={6}
                            style={{ resize: 'vertical', minHeight: '80px', fontFamily: 'inherit' }}
                            placeholder="Describe what this scenario tests..."
                        />
                    </div>

                    <ConfigEditor config={config} onUpdateConfig={onUpdateConfig} />

                    {name && (
                        <div className={styles.paramItem} style={{ display: 'flex', gap: '8px' }}>
                            <button
                                onClick={() => setIsDocsOpen(true)}
                                style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '8px',
                                    padding: '8px 16px',
                                    backgroundColor: 'var(--bg-secondary)',
                                    border: '1px solid var(--border-color)',
                                    borderRadius: '4px',
                                    cursor: 'pointer',
                                    flex: 1,
                                    justifyContent: 'center',
                                    color: 'var(--text-primary)'
                                }}
                                title="View scenario documentation"
                            >
                                <BookOpen size={16} />
                                Docs
                            </button>
                            <button
                                onClick={onOpenReport}
                                style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '8px',
                                    padding: '8px 16px',
                                    backgroundColor: 'var(--bg-secondary)',
                                    border: '1px solid var(--border-color)',
                                    borderRadius: '4px',
                                    cursor: 'pointer',
                                    flex: 1,
                                    justifyContent: 'center',
                                    color: 'var(--text-primary)'
                                }}
                                title="Open latest report"
                            >
                                <FileText size={16} />
                                Report
                            </button>
                        </div>
                    )}
                </div>
            </div>

            <DocumentationModal
                scenarioName={name}
                isOpen={isDocsOpen}
                onClose={() => setIsDocsOpen(false)}
            />
        </aside>
    );
};

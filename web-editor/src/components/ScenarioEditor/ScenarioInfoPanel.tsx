import { useCallback, useEffect, useRef, useState } from 'react';
import { X, FileText, Info, ChevronDown, ChevronUp } from 'lucide-react';
import layoutStyles from '../../styles/EditorLayout.module.css';
import styles from '../../styles/SidebarPanel.module.css';
import docStyles from '../../styles/DocumentationPanel.module.css';
import { DocumentationPanel } from './DocumentationPanel';
import { ConfigEditor } from './ConfigEditor';
import type { ScenarioConfig } from '../../types/scenario';
import { useSidebarResize } from '../../hooks/useSidebarResize';

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

const DEFAULT_WIDTH = Math.max(380, Math.floor(window.innerWidth * 0.25));
const DEFAULT_DOCS_HEIGHT = Math.floor(window.innerHeight * 0.45);
const MIN_DOCS_HEIGHT = 80;
const MAX_DOCS_HEIGHT_RATIO = 0.8;

export const ScenarioInfoPanel = ({ name, description, config, onUpdateName, onUpdateDescription, onUpdateConfig, onOpenReport, onClose }: ScenarioInfoPanelProps) => {
    const { sidebarWidth: width, isResizing: isWidthResizing, startResizing: startWidthResize } = useSidebarResize(DEFAULT_WIDTH, 300, 800);

    const [docsHeight, setDocsHeight] = useState(DEFAULT_DOCS_HEIGHT);
    // Track which scenario the user explicitly collapsed docs for — auto-expands when name changes
    const [collapsedForName, setCollapsedForName] = useState<string | null>(null);
    const isDocsCollapsed = collapsedForName === name && name !== null;
    const [isSettingsCollapsed, setIsSettingsCollapsed] = useState(false);
    const [isDraggingHeight, setIsDraggingHeight] = useState(false);
    const [firstParagraph, setFirstParagraph] = useState<string | null>(null);

    const panelRef = useRef<HTMLElement>(null);
    const dragStartY = useRef(0);
    const dragStartHeight = useRef(0);

    const startHeightDrag = useCallback((e: React.MouseEvent) => {
        e.preventDefault();
        dragStartY.current = e.clientY;
        dragStartHeight.current = docsHeight;
        setIsDraggingHeight(true);
    }, [docsHeight]);

    useEffect(() => {
        if (!isDraggingHeight) return;

        const onMouseMove = (e: MouseEvent) => {
            const panelHeight = panelRef.current?.clientHeight ?? window.innerHeight;
            const maxHeight = Math.floor(panelHeight * MAX_DOCS_HEIGHT_RATIO);
            const delta = e.clientY - dragStartY.current;
            const newHeight = Math.min(maxHeight, Math.max(MIN_DOCS_HEIGHT, dragStartHeight.current + delta));
            setDocsHeight(newHeight);
        };

        const onMouseUp = () => setIsDraggingHeight(false);

        window.addEventListener('mousemove', onMouseMove);
        window.addEventListener('mouseup', onMouseUp);
        return () => {
            window.removeEventListener('mousemove', onMouseMove);
            window.removeEventListener('mouseup', onMouseUp);
        };
    }, [isDraggingHeight]);

    return (
        <aside ref={panelRef} className={layoutStyles.rightSidebar} style={{ width, position: 'relative', display: 'flex', flexDirection: 'column' }}>
            {/* Left-edge width resize handle */}
            <div
                onMouseDown={(e) => {
                    e.preventDefault();
                    startWidthResize();
                }}
                style={{
                    position: 'absolute',
                    left: 0,
                    top: 0,
                    bottom: 0,
                    width: '5px',
                    cursor: 'col-resize',
                    zIndex: 100,
                    backgroundColor: isWidthResizing ? 'var(--accent-primary)' : 'transparent',
                }}
                title="Drag to resize"
            />

            {/* Panel header: prominent scenario title + Report button */}
            <div style={{
                padding: '14px 20px',
                borderBottom: '1px solid var(--border-color)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: '8px',
                flexShrink: 0,
                background: 'var(--bg-primary)',
            }}>
                <span style={{
                    fontSize: '15px',
                    fontWeight: 700,
                    color: 'var(--text-primary)',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                    flex: 1,
                    letterSpacing: '-0.01em',
                }}>
                    {name ?? 'No scenario loaded'}
                </span>
                <div style={{ display: 'flex', gap: '6px', flexShrink: 0 }}>
                    {name && (
                        <button
                            onClick={onOpenReport}
                            style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: '6px',
                                padding: '6px 12px',
                                backgroundColor: 'var(--bg-secondary)',
                                border: '1px solid var(--border-color)',
                                borderRadius: '4px',
                                cursor: 'pointer',
                                color: 'var(--text-primary)',
                                fontSize: '12px',
                                fontWeight: 500,
                            }}
                            title="Open latest report"
                        >
                            <FileText size={13} />
                            Report
                        </button>
                    )}
                    {onClose && (
                        <button onClick={onClose} className={styles.closeButton} type="button">
                            <X size={16} />
                        </button>
                    )}
                </div>
            </div>

            {/* Documentation panel */}
            <DocumentationPanel
                scenarioName={name}
                height={docsHeight}
                isCollapsed={isDocsCollapsed}
                onToggleCollapse={() => setCollapsedForName(isDocsCollapsed ? null : name)}
                firstParagraph={firstParagraph}
                onFirstParagraphChange={setFirstParagraph}
            />

            {/* Vertical drag handle */}
            {!isDocsCollapsed && (
                <div
                    className={`${docStyles.verticalDragHandle}${isDraggingHeight ? ` ${docStyles.active}` : ''}`}
                    onMouseDown={startHeightDrag}
                    title="Drag to resize"
                />
            )}

            {/* Settings section */}
            <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0, overflow: 'hidden' }}>
                <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '10px 20px',
                    borderBottom: '1px solid var(--border-color)',
                    flexShrink: 0,
                }}>
                    <span style={{
                        fontSize: '11px',
                        fontWeight: 600,
                        color: 'var(--text-secondary)',
                        textTransform: 'uppercase',
                        letterSpacing: '0.05em',
                    }}>
                        Settings
                    </span>
                    <button
                        className={styles.closeButton}
                        onClick={() => setIsSettingsCollapsed(c => !c)}
                        title={isSettingsCollapsed ? 'Expand settings' : 'Collapse settings'}
                        type="button"
                    >
                        {isSettingsCollapsed ? <ChevronDown size={14} /> : <ChevronUp size={14} />}
                    </button>
                </div>

                {!isSettingsCollapsed && (
                    <div className={styles.content} style={{ overflowY: 'auto', padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
                        <div className={styles.paramItem}>
                            <label style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                <FileText size={14} />
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
                                Saving as: <strong>{name || 'new_scenario'}.yaml</strong>
                            </div>
                        </div>

                        <div className={styles.paramItem}>
                            <label style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                <Info size={14} />
                                Description
                            </label>
                            <textarea
                                className={styles.paramInput}
                                value={description}
                                onChange={(e) => onUpdateDescription(e.target.value)}
                                rows={4}
                                style={{ resize: 'vertical', minHeight: '72px', fontFamily: 'inherit' }}
                                placeholder="Describe what this scenario tests..."
                            />
                        </div>

                        <ConfigEditor config={config} onUpdateConfig={onUpdateConfig} />
                    </div>
                )}
            </div>
        </aside>
    );
};

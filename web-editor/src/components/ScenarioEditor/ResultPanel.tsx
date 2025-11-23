import { X } from 'lucide-react';
import layoutStyles from '../../styles/EditorLayout.module.css';
import panelStyles from '../../styles/SidebarPanel.module.css';
import styles from '../../styles/ResultPanel.module.css';
import { useSidebarResize } from '../../hooks/useSidebarResize';

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

interface ResultPanelProps {
    result: unknown;
    onClose: () => void;
}

export const ResultPanel = ({ result, onClose }: ResultPanelProps) => {
    const { sidebarWidth, isResizing, startResizing } = useSidebarResize();

    return (
        <aside className={layoutStyles.rightSidebar} style={{ width: sidebarWidth, position: 'relative' }}>
            <button
                className={`${styles.resizeHandle} ${isResizing ? styles.resizeHandleActive : ''}`}
                onMouseDown={startResizing}
                aria-label="Resize sidebar"
                type="button"
            />
            <div className={panelStyles.panel}>
                <div className={layoutStyles.sidebarHeader}>
                    Step Result
                    {' '}
                    <button
                        onClick={onClose}
                        className={panelStyles.closeButton}
                        type="button"
                    >
                        <X size={16} />
                    </button>
                </div>
                <div className={panelStyles.content} style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                    <JsonViewer data={result} />
                </div>
            </div>
        </aside>
    );
};

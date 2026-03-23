import { useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { ChevronUp, ChevronDown, Copy, Check } from 'lucide-react';
import styles from '../../styles/DocumentationPanel.module.css';

interface DocumentationPanelProps {
    scenarioName: string | null;
    height: number;
    isCollapsed: boolean;
    onToggleCollapse: () => void;
    firstParagraph: string | null;
    onFirstParagraphChange: (text: string | null) => void;
}

export const DocumentationPanel = ({
    scenarioName,
    height,
    isCollapsed,
    onToggleCollapse,
    firstParagraph,
    onFirstParagraphChange,
}: DocumentationPanelProps) => {
    const [content, setContent] = useState<string>('');
    const [loading, setLoading] = useState(false);
    const [notFound, setNotFound] = useState(false);
    const [copied, setCopied] = useState(false);

    useEffect(() => {
        if (!scenarioName) {
            setContent('');
            setNotFound(false);
            onFirstParagraphChange(null);
            return;
        }

        setLoading(true);
        setNotFound(false);
        setContent('');

        fetch(`/api/scenarios/${scenarioName}/docs`)
            .then(async (res) => {
                if (!res.ok) {
                    if (res.status === 404) {
                        setNotFound(true);
                        onFirstParagraphChange(null);
                    }
                    return '';
                }
                return res.text();
            })
            .then(text => {
                if (text) {
                    setContent(text);
                    const firstLine = text.split('\n').find(line => line.trim() && !line.startsWith('#'));
                    onFirstParagraphChange(firstLine?.trim() ?? null);
                }
            })
            .catch(() => {
                setNotFound(true);
                onFirstParagraphChange(null);
            })
            .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [scenarioName]);

    const expectedPath = scenarioName ? `docs/scenarios/${scenarioName}.md` : '';

    const handleCopy = () => {
        navigator.clipboard.writeText(expectedPath).then(() => {
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        });
    };

    return (
        <div
            className={styles.docPanel}
            style={{ height: isCollapsed ? undefined : height }}
        >
            <div className={styles.docSectionHeader}>
                <div style={{ flex: 1, minWidth: 0 }}>
                    <span className={styles.docSectionLabel}>Documentation</span>
                    {isCollapsed && firstParagraph && (
                        <div className={styles.collapsedPreview}>{firstParagraph}</div>
                    )}
                </div>
                <button
                    className={styles.collapseBtn}
                    onClick={onToggleCollapse}
                    title={isCollapsed ? 'Expand documentation' : 'Collapse documentation'}
                    type="button"
                >
                    {isCollapsed ? <ChevronDown size={14} /> : <ChevronUp size={14} />}
                </button>
            </div>

            {!isCollapsed && (
                <div className={styles.docContent}>
                    {loading && (
                        <div className={styles.statusMessage}>Loading documentation...</div>
                    )}

                    {!loading && notFound && scenarioName && (
                        <div className={styles.noDocsMessage}>
                            <p>No documentation found for this scenario.</p>
                            <p>Create a file at:</p>
                            <div className={styles.pathRow}>
                                <code className={styles.pathCode}>{expectedPath}</code>
                                <button
                                    className={styles.copyBtn}
                                    onClick={handleCopy}
                                    title="Copy path to clipboard"
                                    type="button"
                                >
                                    {copied ? <Check size={13} /> : <Copy size={13} />}
                                </button>
                            </div>
                            <p>to add documentation for this scenario.</p>
                        </div>
                    )}

                    {!loading && !notFound && !scenarioName && (
                        <div className={styles.statusMessage}>Load a scenario to see its documentation.</div>
                    )}

                    {!loading && !notFound && content && (
                        <div className={styles.markdownBody}>
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                {content}
                            </ReactMarkdown>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};

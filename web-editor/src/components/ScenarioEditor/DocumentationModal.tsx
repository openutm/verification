import { useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { X } from 'lucide-react';
import styles from '../../styles/DocumentationModal.module.css';

interface DocumentationModalProps {
    scenarioName: string | null;
    isOpen: boolean;
    onClose: () => void;
}

export const DocumentationModal = ({ scenarioName, isOpen, onClose }: DocumentationModalProps) => {
    const [content, setContent] = useState<string>('');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (!isOpen || !scenarioName) return;

        // Use a timeout to avoid preventing cascading renders warning from synchronous setState
        const timer = setTimeout(() => {
            setLoading(true);
            setError(null);

            fetch(`/api/scenarios/${scenarioName}/docs`)
                .then(async (res) => {
                    if (!res.ok) {
                        if (res.status === 404) {
                            throw new Error('Documentation not found for this scenario.');
                        }
                        throw new Error('Failed to load documentation.');
                    }
                    return res.text();
                })
                .then(text => setContent(text))
                .catch(err => {
                    console.error(err);
                    setError(err.message);
                    setContent('');
                })
                .finally(() => setLoading(false));
        }, 0);

        return () => clearTimeout(timer);
    }, [isOpen, scenarioName]);

    if (!isOpen) return null;

    return (
        <div className={styles.modalOverlay} onClick={onClose}>
            <div className={styles.modalContent} onClick={e => e.stopPropagation()}>
                <button className={styles.closeButton} onClick={onClose}>
                    <X size={24} />
                </button>

                {loading && <div>Loading documentation...</div>}

                {error && (
                    <div style={{ color: 'red', padding: '1rem' }}>
                        {error}
                    </div>
                )}

                {!loading && !error && (
                    <div className={styles.markdownBody}>
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                            {content}
                        </ReactMarkdown>
                    </div>
                )}
            </div>
        </div>
    );
};

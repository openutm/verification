import { Activity, Moon, Sun, Layout, FilePlus, Save, Play, Loader2, Copy, Square } from 'lucide-react';
import styles from '../../styles/Header.module.css';
import btnStyles from '../../styles/Button.module.css';

interface HeaderProps {
    theme: 'light' | 'dark';
    toggleTheme: () => void;
    onLayout: () => void;
    onNew: () => void;
    onSave: () => void;
    onSaveAs: () => void;
    onRun: () => void;
    onStop: () => void;
    isRunning: boolean;
}

export const Header = ({
    theme,
    toggleTheme,
    onLayout,
    onNew,
    onSave,
    onSaveAs,
    onRun,
    onStop,
    isRunning,
}: HeaderProps) => {
    return (
        <header className={styles.header}>
            <div className={styles.title}>
                <Activity size={20} color="#58a6ff" />
                <span>OpenUTM Scenario Designer</span>
            </div>
            <div className={styles.actions}>
                <button className={btnStyles.button} onClick={toggleTheme} title={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`} type="button">
                    {theme === 'light' ? <Moon size={16} /> : <Sun size={16} />}
                </button>
                <button className={btnStyles.button} onClick={onLayout} title="Auto-arrange nodes" type="button">
                    <Layout size={16} />
                    Auto Layout
                </button>
                <button className={btnStyles.button} onClick={onNew} title="Create new scenario" type="button">
                    <FilePlus size={16} />
                    New
                </button>
                <button className={btnStyles.button} onClick={onSave} title="Save to Server" type="button">
                    <Save size={16} />
                    Save
                </button>
                <button className={btnStyles.button} onClick={onSaveAs} title="Save As..." type="button">
                    <Copy size={16} />
                    Save As
                </button>
                <button className={`${btnStyles.button} ${btnStyles.primary}`} onClick={onRun} disabled={isRunning} title="Run scenario" type="button">
                    {isRunning ? <Loader2 size={16} className={styles.spin} /> : <Play size={16} />}
                    Run Scenario
                </button>
                {isRunning && (
                    <button className={`${btnStyles.button} ${btnStyles.danger}`} onClick={onStop} title="Stop scenario" type="button">
                        <Square size={16} />
                        Stop
                    </button>
                )}
            </div>
        </header>
    );
};

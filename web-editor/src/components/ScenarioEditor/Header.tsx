import { Activity, Moon, Sun, Layout, Trash2, Save, Play, Loader2 } from 'lucide-react';
import styles from '../../styles/Header.module.css';
import btnStyles from '../../styles/Button.module.css';

interface HeaderProps {
    theme: 'light' | 'dark';
    toggleTheme: () => void;
    onLayout: () => void;
    onClear: () => void;
    onSave: () => void;
    onRun: () => void;
    isRunning: boolean;
}

export const Header = ({
    theme,
    toggleTheme,
    onLayout,
    onClear,
    onSave,
    onRun,
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
                <button className={btnStyles.button} onClick={onClear} title="Clear current scenario" type="button">
                    <Trash2 size={16} />
                    Clear
                </button>
                <button className={btnStyles.button} onClick={onSave} title="Save to Server" type="button">
                    <Save size={16} />
                    Save
                </button>
                <button className={`${btnStyles.button} ${btnStyles.primary}`} onClick={onRun} disabled={isRunning} title="Run scenario" type="button">
                    {isRunning ? <Loader2 size={16} className={styles.spin} /> : <Play size={16} />}
                    Run Scenario
                </button>
            </div>
        </header>
    );
};

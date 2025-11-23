import React from 'react';
import { Activity, Moon, Sun, Layout, Trash2, Upload, Save, Play, Loader2 } from 'lucide-react';
import styles from '../../styles/Header.module.css';
import btnStyles from '../../styles/Button.module.css';

interface HeaderProps {
    theme: 'light' | 'dark';
    toggleTheme: () => void;
    onLayout: () => void;
    onClear: () => void;
    onLoad: () => void;
    onExport: () => void;
    onRun: () => void;
    isRunning: boolean;
    fileInputRef: React.RefObject<HTMLInputElement>;
    onFileChange: (event: React.ChangeEvent<HTMLInputElement>) => void;
}

export const Header = ({
    theme,
    toggleTheme,
    onLayout,
    onClear,
    onLoad,
    onExport,
    onRun,
    isRunning,
    fileInputRef,
    onFileChange
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
                <button className={btnStyles.button} onClick={onLoad} title="Load JSON scenario" type="button">
                    <Upload size={16} />
                    Load Scenario
                </button>
                <input
                    type="file"
                    ref={fileInputRef}
                    onChange={onFileChange}
                    style={{ display: 'none' }}
                    accept=".json"
                />
                <button className={btnStyles.button} onClick={onExport} title="Export to JSON" type="button">
                    <Save size={16} />
                    Export
                </button>
                <button className={`${btnStyles.button} ${btnStyles.primary}`} onClick={onRun} disabled={isRunning} title="Run scenario" type="button">
                    {isRunning ? <Loader2 size={16} className={styles.spin} /> : <Play size={16} />}
                    Run Scenario
                </button>
            </div>
        </header>
    );
};

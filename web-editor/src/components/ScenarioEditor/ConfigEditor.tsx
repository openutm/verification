import React, { useState } from 'react';
import { Settings, Database, Server, ChevronDown, ChevronRight, HelpCircle } from 'lucide-react';
import styles from '../../styles/SidebarPanel.module.css';
import type { ScenarioConfig } from '../../types/scenario';

const sectionTooltips: Record<string, string> = {
    flight_blender: 'Configure connection to Flight Blender, the UTM integration server. Set the URL, authentication method, and OAuth scopes.',
    data_files: 'Specify paths to data files used in the scenario: trajectories, flight declarations, operational intents, and geo-fences.',
    air_traffic: 'Settings for the default air traffic simulator including number of aircraft, simulation duration, and sensor configuration.',
    blue_sky_air_traffic: 'Settings for the BlueSky air traffic simulator, an alternative simulator with its own aircraft count, duration, and sensor IDs.',
};

const Tooltip: React.FC<{ text: string }> = ({ text }) => (
    <div style={{
        padding: '6px 10px',
        background: 'var(--bg-tertiary, #1e1e2e)',
        border: '1px solid var(--border-color)',
        borderRadius: '4px',
        fontSize: '11px',
        lineHeight: '1.4',
        color: 'var(--text-secondary)',
        marginBottom: '4px',
        boxShadow: '0 2px 8px rgba(0,0,0,0.2)',
    }}>
        {text}
    </div>
);

interface ConfigEditorProps {
    config: ScenarioConfig;
    onUpdateConfig: (config: ScenarioConfig) => void;
}

export const ConfigEditor: React.FC<ConfigEditorProps> = ({ config, onUpdateConfig }) => {
    const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set());
    const [showHelp, setShowHelp] = useState(false);

    const toggleSection = (section: string) => {
        setExpandedSections(prev => {
            const next = new Set(prev);
            if (next.has(section)) {
                next.delete(section);
            } else {
                next.add(section);
            }
            return next;
        });
    };

    const updateFlightBlender = (field: string, value: string) => {
        onUpdateConfig({
            ...config,
            flight_blender: {
                ...config.flight_blender,
                [field]: value
            }
        });
    };

    const updateFlightBlenderAuth = (field: string, value: string | string[]) => {
        onUpdateConfig({
            ...config,
            flight_blender: {
                ...config.flight_blender,
                auth: {
                    ...config.flight_blender.auth,
                    [field]: value
                }
            }
        });
    };

    const updateDataFiles = (field: string, value: string) => {
        onUpdateConfig({
            ...config,
            data_files: {
                ...config.data_files,
                [field]: value
            }
        });
    };

    const updateAirTrafficSimulator = (field: string, value: string | number | string[]) => {
        onUpdateConfig({
            ...config,
            air_traffic_simulator_settings: {
                ...config.air_traffic_simulator_settings,
                [field]: value
            }
        });
    };

    const updateBlueSkyAirTrafficSimulator = (field: string, value: string | number | string[]) => {
        onUpdateConfig({
            ...config,
            blue_sky_air_traffic_simulator_settings: {
                ...(config.blue_sky_air_traffic_simulator_settings || {}),
                [field]: value
            }
        });
    };

    const updateSensorIds = (value: string) => {
        const ids = value.split(',').map(id => id.trim()).filter(id => id.length > 0);
        updateAirTrafficSimulator('sensor_ids', ids);
    };

    const updateBlueSkySensorIds = (value: string) => {
        const ids = value.split(',').map(id => id.trim()).filter(id => id.length > 0);
        updateBlueSkyAirTrafficSimulator('sensor_ids', ids);
    };

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div style={{
                fontSize: '12px',
                fontWeight: 600,
                color: 'var(--text-secondary)',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                marginBottom: '4px'
            }}>
                <Settings size={14} />
                CONFIGURATION
                <button
                    onClick={() => setShowHelp(prev => !prev)}
                    title={showHelp ? 'Hide help tooltips' : 'Show help tooltips'}
                    style={{
                        marginLeft: 'auto',
                        background: showHelp ? 'var(--accent-color, #007acc)' : 'transparent',
                        border: '1px solid var(--border-color)',
                        borderRadius: '4px',
                        padding: '2px 4px',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        color: showHelp ? '#fff' : 'var(--text-secondary)',
                    }}
                >
                    <HelpCircle size={14} />
                </button>
            </div>
            <p style={{ fontSize: '11px', color: 'var(--text-secondary)', margin: '0 0 8px 0' }}>
                Configure settings and sources for Flight Blender, data files, and air traffic simulators to customize your scenario.
            </p>

            {/* Flight Blender Section */}
            <div className={styles.configSection}>
                {showHelp && <Tooltip text={sectionTooltips.flight_blender} />}
                <button
                    onClick={() => toggleSection('flight_blender')}
                    className={styles.configSectionHeader}
                    style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px',
                        width: '100%',
                        padding: '8px',
                        background: 'var(--bg-secondary)',
                        border: '1px solid var(--border-color)',
                        borderRadius: '4px',
                        cursor: 'pointer',
                        color: 'var(--text-primary)',
                        fontSize: '13px',
                        fontWeight: 500
                    }}
                >
                    {expandedSections.has('flight_blender') ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                    <Server size={16} />
                    Flight Blender
                </button>

                {expandedSections.has('flight_blender') && (
                    <div style={{ padding: '12px 4px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
                        <div className={styles.paramItem}>
                            <label style={{ display: 'block', fontSize: '12px', fontWeight: 500, marginBottom: '6px', color: 'var(--text-secondary)' }}>URL</label>
                            <input
                                type="text"
                                className={styles.paramInput}
                                value={config.flight_blender.url}
                                onChange={(e) => updateFlightBlender('url', e.target.value)}
                                placeholder="http://localhost:8000"
                            />
                        </div>

                        <div className={styles.paramItem}>
                            <label style={{ display: 'block', fontSize: '12px', fontWeight: 500, marginBottom: '6px', color: 'var(--text-secondary)' }}>Auth Type</label>
                            <select
                                className={styles.paramInput}
                                value={config.flight_blender.auth.type}
                                onChange={(e) => updateFlightBlenderAuth('type', e.target.value)}
                            >
                                <option value="none">none</option>
                                <option value="passport">passport</option>
                            </select>
                        </div>

                        {config.flight_blender.auth.type === 'passport' && (
                            <>
                                <div className={styles.paramItem}>
                                    <label style={{ display: 'block', fontSize: '12px', fontWeight: 500, marginBottom: '6px', color: 'var(--text-secondary)' }}>Client ID</label>
                                    <input
                                        type="text"
                                        className={styles.paramInput}
                                        value={config.flight_blender.auth.client_id || ''}
                                        onChange={(e) => updateFlightBlenderAuth('client_id', e.target.value)}
                                        placeholder="your-client-id"
                                    />
                                </div>

                                <div className={styles.paramItem}>
                                    <label style={{ display: 'block', fontSize: '12px', fontWeight: 500, marginBottom: '6px', color: 'var(--text-secondary)' }}>Client Secret</label>
                                    <input
                                        type="password"
                                        className={styles.paramInput}
                                        value={config.flight_blender.auth.client_secret || ''}
                                        onChange={(e) => updateFlightBlenderAuth('client_secret', e.target.value)}
                                        placeholder="your-client-secret"
                                    />
                                </div>

                                <div className={styles.paramItem}>
                                    <label style={{ display: 'block', fontSize: '12px', fontWeight: 500, marginBottom: '6px', color: 'var(--text-secondary)' }}>Token Endpoint</label>
                                    <input
                                        type="text"
                                        className={styles.paramInput}
                                        value={config.flight_blender.auth.token_endpoint || ''}
                                        onChange={(e) => updateFlightBlenderAuth('token_endpoint', e.target.value)}
                                        placeholder="/oauth/token/"
                                    />
                                </div>

                                <div className={styles.paramItem}>
                                    <label style={{ display: 'block', fontSize: '12px', fontWeight: 500, marginBottom: '6px', color: 'var(--text-secondary)' }}>Passport Base URL</label>
                                    <input
                                        type="text"
                                        className={styles.paramInput}
                                        value={config.flight_blender.auth.passport_base_url || ''}
                                        onChange={(e) => updateFlightBlenderAuth('passport_base_url', e.target.value)}
                                        placeholder="https://passport.testflight.openutm.net"
                                    />
                                </div>
                            </>
                        )}

                        <div className={styles.paramItem}>
                            <label style={{ display: 'block', fontSize: '12px', fontWeight: 500, marginBottom: '6px', color: 'var(--text-secondary)' }}>Audience</label>
                            <input
                                type="text"
                                className={styles.paramInput}
                                value={config.flight_blender.auth.audience || ''}
                                onChange={(e) => updateFlightBlenderAuth('audience', e.target.value)}
                                placeholder="testflight.flightblender.com"
                            />
                        </div>

                        <div className={styles.paramItem}>
                            <label style={{ display: 'block', fontSize: '12px', fontWeight: 500, marginBottom: '6px', color: 'var(--text-secondary)' }}>Scopes (comma-separated)</label>
                            <input
                                type="text"
                                className={styles.paramInput}
                                value={config.flight_blender.auth.scopes?.join(', ') || ''}
                                onChange={(e) => updateFlightBlenderAuth('scopes', e.target.value.split(',').map(s => s.trim()))}
                                placeholder="flightblender.write, flightblender.read"
                            />
                        </div>
                    </div>
                )}
            </div>

            {/* Data Files Section */}
            <div className={styles.configSection}>
                {showHelp && <Tooltip text={sectionTooltips.data_files} />}
                <button
                    onClick={() => toggleSection('data_files')}
                    className={styles.configSectionHeader}
                    style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px',
                        width: '100%',
                        padding: '8px',
                        background: 'var(--bg-secondary)',
                        border: '1px solid var(--border-color)',
                        borderRadius: '4px',
                        cursor: 'pointer',
                        color: 'var(--text-primary)',
                        fontSize: '13px',
                        fontWeight: 500
                    }}
                >
                    {expandedSections.has('data_files') ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                    <Database size={16} />
                    Data Files
                </button>

                {expandedSections.has('data_files') && (
                    <div style={{ padding: '12px 4px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
                        <div className={styles.paramItem}>
                            <label style={{ display: 'block', fontSize: '12px', fontWeight: 500, marginBottom: '6px', color: 'var(--text-secondary)' }}>Trajectory</label>
                            <input
                                type="text"
                                className={styles.paramInput}
                                value={config.data_files.trajectory || ''}
                                onChange={(e) => updateDataFiles('trajectory', e.target.value)}
                                placeholder="config/bern/trajectory_f1.json"
                            />
                        </div>

                        <div className={styles.paramItem}>
                            <label style={{ display: 'block', fontSize: '12px', fontWeight: 500, marginBottom: '6px', color: 'var(--text-secondary)' }}>Flight Declaration</label>
                            <input
                                type="text"
                                className={styles.paramInput}
                                value={config.data_files.flight_declaration || ''}
                                onChange={(e) => updateDataFiles('flight_declaration', e.target.value)}
                                placeholder="config/bern/flight_declaration.json"
                            />
                        </div>

                        <div className={styles.paramItem}>
                            <label style={{ display: 'block', fontSize: '12px', fontWeight: 500, marginBottom: '6px', color: 'var(--text-secondary)' }}>Flight Declaration via Operational Intent</label>
                            <input
                                type="text"
                                className={styles.paramInput}
                                value={config.data_files.flight_declaration_via_operational_intent || ''}
                                onChange={(e) => updateDataFiles('flight_declaration_via_operational_intent', e.target.value)}
                                placeholder="config/bern/flight_declaration_via_operational_intent.json"
                            />
                        </div>

                        <div className={styles.paramItem}>
                            <label style={{ display: 'block', fontSize: '12px', fontWeight: 500, marginBottom: '6px', color: 'var(--text-secondary)' }}>Geo Fence</label>
                            <input
                                type="text"
                                className={styles.paramInput}
                                value={config.data_files.geo_fence || ''}
                                onChange={(e) => updateDataFiles('geo_fence', e.target.value)}
                                placeholder="config/geo_fences.json"
                            />
                        </div>
                    </div>
                )}
            </div>

            {/* Air Traffic Simulator Section */}
            <div className={styles.configSection}>
                {showHelp && <Tooltip text={sectionTooltips.air_traffic} />}
                <button
                    onClick={() => toggleSection('air_traffic')}
                    className={styles.configSectionHeader}
                    style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px',
                        width: '100%',
                        padding: '8px',
                        background: 'var(--bg-secondary)',
                        border: '1px solid var(--border-color)',
                        borderRadius: '4px',
                        cursor: 'pointer',
                        color: 'var(--text-primary)',
                        fontSize: '13px',
                        fontWeight: 500
                    }}
                >
                    {expandedSections.has('air_traffic') ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                    <Settings size={16} />
                    Air Traffic Simulator
                </button>

                {expandedSections.has('air_traffic') && (
                    <div style={{ padding: '12px 4px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
                        <div className={styles.paramItem}>
                            <label style={{ display: 'block', fontSize: '12px', fontWeight: 500, marginBottom: '6px', color: 'var(--text-secondary)' }}>Number of Aircraft</label>
                            <input
                                type="number"
                                className={styles.paramInput}
                                value={config.air_traffic_simulator_settings.number_of_aircraft || 3}
                                onChange={(e) => updateAirTrafficSimulator('number_of_aircraft', parseInt(e.target.value))}
                                min="1"
                                max="100"
                            />
                        </div>

                        <div className={styles.paramItem}>
                            <label style={{ display: 'block', fontSize: '12px', fontWeight: 500, marginBottom: '6px', color: 'var(--text-secondary)' }}>Simulation Duration (seconds)</label>
                            <input
                                type="number"
                                className={styles.paramInput}
                                value={config.air_traffic_simulator_settings.simulation_duration || 10}
                                onChange={(e) => updateAirTrafficSimulator('simulation_duration', parseInt(e.target.value))}
                                min="1"
                                max="3600"
                            />
                        </div>

                        <div className={styles.paramItem}>
                            <label style={{ display: 'block', fontSize: '12px', fontWeight: 500, marginBottom: '6px', color: 'var(--text-secondary)' }}>Single or Multiple Sensors</label>
                            <select
                                className={styles.paramInput}
                                value={config.air_traffic_simulator_settings.single_or_multiple_sensors || 'multiple'}
                                onChange={(e) => updateAirTrafficSimulator('single_or_multiple_sensors', e.target.value)}
                            >
                                <option value="single">single</option>
                                <option value="multiple">multiple</option>
                            </select>
                        </div>

                        <div className={styles.paramItem}>
                            <label style={{ display: 'block', fontSize: '12px', fontWeight: 500, marginBottom: '6px', color: 'var(--text-secondary)' }}>Sensor IDs (comma-separated)</label>
                            <input
                                type="text"
                                className={styles.paramInput}
                                value={config.air_traffic_simulator_settings.sensor_ids?.join(', ') || ''}
                                onChange={(e) => updateSensorIds(e.target.value)}
                                placeholder="a0b7d47e5eac45dc8cbaf47e6fe0e558"
                            />
                        </div>
                    </div>
                )}
            </div>

            {/* BlueSky Air Traffic Simulator Section */}
            <div className={styles.configSection}>
                {showHelp && <Tooltip text={sectionTooltips.blue_sky_air_traffic} />}
                <button
                    onClick={() => toggleSection('blue_sky_air_traffic')}
                    className={styles.configSectionHeader}
                    style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px',
                        width: '100%',
                        padding: '8px',
                        background: 'var(--bg-secondary)',
                        border: '1px solid var(--border-color)',
                        borderRadius: '4px',
                        cursor: 'pointer',
                        color: 'var(--text-primary)',
                        fontSize: '13px',
                        fontWeight: 500
                    }}
                >
                    {expandedSections.has('blue_sky_air_traffic') ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                    <Settings size={16} />
                    BlueSky Air Traffic Simulator
                </button>

                {expandedSections.has('blue_sky_air_traffic') && (
                    <div style={{ padding: '12px 4px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
                        <div className={styles.paramItem}>
                            <label style={{ display: 'block', fontSize: '12px', fontWeight: 500, marginBottom: '6px', color: 'var(--text-secondary)' }}>Number of Aircraft</label>
                            <input
                                type="number"
                                className={styles.paramInput}
                                value={config.blue_sky_air_traffic_simulator_settings?.number_of_aircraft || 3}
                                onChange={(e) => updateBlueSkyAirTrafficSimulator('number_of_aircraft', parseInt(e.target.value))}
                                min="1"
                                max="100"
                            />
                        </div>

                        <div className={styles.paramItem}>
                            <label style={{ display: 'block', fontSize: '12px', fontWeight: 500, marginBottom: '6px', color: 'var(--text-secondary)' }}>Simulation Duration (seconds)</label>
                            <input
                                type="number"
                                className={styles.paramInput}
                                value={config.blue_sky_air_traffic_simulator_settings?.simulation_duration_seconds || 30}
                                onChange={(e) => updateBlueSkyAirTrafficSimulator('simulation_duration_seconds', parseInt(e.target.value))}
                                min="1"
                                max="3600"
                            />
                        </div>

                        <div className={styles.paramItem}>
                            <label style={{ display: 'block', fontSize: '12px', fontWeight: 500, marginBottom: '6px', color: 'var(--text-secondary)' }}>Single or Multiple Sensors</label>
                            <select
                                className={styles.paramInput}
                                value={config.blue_sky_air_traffic_simulator_settings?.single_or_multiple_sensors || 'multiple'}
                                onChange={(e) => updateBlueSkyAirTrafficSimulator('single_or_multiple_sensors', e.target.value)}
                            >
                                <option value="single">single</option>
                                <option value="multiple">multiple</option>
                            </select>
                        </div>

                        <div className={styles.paramItem}>
                            <label style={{ display: 'block', fontSize: '12px', fontWeight: 500, marginBottom: '6px', color: 'var(--text-secondary)' }}>Sensor IDs (comma-separated)</label>
                            <input
                                type="text"
                                className={styles.paramInput}
                                value={config.blue_sky_air_traffic_simulator_settings?.sensor_ids?.join(', ') || ''}
                                onChange={(e) => updateBlueSkySensorIds(e.target.value)}
                                placeholder="562e6297036a4adebb4848afcd1ede90"
                            />
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

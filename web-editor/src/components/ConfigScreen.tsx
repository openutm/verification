import { useEffect, useState } from 'react';
import { ArrowLeft, Save, RefreshCw, Loader2, AlertCircle, CheckCircle2 } from 'lucide-react';
import btnStyles from '../styles/Button.module.css';

// Schema mirrors the JSON returned by GET /api/config and the editable subset
// accepted by PUT /api/config. Optional sections may be null on the wire.
interface FlightBlenderAuth {
    type: string;
    client_id?: string;
    client_secret?: string;
    audience?: string;
    scopes?: string[];
    token_endpoint?: string;
    passport_base_url?: string;
}
interface FlightBlender { url: string; auth: FlightBlenderAuth; }
interface OpenSky { auth: FlightBlenderAuth; }
interface AMQP {
    url: string;
    exchange_name: string;
    exchange_type: string;
    routing_key: string;
    queue_name: string;
}
interface AirTrafficSim {
    number_of_aircraft: number;
    simulation_duration: number;
    single_or_multiple_sensors: 'single' | 'multiple';
    sensor_ids: string[];
    session_ids: string[];
}
interface DataFiles {
    trajectory?: string | null;
    simulation?: string | null;
    flight_declaration?: string | null;
    flight_declaration_via_operational_intent?: string | null;
    geo_fence?: string | null;
}
interface DeploymentDetails {
    name: string;
    version: string;
    notes: string;
}
interface AllureReporting {
    enabled: boolean;
    capture_http: boolean;
    results_dir: string;
}
interface Reporting {
    output_dir: string;
    formats: string[];
    deployment_details: DeploymentDetails;
    allure: AllureReporting;
}
interface FullConfig {
    version: string;
    run_id: string;
    config_path: string;
    flight_blender: FlightBlender;
    opensky: OpenSky;
    amqp: AMQP | null;
    air_traffic_simulator_settings: AirTrafficSim | null;
    data_files: DataFiles;
    reporting: Reporting;
}

const navigateBack = () => {
    globalThis.location.hash = '';
};

const labelStyle: React.CSSProperties = {
    display: 'block',
    fontSize: '12px',
    fontWeight: 500,
    marginBottom: '4px',
    color: 'var(--text-secondary)',
};

const inputStyle: React.CSSProperties = {
    width: '100%',
    padding: '6px 8px',
    background: 'var(--bg-tertiary)',
    border: '1px solid var(--border-color)',
    borderRadius: '4px',
    color: 'var(--text-primary)',
    fontSize: '13px',
    fontFamily: 'inherit',
    boxSizing: 'border-box',
};

const sectionStyle: React.CSSProperties = {
    background: 'var(--bg-secondary)',
    border: '1px solid var(--border-color)',
    borderRadius: '6px',
    padding: '16px 20px',
    marginBottom: '16px',
};

const sectionTitleStyle: React.CSSProperties = {
    fontSize: '14px',
    fontWeight: 600,
    color: 'var(--text-primary)',
    marginTop: 0,
    marginBottom: '12px',
    paddingBottom: '8px',
    borderBottom: '1px solid var(--border-color)',
};

const gridTwoCol: React.CSSProperties = {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: '12px',
};

interface FieldProps {
    label: string;
    value: string | number | undefined | null;
    onChange: (v: string) => void;
    type?: string;
    placeholder?: string;
}
const Field = ({ label, value, onChange, type = 'text', placeholder }: FieldProps) => (
    <div>
        <label style={labelStyle}>{label}</label>
        <input
            type={type}
            style={inputStyle}
            value={value ?? ''}
            placeholder={placeholder}
            onChange={(e) => onChange(e.target.value)}
        />
    </div>
);

export default function ConfigScreen() {
    const [config, setConfig] = useState<FullConfig | null>(null);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [message, setMessage] = useState<{ kind: 'ok' | 'err'; text: string } | null>(null);

    const load = async () => {
        setLoading(true);
        setMessage(null);
        try {
            const res = await fetch('/api/config');
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data: FullConfig = await res.json();
            setConfig(data);
        } catch (err) {
            setMessage({ kind: 'err', text: `Failed to load config: ${err}` });
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { load(); }, []);

    const save = async () => {
        if (!config) return;
        setSaving(true);
        setMessage(null);
        try {
            const payload = {
                flight_blender: config.flight_blender,
                opensky: config.opensky,
                amqp: config.amqp,
                air_traffic_simulator_settings: config.air_traffic_simulator_settings,
                data_files: config.data_files,
                reporting: config.reporting,
            };
            const res = await fetch('/api/config', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            const body = await res.json();
            if (!res.ok || body.status === 'error') {
                throw new Error(body.message || body.error || `HTTP ${res.status}`);
            }
            setMessage({
                kind: 'ok',
                text: body.status === 'saved'
                    ? `Saved to ${body.config_path} and reloaded.`
                    : `Saved but reload failed: ${body.error}`,
            });
        } catch (err) {
            setMessage({ kind: 'err', text: `Save failed: ${err}` });
        } finally {
            setSaving(false);
        }
    };

    if (loading) {
        return (
            <div style={{ padding: '40px', display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-secondary)' }}>
                <Loader2 className="spin" size={18} /> Loading server config…
            </div>
        );
    }

    if (!config) {
        return (
            <div style={{ padding: '40px' }}>
                <div style={{ color: 'var(--danger, #ff6b6b)' }}>{message?.text || 'No config available.'}</div>
                <button className={btnStyles.button} onClick={navigateBack} style={{ marginTop: '16px' }}>
                    <ArrowLeft size={14} /> Back
                </button>
            </div>
        );
    }

    const updateFB = (patch: Partial<FlightBlender>) =>
        setConfig({ ...config, flight_blender: { ...config.flight_blender, ...patch } });
    const updateFBAuth = (patch: Partial<FlightBlenderAuth>) =>
        setConfig({ ...config, flight_blender: { ...config.flight_blender, auth: { ...config.flight_blender.auth, ...patch } } });
    const updateOpenSkyAuth = (patch: Partial<FlightBlenderAuth>) =>
        setConfig({ ...config, opensky: { auth: { ...config.opensky.auth, ...patch } } });
    // Defaults mirror the backend AMQPConfig model so seeding an empty
    // section doesn't silently overwrite users' existing values with mismatched
    // defaults when only one field is being edited.
    const updateAMQP = (patch: Partial<AMQP>) =>
        setConfig({ ...config, amqp: { ...(config.amqp ?? { url: '', exchange_name: 'operational_events', exchange_type: 'direct', routing_key: '#', queue_name: '' }), ...patch } });
    const updateATS = (patch: Partial<AirTrafficSim>) =>
        setConfig({
            ...config,
            air_traffic_simulator_settings: {
                ...(config.air_traffic_simulator_settings ?? {
                    number_of_aircraft: 0,
                    simulation_duration: 0,
                    single_or_multiple_sensors: 'single',
                    sensor_ids: [],
                    session_ids: [],
                }),
                ...patch,
            },
        });
    const updateDF = (patch: Partial<DataFiles>) =>
        setConfig({ ...config, data_files: { ...config.data_files, ...patch } });
    const updateReporting = (patch: Partial<Reporting>) =>
        setConfig({ ...config, reporting: { ...config.reporting, ...patch } });
    const updateDeployment = (patch: Partial<DeploymentDetails>) =>
        setConfig({
            ...config,
            reporting: {
                ...config.reporting,
                deployment_details: { ...config.reporting.deployment_details, ...patch },
            },
        });
    const updateAllure = (patch: Partial<AllureReporting>) =>
        setConfig({
            ...config,
            reporting: {
                ...config.reporting,
                allure: { ...config.reporting.allure, ...patch },
            },
        });

    const fb = config.flight_blender;
    const os = config.opensky;
    const amqp = config.amqp;
    const ats = config.air_traffic_simulator_settings;
    const df = config.data_files;
    const rep = config.reporting;

    return (
        <div style={{ width: '100%', height: '100%', overflow: 'auto', background: 'var(--bg-primary)' }}>
            <div style={{
                position: 'sticky',
                top: 0,
                zIndex: 10,
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
                padding: '12px 24px',
                background: 'var(--bg-secondary)',
                borderBottom: '1px solid var(--border-color)',
            }}>
                <button className={btnStyles.button} onClick={navigateBack} type="button">
                    <ArrowLeft size={14} /> Back
                </button>
                <h2 style={{ margin: 0, fontSize: '16px', color: 'var(--text-primary)' }}>Server Configuration</h2>
                <span style={{ fontSize: '12px', color: 'var(--text-secondary)', marginLeft: '4px' }}>
                    {config.config_path}
                </span>
                <div style={{ marginLeft: 'auto', display: 'flex', gap: '8px', alignItems: 'center' }}>
                    {message && (
                        <span style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '6px',
                            fontSize: '12px',
                            color: message.kind === 'ok' ? 'var(--success, #4caf50)' : 'var(--danger, #ff6b6b)',
                        }}>
                            {message.kind === 'ok' ? <CheckCircle2 size={14} /> : <AlertCircle size={14} />}
                            {message.text}
                        </span>
                    )}
                    <button className={btnStyles.button} onClick={load} disabled={saving} type="button" title="Reload from disk">
                        <RefreshCw size={14} /> Reload
                    </button>
                    <button className={`${btnStyles.button} ${btnStyles.primary}`} onClick={save} disabled={saving} type="button">
                        {saving ? <Loader2 size={14} className="spin" /> : <Save size={14} />}
                        Save & Apply
                    </button>
                </div>
            </div>

            <div style={{ padding: '20px 24px', maxWidth: '1100px' }}>
                <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: 0 }}>
                    Edits here are written back to the YAML file shown above (comments preserved) and applied
                    to the running server immediately. Suite definitions are intentionally not editable from the GUI.
                </p>

                {/* Flight Blender */}
                <div style={sectionStyle}>
                    <h3 style={sectionTitleStyle}>Flight Blender</h3>
                    <Field label="URL" value={fb.url} onChange={(v) => updateFB({ url: v })}
                        placeholder="http://host.docker.internal:8000" />
                    <div style={{ ...gridTwoCol, marginTop: '12px' }}>
                        <div>
                            <label style={labelStyle}>Auth Type</label>
                            <select style={inputStyle} value={fb.auth.type}
                                onChange={(e) => updateFBAuth({ type: e.target.value })}>
                                <option value="none">none</option>
                                <option value="passport">passport</option>
                                <option value="oauth2">oauth2</option>
                            </select>
                        </div>
                        <Field label="Audience" value={fb.auth.audience} onChange={(v) => updateFBAuth({ audience: v })} />
                    </div>
                    <div style={{ marginTop: '12px' }}>
                        <Field label="Scopes (comma-separated)"
                            value={fb.auth.scopes?.join(', ') ?? ''}
                            onChange={(v) => updateFBAuth({ scopes: v.split(',').map(s => s.trim()).filter(Boolean) })} />
                    </div>
                    {fb.auth.type !== 'none' && (
                        <div style={{ ...gridTwoCol, marginTop: '12px' }}>
                            <Field label="Client ID" value={fb.auth.client_id} onChange={(v) => updateFBAuth({ client_id: v })} />
                            <Field label="Client Secret" type="password" value={fb.auth.client_secret} onChange={(v) => updateFBAuth({ client_secret: v })} />
                            <Field label="Token Endpoint" value={fb.auth.token_endpoint} onChange={(v) => updateFBAuth({ token_endpoint: v })} />
                            <Field label="Passport Base URL" value={fb.auth.passport_base_url} onChange={(v) => updateFBAuth({ passport_base_url: v })} />
                        </div>
                    )}
                </div>

                {/* AMQP */}
                <div style={sectionStyle}>
                    <h3 style={sectionTitleStyle}>AMQP / RabbitMQ</h3>
                    <Field label="URL" value={amqp?.url} onChange={(v) => updateAMQP({ url: v })}
                        placeholder="amqp://guest:guest@host.docker.internal:5672/" />
                    <div style={{ ...gridTwoCol, marginTop: '12px' }}>
                        <Field label="Exchange Name" value={amqp?.exchange_name} onChange={(v) => updateAMQP({ exchange_name: v })} />
                        <Field label="Exchange Type" value={amqp?.exchange_type} onChange={(v) => updateAMQP({ exchange_type: v })} />
                        <Field label="Routing Key" value={amqp?.routing_key} onChange={(v) => updateAMQP({ routing_key: v })} />
                        <Field label="Queue Name (empty = auto)" value={amqp?.queue_name} onChange={(v) => updateAMQP({ queue_name: v })} />
                    </div>
                </div>

                {/* OpenSky */}
                <div style={sectionStyle}>
                    <h3 style={sectionTitleStyle}>OpenSky Network</h3>
                    <div style={gridTwoCol}>
                        <div>
                            <label style={labelStyle}>Auth Type</label>
                            <select style={inputStyle} value={os.auth.type}
                                onChange={(e) => updateOpenSkyAuth({ type: e.target.value })}>
                                <option value="none">none</option>
                                <option value="oauth2">oauth2</option>
                            </select>
                        </div>
                        <div />
                        <Field label="Client ID" value={os.auth.client_id} onChange={(v) => updateOpenSkyAuth({ client_id: v })} />
                        <Field label="Client Secret" type="password" value={os.auth.client_secret} onChange={(v) => updateOpenSkyAuth({ client_secret: v })} />
                    </div>
                </div>

                {/* Air Traffic Simulator */}
                <div style={sectionStyle}>
                    <h3 style={sectionTitleStyle}>Air Traffic Simulator (defaults)</h3>
                    <div style={gridTwoCol}>
                        <Field label="Number of Aircraft" type="number" value={ats?.number_of_aircraft}
                            onChange={(v) => updateATS({ number_of_aircraft: Number.parseInt(v, 10) || 0 })} />
                        <Field label="Simulation Duration (seconds)" type="number" value={ats?.simulation_duration}
                            onChange={(v) => updateATS({ simulation_duration: Number.parseInt(v, 10) || 0 })} />
                        <div>
                            <label style={labelStyle}>Single / Multiple Sensors</label>
                            <select style={inputStyle} value={ats?.single_or_multiple_sensors ?? 'single'}
                                onChange={(e) => updateATS({ single_or_multiple_sensors: e.target.value as 'single' | 'multiple' })}>
                                <option value="single">single</option>
                                <option value="multiple">multiple</option>
                            </select>
                        </div>
                        <div />
                        <Field label="Sensor IDs (comma-separated)"
                            value={ats?.sensor_ids?.join(', ') ?? ''}
                            onChange={(v) => updateATS({ sensor_ids: v.split(',').map(s => s.trim()).filter(Boolean) })} />
                        <Field label="Session IDs (comma-separated)"
                            value={ats?.session_ids?.join(', ') ?? ''}
                            onChange={(v) => updateATS({ session_ids: v.split(',').map(s => s.trim()).filter(Boolean) })} />
                    </div>
                </div>

                {/* Data Files */}
                <div style={sectionStyle}>
                    <h3 style={sectionTitleStyle}>Data Files</h3>
                    <Field label="Trajectory" value={df.trajectory} onChange={(v) => updateDF({ trajectory: v || null })} />
                    <div style={{ marginTop: '12px' }}>
                        <Field label="Simulation (.scn)" value={df.simulation} onChange={(v) => updateDF({ simulation: v || null })} />
                    </div>
                    <div style={{ marginTop: '12px' }}>
                        <Field label="Flight Declaration" value={df.flight_declaration}
                            onChange={(v) => updateDF({ flight_declaration: v || null })} />
                    </div>
                    <div style={{ marginTop: '12px' }}>
                        <Field label="Flight Declaration via Operational Intent"
                            value={df.flight_declaration_via_operational_intent}
                            onChange={(v) => updateDF({ flight_declaration_via_operational_intent: v || null })} />
                    </div>
                    <div style={{ marginTop: '12px' }}>
                        <Field label="Geo-fence" value={df.geo_fence} onChange={(v) => updateDF({ geo_fence: v || null })} />
                    </div>
                </div>

                {/* Reporting */}
                <div style={sectionStyle}>
                    <h3 style={sectionTitleStyle}>Reporting</h3>
                    <div style={gridTwoCol}>
                        <Field label="Output Directory" value={rep.output_dir}
                            onChange={(v) => updateReporting({ output_dir: v })}
                            placeholder="reports" />
                        <Field label="Formats (comma-separated)"
                            value={rep.formats?.join(', ') ?? ''}
                            onChange={(v) => updateReporting({
                                formats: v.split(',').map(s => s.trim()).filter(Boolean),
                            })}
                            placeholder="json, html, log" />
                    </div>

                    <h4 style={{ ...sectionTitleStyle, fontSize: '13px', marginTop: '16px' }}>
                        Deployment Details
                    </h4>
                    <div style={gridTwoCol}>
                        <Field label="Name" value={rep.deployment_details.name}
                            onChange={(v) => updateDeployment({ name: v })} />
                        <Field label="Version" value={rep.deployment_details.version}
                            onChange={(v) => updateDeployment({ version: v })} />
                    </div>
                    <div style={{ marginTop: '12px' }}>
                        <Field label="Notes" value={rep.deployment_details.notes}
                            onChange={(v) => updateDeployment({ notes: v })} />
                    </div>

                    <h4 style={{ ...sectionTitleStyle, fontSize: '13px', marginTop: '16px' }}>
                        Allure
                    </h4>
                    <div style={{ display: 'flex', gap: '24px', marginBottom: '12px', flexWrap: 'wrap' }}>
                        <label style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '13px', color: 'var(--text-primary)' }}>
                            <input
                                type="checkbox"
                                checked={rep.allure.enabled}
                                onChange={(e) => updateAllure({ enabled: e.target.checked })}
                            /><span>Enabled</span>
                        </label>
                        <label style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '13px', color: 'var(--text-primary)' }}>
                            <input
                                type="checkbox"
                                checked={rep.allure.capture_http}
                                onChange={(e) => updateAllure({ capture_http: e.target.checked })}
                            /><span>Capture HTTP exchanges</span>
                        </label>
                    </div>
                    <Field label="Results Directory (relative to per-run output dir)"
                        value={rep.allure.results_dir}
                        onChange={(v) => updateAllure({ results_dir: v })}
                        placeholder="allure-results" />
                </div>

                <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '8px' }}>
                    Read-only: <strong>version</strong> {config.version} &middot; <strong>run_id</strong> {config.run_id}
                </div>
            </div>
        </div>
    );
}

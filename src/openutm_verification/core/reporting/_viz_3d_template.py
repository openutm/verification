"""HTML template for the replay-capable 3D flight visualization.

Extracted from ``visualize_flight.py`` to reduce file size and satisfy SRP.
The ``__DATA__`` placeholder is replaced at render time with a JSON payload.
"""

REPLAY_3D_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Flight Replay 3D — Multi-Intruder HUD</title>
    <style>
        html, body {
            margin: 0; width: 100%; height: 100%; overflow: hidden;
            font-family: Inter, Arial, sans-serif; background: #111; color: #f4f4f4;
        }
        #canvas-root { width: 100%; height: 100%; }
        .hud {
            background: rgba(18, 18, 18, 0.78); border: 1px solid rgba(255,255,255,0.15);
            border-radius: 10px; padding: 10px 12px; backdrop-filter: blur(4px);
        }
        .hud-main { position: absolute; top: 12px; left: 12px; right: 12px; z-index: 3; }
        .hud-stack {
            position: absolute; top: 112px; right: 12px; width: min(500px, 46vw);
            display: flex; flex-direction: column; gap: 8px; z-index: 3;
            max-height: calc(100vh - 124px); overflow-y: auto;
        }
        .controls-row { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }
        button, select {
            background: #222; color: #f4f4f4; border: 1px solid #555;
            border-radius: 6px; padding: 5px 9px; cursor: pointer; font-size: 12px;
        }
        button:hover { background: #333; }
        input[type=range] { flex: 1; min-width: 120px; }
        .time-label { font-size: 12px; white-space: nowrap; opacity: 0.9; min-width: 170px; }
        .legend { margin-top: 6px; display: flex; gap: 12px; font-size: 11px; opacity: 0.9; flex-wrap: wrap; }
        .dot { width: 9px; height: 9px; border-radius: 50%; display: inline-block; margin-right: 4px; vertical-align: middle; }
        .hud-card {
            background: rgba(18, 18, 18, 0.84); border: 1px solid rgba(255,255,255,0.15);
            border-radius: 10px; padding: 10px 12px;
        }
        .hud-card h3 {
            margin: 0 0 6px 0; font-size: 13px; font-weight: 600;
            display: flex; justify-content: space-between; align-items: center;
        }
        .hud-card h3 .badge { font-size: 11px; font-weight: 400; opacity: 0.7; }
        .intruder-card {
            border-radius: 8px; padding: 8px 10px; margin-bottom: 6px;
            border-left: 3px solid #555; background: rgba(0,0,0,0.25);
        }
        .intruder-card:last-child { margin-bottom: 0; }
        .intruder-header { display: flex; justify-content: space-between; align-items: center; cursor: pointer; }
        .intruder-header .icao { font-weight: 600; font-size: 12px; }
        .intruder-header .level-badge { font-size: 11px; font-weight: 500; padding: 1px 6px; border-radius: 4px; }
        .intruder-header .range-label { font-size: 11px; opacity: 0.8; }
        .intruder-detail { margin-top: 6px; font-size: 11px; line-height: 1.5; display: none; }
        .intruder-detail.expanded { display: block; }
        .intruder-card.resolved { opacity: 0.6; }
        .intruder-card.resolved .intruder-detail { display: none; }
        .metrics { display: grid; grid-template-columns: 1fr 1fr; gap: 2px 12px; }
        .metrics .metric-label { opacity: 0.6; }
        .metrics .metric-value { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
        .log-feed { max-height: 200px; overflow-y: auto; font-size: 11px; line-height: 1.4; }
        .log-entry {
            padding: 3px 6px; border-left: 2px solid transparent;
            margin-bottom: 1px; border-radius: 2px;
        }
        .log-entry:hover { background: rgba(255,255,255,0.05); }
        .log-entry .entry-time { opacity: 0.6; font-family: ui-monospace, monospace; min-width: 36px; display: inline-block; }
        .log-entry .entry-icao { font-weight: 600; min-width: 64px; display: inline-block; }
        .log-entry .entry-type { opacity: 0.7; min-width: 80px; display: inline-block; }
        .filter-bar { display: flex; gap: 4px; margin-bottom: 6px; flex-wrap: wrap; }
        .filter-btn {
            font-size: 10px; padding: 2px 8px; border-radius: 4px;
            background: #333; border: 1px solid #555; cursor: pointer;
        }
        .filter-btn.active { background: #444; border-color: #82b1ff; color: #82b1ff; }
        .alert-timeline { font-size: 11px; line-height: 1.6; max-height: 220px; overflow-y: auto; }
        .alert-entry { padding: 2px 6px; border-radius: 3px; }
        .alert-entry.current { background: rgba(255,255,255,0.08); outline: 1px solid rgba(255,255,255,0.2); }
        .alert-entry.future { opacity: 0.4; }
        .alert-entry .arrow { opacity: 0.7; }
        .json-toggle { font-size: 10px; cursor: pointer; color: #82b1ff; opacity: 0.5; float: right; margin-left: 6px; line-height: 1; }
        .json-toggle:hover { opacity: 1; }
        .raw-json {
            display: none; clear: both; margin-top: 4px; padding: 6px;
            background: rgba(0,0,0,0.3); border: 1px solid rgba(255,255,255,0.1);
            border-radius: 6px; font-size: 10px;
            font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
            white-space: pre-wrap; word-break: break-word; max-height: 160px; overflow-y: auto;
        }
    </style>
</head>
<body>
    <div id="canvas-root"></div>

    <div class="hud hud-main">
        <div class="controls-row">
            <button id="playPauseBtn">&#9654; Play</button>
            <button id="prevLogBtn" title="Previous log entry">&#9664; Prev</button>
            <button id="nextLogBtn" title="Next log entry">Next &#9654;</button>
            <button id="prevSecBtn" title="Previous second">&#9664;&#9664; 1s</button>
            <button id="nextSecBtn" title="Next second">1s &#9654;&#9654;</button>
            <select id="speedSelect">
                <option value="600">0.5x</option>
                <option value="300" selected>1x</option>
                <option value="150">2x</option>
                <option value="75">4x</option>
            </select>
            <input id="timelineSlider" type="range" min="0" step="1" value="0" />
            <span id="timeLabel" class="time-label">Log 0/0 &bull; t = 0s</span>
        </div>
        <div class="legend" id="legendBar">
            <span><span class="dot" style="background:#ff5252"></span>WARNING</span>
            <span><span class="dot" style="background:#ff9800"></span>CAUTION</span>
            <span><span class="dot" style="background:#82b1ff"></span>ADVISORY</span>
            <span><span class="dot" style="background:#b0bec5"></span>Non-alert</span>
            <span><span class="dot" style="background:#1f77b4"></span>WC vol</span>
            <span><span class="dot" style="background:#d62728"></span>NMAC vol</span>
        </div>
    </div>

    <div class="hud-stack">
        <div class="hud-card" id="sharedFilterCard">
            <div class="filter-bar" id="ownshipFilters"></div>
            <div class="filter-bar" id="intruderFilters"></div>
        </div>
        <div class="hud-card" id="rosterCard">
            <h3>Active Intruders <span class="badge" id="rosterBadge">0/0</span></h3>
            <div id="rosterBody"></div>
        </div>
        <div class="hud-card" id="alertsCard">
            <h3>Alert Lifecycle <span class="badge" id="alertsBadge">0 events</span></h3>
            <div class="alert-timeline" id="alertsBody"></div>
        </div>
        <div class="hud-card" id="amqpCard">
            <h3>AMQP Messages <span class="badge" id="amqpBadge">0 records</span></h3>
            <div class="log-feed" id="amqpFeed"></div>
        </div>
        <div class="hud-card" id="incidentCard">
            <h3>Incident Logs <span class="badge" id="incidentBadge">0 periodic</span></h3>
            <div class="log-feed" id="incidentFeed"></div>
        </div>
    </div>

    <script type="importmap">
    {
        "imports": {
            "three": "https://unpkg.com/three@0.160.0/build/three.module.js",
            "three/addons/": "https://unpkg.com/three@0.160.0/examples/jsm/"
        }
    }
    </script>
    <script type="module">
        import * as THREE from "three";
        import { OrbitControls } from "three/addons/controls/OrbitControls.js";

        const DATA = __DATA__;

        /* ── Scene setup ── */
        const root = document.getElementById('canvas-root');
        const scene = new THREE.Scene();
        scene.background = new THREE.Color(0x121212);

        const camera = new THREE.PerspectiveCamera(58, window.innerWidth / window.innerHeight, 0.1, 50000);
        const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance', stencil: false });
        renderer.setSize(window.innerWidth, window.innerHeight);
        renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
        root.appendChild(renderer.domElement);

        const controls = new OrbitControls(camera, renderer.domElement);
        controls.enableDamping = true;
        controls.dampingFactor = 0.01;
        controls.minDistance = 1;
        controls.maxDistance = 50000;
        controls.zoomSpeed = 1.2;
        controls.rotateSpeed = 0.35;
        controls.minPolarAngle = 0.3;
        controls.maxPolarAngle = Math.PI * 0.48;

        scene.add(new THREE.AmbientLight(0xffffff, 0.55));
        const dirLight = new THREE.DirectionalLight(0xffffff, 0.75);
        dirLight.position.set(400, 600, 300);
        scene.add(dirLight);
        scene.add(new THREE.GridHelper(4000, 40, 0x555555, 0x2b2b2b));
        scene.add(new THREE.AxesHelper(120));

        /* ── Helpers ── */
        /* Binary search: returns count of points with t <= tSec (O(log N), zero alloc) */
        function getTrailEndIndex(track, tSec) {
            let lo = 0, hi = track.length;
            while (lo < hi) {
                const mid = (lo + hi) >> 1;
                track[mid].t <= tSec ? lo = mid + 1 : hi = mid;
            }
            return lo;
        }
        /* Pre-allocate a Float32Array position buffer for a track */
        function buildTrackGeometry(track) {
            const positions = new Float32Array(track.length * 3);
            for (let i = 0; i < track.length; i++) {
                positions[i * 3] = track[i].x;
                positions[i * 3 + 1] = track[i].y;
                positions[i * 3 + 2] = track[i].z;
            }
            const geom = new THREE.BufferGeometry();
            geom.setAttribute('position', new THREE.BufferAttribute(positions, 3));
            geom.setDrawRange(0, 0);
            return geom;
        }
        /* Legacy helpers kept for one-off use (velocity calc) */
        const getTrail = (track, tSec) => track.filter((p) => p.t <= tSec);
        const pointsToVectors = (points) => points.map((p) => new THREE.Vector3(p.x, p.y, p.z));

        /* ── Ownships (multi-ownship support) ── */
        let activeOwnshipIdx = 0;
        const ownshipObjects = DATA.ownships.map((ownship, idx) => {
            const color = new THREE.Color(ownship.color);
            const geom = buildTrackGeometry(ownship.track);
            const line = new THREE.Line(geom, new THREE.LineBasicMaterial({ color }));
            scene.add(line);
            const marker = new THREE.Mesh(new THREE.SphereGeometry(9, 20, 20), new THREE.MeshStandardMaterial({ color }));
            marker.visible = false;
            scene.add(marker);
            return { ownship, line, marker };
        });

        /* ── Ownship labels (from payload) ── */
        const ownshipLabels = (DATA.ownship_labels && DATA.ownship_labels.length > 0)
            ? DATA.ownship_labels
            : DATA.ownships.map(o => o.label);
        const multiOwnship = ownshipLabels.length > 1;

        /* ── Legend: dynamic ownship color dots ── */
        const legendBar = document.getElementById('legendBar');
        const ownshipLegendHtml = DATA.ownships.map(o =>
            '<span><span class="dot" style="background:' + o.color + '"></span>' + o.label + '</span>'
        ).join('');
        legendBar.innerHTML = ownshipLegendHtml + legendBar.innerHTML;

        /* ── Ownship label sprites (floating name tooltips) ── */
        for (const obj of ownshipObjects) {
            const canvas = document.createElement('canvas');
            canvas.width = 256; canvas.height = 48;
            const ctx = canvas.getContext('2d');
            ctx.fillStyle = 'rgba(0,0,0,0.6)';
            ctx.beginPath(); ctx.roundRect(0, 0, canvas.width, canvas.height, 8); ctx.fill();
            ctx.font = 'bold 22px Arial';
            ctx.fillStyle = obj.ownship.color;
            ctx.textAlign = 'center';
            ctx.fillText(obj.ownship.label, canvas.width / 2, 32);
            const texture = new THREE.CanvasTexture(canvas);
            const spriteMat = new THREE.SpriteMaterial({ map: texture, transparent: true, depthTest: false });
            const sprite = new THREE.Sprite(spriteMat);
            sprite.scale.set(100, 20, 1);
            sprite.visible = false;
            scene.add(sprite);
            obj.labelSprite = sprite;
        }

        /* ── Intruder objects (with per-intruder label sprites) ── */
        const ALERT_COLORS = { 3: 0xff5252, 2: 0xff9800, 1: 0x82b1ff, 0: 0xb0bec5 };
        const intruderObjects = DATA.intruders.map((intruder) => {
            const color = new THREE.Color(intruder.color);
            const geom = buildTrackGeometry(intruder.points);
            const line = new THREE.Line(geom, new THREE.LineBasicMaterial({ color }));
            const marker = new THREE.Mesh(new THREE.SphereGeometry(8, 16, 16), new THREE.MeshStandardMaterial({ color }));
            marker.visible = false;
            scene.add(line);
            scene.add(marker);

            /* Floating label sprite */
            const canvas = document.createElement('canvas');
            canvas.width = 256; canvas.height = 64;
            const ctx = canvas.getContext('2d');
            const texture = new THREE.CanvasTexture(canvas);
            const spriteMat = new THREE.SpriteMaterial({ map: texture, transparent: true, depthTest: false });
            const sprite = new THREE.Sprite(spriteMat);
            sprite.scale.set(120, 30, 1);
            sprite.visible = false;
            scene.add(sprite);

            return { intruder, line, marker, sprite, labelCanvas: canvas, labelCtx: ctx, labelTexture: texture, defaultColor: color.clone(), _lastAlertLevel: null, _lastEventType: null };
        });

        /* ── WC / NMAC volumes (one pair per ownship — always visible) ── */
        const wcVolumes = [];
        const nmacVolumes = [];
        for (let i = 0; i < DATA.ownships.length; i++) {
            const wc = new THREE.Mesh(
                new THREE.CylinderGeometry(DATA.volumes.wc_horizontal_m, DATA.volumes.wc_horizontal_m, 2 * DATA.volumes.wc_vertical_m, 48, 1, true),
                new THREE.MeshBasicMaterial({ color: 0x1f77b4, transparent: true, opacity: 0.12, wireframe: true }),
            );
            wc.visible = false;
            scene.add(wc);
            wcVolumes.push(wc);

            const nmac = new THREE.Mesh(
                new THREE.CylinderGeometry(DATA.volumes.nmac_horizontal_m, DATA.volumes.nmac_horizontal_m, 2 * DATA.volumes.nmac_vertical_m, 48, 1, true),
                new THREE.MeshBasicMaterial({ color: 0xd62728, transparent: true, opacity: 0.24, wireframe: true }),
            );
            nmac.visible = false;
            scene.add(nmac);
            nmacVolumes.push(nmac);
        }

        /* ── Geofence (legacy single + multi-ownship) — store lines for filter toggling ── */
        const geofenceColors = [0xff5555, 0x55aaff, 0x55ff55, 0xffaa55, 0xaa55ff];
        const geofenceEdgeColors = [0xff7777, 0x77bbff, 0x77ff77, 0xffbb77, 0xbb77ff];
        const geofenceLineGroups = [];
        const drawGeofence = (gf, colorIdx) => {
            const lines = [];
            if (!gf || !gf.corners || gf.corners.length < 3) return lines;
            const addLine = (pts, colorHex) => {
                const geom = new THREE.BufferGeometry().setFromPoints(pts.map((p) => new THREE.Vector3(p.x, p.y, p.z)));
                const ln = new THREE.Line(geom, new THREE.LineBasicMaterial({ color: colorHex }));
                scene.add(ln);
                lines.push(ln);
            };
            const bottom = gf.corners.map((p) => ({ x: p.x, y: gf.min_alt, z: p.z }));
            const top = gf.corners.map((p) => ({ x: p.x, y: gf.max_alt, z: p.z }));
            addLine([...bottom, bottom[0]], geofenceColors[colorIdx % geofenceColors.length]);
            addLine([...top, top[0]], geofenceColors[colorIdx % geofenceColors.length]);
            for (let i = 0; i < bottom.length; i += 1) addLine([bottom[i], top[i]], geofenceEdgeColors[colorIdx % geofenceEdgeColors.length]);
            return lines;
        };
        if (DATA.geofences && DATA.geofences.length > 0) {
            DATA.geofences.forEach((gf, idx) => geofenceLineGroups.push(drawGeofence(gf, idx)));
        } else if (DATA.geofence && DATA.geofence.corners && DATA.geofence.corners.length >= 3) {
            geofenceLineGroups.push(drawGeofence(DATA.geofence, 0));
        }

        /* ── Velocity vectors (1-second displacement arrows) ── */
        const ownshipArrows = ownshipObjects.map(obj => {
            const arrow = new THREE.ArrowHelper(
                new THREE.Vector3(1, 0, 0), new THREE.Vector3(), 1,
                new THREE.Color(obj.ownship.color).getHex(), 8, 4
            );
            arrow.visible = false;
            scene.add(arrow);
            return arrow;
        });
        const intruderArrows = intruderObjects.map(obj => {
            const arrow = new THREE.ArrowHelper(
                new THREE.Vector3(1, 0, 0), new THREE.Vector3(), 1,
                new THREE.Color(obj.intruder.color).getHex(), 8, 4
            );
            arrow.visible = false;
            scene.add(arrow);
            return arrow;
        });

        function getOneSecVelocity(track, currentT) {
            const endIdx = getTrailEndIndex(track, currentT);
            if (endIdx === 0) return null;
            const p0 = track[endIdx - 1];
            const aheadIdx = getTrailEndIndex(track, currentT + 1);
            if (aheadIdx > endIdx) {
                const p1 = track[aheadIdx - 1];
                const dt = p1.t - p0.t;
                if (dt > 0) {
                    const s = 1 / dt;
                    return new THREE.Vector3((p1.x - p0.x) * s, (p1.y - p0.y) * s, (p1.z - p0.z) * s);
                }
            }
            if (endIdx >= 2) {
                const pPrev = track[endIdx - 2];
                const dt = p0.t - pPrev.t;
                if (dt > 0) {
                    const s = 1 / dt;
                    return new THREE.Vector3((p0.x - pPrev.x) * s, (p0.y - pPrev.y) * s, (p0.z - pPrev.z) * s);
                }
            }
            return null;
        }

        function setArrowFromVelocity(arrow, pos, vel) {
            if (!vel || vel.length() < 0.5) { arrow.visible = false; return; }
            const len = vel.length();
            arrow.position.copy(pos);
            arrow.setDirection(vel.clone().normalize());
            arrow.setLength(len, Math.min(len * 0.2, 12), Math.min(len * 0.1, 6));
            arrow.visible = true;
        }

        /* ── Camera framing ── */
        const framingPoints = [...DATA.ownships.flatMap(o => o.track), ...DATA.intruders.flatMap((i) => i.points)];
        const allGeofences = (DATA.geofences && DATA.geofences.length > 0) ? DATA.geofences : (DATA.geofence ? [DATA.geofence] : []);
        for (const gf of allGeofences) {
            if (gf && gf.corners) {
                for (const c of gf.corners) {
                    framingPoints.push({ x: c.x, y: gf.min_alt, z: c.z });
                    framingPoints.push({ x: c.x, y: gf.max_alt, z: c.z });
                }
            }
        }
        if (framingPoints.length > 0) {
            const xs = framingPoints.map((p) => p.x), ys = framingPoints.map((p) => p.y), zs = framingPoints.map((p) => p.z);
            const minX = Math.min(...xs), maxX = Math.max(...xs);
            const minY = Math.min(...ys), maxY = Math.max(...ys);
            const minZ = Math.min(...zs), maxZ = Math.max(...zs);
            const cx = (minX + maxX) / 2, cy = (minY + maxY) / 2, cz = (minZ + maxZ) / 2;
            const size = Math.max(maxX - minX, maxY - minY, maxZ - minZ, 180);
            camera.position.set(cx + size * 0.09, cy + size * 0.07, cz + size * 0.08);
            controls.target.set(cx - size * 0.1, cy, cz);
        }

        /* ── DOM refs ── */
        const slider = document.getElementById('timelineSlider');
        const playPauseBtn = document.getElementById('playPauseBtn');
        const prevLogBtn = document.getElementById('prevLogBtn');
        const nextLogBtn = document.getElementById('nextLogBtn');
        const prevSecBtn = document.getElementById('prevSecBtn');
        const nextSecBtn = document.getElementById('nextSecBtn');
        const speedSelect = document.getElementById('speedSelect');
        const timeLabel = document.getElementById('timeLabel');

        /* ── Event data: JS-side filtering (proposal §3) ── */
        const unifiedTimeline = DATA.unified_timeline || [];
        const allIncidentEvents = [...((DATA.daa_events && DATA.daa_events.incident_logs) || [])].sort((a, b) => (a.t || 0) - (b.t || 0));
        const periodicEvents = allIncidentEvents.filter(e => (e.event_type || '').toLowerCase() === 'periodic_update');
        const lifecycleEvents = allIncidentEvents.filter(e => (e.event_type || '').toLowerCase() !== 'periodic_update');
        const amqpEvents = [...(DATA.amqp_messages || [])].sort((a, b) => (a.t || 0) - (b.t || 0));
        const allIcaos = [...new Set([...allIncidentEvents.map(e => e.intruder_icao).filter(Boolean), ...DATA.intruders.map(i => i.icao).filter(Boolean)])].sort();

        const maxT = Math.max(0, DATA.timeline.max_t || 0);
        /* Time-based fallback when no DAA events exist */
        const timeBasedMode = unifiedTimeline.length === 0 && maxT > 0;
        const logCount = timeBasedMode ? (maxT + 1) : (unifiedTimeline.length || 1);
        slider.max = String(Math.max(0, logCount - 1));

        /* ── Playback state ── */
        let currentLogIndex = 0;
        let isPlaying = false;
        let playSpeed = 300;

        /* ── Alert level helpers (ASTM F3442 §8.4.5 compliant) ── */
        const LEVEL_META = {
            3: { icon: '\\ud83d\\udd34', color: '#ff5252', label: 'Warning', bg: 'rgba(255,82,82,0.15)' },
            2: { icon: '\\ud83d\\udfe0', color: '#ff9800', label: 'Caution', bg: 'rgba(255,152,0,0.15)' },
            1: { icon: '\\ud83d\\udd35', color: '#82b1ff', label: 'Advisory', bg: 'rgba(130,177,255,0.15)' },
            0: { icon: '\\u26aa', color: '#b0bec5', label: 'Non Alert', bg: 'rgba(176,190,197,0.10)' },
        };
        const RESOLVED_META = { icon: '\\ud83d\\udfe2', color: '#4caf50', label: 'Resolved', bg: 'rgba(76,175,80,0.12)' };

        const getLevelMeta = (level, eventType) => {
            if (String(eventType || '').toLowerCase() === 'alert_resolved') return RESOLVED_META;
            const num = Number(level);
            if (LEVEL_META[num]) return LEVEL_META[num];
            const text = String(level || '').toUpperCase();
            if (text.includes('WARNING')) return LEVEL_META[3];
            if (text.includes('CAUTION')) return LEVEL_META[2];
            if (text.includes('ADVISORY')) return LEVEL_META[1];
            if (text.includes('NON')) return LEVEL_META[0];
            return { icon: '\\u26aa', color: '#90a4ae', label: String(level || 'Unknown'), bg: 'rgba(144,164,174,0.10)' };
        };

        const formatLevel = (val) => {
            if (val === null || val === undefined) return '';
            return String(val).replace(/[_-]+/g, ' ').toLowerCase().replace(/\\b\\w/g, c => c.toUpperCase());
        };

        const fmtNum = (v, d) => {
            const decimals = d !== undefined ? d : 1;
            return v !== null && v !== undefined && Number.isFinite(Number(v)) ? Number(v).toFixed(decimals) : '\\u2014';
        };

        const parseJsonSafe = (value) => {
            if (typeof value !== 'string') return value;
            const t = value.trim();
            if ((!t.startsWith('{') || !t.endsWith('}')) && (!t.startsWith('[') || !t.endsWith(']'))) return value;
            try { return JSON.parse(t); } catch { return value; }
        };

        /* Helper: generate a clickable JSON toggle + hidden <pre> block */
        let _jsonId = 0;
        const jsonToggleHtml = (obj) => {
            const id = '_rj' + (++_jsonId);
            const safeJson = JSON.stringify(obj, null, 2)
                .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
            return '<span class="json-toggle" data-target="' + id + '" title="Show JSON">{}</span>'
                 + '<pre class="raw-json" id="' + id + '">' + safeJson + '</pre>';
        };

        /* Delegated click handlers for JSON toggles and intruder expand/collapse */
        document.addEventListener('click', (e) => {
            const toggle = e.target.closest('.json-toggle');
            if (toggle) {
                const targetId = toggle.getAttribute('data-target');
                const el = targetId && document.getElementById(targetId);
                if (el) {
                    el.style.display = el.style.display === 'block' ? 'none' : 'block';
                    toggle.textContent = el.style.display === 'block' ? '\\u2716' : '{}';
                }
                return;
            }
            const header = e.target.closest('.intruder-header');
            if (header) {
                const detailId = header.getAttribute('data-detail');
                const el = detailId && document.getElementById(detailId);
                if (el) {
                    el.style.display = el.style.display === 'none' ? 'block' : 'none';
                }
            }
        });

        /* ── §8.2.6 / §8.2.7: Per-intruder state accumulator (ownship-aware, incremental) ── */
        let _stateCache = { logIndex: -1, ownFilter: null, states: new Map() };

        function getIntruderStates(logIndex) {
            const of = filterState.ownship;
            /* Reset cache on seek-backward or filter change */
            if (logIndex < _stateCache.logIndex || of !== _stateCache.ownFilter) {
                _stateCache = { logIndex: -1, ownFilter: of, states: new Map() };
            }
            for (let i = _stateCache.logIndex + 1; i <= logIndex && i < unifiedTimeline.length; i++) {
                const entry = unifiedTimeline[i];
                if (entry._source !== 'incident') continue;
                if ((entry.event_type || '').toLowerCase() === 'periodic_update') continue;
                const icao = entry.intruder_icao;
                if (!icao) continue;
                if (of !== null && entry.ownship_label && entry.ownship_label !== of) continue;
                const ownLabel = entry.ownship_label || '';
                const key = multiOwnship ? (icao + '|' + ownLabel) : icao;
                _stateCache.states.set(key, { ...entry, _lastSeenIndex: i, _key: key, _ownLabel: ownLabel });
            }
            _stateCache.logIndex = logIndex;
            return _stateCache.states;
        }

        /* ── Shared filter infrastructure (ownship row + intruder row) ── */
        const filterState = { ownship: null, intruder: null };

        function refreshAllHuds() {
            updateFrame(currentLogIndex);
        }

        const FILTER_DROPDOWN_THRESHOLD = 8;

        function buildSharedFilters() {
            const ownBar = document.getElementById('ownshipFilters');
            const intBar = document.getElementById('intruderFilters');

            /* Ownship row (hidden for single-ownship) */
            if (multiOwnship) {
                if (ownshipLabels.length > FILTER_DROPDOWN_THRESHOLD) {
                    const sel = document.createElement('select');
                    sel.id = 'ownshipSelect';
                    const allOpt = document.createElement('option');
                    allOpt.value = '';
                    allOpt.textContent = 'All Ownships (' + ownshipLabels.length + ')';
                    sel.appendChild(allOpt);
                    for (let i = 0; i < ownshipLabels.length; i++) {
                        const opt = document.createElement('option');
                        opt.value = ownshipLabels[i];
                        opt.textContent = ownshipLabels[i];
                        sel.appendChild(opt);
                    }
                    sel.addEventListener('change', () => {
                        const val = sel.value;
                        filterState.ownship = val || null;
                        activeOwnshipIdx = val ? ownshipLabels.indexOf(val) : 0;
                        refreshAllHuds();
                    });
                    ownBar.appendChild(sel);
                } else {
                    const allOwnBtn = document.createElement('button');
                    allOwnBtn.className = 'filter-btn active';
                    allOwnBtn.textContent = 'All Ownships';
                    allOwnBtn.addEventListener('click', () => {
                        filterState.ownship = null;
                        activeOwnshipIdx = 0;
                        syncOwnshipBar();
                        refreshAllHuds();
                    });
                    ownBar.appendChild(allOwnBtn);
                    for (let i = 0; i < ownshipLabels.length; i++) {
                        const lbl = ownshipLabels[i];
                        const btn = document.createElement('button');
                        btn.className = 'filter-btn';
                        btn.textContent = lbl;
                        btn.dataset.ownship = lbl;
                        btn.addEventListener('click', () => {
                            filterState.ownship = lbl;
                            activeOwnshipIdx = i;
                            syncOwnshipBar();
                            refreshAllHuds();
                        });
                        ownBar.appendChild(btn);
                    }
                }
            } else {
                ownBar.style.display = 'none';
            }

            /* Intruder row */
            if (allIcaos.length > FILTER_DROPDOWN_THRESHOLD) {
                const sel = document.createElement('select');
                sel.id = 'intruderSelect';
                const allOpt = document.createElement('option');
                allOpt.value = '';
                allOpt.textContent = 'All Intruders (' + allIcaos.length + ')';
                sel.appendChild(allOpt);
                for (const icao of allIcaos) {
                    const opt = document.createElement('option');
                    opt.value = icao;
                    opt.textContent = icao;
                    sel.appendChild(opt);
                }
                sel.addEventListener('change', () => {
                    filterState.intruder = sel.value || null;
                    refreshAllHuds();
                });
                intBar.appendChild(sel);
            } else {
                const allIntBtn = document.createElement('button');
                allIntBtn.className = 'filter-btn active';
                allIntBtn.textContent = 'All Intruders';
                allIntBtn.addEventListener('click', () => { filterState.intruder = null; syncIntruderBar(); refreshAllHuds(); });
                intBar.appendChild(allIntBtn);
                for (const icao of allIcaos) {
                    const btn = document.createElement('button');
                    btn.className = 'filter-btn';
                    btn.textContent = icao;
                    btn.dataset.icao = icao;
                    btn.addEventListener('click', () => { filterState.intruder = icao; syncIntruderBar(); refreshAllHuds(); });
                    intBar.appendChild(btn);
                }
            }
            if (allIcaos.length === 0) intBar.style.display = 'none';
        }

        function syncOwnshipBar() {
            const sel = document.getElementById('ownshipSelect');
            if (sel) { sel.value = filterState.ownship || ''; return; }
            const bar = document.getElementById('ownshipFilters');
            const active = filterState.ownship;
            for (const btn of bar.children) {
                const isAll = !btn.dataset.ownship;
                btn.classList.toggle('active', active === null ? isAll : btn.dataset.ownship === active);
            }
        }

        function syncIntruderBar() {
            const sel = document.getElementById('intruderSelect');
            if (sel) { sel.value = filterState.intruder || ''; return; }
            const bar = document.getElementById('intruderFilters');
            const active = filterState.intruder;
            for (const btn of bar.children) {
                const isAll = !btn.dataset.icao;
                btn.classList.toggle('active', active === null ? isAll : btn.dataset.icao === active);
            }
        }

        /* Hide shared filter card entirely when single-ownship + single/no intruder */
        function updateFilterCardVisibility() {
            const card = document.getElementById('sharedFilterCard');
            if (!multiOwnship && allIcaos.length <= 1) {
                card.style.display = 'none';
            }
        }

        buildSharedFilters();
        updateFilterCardVisibility();

        /* ── Shared filter predicate ── */
        function matchesFilter(event) {
            if (filterState.ownship !== null && event.ownship_label && event.ownship_label !== filterState.ownship) return false;
            if (filterState.intruder !== null && event.intruder_icao && event.intruder_icao !== filterState.intruder) return false;
            return true;
        }

        /* ── HUD: Intruder Roster (§8.2.6 priority, §8.2.7 CPA sub-sort) ── */
        function updateIntruderRoster(logIndex) {
            const states = getIntruderStates(logIndex);
            const rosterBody = document.getElementById('rosterBody');
            const rosterBadge = document.getElementById('rosterBadge');

            /* Apply intruder filter */
            const filteredStates = filterState.intruder === null
                ? [...states.entries()]
                : [...states.entries()].filter(([, s]) => s.intruder_icao === filterState.intruder);

            const activeCount = filteredStates.filter(([, s]) => String(s.event_type || '').toLowerCase() !== 'alert_resolved').length;
            rosterBadge.textContent = activeCount + '/' + filteredStates.length + ' active';

            const sorted = filteredStates.sort(([, a], [, b]) => {
                const isResA = String(a.event_type || '').toLowerCase() === 'alert_resolved' ? 1 : 0;
                const isResB = String(b.event_type || '').toLowerCase() === 'alert_resolved' ? 1 : 0;
                if (isResA !== isResB) return isResA - isResB;
                const levelDiff = (Number(b.alert_level) || 0) - (Number(a.alert_level) || 0);
                if (levelDiff !== 0) return levelDiff;
                return (Number(a.cpa_time_seconds) || Infinity) - (Number(b.cpa_time_seconds) || Infinity);
            });

            let html = '';
            for (const [key, state] of sorted) {
                const icao = state.intruder_icao || key.split('|')[0];
                const ownLabel = multiOwnship ? (state._ownLabel || state.ownship_label || '') : '';
                const meta = getLevelMeta(state.alert_level, state.event_type);
                const isResolved = String(state.event_type || '').toLowerCase() === 'alert_resolved';
                const cardCls = isResolved ? 'intruder-card resolved' : 'intruder-card';

                const detailId = '_ic' + (++_jsonId);
                html += '<div class="' + cardCls + '" style="border-left-color:' + meta.color + '">';
                html += '<div class="intruder-header" data-detail="' + detailId + '">';
                html += '<span class="icao">' + meta.icon + ' ' + icao;
                if (ownLabel) html += ' <span style="opacity:0.6;font-size:10px">\\u2192 ' + ownLabel + '</span>';
                html += '</span>';
                html += '<span class="level-badge" style="background:' + meta.bg + ';color:' + meta.color + '">' + meta.label + '</span>';
                html += '<span class="range-label">' + (isResolved ? 'resolved' : 'r=' + fmtNum(state.range_m, 0) + 'm') + '</span>';
                html += '</div>';

                html += '<div class="intruder-detail" id="' + detailId + '" style="display:' + (isResolved ? 'none' : 'block') + '">';
                html += '<div class="metrics">';
                html += '<span class="metric-label">Range</span><span class="metric-value">' + fmtNum(state.range_m) + 'm</span>';
                html += '<span class="metric-label">Vert sep</span><span class="metric-value">' + fmtNum(state.vertical_separation_m) + 'm</span>';
                html += '<span class="metric-label">Bearing</span><span class="metric-value">' + fmtNum(state.bearing_deg) + '\\u00b0</span>';
                html += '<span class="metric-label">CPA</span><span class="metric-value">' + fmtNum(state.cpa_time_seconds) + 's</span>';
                html += '<span class="metric-label">Speed</span><span class="metric-value">' + fmtNum(state.intruder_speed_mps) + ' m/s</span>';
                html += '<span class="metric-label">Heading</span><span class="metric-value">' + fmtNum(state.intruder_heading_deg) + '\\u00b0</span>';                const am = state.avoidance_maneuver;
                if (am && typeof am === 'object') {
                    const amColor = am.is_feasible ? '#66bb6a' : '#ef5350';
                    const amIcon = am.is_feasible ? '\u2705' : '\u26a0\ufe0f';
                    html += '<span class="metric-label">Avoidance</span><span class="metric-value" style="color:' + amColor + '">' + amIcon + ' ' + (am.maneuver_type || 'n/a') + '</span>';
                    if (am.advisory_text) {
                        html += '<span class="metric-label">Advisory</span><span class="metric-value" style="font-size:10px">' + am.advisory_text + '</span>';
                    }
                }                html += '</div>';
                html += jsonToggleHtml(state.raw || state);
                html += '</div>';

                html += '</div>';
            }

            rosterBody.innerHTML = html || '<div style="opacity:0.5;font-size:12px">No intruders detected yet.</div>';
        }

        /* ── HUD: Alert Lifecycle Timeline ── */
        function updateAlertTimeline(logIndex) {
            const alertsBody = document.getElementById('alertsBody');
            const alertsBadge = document.getElementById('alertsBadge');
            const filtered = lifecycleEvents.filter(matchesFilter);
            alertsBadge.textContent = filtered.length + '/' + lifecycleEvents.length + ' events';

            const currentT = timeBasedMode ? logIndex : (unifiedTimeline[logIndex] ? (unifiedTimeline[logIndex].t || 0) : 0);
            const pastEvents = filtered.filter(e => e.t <= currentT);

            let html = '';
            for (const evt of filtered) {
                const meta = getLevelMeta(evt.alert_level, evt.event_type);
                const isCurrent = pastEvents.length > 0 && pastEvents[pastEvents.length - 1] === evt;
                const isFuture = evt.t > currentT;
                const cls = isCurrent ? 'alert-entry current' : isFuture ? 'alert-entry future' : 'alert-entry';
                const evtType = String(evt.event_type || '').replace('alert_', '');
                const arrow = evtType === 'updated'
                    ? ' <span class="arrow">\\u2192 ' + formatLevel(evt.alert_level_display || evt.alert_level) + '</span>'
                    : '';

                const ownTag = multiOwnship && evt.ownship_label
                    ? '<span style="opacity:0.5;font-size:10px"> [' + evt.ownship_label + ']</span>'
                    : '';

                html += '<div class="' + cls + '" style="border-left:2px solid ' + meta.color + ';padding-left:6px;margin-bottom:2px">';
                html += '<span style="opacity:0.6">t=' + evt.t + '</span> ' + meta.icon + ' ';
                html += '<strong>' + (evt.intruder_icao || '?') + '</strong>' + ownTag + ' ';
                html += '<span style="color:' + meta.color + '">' + evtType + '</span>' + arrow;
                const evtAm = evt.avoidance_maneuver;
                if (evtAm && typeof evtAm === 'object') {
                    const amFeas = evtAm.is_feasible;
                    const amC = amFeas ? '#66bb6a' : '#ef5350';
                    html += '<div style="margin-left:14px;font-size:10px;color:' + amC + '">';
                    html += (amFeas ? '\u2705' : '\u26a0\ufe0f') + ' ' + (evtAm.maneuver_type || '') + ' — ' + (evtAm.advisory_text || '');
                    if (evtAm.predicted_min_horizontal_m != null) html += ' (sep ' + fmtNum(evtAm.predicted_min_horizontal_m, 0) + 'm)';
                    html += '</div>';
                }
                html += jsonToggleHtml(evt.raw || evt);
                html += '</div>';
            }
            alertsBody.innerHTML = html || '<div style="opacity:0.5;font-size:12px">No alert lifecycle events.</div>';
        }

        /* ── HUD: Incident Log Feed (periodic_update only) ── */
        function updateIncidentFeed(logIndex) {
            const feed = document.getElementById('incidentFeed');
            const badge = document.getElementById('incidentBadge');
            const currentT = timeBasedMode ? logIndex : (unifiedTimeline[logIndex] ? (unifiedTimeline[logIndex].t || 0) : 0);
            const visible = periodicEvents.filter(e => e.t <= currentT && matchesFilter(e));
            badge.textContent = visible.length + '/' + periodicEvents.length + ' periodic';

            const shown = visible.slice(-50);
            let html = '';
            for (const evt of shown) {
                const meta = getLevelMeta(evt.alert_level, evt.event_type);
                const ownTag = multiOwnship && evt.ownship_label
                    ? '<span style="opacity:0.5;font-size:10px"> [' + evt.ownship_label + ']</span>'
                    : '';
                html += '<div class="log-entry" style="border-left-color:' + meta.color + '">';
                html += '<span class="entry-time">t=' + evt.t + '</span>';
                html += '<span class="entry-icao" style="color:' + meta.color + '">' + (evt.intruder_icao || '?') + '</span>' + ownTag;
                html += '<span class="entry-type">' + meta.icon + ' ' + meta.label + '</span>';
                html += 'r=' + fmtNum(evt.range_m, 0) + 'm vert=' + fmtNum(evt.vertical_separation_m, 0) + 'm';
                html += jsonToggleHtml(evt.raw || evt);
                html += '</div>';
            }
            feed.innerHTML = html || '<div style="opacity:0.5;font-size:12px">No incident logs yet.</div>';
        }

        /* ── HUD: AMQP Feed ── */
        function updateAmqpFeed(logIndex) {
            const feed = document.getElementById('amqpFeed');
            const badge = document.getElementById('amqpBadge');
            const currentT = timeBasedMode ? logIndex : (unifiedTimeline[logIndex] ? (unifiedTimeline[logIndex].t || 0) : 0);
            const rkMap = DATA.routing_key_to_ownship || {};
            const visible = amqpEvents.filter(e => {
                if (e.t > currentT) return false;
                const bp = parseJsonSafe(e.body_body);
                const eIcao = (typeof bp === 'object' && bp) ? (bp.intruder_icao || '') : '';
                if (filterState.intruder !== null && eIcao && eIcao !== filterState.intruder) return false;
                if (filterState.ownship !== null && e.routing_key && rkMap[e.routing_key] && rkMap[e.routing_key] !== filterState.ownship) return false;
                return true;
            });
            badge.textContent = visible.length + '/' + amqpEvents.length + ' records';

            const shown = visible.slice(-20);
            let html = '';
            for (const evt of shown) {
                const bodyParsed = parseJsonSafe(evt.body_body);
                const icao = (typeof bodyParsed === 'object' && bodyParsed) ? (bodyParsed.intruder_icao || '') : '';
                const level = (typeof bodyParsed === 'object' && bodyParsed) ? (bodyParsed.alert_level ?? bodyParsed.current_level) : null;
                const status = (typeof bodyParsed === 'object' && bodyParsed) ? (bodyParsed.alert_status || '') : '';
                const isResolved = String(status).toLowerCase().includes('resolved');
                const meta = isResolved ? RESOLVED_META
                    : (level !== null && level !== undefined ? getLevelMeta(level) : { icon: '\\ud83d\\udce8', color: '#90a4ae' });
                const statusLabel = isResolved ? ' resolved' : '';

                html += '<div class="log-entry" style="border-left-color:' + meta.color + '">';
                html += '<span class="entry-time">t=' + evt.t + '</span> ';
                if (icao) html += '<span class="entry-icao" style="color:' + meta.color + '">' + icao + '</span> ';
                const ownLabel = rkMap[evt.routing_key];
                if (ownLabel) html += '<span class="entry-own" style="opacity:0.7">[' + ownLabel + ']</span> ';
                html += meta.icon + ' ' + (evt.routing_key || 'amqp') + '<span style="color:' + meta.color + '">' + statusLabel + '</span>';
                const amqpAm = (typeof bodyParsed === 'object' && bodyParsed) ? bodyParsed.avoidance_maneuver : null;
                if (amqpAm && typeof amqpAm === 'object') {
                    const amqpFeas = amqpAm.is_feasible;
                    const amqpC = amqpFeas ? '#66bb6a' : '#ef5350';
                    html += '<div style="margin-left:14px;font-size:10px;color:' + amqpC + '">';
                    html += (amqpFeas ? '\u2705' : '\u26a0\ufe0f') + ' ' + (amqpAm.maneuver_type || '') + ': ' + (amqpAm.advisory_text || '');
                    html += '</div>';
                }
                html += jsonToggleHtml(evt.raw || evt);
                html += '</div>';
            }
            feed.innerHTML = html || '<div style="opacity:0.5;font-size:12px">No AMQP messages yet.</div>';
        }

        /* ── Update intruder label sprite (cached — only redraws on alert level change) ── */
        function updateIntruderLabel(obj) {
            if (obj._labelDrawn) return;
            obj._labelDrawn = true;

            const ctx = obj.labelCtx;
            const canvas = obj.labelCanvas;
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            ctx.fillStyle = 'rgba(0,0,0,0.6)';
            ctx.beginPath();
            ctx.roundRect(0, 0, canvas.width, canvas.height, 8);
            ctx.fill();
            ctx.font = 'bold 22px Arial';
            ctx.fillStyle = '#e0e0e0';
            ctx.textAlign = 'center';
            ctx.fillText(obj.intruder.icao, canvas.width / 2, 38);
            obj.labelTexture.needsUpdate = true;
        }

        /* ── Dirty-flag tracking for HUD panels ── */
        let _lastHudLogIndex = -1;
        let _lastHudOwnFilter = undefined;
        let _lastHudIntFilter = undefined;

        /* ── Main frame update (log-index based) ── */
        function updateFrame(logIndex) {
            currentLogIndex = Math.max(0, Math.min(logCount - 1, logIndex));
            slider.value = String(currentLogIndex);

            const entry = timeBasedMode ? null : unifiedTimeline[currentLogIndex];
            const currentT = timeBasedMode ? currentLogIndex : (entry ? (entry.t || 0) : 0);
            timeLabel.textContent = timeBasedMode
                ? 't = ' + currentT + 's / ' + maxT + 's'
                : 'Log ' + (currentLogIndex + 1) + '/' + logCount + ' \\u2022 t = ' + currentT + 's';

            /* 3D scene positions by time — multi-ownship, filter-aware */
            let primaryPoint = null;
            for (let i = 0; i < ownshipObjects.length; i++) {
                const obj = ownshipObjects[i];
                const isVisible = filterState.ownship === null || ownshipLabels[i] === filterState.ownship;
                const trailEnd = getTrailEndIndex(obj.ownship.track, currentT);
                const point = trailEnd > 0 ? obj.ownship.track[trailEnd - 1] : null;

                obj.line.visible = isVisible;
                if (isVisible) obj.line.geometry.setDrawRange(0, trailEnd);

                if (point && isVisible) {
                    obj.marker.visible = true;
                    obj.marker.position.set(point.x, point.y, point.z);
                    if (obj.labelSprite) {
                        obj.labelSprite.visible = true;
                        obj.labelSprite.position.set(point.x, point.y + 25, point.z);
                    }
                    if (wcVolumes[i]) {
                        wcVolumes[i].visible = true;
                        nmacVolumes[i].visible = true;
                        wcVolumes[i].position.set(point.x, point.y, point.z);
                        nmacVolumes[i].position.set(point.x, point.y, point.z);
                    }
                    const vel = getOneSecVelocity(obj.ownship.track, currentT);
                    setArrowFromVelocity(ownshipArrows[i], obj.marker.position, vel);
                } else {
                    obj.marker.visible = false;
                    if (obj.labelSprite) obj.labelSprite.visible = false;
                    if (wcVolumes[i]) {
                        wcVolumes[i].visible = false;
                        nmacVolumes[i].visible = false;
                    }
                    if (ownshipArrows[i]) ownshipArrows[i].visible = false;
                }

                /* Geofence visibility tracks ownship filter */
                if (geofenceLineGroups[i]) {
                    for (const ln of geofenceLineGroups[i]) ln.visible = isVisible;
                }

                if (i === activeOwnshipIdx && point) primaryPoint = point;
            }

            /* Intruder positions + alert-colored labels + velocity arrows (filter-aware) */
            const intruderStates = getIntruderStates(currentLogIndex);
            for (let iIdx = 0; iIdx < intruderObjects.length; iIdx++) {
                const obj = intruderObjects[iIdx];
                const isVisible = filterState.intruder === null || obj.intruder.icao === filterState.intruder;
                const trailEnd = getTrailEndIndex(obj.intruder.points, currentT);
                const point = trailEnd > 0 ? obj.intruder.points[trailEnd - 1] : null;

                obj.line.visible = isVisible;
                if (isVisible) obj.line.geometry.setDrawRange(0, trailEnd);

                if (point && isVisible) {
                    obj.marker.visible = true;
                    obj.marker.position.set(point.x, point.y, point.z);
                    obj.sprite.visible = true;
                    obj.sprite.position.set(point.x, point.y + 25, point.z);
                    updateIntruderLabel(obj);
                    const vel = getOneSecVelocity(obj.intruder.points, currentT);
                    setArrowFromVelocity(intruderArrows[iIdx], obj.marker.position, vel);
                } else {
                    obj.marker.visible = false;
                    obj.sprite.visible = false;
                    if (intruderArrows[iIdx]) intruderArrows[iIdx].visible = false;
                }
            }

            /* HUD updates — only rebuild DOM when data actually changed */
            const hudDirty = currentLogIndex !== _lastHudLogIndex
                || filterState.ownship !== _lastHudOwnFilter
                || filterState.intruder !== _lastHudIntFilter;
            if (hudDirty) {
                _lastHudLogIndex = currentLogIndex;
                _lastHudOwnFilter = filterState.ownship;
                _lastHudIntFilter = filterState.intruder;
                updateIntruderRoster(currentLogIndex);
                updateAlertTimeline(currentLogIndex);
                updateIncidentFeed(currentLogIndex);
                updateAmqpFeed(currentLogIndex);
            }
        }

        /* ── Navigation: jump to next/previous second ── */
        function jumpToNextSecond(direction) {
            if (logCount <= 1) return;
            if (timeBasedMode) {
                updateFrame(Math.max(0, Math.min(logCount - 1, currentLogIndex + direction)));
                return;
            }
            const currentT = (unifiedTimeline[currentLogIndex] || {}).t || 0;
            const targetT = currentT + direction;
            let bestIdx = currentLogIndex;
            if (direction > 0) {
                for (let i = currentLogIndex + 1; i < logCount; i++) {
                    if ((unifiedTimeline[i].t || 0) >= targetT) { bestIdx = i; break; }
                    if (i === logCount - 1) bestIdx = i;
                }
            } else {
                for (let i = currentLogIndex - 1; i >= 0; i--) {
                    if ((unifiedTimeline[i].t || 0) <= targetT) { bestIdx = i; break; }
                    if (i === 0) bestIdx = 0;
                }
            }
            updateFrame(bestIdx);
        }

        /* ── Playback controls (rAF-driven, delta-time based) ── */
        function setPlaying(playing) {
            isPlaying = playing;
            playPauseBtn.textContent = isPlaying ? '\\u23f8 Pause' : '\\u25b6 Play';
        }

        playPauseBtn.addEventListener('click', () => setPlaying(!isPlaying));
        prevLogBtn.addEventListener('click', () => updateFrame(currentLogIndex - 1));
        nextLogBtn.addEventListener('click', () => updateFrame(currentLogIndex + 1));
        prevSecBtn.addEventListener('click', () => jumpToNextSecond(-1));
        nextSecBtn.addEventListener('click', () => jumpToNextSecond(1));
        speedSelect.addEventListener('change', (e) => {
            playSpeed = Number(e.target.value);
        });
        slider.addEventListener('input', (e) => updateFrame(Number(e.target.value)));
        window.addEventListener('resize', () => {
            camera.aspect = window.innerWidth / window.innerHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(window.innerWidth, window.innerHeight);
        });

        /* ── Initial render ── */
        updateFrame(0);

        let _lastRenderTime = 0;
        let _accumulatedTime = 0;

        const renderLoop = (timestamp) => {
            const delta = timestamp - _lastRenderTime;
            _lastRenderTime = timestamp;

            if (isPlaying && delta < 500) {
                _accumulatedTime += delta;
                if (_accumulatedTime >= playSpeed) {
                    _accumulatedTime -= playSpeed;
                    if (currentLogIndex < logCount - 1) updateFrame(currentLogIndex + 1);
                    else setPlaying(false);
                }
            }

            controls.update();
            renderer.render(scene, camera);
            requestAnimationFrame(renderLoop);
        };
        requestAnimationFrame(renderLoop);
    </script>
</body>
</html>
"""

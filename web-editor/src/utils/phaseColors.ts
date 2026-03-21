/** Color mapping for flight phase codes. */
const PHASE_COLORS: Record<string, { bg: string; text: string; border: string }> = {
    'FLIGHT PLANNING': { bg: 'rgba(99, 102, 241, 0.15)', text: '#6366f1', border: 'rgba(99, 102, 241, 0.4)' },     // Indigo
    'PRE FLIGHT':      { bg: 'rgba(59, 130, 246, 0.15)', text: '#3b82f6', border: 'rgba(59, 130, 246, 0.4)' },     // Blue
    'ENGINE START':    { bg: 'rgba(6, 182, 212, 0.15)', text: '#06b6d4', border: 'rgba(6, 182, 212, 0.4)' },       // Cyan
    'TAXI OUT':        { bg: 'rgba(168, 85, 247, 0.15)', text: '#a855f7', border: 'rgba(168, 85, 247, 0.4)' },     // Purple
    'TAKEOFF':         { bg: 'rgba(236, 72, 153, 0.15)', text: '#ec4899', border: 'rgba(236, 72, 153, 0.4)' },     // Pink
    'REJECTED TAKEOFF':{ bg: 'rgba(220, 38, 38, 0.15)', text: '#dc2626', border: 'rgba(220, 38, 38, 0.4)' },       // Red
    'INITIAL CLIMB':   { bg: 'rgba(245, 158, 11, 0.15)', text: '#f59e0b', border: 'rgba(245, 158, 11, 0.4)' },     // Amber
    'EN ROUTE CLIMB':  { bg: 'rgba(132, 204, 22, 0.15)', text: '#84cc16', border: 'rgba(132, 204, 22, 0.4)' },     // Lime
    'CRUISE':          { bg: 'rgba(34, 197, 94, 0.15)',  text: '#22c55e', border: 'rgba(34, 197, 94, 0.4)' },      // Green
    'DESCENT':         { bg: 'rgba(20, 184, 166, 0.15)', text: '#14b8a6', border: 'rgba(20, 184, 166, 0.4)' },     // Teal
    'APPROACH':        { bg: 'rgba(249, 115, 22, 0.15)', text: '#f97316', border: 'rgba(249, 115, 22, 0.4)' },     // Orange
    'GO AROUND':       { bg: 'rgba(251, 191, 36, 0.15)', text: '#fbbf24', border: 'rgba(251, 191, 36, 0.4)' },     // Yellow
    'LANDING':         { bg: 'rgba(239, 68, 68, 0.15)',  text: '#ef4444', border: 'rgba(239, 68, 68, 0.4)' },      // Red
    'TAXI IN':         { bg: 'rgba(168, 85, 247, 0.15)', text: '#a855f7', border: 'rgba(168, 85, 247, 0.4)' },     // Purple
    'ARRIVAL':         { bg: 'rgba(75, 85, 99, 0.15)', text: '#4b5563', border: 'rgba(75, 85, 99, 0.4)' },         // Gray
    'POST FLIGHT':     { bg: 'rgba(107, 114, 128, 0.15)', text: '#6b7280', border: 'rgba(107, 114, 128, 0.4)' },   // Gray
    'FLIGHT CLOSE':    { bg: 'rgba(156, 163, 175, 0.15)', text: '#9ca3af', border: 'rgba(156, 163, 175, 0.4)' },   // Light Gray
    'GROUND SERVICES': { bg: 'rgba(120, 113, 108, 0.15)', text: '#78716c', border: 'rgba(120, 113, 108, 0.4)' },   // Stone
};

const DEFAULT_COLOR = { bg: 'rgba(107, 114, 128, 0.12)', text: '#6b7280', border: 'rgba(107, 114, 128, 0.3)' };

export function getPhaseColor(phase: string) {
    return PHASE_COLORS[phase] ?? DEFAULT_COLOR;
}

/** Human-readable labels for flight phase codes. */
export const PHASE_LABELS: Record<string, string> = {
    'FLIGHT PLANNING':  'Flight Planning',
    'PRE FLIGHT':       'Pre-flight',
    'ENGINE START':     'Engine Start / Depart',
    'TAXI OUT':         'Taxi Out',
    'TAKEOFF':          'Takeoff',
    'REJECTED TAKEOFF': 'Rejected Takeoff',
    'INITIAL CLIMB':    'Initial Climb',
    'EN ROUTE CLIMB':   'En Route Climb',
    'CRUISE':           'Cruise',
    'DESCENT':          'Descent',
    'APPROACH':         'Approach',
    'GO AROUND':        'Go-around',
    'LANDING':          'Landing',
    'TAXI IN':          'Taxi In',
    'ARRIVAL':          'Arrival / Engine Shutdown',
    'POST FLIGHT':      'Post-flight',
    'FLIGHT CLOSE':     'Flight Close',
    'GROUND SERVICES':  'Ground Services',
};

/** Canonical ordering of phases (matches flight progression). */
export const PHASE_ORDER = [
    'FLIGHT PLANNING',
    'PRE FLIGHT',
    'ENGINE START',
    'TAXI OUT',
    'TAKEOFF',
    'REJECTED TAKEOFF',
    'INITIAL CLIMB',
    'EN ROUTE CLIMB',
    'CRUISE',
    'DESCENT',
    'APPROACH',
    'GO AROUND',
    'LANDING',
    'TAXI IN',
    'ARRIVAL',
    'POST FLIGHT',
    'FLIGHT CLOSE',
    'GROUND SERVICES',
];

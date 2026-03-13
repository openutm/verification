/** Color mapping for flight phase codes. */
const PHASE_COLORS: Record<string, { bg: string; text: string; border: string }> = {
    FPL: { bg: 'rgba(99, 102, 241, 0.15)', text: '#6366f1', border: 'rgba(99, 102, 241, 0.4)' },     // Indigo — Flight Planning
    PRF: { bg: 'rgba(59, 130, 246, 0.15)', text: '#3b82f6', border: 'rgba(59, 130, 246, 0.4)' },     // Blue — Pre-flight
    ESD: { bg: 'rgba(6, 182, 212, 0.15)', text: '#06b6d4', border: 'rgba(6, 182, 212, 0.4)' },       // Cyan — Engine Start / Depart
    TXO: { bg: 'rgba(168, 85, 247, 0.15)', text: '#a855f7', border: 'rgba(168, 85, 247, 0.4)' },     // Purple — Taxi Out
    TOF: { bg: 'rgba(236, 72, 153, 0.15)', text: '#ec4899', border: 'rgba(236, 72, 153, 0.4)' },     // Pink — Takeoff
    RTO: { bg: 'rgba(220, 38, 38, 0.15)', text: '#dc2626', border: 'rgba(220, 38, 38, 0.4)' },       // Red — Rejected Takeoff
    ICL: { bg: 'rgba(245, 158, 11, 0.15)', text: '#f59e0b', border: 'rgba(245, 158, 11, 0.4)' },     // Amber — Initial Climb
    ERC: { bg: 'rgba(132, 204, 22, 0.15)', text: '#84cc16', border: 'rgba(132, 204, 22, 0.4)' },     // Lime — En Route Climb
    CRZ: { bg: 'rgba(34, 197, 94, 0.15)',  text: '#22c55e', border: 'rgba(34, 197, 94, 0.4)' },      // Green — Cruise
    DES: { bg: 'rgba(20, 184, 166, 0.15)', text: '#14b8a6', border: 'rgba(20, 184, 166, 0.4)' },     // Teal — Descent
    APR: { bg: 'rgba(249, 115, 22, 0.15)', text: '#f97316', border: 'rgba(249, 115, 22, 0.4)' },     // Orange — Approach
    GAR: { bg: 'rgba(251, 191, 36, 0.15)', text: '#fbbf24', border: 'rgba(251, 191, 36, 0.4)' },     // Yellow — Go-around
    LDG: { bg: 'rgba(239, 68, 68, 0.15)',  text: '#ef4444', border: 'rgba(239, 68, 68, 0.4)' },      // Red — Landing
    TXI: { bg: 'rgba(168, 85, 247, 0.15)', text: '#a855f7', border: 'rgba(168, 85, 247, 0.4)' },     // Purple — Taxi In
    AES: { bg: 'rgba(75, 85, 99, 0.15)', text: '#4b5563', border: 'rgba(75, 85, 99, 0.4)' },         // Gray — Arrival / Engine Shutdown
    PST: { bg: 'rgba(107, 114, 128, 0.15)', text: '#6b7280', border: 'rgba(107, 114, 128, 0.4)' },   // Gray — Post-flight
    FCL: { bg: 'rgba(156, 163, 175, 0.15)', text: '#9ca3af', border: 'rgba(156, 163, 175, 0.4)' },   // Light Gray — Flight Close
    GND: { bg: 'rgba(120, 113, 108, 0.15)', text: '#78716c', border: 'rgba(120, 113, 108, 0.4)' },   // Stone — Ground Services
};

const DEFAULT_COLOR = { bg: 'rgba(107, 114, 128, 0.12)', text: '#6b7280', border: 'rgba(107, 114, 128, 0.3)' };

export function getPhaseColor(phase: string) {
    return PHASE_COLORS[phase] ?? DEFAULT_COLOR;
}

/** Human-readable labels for flight phase codes. */
export const PHASE_LABELS: Record<string, string> = {
    FPL: 'Flight Planning',
    PRF: 'Pre-flight',
    ESD: 'Engine Start / Depart',
    TXO: 'Taxi Out',
    TOF: 'Takeoff',
    RTO: 'Rejected Takeoff',
    ICL: 'Initial Climb',
    ERC: 'En Route Climb',
    CRZ: 'Cruise',
    DES: 'Descent',
    APR: 'Approach',
    GAR: 'Go-around',
    LDG: 'Landing',
    TXI: 'Taxi In',
    AES: 'Arrival / Engine Shutdown',
    PST: 'Post-flight',
    FCL: 'Flight Close',
    GND: 'Ground Services',
};

/** Canonical ordering of phases (matches flight progression). */
export const PHASE_ORDER = ['FPL', 'PRF', 'ESD', 'TXO', 'TOF', 'RTO', 'ICL', 'ERC', 'CRZ', 'DES', 'APR', 'GAR', 'LDG', 'TXI', 'AES', 'PST', 'FCL', 'GND'];

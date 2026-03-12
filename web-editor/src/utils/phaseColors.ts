/** Color mapping for IATA flight phase codes. */
const PHASE_COLORS: Record<string, { bg: string; text: string; border: string }> = {
    STD: { bg: 'rgba(59, 130, 246, 0.15)', text: '#3b82f6', border: 'rgba(59, 130, 246, 0.4)' },     // Blue — Standing
    PBT: { bg: 'rgba(99, 102, 241, 0.15)', text: '#6366f1', border: 'rgba(99, 102, 241, 0.4)' },     // Indigo — Pushback
    TXO: { bg: 'rgba(168, 85, 247, 0.15)', text: '#a855f7', border: 'rgba(168, 85, 247, 0.4)' },     // Purple — Taxi Out
    TOF: { bg: 'rgba(236, 72, 153, 0.15)', text: '#ec4899', border: 'rgba(236, 72, 153, 0.4)' },     // Pink — Takeoff
    ICL: { bg: 'rgba(245, 158, 11, 0.15)', text: '#f59e0b', border: 'rgba(245, 158, 11, 0.4)' },     // Amber — Initial Climb
    ENR: { bg: 'rgba(34, 197, 94, 0.15)',  text: '#22c55e', border: 'rgba(34, 197, 94, 0.4)' },      // Green — En Route
    MAN: { bg: 'rgba(20, 184, 166, 0.15)', text: '#14b8a6', border: 'rgba(20, 184, 166, 0.4)' },     // Teal — Maneuvering
    APR: { bg: 'rgba(249, 115, 22, 0.15)', text: '#f97316', border: 'rgba(249, 115, 22, 0.4)' },     // Orange — Approach
    LDG: { bg: 'rgba(239, 68, 68, 0.15)',  text: '#ef4444', border: 'rgba(239, 68, 68, 0.4)' },      // Red — Landing
    TXI: { bg: 'rgba(168, 85, 247, 0.15)', text: '#a855f7', border: 'rgba(168, 85, 247, 0.4)' },     // Purple — Taxi In
    PST: { bg: 'rgba(107, 114, 128, 0.15)', text: '#6b7280', border: 'rgba(107, 114, 128, 0.4)' },   // Gray — Post-Flight
};

const DEFAULT_COLOR = { bg: 'rgba(107, 114, 128, 0.12)', text: '#6b7280', border: 'rgba(107, 114, 128, 0.3)' };

export function getPhaseColor(phase: string) {
    return PHASE_COLORS[phase] ?? DEFAULT_COLOR;
}

/** Human-readable labels for IATA phase codes. */
export const PHASE_LABELS: Record<string, string> = {
    STD: 'Standing',
    PBT: 'Pushback / Towing',
    TXO: 'Taxi Out',
    TOF: 'Takeoff',
    ICL: 'Initial Climb',
    ENR: 'En Route',
    MAN: 'Maneuvering',
    APR: 'Approach',
    LDG: 'Landing',
    TXI: 'Taxi In',
    PST: 'Post-Flight',
};

/** Canonical ordering of phases (matches flight progression). */
export const PHASE_ORDER = ['STD', 'PBT', 'TXO', 'TOF', 'ICL', 'ENR', 'MAN', 'APR', 'LDG', 'TXI', 'PST'];

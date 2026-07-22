/** Deterministic color assignment for client/category badges. */
const CLIENT_COLORS: { bg: string; text: string; border: string }[] = [
    { bg: 'rgba(42, 120, 214, 0.15)', text: '#2a78d6', border: 'rgba(42, 120, 214, 0.4)' },   // Blue
    { bg: 'rgba(235, 104, 52, 0.15)', text: '#eb6834', border: 'rgba(235, 104, 52, 0.4)' },    // Orange
    { bg: 'rgba(27, 175, 122, 0.15)', text: '#1baf7a', border: 'rgba(27, 175, 122, 0.4)' },    // Aqua
    { bg: 'rgba(237, 161, 0, 0.15)', text: '#eda100', border: 'rgba(237, 161, 0, 0.4)' },      // Yellow
    { bg: 'rgba(232, 123, 164, 0.15)', text: '#e87ba4', border: 'rgba(232, 123, 164, 0.4)' },  // Magenta
    { bg: 'rgba(0, 131, 0, 0.15)', text: '#008300', border: 'rgba(0, 131, 0, 0.4)' },          // Green
    { bg: 'rgba(74, 58, 167, 0.15)', text: '#4a3aa7', border: 'rgba(74, 58, 167, 0.4)' },      // Violet
    { bg: 'rgba(227, 73, 72, 0.15)', text: '#e34948', border: 'rgba(227, 73, 72, 0.4)' },      // Red
];

function hashString(value: string): number {
    let hash = 0;
    for (let i = 0; i < value.length; i++) {
        hash = (hash * 31 + value.charCodeAt(i)) | 0;
    }
    return Math.abs(hash);
}

export function getClientColor(client: string) {
    return CLIENT_COLORS[hashString(client) % CLIENT_COLORS.length];
}

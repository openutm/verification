import { MarkerType } from '@xyflow/react';
import type { Edge } from '@xyflow/react';

const WAIT_EDGE_DECORATION: Pick<Edge, 'style' | 'markerEnd' | 'label' | 'labelStyle' | 'labelBgPadding' | 'labelBgBorderRadius' | 'labelBgStyle'> & {
    type: Edge['type'];
    selectable: Edge['selectable'];
} = {
    type: 'smoothstep',
    selectable: false,
    style: {
        strokeDasharray: '5 5',
        stroke: 'var(--accent-warning, #f97316)',
        strokeWidth: 2,
        opacity: 0.9,
    },
    markerEnd: { type: MarkerType.ArrowClosed, color: 'var(--accent-warning, #f97316)' },
    label: 'wait',
    labelStyle: { fill: 'var(--text-primary)', fontSize: 11, fontWeight: 600 },
    labelBgPadding: [4, 2],
    labelBgBorderRadius: 4,
    labelBgStyle: { fill: 'var(--bg-primary)', stroke: 'var(--border-color)' },
};

export const createWaitEdge = (sourceId: string, targetId: string, id?: string): Edge => ({
    id: id ?? `dep_${sourceId}-${targetId}`,
    source: sourceId,
    target: targetId,
    ...WAIT_EDGE_DECORATION,
});

export { WAIT_EDGE_DECORATION };

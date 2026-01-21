import { MarkerType, Position } from '@xyflow/react';

export const LAYOUT_CONFIG = {
    nodeWidth: 180,
    nodeHeight: 80,
    rankSep: 80,
    nodeSep: 250,
    direction: 'TB',
};

export const CONVERSION_LAYOUT = {
    startX: LAYOUT_CONFIG.nodeSep,
    groupContainerOffset: -50,
    groupChildOffset: 80,
};

export const COMMON_EDGE_OPTIONS = {
    type: 'default',
    animated: true,
    style: { stroke: 'var(--accent-primary)', strokeWidth: 1 },
    markerEnd: { type: MarkerType.ArrowClosed, color: 'var(--accent-primary)' },
};

export const COMMON_NODE_DEFAULTS = {
    sourcePosition: Position.Bottom,
    targetPosition: Position.Top,
};

export const GROUP_CONFIG = {
    paddingTop: 60,
    paddingBottom: 40,
    width: 600,
    minHeight: 150,
};

export const getVerticalGap = () => LAYOUT_CONFIG.nodeHeight + LAYOUT_CONFIG.rankSep;

export const getGroupHeight = (rowCount: number) => {
    if (rowCount <= 0) return GROUP_CONFIG.minHeight;
    // Height = top_padding + (rows * gap) - rankSep (remove last gap after node) + bottom_padding
    // This assumes rows are stacked with 'gap' spacing completely.
    const gap = getVerticalGap();
    // Start of last node = Top + (rows-1)*gap.
    // End of last node = Start + NodeHeight.
    // Total = Top + (rows-1)*gap + NodeHeight + Bottom.
    const height = GROUP_CONFIG.paddingTop + (rowCount - 1) * gap + LAYOUT_CONFIG.nodeHeight + GROUP_CONFIG.paddingBottom;
    return Math.max(GROUP_CONFIG.minHeight, height);
};

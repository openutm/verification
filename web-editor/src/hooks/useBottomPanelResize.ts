import { useState, useCallback, useEffect } from 'react';

export const useBottomPanelResize = (initialHeight = 300, minHeight = 100, maxHeight = 600) => {
    const [panelHeight, setPanelHeight] = useState(initialHeight);
    const [isResizing, setIsResizing] = useState(false);

    const startResizing = useCallback(() => {
        setIsResizing(true);
    }, []);

    const stopResizing = useCallback(() => {
        setIsResizing(false);
    }, []);

    const resize = useCallback((mouseMoveEvent: MouseEvent) => {
        if (isResizing) {
            const newHeight = document.body.clientHeight - mouseMoveEvent.clientY;
            if (newHeight > minHeight && newHeight < maxHeight) {
                setPanelHeight(newHeight);
            }
        }
    }, [isResizing, minHeight, maxHeight]);

    useEffect(() => {
        globalThis.addEventListener("mousemove", resize);
        globalThis.addEventListener("mouseup", stopResizing);
        return () => {
            globalThis.removeEventListener("mousemove", resize);
            globalThis.removeEventListener("mouseup", stopResizing);
        };
    }, [resize, stopResizing]);

    return { panelHeight, isResizing, startResizing };
};

import { useState, useCallback, useEffect } from 'react';

export const useSidebarResize = (initialWidth = 400, minWidth = 200, maxWidth = 800) => {
    const [sidebarWidth, setSidebarWidth] = useState(initialWidth);
    const [isResizing, setIsResizing] = useState(false);

    const startResizing = useCallback(() => {
        setIsResizing(true);
    }, []);

    const stopResizing = useCallback(() => {
        setIsResizing(false);
    }, []);

    const resize = useCallback((mouseMoveEvent: MouseEvent) => {
        if (isResizing) {
            const newWidth = document.body.clientWidth - mouseMoveEvent.clientX;
            if (newWidth > minWidth && newWidth < maxWidth) {
                setSidebarWidth(newWidth);
            }
        }
    }, [isResizing, minWidth, maxWidth]);

    useEffect(() => {
        globalThis.addEventListener("mousemove", resize);
        globalThis.addEventListener("mouseup", stopResizing);
        return () => {
            globalThis.removeEventListener("mousemove", resize);
            globalThis.removeEventListener("mouseup", stopResizing);
        };
    }, [resize, stopResizing]);

    return { sidebarWidth, isResizing, startResizing };
};

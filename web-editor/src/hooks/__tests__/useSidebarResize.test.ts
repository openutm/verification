import { renderHook, act } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { useSidebarResize } from '../useSidebarResize';

describe('useSidebarResize', () => {
    it('initializes with default width', () => {
        const { result } = renderHook(() => useSidebarResize());
        expect(result.current.sidebarWidth).toBe(400);
        expect(result.current.isResizing).toBe(false);
    });

    it('starts resizing', () => {
        const { result } = renderHook(() => useSidebarResize());
        act(() => {
            result.current.startResizing();
        });
        expect(result.current.isResizing).toBe(true);
    });

    it('resizes on mouse move', () => {
        const { result } = renderHook(() => useSidebarResize());

        act(() => {
            result.current.startResizing();
        });

        // Mock document.body.clientWidth
        Object.defineProperty(document.body, 'clientWidth', { value: 1000, configurable: true });

        act(() => {
            const mouseEvent = new MouseEvent('mousemove', { clientX: 600 });
            globalThis.dispatchEvent(mouseEvent);
        });

        // New width = 1000 - 600 = 400. Wait, default is 400.
        // Let's try clientX = 500. New width = 500.

        act(() => {
            const mouseEvent = new MouseEvent('mousemove', { clientX: 500 });
            globalThis.dispatchEvent(mouseEvent);
        });

        expect(result.current.sidebarWidth).toBe(500);
    });

    it('stops resizing on mouse up', () => {
        const { result } = renderHook(() => useSidebarResize());

        act(() => {
            result.current.startResizing();
        });
        expect(result.current.isResizing).toBe(true);

        act(() => {
            const mouseEvent = new MouseEvent('mouseup');
            globalThis.dispatchEvent(mouseEvent);
        });

        expect(result.current.isResizing).toBe(false);
    });

    it('respects min and max width', () => {
        const { result } = renderHook(() => useSidebarResize(400, 200, 800));

        act(() => {
            result.current.startResizing();
        });

        Object.defineProperty(document.body, 'clientWidth', { value: 1000, configurable: true });

        // Try to resize to 100 (below min 200) -> clientX = 900
        act(() => {
            const mouseEvent = new MouseEvent('mousemove', { clientX: 900 });
            globalThis.dispatchEvent(mouseEvent);
        });
        expect(result.current.sidebarWidth).toBe(400); // Should not change

        // Try to resize to 900 (above max 800) -> clientX = 100
        act(() => {
            const mouseEvent = new MouseEvent('mousemove', { clientX: 100 });
            globalThis.dispatchEvent(mouseEvent);
        });
        expect(result.current.sidebarWidth).toBe(400); // Should not change
    });
});

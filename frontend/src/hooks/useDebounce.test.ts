import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useDebounce } from './useDebounce';

/** Phase 62 — fake timers so the delay is asserted, never waited on. */
describe('useDebounce', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('returns the initial value immediately', () => {
    const { result } = renderHook(() => useDebounce('first', 200));

    expect(result.current).toBe('first');
  });

  it('updates only after the delay has elapsed', () => {
    const { result, rerender } = renderHook(({ value }) => useDebounce(value, 200), {
      initialProps: { value: 'first' },
    });

    rerender({ value: 'second' });
    expect(result.current).toBe('first');

    act(() => {
      vi.advanceTimersByTime(199);
    });
    expect(result.current).toBe('first');

    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(result.current).toBe('second');
  });

  it('collapses rapid successive changes to the last value', () => {
    const { result, rerender } = renderHook(({ value }) => useDebounce(value, 200), {
      initialProps: { value: 'a' },
    });

    // Each keystroke lands well inside the window, so the timer keeps resetting.
    for (const value of ['ab', 'abc', 'abcd']) {
      act(() => {
        vi.advanceTimersByTime(50);
      });
      rerender({ value });
    }

    expect(result.current).toBe('a');

    act(() => {
      vi.advanceTimersByTime(200);
    });
    expect(result.current).toBe('abcd');

    // Only the final value ever became visible — no intermediate renders.
    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(result.current).toBe('abcd');
  });

  it('clears the pending timer on unmount so no state update lands after teardown', () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});
    const { rerender, unmount } = renderHook(({ value }) => useDebounce(value, 200), {
      initialProps: { value: 'first' },
    });

    rerender({ value: 'second' });
    expect(vi.getTimerCount()).toBe(1);

    unmount();
    expect(vi.getTimerCount()).toBe(0);

    act(() => {
      vi.advanceTimersByTime(500);
    });
    expect(consoleError).not.toHaveBeenCalled();
  });
});

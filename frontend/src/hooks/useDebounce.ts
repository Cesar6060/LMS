import { useEffect, useState } from 'react';

/**
 * Phase 62 — returns `value` delayed by `delayMs`, so expensive renders driven
 * by fast-changing state (the SectionEditor previews re-running highlight.js on
 * every keystroke) settle once the user pauses instead of firing per change.
 *
 * Generalizes the inline `useRef` + `window.setTimeout` debounce at
 * `src/pages/instructor/LessonEditorPage.tsx:124-132`; that call site is left
 * as-is. The pending timer is cleared both when `value` changes again and on
 * unmount, so no state update lands after teardown.
 */
export function useDebounce<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState<T>(value);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delayMs);
    return () => window.clearTimeout(timer);
  }, [value, delayMs]);

  return debounced;
}

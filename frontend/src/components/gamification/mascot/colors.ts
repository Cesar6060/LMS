/**
 * Palette swaps per color-scheme key (Phase 33, extended Phase 64).
 *
 * `classic` deliberately stays on the theme variable so the default Circuit
 * follows light/dark; every other scheme is a fixed hue that reads on both.
 * Lives outside `Mascot.tsx` so adding a color isn't a merge point with the
 * layer modules.
 */
export const COLOR_SCHEMES: Record<string, string> = {
  classic: 'hsl(var(--primary))',
  ember: '#f97316',
  ocean: '#0ea5e9',
  bubblegum: '#ec4899',
  gold: '#f59e0b',
  // Phase 64
  mint: '#2dd4bf',
  violet: '#8b5cf6',
  crimson: '#dc2626',
  chrome: '#94a3b8',
  aurora: '#22d3ee',
};

/** The shared accent gold used by crowns, halos, stars and medals. */
export const GOLD = '#facc15';

export function colorFor(key: string | undefined | null): string {
  return COLOR_SCHEMES[key ?? 'classic'] ?? COLOR_SCHEMES.classic;
}

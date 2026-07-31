/**
 * Shared contract for Circuit's cosmetic layers (Phase 64).
 *
 * Every slot renders as its own module under `mascot/` taking these props,
 * so the layers can be authored independently instead of all landing in
 * `Mascot.tsx`. `Mascot` owns the base body, the palette, the pose math and
 * the composition order; a layer only draws itself.
 *
 * All layers draw into the same `viewBox="0 0 120 120"` as the base body.
 */

export type MascotPose = 'idle' | 'cheer' | 'encourage' | 'celebrate';

/** A point in mascot viewBox coordinates. */
export interface HandPoint {
  x: number;
  y: number;
}

export interface LayerProps {
  /** The equipped catalog key for this slot. `'none'` renders nothing. */
  itemKey: string;
  /** Palette-swapped primary from the equipped color scheme. */
  primary: string;
  /** Theme surface fill (`hsl(var(--muted))`). */
  surface: string;
  /** Theme outline stroke (`hsl(var(--foreground))`). */
  outline: string;
  /** The shared accent gold. */
  gold: string;
  pose: MascotPose;
  /**
   * `useId()` value from the owning Mascot. Every gradient/filter/mask id a
   * layer defines MUST be namespaced with this — the customizer grid mounts
   * dozens of mascots at once and colliding ids silently swap fills across
   * instances.
   */
  gradientId: string;
}

/** Held items additionally receive the hand they hang from. */
export interface HeldLayerProps extends LayerProps {
  /**
   * Where Circuit's right hand currently is for this pose. Computed once in
   * `Mascot` from the same expressions that position the arm, so the item and
   * the hand can never drift apart.
   */
  hand: HandPoint;
}

/** Eye layers need to know whether the base eyes are in their happy state. */
export interface EyeLayerProps extends LayerProps {
  /** True on `cheer` / `celebrate`, when base eyes render as closed arcs. */
  happyEyes: boolean;
}

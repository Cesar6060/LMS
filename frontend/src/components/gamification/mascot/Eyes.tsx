import { starPath } from '@/components/gamification/starPath';
import type { EyeLayerProps } from './types';

/**
 * Eye-slot cosmetics (Phase 33, extended Phase 64). Drawn OVER the base eyes,
 * which Mascot has already rendered — either as dots (idle/encourage) or as
 * closed happy arcs (`happyEyes`, on cheer/celebrate).
 *
 * A cosmetic that fully covers the eye area (visor, shades, scanner) must
 * render its own happy variant, or Circuit stops emoting exactly when the
 * quiz flow celebrates. A cosmetic that frames the eyes (glasses) can ignore
 * `happyEyes` and let the base arcs show through.
 *
 * Base eye centres: left (47, 42), right (73, 42).
 */
export function Eyes({ itemKey, primary, outline, gold, happyEyes }: EyeLayerProps) {
  if (itemKey === 'visor') {
    return (
      <>
        <rect x="38" y="34" width="44" height="16" rx="8" fill={outline} opacity="0.85" />
        {happyEyes ? (
          <>
            <path d="M42 44 q 5 -6 10 0" fill="none" stroke={primary} strokeWidth="3" strokeLinecap="round" />
            <path d="M68 44 q 5 -6 10 0" fill="none" stroke={primary} strokeWidth="3" strokeLinecap="round" />
          </>
        ) : (
          <>
            <circle cx="47" cy="42" r="3.5" fill={primary} />
            <circle cx="73" cy="42" r="3.5" fill={primary} />
          </>
        )}
      </>
    );
  }

  if (itemKey === 'glasses') {
    return (
      <>
        <circle cx="47" cy="42" r="8.5" fill="none" stroke={primary} strokeWidth="2.5" />
        <circle cx="73" cy="42" r="8.5" fill="none" stroke={primary} strokeWidth="2.5" />
        <line x1="55.5" y1="42" x2="64.5" y2="42" stroke={primary} strokeWidth="2.5" strokeLinecap="round" />
      </>
    );
  }

  if (itemKey === 'starry') {
    return (
      <>
        <path d={starPath(47, 42, 6.5)} fill={gold} stroke={outline} strokeWidth="1" />
        <path d={starPath(73, 42, 6.5)} fill={gold} stroke={outline} strokeWidth="1" />
      </>
    );
  }

  if (itemKey === 'shades') {
    return (
      <>
        <rect x="38" y="35" width="18" height="12" rx="4" fill={outline} opacity="0.9" />
        <rect x="64" y="35" width="18" height="12" rx="4" fill={outline} opacity="0.9" />
        <line x1="56" y1="38" x2="64" y2="38" stroke={outline} strokeWidth="3" />
      </>
    );
  }

  // -- Phase 64 ------------------------------------------------------------

  if (itemKey === 'sleepy') {
    // Half-lidded: a heavy lid clipped over each base eye plus a lower lash
    // line. Reads the same whether the base eyes are dots or arcs, so no
    // happyEyes branch — a sleepy Circuit stays sleepy when it cheers.
    return (
      <>
        <path d="M39 42 q 8 -9 16 0 z" fill="hsl(var(--muted))" />
        <path d="M65 42 q 8 -9 16 0 z" fill="hsl(var(--muted))" />
        <path d="M39 42 q 8 -3 16 0" fill="none" stroke={outline} strokeWidth="3" strokeLinecap="round" />
        <path d="M65 42 q 8 -3 16 0" fill="none" stroke={outline} strokeWidth="3" strokeLinecap="round" />
      </>
    );
  }

  if (itemKey === 'heart') {
    const heart = (cx: number, cy: number) =>
      `M${cx} ${cy + 5.5} C${cx - 7} ${cy - 1} ${cx - 5} ${cy - 7} ${cx} ${cy - 3} ` +
      `C${cx + 5} ${cy - 7} ${cx + 7} ${cy - 1} ${cx} ${cy + 5.5} Z`;
    return (
      <>
        <path d={heart(47, 42)} fill="#f43f5e" stroke={outline} strokeWidth="1" />
        <path d={heart(73, 42)} fill="#f43f5e" stroke={outline} strokeWidth="1" />
      </>
    );
  }

  if (itemKey === 'scanner') {
    // A single sweeping sensor band replacing both eyes, so it needs its own
    // happy variant — the base arcs are hidden underneath.
    return (
      <>
        <rect x="36" y="36" width="48" height="12" rx="6" fill={outline} opacity="0.9" />
        {happyEyes ? (
          <path d="M46 42 q 14 -6 28 0" fill="none" stroke={primary} strokeWidth="3" strokeLinecap="round" />
        ) : (
          <>
            <circle cx="60" cy="42" r="4" fill={primary} />
            <circle cx="60" cy="42" r="7" fill="none" stroke={primary} strokeWidth="1.5" opacity="0.6" />
          </>
        )}
      </>
    );
  }

  if (itemKey === 'laser') {
    // Glowing pupils plus a short beam. On the happy poses the eyes are shut,
    // so the beams retract to a spark — a closed eye firing a laser reads
    // as a bug.
    return happyEyes ? (
      <>
        <path d="M42 44 q 5 -7 10 0" fill="none" stroke="#ef4444" strokeWidth="3.5" strokeLinecap="round" />
        <path d="M68 44 q 5 -7 10 0" fill="none" stroke="#ef4444" strokeWidth="3.5" strokeLinecap="round" />
      </>
    ) : (
      <>
        <circle cx="47" cy="42" r="5" fill="#ef4444" />
        <circle cx="73" cy="42" r="5" fill="#ef4444" />
        <circle cx="47" cy="42" r="2" fill="#fecaca" />
        <circle cx="73" cy="42" r="2" fill="#fecaca" />
        <path d="M47 42 L30 34" stroke="#ef4444" strokeWidth="2.5" strokeLinecap="round" opacity="0.75" />
        <path d="M73 42 L90 34" stroke="#ef4444" strokeWidth="2.5" strokeLinecap="round" opacity="0.75" />
      </>
    );
  }

  if (itemKey === 'focus') {
    // Narrowed, determined eyes with a hard brow — the streak-reward look.
    return (
      <>
        <rect x="40" y="39" width="14" height="6" rx="3" fill={outline} />
        <rect x="66" y="39" width="14" height="6" rx="3" fill={outline} />
        <circle cx="47" cy="42" r="2" fill={primary} />
        <circle cx="73" cy="42" r="2" fill={primary} />
        <line x1="39" y1="32" x2="54" y2="35.5" stroke={outline} strokeWidth="3" strokeLinecap="round" />
        <line x1="81" y1="32" x2="66" y2="35.5" stroke={outline} strokeWidth="3" strokeLinecap="round" />
      </>
    );
  }

  // 'none' and any unknown key: the base eyes show through unchanged.
  return null;
}

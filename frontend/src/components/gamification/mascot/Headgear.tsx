import { starPath } from '@/components/gamification/starPath';
import type { LayerProps } from './types';

/**
 * Headgear layer (Phase 33, extended Phase 64). Drawn over the head and
 * antenna, after the mouth and before the arms.
 *
 * The head rect occupies x 32–88, y 22–64; the antenna rises to y 8. Hats sit
 * on or above y ~28 so they read as worn rather than pasted on.
 */
export function Headgear({ itemKey, primary, surface, outline, gold }: LayerProps) {
  if (itemKey === 'cap') {
    return (
      <>
        <path d="M34 27 Q34 11 60 11 Q86 11 86 27 Z" fill={primary} stroke={outline} strokeWidth="2" />
        <rect x="58" y="25" width="38" height="5" rx="2.5" fill={primary} stroke={outline} strokeWidth="2" />
        <circle cx="60" cy="14" r="2.5" fill={surface} />
      </>
    );
  }

  if (itemKey === 'headphones') {
    return (
      <>
        <path d="M32 38 Q32 12 60 12 Q88 12 88 38" fill="none" stroke={outline} strokeWidth="4" strokeLinecap="round" />
        <rect x="26" y="34" width="10" height="18" rx="5" fill={primary} stroke={outline} strokeWidth="2" />
        <rect x="84" y="34" width="10" height="18" rx="5" fill={primary} stroke={outline} strokeWidth="2" />
      </>
    );
  }

  if (itemKey === 'wizard_hat') {
    return (
      <>
        <path d="M60 2 L42 28 L78 28 Z" fill={primary} stroke={outline} strokeWidth="2" />
        <ellipse cx="60" cy="28" rx="26" ry="5" fill={primary} stroke={outline} strokeWidth="2" />
        <path d={starPath(60, 16, 4)} fill={gold} />
      </>
    );
  }

  if (itemKey === 'crown') {
    return (
      <path
        d="M38 25 L38 10 L49 18 L60 6 L71 18 L82 10 L82 25 Z"
        fill={gold}
        stroke={outline}
        strokeWidth="2"
      />
    );
  }

  if (itemKey === 'halo') {
    return <ellipse cx="60" cy="6" rx="17" ry="5" fill="none" stroke={gold} strokeWidth="3.5" />;
  }

  // -- Phase 64 ------------------------------------------------------------

  if (itemKey === 'beanie') {
    return (
      <>
        {/* Slouchy dome pulled down over the brow */}
        <path d="M34 28 Q34 10 60 10 Q86 10 86 28 Z" fill={primary} stroke={outline} strokeWidth="2" />
        <rect x="32" y="25" width="56" height="7" rx="3.5" fill={surface} stroke={outline} strokeWidth="2" />
        {/* Pom-pom, offset for the slouch */}
        <circle cx="72" cy="8" r="5" fill={surface} stroke={outline} strokeWidth="2" />
      </>
    );
  }

  if (itemKey === 'hard_hat') {
    return (
      <>
        <path d="M36 26 Q36 8 60 8 Q84 8 84 26 Z" fill="#fbbf24" stroke={outline} strokeWidth="2" />
        <rect x="30" y="24" width="60" height="5" rx="2.5" fill="#f59e0b" stroke={outline} strokeWidth="2" />
        {/* Centre reinforcing ridge */}
        <path d="M60 8 L60 24" stroke={outline} strokeWidth="2" opacity="0.5" />
      </>
    );
  }

  if (itemKey === 'space_helmet') {
    return (
      <>
        {/* Bubble over the whole head — stroked, low-opacity fill so the face
            and any eye cosmetic underneath stay visible. */}
        <circle cx="60" cy="42" r="34" fill="#bae6fd" opacity="0.22" />
        <circle cx="60" cy="42" r="34" fill="none" stroke={primary} strokeWidth="2.5" />
        {/* Neck ring seals it to the body */}
        <rect x="40" y="64" width="40" height="7" rx="3.5" fill={surface} stroke={outline} strokeWidth="2" />
        {/* Specular highlight */}
        <path d="M38 30 Q44 20 56 16" fill="none" stroke="#f8fafc" strokeWidth="3" strokeLinecap="round" opacity="0.65" />
      </>
    );
  }

  if (itemKey === 'laurel') {
    return (
      <>
        {/* Two symmetrical sprigs curving up around the head */}
        <path d="M34 34 Q28 18 46 10" fill="none" stroke="#4ade80" strokeWidth="3" strokeLinecap="round" />
        <path d="M86 34 Q92 18 74 10" fill="none" stroke="#4ade80" strokeWidth="3" strokeLinecap="round" />
        <g fill="#22c55e">
          <ellipse cx="31" cy="27" rx="4" ry="2.5" transform="rotate(-50 31 27)" />
          <ellipse cx="34" cy="18" rx="4" ry="2.5" transform="rotate(-35 34 18)" />
          <ellipse cx="42" cy="11" rx="4" ry="2.5" transform="rotate(-15 42 11)" />
          <ellipse cx="89" cy="27" rx="4" ry="2.5" transform="rotate(50 89 27)" />
          <ellipse cx="86" cy="18" rx="4" ry="2.5" transform="rotate(35 86 18)" />
          <ellipse cx="78" cy="11" rx="4" ry="2.5" transform="rotate(15 78 11)" />
        </g>
        <circle cx="60" cy="9" r="3" fill={gold} stroke={outline} strokeWidth="1" />
      </>
    );
  }

  if (itemKey === 'flame_crest') {
    return (
      <>
        {/* A mohawk of flame along the crown, hottest at the centre */}
        <path d="M46 26 Q44 12 52 4 Q52 14 58 18 Q56 24 46 26 Z" fill="#f97316" />
        <path d="M58 26 Q56 8 66 0 Q64 12 72 18 Q70 24 58 26 Z" fill="#fb923c" />
        <path d="M68 27 Q68 16 78 10 Q74 18 80 24 Q76 27 68 27 Z" fill="#fbbf24" />
        <path d="M54 24 Q54 16 60 10 Q59 17 63 20 Q61 24 54 24 Z" fill="#fef08a" opacity="0.9" />
      </>
    );
  }

  // 'none' and any unknown key: just the antenna.
  return null;
}

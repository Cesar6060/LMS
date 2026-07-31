import { starPath } from '@/components/gamification/starPath';
import type { LayerProps } from './types';

/**
 * The accessory slot (Phase 33, extended Phase 64) renders in TWO passes,
 * because its items sit on opposite sides of Circuit in the draw order:
 *
 *   BehindBodyAccessory — before the antenna/head, so capes and wings hang
 *                         behind the whole robot.
 *   ChestAccessory      — after the body rect, so ties and pins sit on top.
 *
 * Every key belongs to exactly one pass; the other pass returns null for it.
 * Body rect is x 38–82 / y 70–102; the neck line is around y 64–70.
 */

/** Accessories drawn behind Circuit. */
export function BehindBodyAccessory({ itemKey, primary, surface, outline }: LayerProps) {
  if (itemKey === 'cape') {
    return (
      <path
        d="M40 70 Q22 94 30 106 Q45 100 60 106 Q75 100 90 106 Q98 94 80 70 Z"
        fill={primary}
        opacity="0.55"
      />
    );
  }

  if (itemKey === 'jetpack') {
    return (
      <>
        <rect x="24" y="70" width="11" height="24" rx="5.5" fill={surface} stroke={primary} strokeWidth="3" />
        <rect x="85" y="70" width="11" height="24" rx="5.5" fill={surface} stroke={primary} strokeWidth="3" />
        <path d="M27 96 l2.5 7 2.5 -7 z" fill="#f97316" />
        <path d="M88 96 l2.5 7 2.5 -7 z" fill="#f97316" />
      </>
    );
  }

  // -- Phase 64 ------------------------------------------------------------

  if (itemKey === 'backpack') {
    // Straps cross the chest in the front pass; the pack itself sits behind.
    return (
      <>
        <rect x="30" y="70" width="60" height="28" rx="8" fill={primary} stroke={outline} strokeWidth="2" opacity="0.9" />
        <rect x="38" y="76" width="44" height="10" rx="4" fill={surface} stroke={outline} strokeWidth="1.5" opacity="0.8" />
      </>
    );
  }

  if (itemKey === 'wings') {
    return (
      <>
        {/* Feathered circuit wings sweeping up and out from the shoulders */}
        <path
          d="M40 74 Q16 62 6 40 Q22 50 30 46 Q18 36 14 22 Q30 38 40 40 Z"
          fill={primary}
          stroke={outline}
          strokeWidth="1.5"
          opacity="0.75"
        />
        <path
          d="M80 74 Q104 62 114 40 Q98 50 90 46 Q102 36 106 22 Q90 38 80 40 Z"
          fill={primary}
          stroke={outline}
          strokeWidth="1.5"
          opacity="0.75"
        />
      </>
    );
  }

  return null;
}

/** Accessories drawn on Circuit's neck / chest, over the body. */
export function ChestAccessory({ itemKey, primary, surface, outline, gold }: LayerProps) {
  if (itemKey === 'bowtie') {
    return (
      <>
        <path d="M60 67 L48 61 L48 73 Z" fill={primary} stroke={outline} strokeWidth="1.5" />
        <path d="M60 67 L72 61 L72 73 Z" fill={primary} stroke={outline} strokeWidth="1.5" />
        <circle cx="60" cy="67" r="3" fill={outline} />
      </>
    );
  }

  if (itemKey === 'scarf') {
    return (
      <>
        <rect x="42" y="62" width="36" height="9" rx="4.5" fill={primary} stroke={outline} strokeWidth="1.5" />
        <rect x="64" y="66" width="9" height="16" rx="4" fill={primary} stroke={outline} strokeWidth="1.5" />
      </>
    );
  }

  if (itemKey === 'medal') {
    return (
      <>
        <path d="M42 68 L46 80 L50 68 Z" fill="#dc2626" />
        <circle cx="46" cy="84" r="6" fill={gold} stroke={outline} strokeWidth="1.5" />
        <path d={starPath(46, 84, 3)} fill={outline} opacity="0.7" />
      </>
    );
  }

  // -- Phase 64 ------------------------------------------------------------

  if (itemKey === 'backpack') {
    // The shoulder straps of the pack drawn behind.
    return (
      <>
        <path d="M46 66 L44 92" stroke={primary} strokeWidth="4" strokeLinecap="round" />
        <path d="M74 66 L76 92" stroke={primary} strokeWidth="4" strokeLinecap="round" />
        <rect x="42" y="78" width="36" height="4" rx="2" fill={primary} opacity="0.8" />
      </>
    );
  }

  if (itemKey === 'sash') {
    return (
      <>
        <path d="M42 66 L78 96 L72 102 L36 72 Z" fill={primary} stroke={outline} strokeWidth="1.5" />
        <circle cx="70" cy="90" r="4.5" fill={gold} stroke={outline} strokeWidth="1.5" />
      </>
    );
  }

  if (itemKey === 'marksman_pin') {
    // A small target pinned high on the chest.
    return (
      <>
        <circle cx="70" cy="78" r="7" fill={surface} stroke={outline} strokeWidth="1.5" />
        <circle cx="70" cy="78" r="4.5" fill="#ef4444" />
        <circle cx="70" cy="78" r="1.8" fill={surface} />
      </>
    );
  }

  return null;
}

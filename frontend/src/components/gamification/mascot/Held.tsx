import { starPath } from '@/components/gamification/starPath';
import type { HeldLayerProps } from './types';

/**
 * Held-item layer (Phase 64). Drawn after the arms so the item sits in front
 * of Circuit's right hand.
 *
 * Hand-tracking contract: every item is authored around a LOCAL origin of
 * (0,0) and wrapped in `translate(hand.x hand.y)`, where `hand` is the right
 * arm's current endpoint supplied by `Mascot` (it comes from the same
 * expressions that draw the arm line — (102,62) on `celebrate`, (98,94)
 * otherwise). Because the art never names an absolute coordinate, adding or
 * retuning a pose can't leave an item floating away from the hand.
 *
 * Items straddle the origin — a handle, stem or body passes through it — so
 * they read as gripped rather than parked next to the hand. Long upright items
 * (torch, blade) also take a small outward tilt on `celebrate`, the only pose
 * where the RIGHT arm raises.
 */
export function Held({ itemKey, primary, surface, outline, gold, pose, gradientId, hand }: HeldLayerProps) {
  const raised = pose === 'celebrate';

  /** Local origin == the hand; `tilt` (deg, clockwise) angles long items out. */
  const grip = (tilt = 0): string =>
    `translate(${hand.x} ${hand.y})${tilt ? ` rotate(${tilt})` : ''}`;

  if (itemKey === 'wrench') {
    return (
      <g transform={grip()}>
        {/* Grip runs through the hand, jaw sits above it */}
        <rect x="-2.5" y="-8" width="5" height="17" rx="2.5" fill={surface} stroke={outline} strokeWidth="1.5" />
        {/* Open-end head: a block with a slot cut out of the top */}
        <path
          d="M-5.5 -15 L-5.5 -7 L5.5 -7 L5.5 -15 L2 -15 L2 -11 L-2 -11 L-2 -15 Z"
          fill={primary}
          stroke={outline}
          strokeWidth="1.5"
          strokeLinejoin="round"
        />
      </g>
    );
  }

  if (itemKey === 'controller') {
    return (
      <g transform={grip()}>
        {/* Body centred on the hand so both grips are supported */}
        <rect x="-11" y="-6.5" width="22" height="13" rx="5.5" fill={primary} stroke={outline} strokeWidth="2" />
        {/* D-pad */}
        <rect x="-9" y="-1.25" width="7" height="2.5" rx="1.25" fill={surface} />
        <rect x="-6.75" y="-3.5" width="2.5" height="7" rx="1.25" fill={surface} />
        {/* Face buttons */}
        <circle cx="5" cy="-2" r="1.8" fill={surface} />
        <circle cx="8.5" cy="1.5" r="1.8" fill={surface} />
      </g>
    );
  }

  if (itemKey === 'codex') {
    return (
      <g transform={grip()}>
        {/* Closed tome, spine to the left, page block to the right */}
        <rect x="-8" y="-10" width="16" height="20" rx="2" fill={primary} stroke={outline} strokeWidth="2" />
        <rect x="4" y="-8" width="4" height="16" rx="1" fill={surface} stroke={outline} strokeWidth="1.5" />
        {/* Spine ridge */}
        <path d="M-5 -10 L-5 10" stroke={outline} strokeWidth="1.5" opacity="0.45" />
        {/* Rune clasp on the cover */}
        <path d="M-1 -1 L2 -4 L5 -1 L2 2 Z" fill={gold} stroke={outline} strokeWidth="1" />
      </g>
    );
  }

  if (itemKey === 'debug_blade') {
    return (
      <g transform={grip(raised ? 20 : 0)}>
        {/* Hilt: grip through the hand, pommel below, guard above */}
        <rect x="-1.75" y="-3" width="3.5" height="9" rx="1.75" fill={outline} />
        <circle cx="0" cy="7" r="2.2" fill={gold} stroke={outline} strokeWidth="1" />
        <rect x="-6" y="-5" width="12" height="3" rx="1.5" fill={gold} stroke={outline} strokeWidth="1.5" />
        {/* Blade */}
        <path
          d="M-3 -5 L-3 -14 L0 -17.5 L3 -14 L3 -5 Z"
          fill={surface}
          stroke={outline}
          strokeWidth="1.5"
          strokeLinejoin="round"
        />
        {/* Energised fuller — the "debug" glow */}
        <path d="M0 -13 L0 -6" stroke={primary} strokeWidth="1.5" strokeLinecap="round" opacity="0.8" />
      </g>
    );
  }

  if (itemKey === 'torch') {
    return (
      <g transform={grip(raised ? 18 : 0)}>
        <defs>
          <linearGradient id={`${gradientId}-held-torch`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#fbbf24" />
            <stop offset="55%" stopColor="#f97316" />
            <stop offset="100%" stopColor="#ef4444" />
          </linearGradient>
        </defs>
        {/* Shaft passes through the hand */}
        <rect x="-2" y="-3" width="4" height="12" rx="2" fill="#92400e" stroke={outline} strokeWidth="1.5" />
        <rect x="-4.5" y="-7" width="9" height="4" rx="1.5" fill={surface} stroke={outline} strokeWidth="1.5" />
        {/* Streak flame */}
        <path
          d="M0 -18 Q5.5 -13 5 -9.5 Q4.5 -7 0 -7 Q-4.5 -7 -5 -9.5 Q-5.5 -13 0 -18 Z"
          fill={`url(#${gradientId}-held-torch)`}
        />
        <path
          d="M0 -15 Q3 -11.5 2.6 -9.5 Q2.2 -8 0 -8 Q-2.2 -8 -2.6 -9.5 Q-3 -11.5 0 -15 Z"
          fill="#fef08a"
          opacity="0.95"
          className="animate-pulse motion-reduce:animate-none"
        />
      </g>
    );
  }

  if (itemKey === 'trophy') {
    return (
      <g transform={grip()}>
        {/* Stem passes through the hand; bowl above, base below */}
        <rect x="-8" y="-16.5" width="16" height="3" rx="1.5" fill={gold} stroke={outline} strokeWidth="1.5" />
        <path d="M-7 -13.5 L7 -13.5 L5.5 -6.5 Q0 -3 -5.5 -6.5 Z" fill={gold} stroke={outline} strokeWidth="1.5" />
        {/* Ear handles */}
        <path d="M-7 -13 Q-11.5 -11 -6.5 -7.5" fill="none" stroke={gold} strokeWidth="2.2" strokeLinecap="round" />
        <path d="M7 -13 Q11.5 -11 6.5 -7.5" fill="none" stroke={gold} strokeWidth="2.2" strokeLinecap="round" />
        <rect x="-2" y="-5" width="4" height="6" fill={gold} stroke={outline} strokeWidth="1.25" />
        <rect x="-6.5" y="1" width="13" height="3.5" rx="1.5" fill={gold} stroke={outline} strokeWidth="1.5" />
        {/* Engraved star */}
        <path d={starPath(0, -10, 3)} fill={outline} opacity="0.45" />
      </g>
    );
  }

  // 'none' and any unknown key: empty hand.
  return null;
}

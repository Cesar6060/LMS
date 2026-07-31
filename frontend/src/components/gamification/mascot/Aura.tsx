import { starPath } from '@/components/gamification/starPath';
import type { LayerProps } from './types';

/**
 * Aura layer (Phase 64). Drawn immediately after the backdrop and before the
 * antenna/head/body, so it sits UNDER the whole robot and reads as a halo
 * around the silhouette rather than an overlay on it.
 *
 * Face clearance rule: Circuit's head is x 32–88 / y 22–64 and the face lives
 * around x 40–80 / y 34–56 (r ~33 from the 60,60 centre). Every aura element
 * therefore stays outside r ~40 of (60,60), or drops to opacity <= 0.3 where
 * it crosses that inner zone. Animation is Tailwind-utility only, and always
 * paired with `motion-reduce:animate-none`.
 */
export function Aura({ itemKey, primary, gold, gradientId }: LayerProps) {
  if (itemKey === 'sparkle') {
    return (
      <>
        {/* Scattered four-point stars ringing the silhouette; the second set
            twinkles out of phase with the first by being the animated group. */}
        <g fill={gold} opacity="0.9">
          <path d={starPath(18, 28, 4)} />
          <path d={starPath(108, 58, 3.6)} />
          <path d={starPath(26, 98, 3.4)} />
        </g>
        <g fill={gold} opacity="0.75" className="animate-pulse motion-reduce:animate-none">
          <path d={starPath(99, 24, 3.2)} />
          <path d={starPath(12, 62, 3)} />
          <path d={starPath(96, 100, 3)} />
        </g>
      </>
    );
  }

  if (itemKey === 'pulse') {
    return (
      <>
        <defs>
          {/* Transparent core so the glow only blooms outside the body */}
          <radialGradient id={`${gradientId}-aura-pulse`}>
            <stop offset="55%" stopColor={primary} stopOpacity="0" />
            <stop offset="80%" stopColor={primary} stopOpacity="0.45" />
            <stop offset="100%" stopColor={primary} stopOpacity="0" />
          </radialGradient>
        </defs>
        <circle
          cx="60"
          cy="60"
          r="58"
          fill={`url(#${gradientId}-aura-pulse)`}
          className="animate-pulse motion-reduce:animate-none"
        />
        <circle cx="60" cy="60" r="46" fill="none" stroke={primary} strokeWidth="2" opacity="0.35" />
      </>
    );
  }

  if (itemKey === 'electric') {
    return (
      <>
        {/* Crackling broken ring */}
        <circle
          cx="60"
          cy="60"
          r="48"
          fill="none"
          stroke={primary}
          strokeWidth="2"
          strokeDasharray="4 7"
          opacity="0.5"
          className="animate-pulse motion-reduce:animate-none"
        />
        {/* Bolts arcing off the shoulders and hips, well clear of the face */}
        <g
          fill="none"
          stroke={primary}
          strokeWidth="3"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="animate-pulse motion-reduce:animate-none"
        >
          <path d="M22 38 L12 52 L19 52 L9 68" />
          <path d="M98 38 L108 52 L101 52 L111 68" />
          <path d="M34 92 L26 104 L33 103 L25 116" />
          <path d="M86 92 L94 104 L87 103 L95 116" />
        </g>
      </>
    );
  }

  if (itemKey === 'rainbow') {
    return (
      <>
        <defs>
          {/* One multi-stop sweep drives both rings, so the hues stay in order */}
          <linearGradient id={`${gradientId}-aura-rainbow`} x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#f87171" />
            <stop offset="20%" stopColor="#fb923c" />
            <stop offset="40%" stopColor="#facc15" />
            <stop offset="60%" stopColor="#4ade80" />
            <stop offset="80%" stopColor="#38bdf8" />
            <stop offset="100%" stopColor="#a78bfa" />
          </linearGradient>
        </defs>
        <circle
          cx="60"
          cy="60"
          r="50"
          fill="none"
          stroke={`url(#${gradientId}-aura-rainbow)`}
          strokeWidth="8"
          opacity="0.55"
          className="animate-pulse motion-reduce:animate-none"
        />
        <circle
          cx="60"
          cy="60"
          r="42"
          fill="none"
          stroke={`url(#${gradientId}-aura-rainbow)`}
          strokeWidth="3"
          opacity="0.3"
        />
      </>
    );
  }

  if (itemKey === 'flame_ring') {
    return (
      <>
        <defs>
          <radialGradient id={`${gradientId}-aura-flame`}>
            <stop offset="58%" stopColor="#f97316" stopOpacity="0" />
            <stop offset="85%" stopColor="#f97316" stopOpacity="0.4" />
            <stop offset="100%" stopColor="#fbbf24" stopOpacity="0" />
          </radialGradient>
        </defs>
        <circle cx="60" cy="60" r="58" fill={`url(#${gradientId}-aura-flame)`} />
        {/* Ember ring the tongues rise from (their bases sit at r 43) */}
        <circle cx="60" cy="60" r="43" fill="none" stroke="#fb923c" strokeWidth="3" opacity="0.45" />
        {/* One tongue authored pointing up, then rotated around the centre.
            Angles skip 0/180 so nothing stacks on the antenna or the feet. */}
        <g className="animate-pulse motion-reduce:animate-none">
          <g fill="#f97316">
            <path d="M60 4 Q66 11 65 17 Q60 13 55 17 Q54 11 60 4 Z" transform="rotate(25 60 60)" />
            <path d="M60 4 Q66 11 65 17 Q60 13 55 17 Q54 11 60 4 Z" transform="rotate(115 60 60)" />
            <path d="M60 4 Q66 11 65 17 Q60 13 55 17 Q54 11 60 4 Z" transform="rotate(205 60 60)" />
            <path d="M60 4 Q66 11 65 17 Q60 13 55 17 Q54 11 60 4 Z" transform="rotate(295 60 60)" />
          </g>
          <g fill="#fbbf24">
            <path d="M60 4 Q66 11 65 17 Q60 13 55 17 Q54 11 60 4 Z" transform="rotate(65 60 60)" />
            <path d="M60 4 Q66 11 65 17 Q60 13 55 17 Q54 11 60 4 Z" transform="rotate(155 60 60)" />
            <path d="M60 4 Q66 11 65 17 Q60 13 55 17 Q54 11 60 4 Z" transform="rotate(245 60 60)" />
            <path d="M60 4 Q66 11 65 17 Q60 13 55 17 Q54 11 60 4 Z" transform="rotate(335 60 60)" />
          </g>
        </g>
      </>
    );
  }

  if (itemKey === 'golden') {
    return (
      <>
        <defs>
          <radialGradient id={`${gradientId}-aura-golden`}>
            <stop offset="52%" stopColor="#fde68a" stopOpacity="0" />
            <stop offset="82%" stopColor={gold} stopOpacity="0.5" />
            <stop offset="100%" stopColor={gold} stopOpacity="0" />
          </radialGradient>
        </defs>
        <circle
          cx="60"
          cy="60"
          r="58"
          fill={`url(#${gradientId}-aura-golden)`}
          className="animate-pulse motion-reduce:animate-none"
        />
        {/* Sunburst crown: a dashed ring reads as 12 evenly spaced rays.
            Circumference at r 48 is ~301.6, so 7 + 18.13 lands 12 per turn. */}
        <circle
          cx="60"
          cy="60"
          r="48"
          fill="none"
          stroke={gold}
          strokeWidth="9"
          strokeDasharray="7 18.13"
          opacity="0.7"
        />
        <g fill="#fef3c7" opacity="0.9">
          <path d={starPath(16, 34, 3.6)} />
          <path d={starPath(104, 30, 3)} />
          <path d={starPath(100, 96, 3.2)} />
        </g>
      </>
    );
  }

  // 'none' and any unknown key: no aura.
  return null;
}

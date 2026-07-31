import { starPath } from '@/components/gamification/starPath';
import type { LayerProps } from './types';

/**
 * The backdrop panel inside the mascot SVG (Phase 33, extended Phase 64).
 * Drawn first, behind everything.
 *
 * The panel fills the full extended viewBox (-18..138) rather than the old
 * 0..120 body box, so a customizer tile stays framed after the phase-64
 * margin was added.
 *
 * Every key here must ALSO exist in `BackdropScene.tsx` (container-scale) and
 * in `backdrop.ts` (`SceneTheme`). A backdrop present in only one of the three
 * renders a mismatched dashboard hero — see the phase-64 spec.
 */
export function Backdrop({ itemKey, primary, gradientId }: LayerProps) {
  if (itemKey === 'plain') {
    return (
      <rect x="-18" y="-18" width="156" height="156" rx="18" fill="hsl(var(--muted))" opacity="0.5" />
    );
  }

  if (itemKey === 'grid') {
    return (
      <>
        <rect x="-18" y="-18" width="156" height="156" rx="18" fill="hsl(var(--muted))" opacity="0.5" />
        <g stroke={primary} strokeWidth="1" opacity="0.25">
          <line x1="2" y1="30" x2="118" y2="30" />
          <line x1="2" y1="60" x2="118" y2="60" />
          <line x1="2" y1="90" x2="118" y2="90" />
          <line x1="30" y1="2" x2="30" y2="118" />
          <line x1="60" y1="2" x2="60" y2="118" />
          <line x1="90" y1="2" x2="90" y2="118" />
        </g>
      </>
    );
  }

  if (itemKey === 'stars') {
    return (
      <>
        <rect x="-18" y="-18" width="156" height="156" rx="18" fill="#0f172a" opacity="0.85" />
        <path d={starPath(18, 20, 3.5)} fill="#e2e8f0" opacity="0.9" />
        <path d={starPath(100, 16, 2.8)} fill="#facc15" opacity="0.9" />
        <path d={starPath(106, 62, 3.2)} fill="#e2e8f0" opacity="0.8" />
        <path d={starPath(14, 74, 2.6)} fill="#facc15" opacity="0.8" />
        <path d={starPath(94, 102, 3)} fill="#e2e8f0" opacity="0.7" />
      </>
    );
  }

  if (itemKey === 'sunset') {
    return (
      <>
        <defs>
          <linearGradient id={`${gradientId}-sunset`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#fbbf24" />
            <stop offset="55%" stopColor="#f97316" />
            <stop offset="100%" stopColor="#ec4899" />
          </linearGradient>
        </defs>
        <rect x="-18" y="-18" width="156" height="156" rx="18" fill={`url(#${gradientId}-sunset)`} opacity="0.55" />
        <circle cx="60" cy="46" r="16" fill="#fde68a" opacity="0.6" />
      </>
    );
  }

  if (itemKey === 'galaxy') {
    return (
      <>
        <defs>
          <linearGradient id={`${gradientId}-galaxy`} x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#1e1b4b" />
            <stop offset="55%" stopColor="#5b21b6" />
            <stop offset="100%" stopColor="#0f172a" />
          </linearGradient>
        </defs>
        <rect x="-18" y="-18" width="156" height="156" rx="18" fill={`url(#${gradientId}-galaxy)`} opacity="0.85" />
        <ellipse cx="88" cy="26" rx="14" ry="5" fill="#a78bfa" opacity="0.45" transform="rotate(-18 88 26)" />
        <path d={starPath(22, 24, 3)} fill="#e2e8f0" opacity="0.9" />
        <path d={starPath(102, 80, 2.8)} fill="#e2e8f0" opacity="0.8" />
        <path d={starPath(16, 96, 2.4)} fill="#c4b5fd" opacity="0.9" />
      </>
    );
  }

  // -- Phase 64 ------------------------------------------------------------

  if (itemKey === 'forest') {
    return (
      <>
        <defs>
          <linearGradient id={`${gradientId}-forest`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#064e3b" />
            <stop offset="100%" stopColor="#022c22" />
          </linearGradient>
        </defs>
        <rect x="-18" y="-18" width="156" height="156" rx="18" fill={`url(#${gradientId}-forest)`} opacity="0.9" />
        {/* Canopy: overlapping conifer silhouettes along the top edge */}
        <g fill="#065f46" opacity="0.85">
          <path d="M16 46 L26 18 L36 46 Z" />
          <path d="M38 40 L48 8 L58 40 Z" />
          <path d="M62 44 L72 14 L82 44 Z" />
          <path d="M86 38 L96 10 L106 38 Z" />
        </g>
        <g fill="#047857" opacity="0.6">
          <path d="M6 50 L16 26 L26 50 Z" />
          <path d="M96 50 L106 24 L116 50 Z" />
        </g>
        {/* Light shafts through the canopy */}
        <path d="M40 12 L52 118 L44 118 Z" fill="#a7f3d0" opacity="0.1" />
        <path d="M92 14 L102 118 L96 118 Z" fill="#a7f3d0" opacity="0.08" />
      </>
    );
  }

  if (itemKey === 'arcade') {
    return (
      <>
        <defs>
          <linearGradient id={`${gradientId}-arcade`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#1e1b4b" />
            <stop offset="100%" stopColor="#4c1d95" />
          </linearGradient>
        </defs>
        <rect x="-18" y="-18" width="156" height="156" rx="18" fill={`url(#${gradientId}-arcade)`} opacity="0.92" />
        {/* Perspective floor grid receding to a horizon */}
        <g stroke="#f472b6" strokeWidth="1" opacity="0.5">
          <line x1="2" y1="76" x2="118" y2="76" />
          <line x1="2" y1="88" x2="118" y2="88" />
          <line x1="2" y1="104" x2="118" y2="104" />
          <line x1="60" y1="76" x2="30" y2="118" />
          <line x1="60" y1="76" x2="90" y2="118" />
          <line x1="60" y1="76" x2="2" y2="106" />
          <line x1="60" y1="76" x2="118" y2="106" />
        </g>
        {/* Neon glow bars top-left / top-right */}
        <rect x="10" y="14" width="22" height="4" rx="2" fill="#22d3ee" opacity="0.75" />
        <rect x="88" y="24" width="20" height="4" rx="2" fill="#f472b6" opacity="0.75" />
      </>
    );
  }

  if (itemKey === 'aurora_sky') {
    return (
      <>
        <defs>
          <linearGradient id={`${gradientId}-aurorasky`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#020617" />
            <stop offset="100%" stopColor="#0f172a" />
          </linearGradient>
          <linearGradient id={`${gradientId}-aurorasky-ribbon`} x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="#34d399" stopOpacity="0" />
            <stop offset="45%" stopColor="#34d399" stopOpacity="0.85" />
            <stop offset="100%" stopColor="#818cf8" stopOpacity="0" />
          </linearGradient>
        </defs>
        <rect x="-18" y="-18" width="156" height="156" rx="18" fill={`url(#${gradientId}-aurorasky)`} />
        <path
          d="M2 34 Q34 14 60 30 Q88 46 118 22 L118 44 Q88 66 60 50 Q34 34 2 54 Z"
          fill={`url(#${gradientId}-aurorasky-ribbon)`}
          opacity="0.75"
        />
        <path
          d="M2 54 Q30 40 60 54 Q92 68 118 48 L118 62 Q92 82 60 68 Q30 54 2 70 Z"
          fill={`url(#${gradientId}-aurorasky-ribbon)`}
          opacity="0.4"
        />
        <path d={starPath(20, 16, 2.6)} fill="#e2e8f0" opacity="0.85" />
        <path d={starPath(98, 12, 2.2)} fill="#e2e8f0" opacity="0.7" />
        <path d={starPath(108, 92, 2.4)} fill="#e2e8f0" opacity="0.6" />
      </>
    );
  }

  // 'none' and any unknown key: no panel.
  return null;
}

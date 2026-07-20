import { useId } from 'react';
import { cn } from '@/lib/utils';
import { useAvatarContext } from '@/contexts/AvatarContext';
import { starPath } from '@/components/gamification/starPath';
import type { AvatarEquipped } from '@/types';

export type MascotPose = 'idle' | 'cheer' | 'encourage' | 'celebrate';

interface MascotProps {
  pose?: MascotPose;
  /** Rendered width/height in px. */
  size?: number;
  className?: string;
  /**
   * Explicit cosmetic overrides (Phase 33). Defaults to the logged-in
   * student's equipped items from AvatarContext, so existing call sites
   * pick up the custom look automatically. Pass values (e.g. a pending
   * selection) to preview a different look.
   */
  customization?: Partial<AvatarEquipped> | null;
  /**
   * Skip the backdrop panel layer (Phase 34): the dashboard hero renders the
   * equipped backdrop at container scale, so the SVG's own panel would
   * double-render the scene.
   */
  hideBackdrop?: boolean;
}

/** Palette swaps per color-scheme key. `classic` stays on the theme var. */
const COLOR_SCHEMES: Record<string, string> = {
  classic: 'hsl(var(--primary))',
  ember: '#f97316',
  ocean: '#0ea5e9',
  bubblegum: '#ec4899',
  gold: '#f59e0b',
};

const GOLD = '#facc15';

/**
 * "Circuit" — the STEM Quest robot mascot. Single built-in inline SVG with a
 * few poses, used in the quiz mastery flow's feedback moments and the
 * dashboard avatar card. Theme-aware via CSS variables; CSS-only animation.
 * Cosmetic slots (color / headgear / eyes / accessory) render as palette
 * swaps and extra SVG layers; unknown keys fall back to the slot default.
 */
export function Mascot({ pose = 'idle', size = 96, className, customization, hideBackdrop = false }: MascotProps) {
  const { avatar } = useAvatarContext();
  const equipped = customization ?? avatar?.equipped ?? null;

  const primary = COLOR_SCHEMES[equipped?.color ?? 'classic'] ?? COLOR_SCHEMES.classic;
  const surface = 'hsl(var(--muted))';
  const outline = 'hsl(var(--foreground))';

  const headgear = equipped?.headgear ?? 'none';
  const eyes = equipped?.eyes ?? 'none';
  const accessory = equipped?.accessory ?? 'none';
  const backdrop = hideBackdrop ? 'none' : equipped?.backdrop ?? 'plain';
  const name = avatar?.mascot_name ?? 'Circuit';
  // Gradient ids must be unique per mascot instance — the customizer grid
  // renders many at once.
  const gradientId = useId();

  const armsUp = pose === 'celebrate';
  const oneArmUp = pose === 'cheer';
  const happyEyes = pose === 'cheer' || pose === 'celebrate';

  return (
    <div
      className={cn(
        'inline-block select-none',
        (pose === 'cheer' || pose === 'celebrate') && 'animate-bounce',
        className
      )}
      style={{ width: size, height: size }}
      role="img"
      aria-label={`${name} the robot (${pose})`}
    >
      <svg viewBox="0 0 120 120" width={size} height={size}>
        {/* Backdrop container (drawn first, behind everything) */}
        {backdrop === 'plain' && (
          <rect x="2" y="2" width="116" height="116" rx="14" fill="hsl(var(--muted))" opacity="0.5" />
        )}
        {backdrop === 'grid' && (
          <>
            <rect x="2" y="2" width="116" height="116" rx="14" fill="hsl(var(--muted))" opacity="0.5" />
            <g stroke={primary} strokeWidth="1" opacity="0.25">
              <line x1="2" y1="30" x2="118" y2="30" />
              <line x1="2" y1="60" x2="118" y2="60" />
              <line x1="2" y1="90" x2="118" y2="90" />
              <line x1="30" y1="2" x2="30" y2="118" />
              <line x1="60" y1="2" x2="60" y2="118" />
              <line x1="90" y1="2" x2="90" y2="118" />
            </g>
          </>
        )}
        {backdrop === 'stars' && (
          <>
            <rect x="2" y="2" width="116" height="116" rx="14" fill="#0f172a" opacity="0.85" />
            <path d={starPath(18, 20, 3.5)} fill="#e2e8f0" opacity="0.9" />
            <path d={starPath(100, 16, 2.8)} fill={GOLD} opacity="0.9" />
            <path d={starPath(106, 62, 3.2)} fill="#e2e8f0" opacity="0.8" />
            <path d={starPath(14, 74, 2.6)} fill={GOLD} opacity="0.8" />
            <path d={starPath(94, 102, 3)} fill="#e2e8f0" opacity="0.7" />
          </>
        )}
        {backdrop === 'sunset' && (
          <>
            <defs>
              <linearGradient id={`${gradientId}-sunset`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#fbbf24" />
                <stop offset="55%" stopColor="#f97316" />
                <stop offset="100%" stopColor="#ec4899" />
              </linearGradient>
            </defs>
            <rect x="2" y="2" width="116" height="116" rx="14" fill={`url(#${gradientId}-sunset)`} opacity="0.55" />
            <circle cx="60" cy="46" r="16" fill="#fde68a" opacity="0.6" />
          </>
        )}
        {backdrop === 'galaxy' && (
          <>
            <defs>
              <linearGradient id={`${gradientId}-galaxy`} x1="0" y1="0" x2="1" y2="1">
                <stop offset="0%" stopColor="#1e1b4b" />
                <stop offset="55%" stopColor="#5b21b6" />
                <stop offset="100%" stopColor="#0f172a" />
              </linearGradient>
            </defs>
            <rect x="2" y="2" width="116" height="116" rx="14" fill={`url(#${gradientId}-galaxy)`} opacity="0.85" />
            <ellipse cx="88" cy="26" rx="14" ry="5" fill="#a78bfa" opacity="0.45" transform="rotate(-18 88 26)" />
            <path d={starPath(22, 24, 3)} fill="#e2e8f0" opacity="0.9" />
            <path d={starPath(102, 80, 2.8)} fill="#e2e8f0" opacity="0.8" />
            <path d={starPath(16, 96, 2.4)} fill="#c4b5fd" opacity="0.9" />
          </>
        )}

        {/* Behind-the-body accessories */}
        {accessory === 'cape' && (
          <path
            d="M40 70 Q22 94 30 106 Q45 100 60 106 Q75 100 90 106 Q98 94 80 70 Z"
            fill={primary}
            opacity="0.55"
          />
        )}
        {accessory === 'jetpack' && (
          <>
            <rect x="24" y="70" width="11" height="24" rx="5.5" fill={surface} stroke={primary} strokeWidth="3" />
            <rect x="85" y="70" width="11" height="24" rx="5.5" fill={surface} stroke={primary} strokeWidth="3" />
            <path d="M27 96 l2.5 7 2.5 -7 z" fill="#f97316" />
            <path d="M88 96 l2.5 7 2.5 -7 z" fill="#f97316" />
          </>
        )}

        {/* Antenna */}
        <line x1="60" y1="22" x2="60" y2="10" stroke={outline} strokeWidth="3" strokeLinecap="round" />
        <circle cx="60" cy="8" r="4.5" fill={primary} className={pose === 'celebrate' ? 'animate-pulse' : undefined} />

        {/* Head */}
        <rect x="32" y="22" width="56" height="42" rx="12" fill={surface} stroke={primary} strokeWidth="3.5" />

        {/* Eyes */}
        {happyEyes ? (
          <>
            {/* Happy closed-arc eyes */}
            <path d="M42 44 q 5 -7 10 0" fill="none" stroke={outline} strokeWidth="3.5" strokeLinecap="round" />
            <path d="M68 44 q 5 -7 10 0" fill="none" stroke={outline} strokeWidth="3.5" strokeLinecap="round" />
          </>
        ) : (
          <>
            <circle cx="47" cy="42" r="4.5" fill={outline} />
            <circle cx="73" cy="42" r="4.5" fill={outline} />
            {pose === 'encourage' && (
              /* Raised, determined brows */
              <>
                <line x1="41" y1="33" x2="52" y2="35.5" stroke={outline} strokeWidth="3" strokeLinecap="round" />
                <line x1="79" y1="33" x2="68" y2="35.5" stroke={outline} strokeWidth="3" strokeLinecap="round" />
              </>
            )}
          </>
        )}

        {/* Eye-slot cosmetics (drawn over the base eyes) */}
        {eyes === 'visor' && (
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
        )}
        {eyes === 'glasses' && (
          <>
            <circle cx="47" cy="42" r="8.5" fill="none" stroke={primary} strokeWidth="2.5" />
            <circle cx="73" cy="42" r="8.5" fill="none" stroke={primary} strokeWidth="2.5" />
            <line x1="55.5" y1="42" x2="64.5" y2="42" stroke={primary} strokeWidth="2.5" strokeLinecap="round" />
          </>
        )}
        {eyes === 'starry' && (
          <>
            <path d={starPath(47, 42, 6.5)} fill={GOLD} stroke={outline} strokeWidth="1" />
            <path d={starPath(73, 42, 6.5)} fill={GOLD} stroke={outline} strokeWidth="1" />
          </>
        )}
        {eyes === 'shades' && (
          <>
            <rect x="38" y="35" width="18" height="12" rx="4" fill={outline} opacity="0.9" />
            <rect x="64" y="35" width="18" height="12" rx="4" fill={outline} opacity="0.9" />
            <line x1="56" y1="38" x2="64" y2="38" stroke={outline} strokeWidth="3" />
          </>
        )}

        {/* Mouth */}
        {pose === 'celebrate' ? (
          <path d="M48 52 q 12 12 24 0 z" fill={primary} opacity="0.85" />
        ) : pose === 'cheer' ? (
          <path d="M48 52 q 12 9 24 0" fill="none" stroke={outline} strokeWidth="3.5" strokeLinecap="round" />
        ) : pose === 'encourage' ? (
          <path d="M50 55 q 10 4 20 0" fill="none" stroke={outline} strokeWidth="3" strokeLinecap="round" />
        ) : (
          <line x1="51" y1="54" x2="69" y2="54" stroke={outline} strokeWidth="3.5" strokeLinecap="round" />
        )}

        {/* Headgear (drawn over the head/antenna) */}
        {headgear === 'cap' && (
          <>
            <path d="M34 27 Q34 11 60 11 Q86 11 86 27 Z" fill={primary} stroke={outline} strokeWidth="2" />
            <rect x="58" y="25" width="38" height="5" rx="2.5" fill={primary} stroke={outline} strokeWidth="2" />
            <circle cx="60" cy="14" r="2.5" fill={surface} />
          </>
        )}
        {headgear === 'headphones' && (
          <>
            <path d="M32 38 Q32 12 60 12 Q88 12 88 38" fill="none" stroke={outline} strokeWidth="4" strokeLinecap="round" />
            <rect x="26" y="34" width="10" height="18" rx="5" fill={primary} stroke={outline} strokeWidth="2" />
            <rect x="84" y="34" width="10" height="18" rx="5" fill={primary} stroke={outline} strokeWidth="2" />
          </>
        )}
        {headgear === 'wizard_hat' && (
          <>
            <path d="M60 2 L42 28 L78 28 Z" fill={primary} stroke={outline} strokeWidth="2" />
            <ellipse cx="60" cy="28" rx="26" ry="5" fill={primary} stroke={outline} strokeWidth="2" />
            <path d={starPath(60, 16, 4)} fill={GOLD} />
          </>
        )}
        {headgear === 'crown' && (
          <path
            d="M38 25 L38 10 L49 18 L60 6 L71 18 L82 10 L82 25 Z"
            fill={GOLD}
            stroke={outline}
            strokeWidth="2"
          />
        )}
        {headgear === 'halo' && (
          <ellipse cx="60" cy="6" rx="17" ry="5" fill="none" stroke={GOLD} strokeWidth="3.5" />
        )}

        {/* Arms */}
        <line
          x1="34" y1="82"
          x2={armsUp || oneArmUp ? 18 : 22}
          y2={armsUp || oneArmUp ? 62 : 94}
          stroke={primary} strokeWidth="4" strokeLinecap="round"
        />
        <line
          x1="86" y1="82"
          x2={armsUp ? 102 : 98}
          y2={armsUp ? 62 : 94}
          stroke={primary} strokeWidth="4" strokeLinecap="round"
        />

        {/* Body with a circuit bolt */}
        <rect x="38" y="70" width="44" height="32" rx="9" fill={surface} stroke={primary} strokeWidth="3.5" />
        <path d="M62 75 L53 88 h6 l-2 10 9 -13 h-6 z" fill={primary} />

        {/* Neck / chest accessories (drawn over the body) */}
        {accessory === 'bowtie' && (
          <>
            <path d="M60 67 L48 61 L48 73 Z" fill={primary} stroke={outline} strokeWidth="1.5" />
            <path d="M60 67 L72 61 L72 73 Z" fill={primary} stroke={outline} strokeWidth="1.5" />
            <circle cx="60" cy="67" r="3" fill={outline} />
          </>
        )}
        {accessory === 'scarf' && (
          <>
            <rect x="42" y="62" width="36" height="9" rx="4.5" fill={primary} stroke={outline} strokeWidth="1.5" />
            <rect x="64" y="66" width="9" height="16" rx="4" fill={primary} stroke={outline} strokeWidth="1.5" />
          </>
        )}
        {accessory === 'medal' && (
          <>
            <path d="M42 68 L46 80 L50 68 Z" fill="#dc2626" />
            <circle cx="46" cy="84" r="6" fill={GOLD} stroke={outline} strokeWidth="1.5" />
            <path d={starPath(46, 84, 3)} fill={outline} opacity="0.7" />
          </>
        )}

        {/* Feet */}
        <circle cx="48" cy="108" r="5" fill={outline} opacity="0.7" />
        <circle cx="72" cy="108" r="5" fill={outline} opacity="0.7" />
      </svg>
    </div>
  );
}

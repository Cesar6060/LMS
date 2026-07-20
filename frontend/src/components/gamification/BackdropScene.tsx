import { useId } from 'react';
import { starPath } from '@/components/gamification/starPath';

const GOLD = '#facc15';

interface BackdropSceneProps {
  /** Equipped backdrop key. `plain`/`none`/unknown/null → default hero look. */
  backdrop?: string | null;
}

/**
 * Container-scale rendering of the Phase 33 backdrop slot (Phase 34): fills
 * its nearest positioned ancestor with a scene matching the SVG art in
 * `Mascot.tsx`. Busy scenes get a bottom-up scrim toward the theme background
 * so foreground text stays readable in both themes. Always renders something —
 * the hero is never unstyled.
 */
export function BackdropScene({ backdrop }: BackdropSceneProps) {
  // Gradient ids must be unique per instance (matches the Mascot pattern).
  const gradientId = useId();
  const key = backdrop ?? 'plain';

  return (
    <div className="absolute inset-0" aria-hidden="true">
      {key === 'grid' && (
        <>
          <div className="absolute inset-0 bg-muted/50" />
          <div
            className="absolute inset-0"
            style={{
              backgroundImage:
                'linear-gradient(rgba(34, 197, 94, 0.14) 1px, transparent 1px), linear-gradient(90deg, rgba(34, 197, 94, 0.14) 1px, transparent 1px)',
              backgroundSize: '44px 44px',
            }}
          />
        </>
      )}

      {key === 'stars' && (
        <>
          <div
            className="absolute inset-0"
            style={{ background: 'linear-gradient(180deg, #0f172a 0%, #1e293b 100%)' }}
          />
          <svg
            className="absolute inset-0 h-full w-full"
            viewBox="0 0 400 200"
            preserveAspectRatio="xMidYMid slice"
          >
            {/* Accents live only in hero dead zones: the narrow top-center
                strip (above the Trophy Case title) and the side edges below
                the corner HUD. Everything else has content over it. */}
            <path d={starPath(185, 15, 5)} fill="#e2e8f0" opacity="0.8" />
            <path d={starPath(215, 26, 6)} fill="#e2e8f0" opacity="0.8" />
            <path d={starPath(370, 85, 4.5)} fill={GOLD} opacity="0.8" />
            <path d={starPath(60, 108, 5)} fill={GOLD} opacity="0.7" />
            <path d={starPath(75, 148, 4)} fill="#e2e8f0" opacity="0.6" />
            <path d={starPath(325, 118, 4.5)} fill="#e2e8f0" opacity="0.6" />
            <path d={starPath(20, 75, 4)} fill="#e2e8f0" opacity="0.5" />
            <path d={starPath(345, 158, 4)} fill={GOLD} opacity="0.5" />
            <circle cx="140" cy="18" r="1.5" fill="#e2e8f0" opacity="0.7" />
            <circle cx="30" cy="115" r="1.5" fill="#e2e8f0" opacity="0.6" />
            <circle cx="390" cy="140" r="1.5" fill="#e2e8f0" opacity="0.6" />
          </svg>
          {/* Scrim: deepen the night sky toward the bottom */}
          <div className="absolute inset-0 bg-gradient-to-t from-[#020617]/95 via-[#0f172a]/40 to-transparent" />
        </>
      )}

      {key === 'sunset' && (
        <>
          <div
            className="absolute inset-0"
            style={{ background: 'linear-gradient(180deg, #fbbf24 0%, #f97316 55%, #ec4899 100%)' }}
          />
          <div
            className="absolute left-1/2 top-[18%] h-56 w-56 -translate-x-1/2 rounded-full"
            style={{ background: 'radial-gradient(circle, rgba(253, 230, 138, 0.85) 0%, transparent 65%)' }}
          />
          {/* Scrim: sink the horizon into deep rose, staying in the sunset palette */}
          <div className="absolute inset-0 bg-gradient-to-t from-[#4c0519]/95 via-[#9f1239]/35 to-transparent" />
        </>
      )}

      {key === 'galaxy' && (
        <>
          <div
            className="absolute inset-0"
            style={{ background: 'linear-gradient(135deg, #1e1b4b 0%, #5b21b6 55%, #0f172a 100%)' }}
          />
          <svg
            className="absolute inset-0 h-full w-full"
            viewBox="0 0 400 200"
            preserveAspectRatio="xMidYMid slice"
          >
            <defs>
              <linearGradient id={`${gradientId}-ring`} x1="0" y1="0" x2="1" y2="0">
                <stop offset="0%" stopColor="#a78bfa" stopOpacity="0" />
                <stop offset="50%" stopColor="#a78bfa" stopOpacity="0.55" />
                <stop offset="100%" stopColor="#a78bfa" stopOpacity="0" />
              </linearGradient>
            </defs>
            {/* Ring + stars steer clear of the corner HUD, same as `stars`. */}
            <ellipse
              cx="305"
              cy="102"
              rx="55"
              ry="16"
              fill="none"
              stroke={`url(#${gradientId}-ring)`}
              strokeWidth="5"
              transform="rotate(-18 305 102)"
            />
            <path d={starPath(190, 16, 5.5)} fill="#e2e8f0" opacity="0.9" />
            <path d={starPath(30, 148, 4.5)} fill="#c4b5fd" opacity="0.9" />
            <path d={starPath(240, 28, 5)} fill="#e2e8f0" opacity="0.8" />
            <path d={starPath(18, 78, 4)} fill="#c4b5fd" opacity="0.7" />
            <path d={starPath(355, 150, 5)} fill="#e2e8f0" opacity="0.6" />
            <circle cx="150" cy="20" r="1.5" fill="#e2e8f0" opacity="0.7" />
            <circle cx="30" cy="112" r="1.5" fill="#c4b5fd" opacity="0.7" />
          </svg>
          {/* Scrim: deepen space toward the bottom */}
          <div className="absolute inset-0 bg-gradient-to-t from-[#020617]/95 via-[#1e1b4b]/35 to-transparent" />
        </>
      )}

      {(key === 'plain' || key === 'none' || !['grid', 'stars', 'sunset', 'galaxy'].includes(key)) && (
        <>
          <div
            className="absolute inset-0"
            style={{
              background:
                'linear-gradient(135deg, rgba(34, 197, 94, 0.1) 0%, rgba(6, 182, 212, 0.05) 50%, transparent 100%)',
            }}
          />
          <div className="absolute inset-0 bg-grid opacity-30" />
        </>
      )}
    </div>
  );
}

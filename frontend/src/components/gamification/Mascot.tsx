import { cn } from '@/lib/utils';

export type MascotPose = 'idle' | 'cheer' | 'encourage' | 'celebrate';

interface MascotProps {
  pose?: MascotPose;
  /** Rendered width/height in px. */
  size?: number;
  className?: string;
}

/**
 * "Circuit" — the STEM Quest robot mascot. Single built-in inline SVG with a
 * few poses, used in the quiz mastery flow's feedback moments and the
 * dashboard greeting. Theme-aware via CSS variables; CSS-only animation.
 */
export function Mascot({ pose = 'idle', size = 96, className }: MascotProps) {
  const primary = 'hsl(var(--primary))';
  const surface = 'hsl(var(--muted))';
  const outline = 'hsl(var(--foreground))';

  const armsUp = pose === 'celebrate';
  const oneArmUp = pose === 'cheer';

  return (
    <div
      className={cn(
        'inline-block select-none',
        (pose === 'cheer' || pose === 'celebrate') && 'animate-bounce',
        className
      )}
      style={{ width: size, height: size }}
      role="img"
      aria-label={`Circuit the robot (${pose})`}
    >
      <svg viewBox="0 0 120 120" width={size} height={size}>
        {/* Antenna */}
        <line x1="60" y1="22" x2="60" y2="10" stroke={outline} strokeWidth="3" strokeLinecap="round" />
        <circle cx="60" cy="8" r="4.5" fill={primary} className={pose === 'celebrate' ? 'animate-pulse' : undefined} />

        {/* Head */}
        <rect x="32" y="22" width="56" height="42" rx="12" fill={surface} stroke={primary} strokeWidth="3.5" />

        {/* Eyes */}
        {pose === 'cheer' || pose === 'celebrate' ? (
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

        {/* Feet */}
        <circle cx="48" cy="108" r="5" fill={outline} opacity="0.7" />
        <circle cx="72" cy="108" r="5" fill={outline} opacity="0.7" />
      </svg>
    </div>
  );
}

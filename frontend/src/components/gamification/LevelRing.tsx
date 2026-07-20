interface LevelRingProps {
  level: number;
  progressPct: number;
  /** Diameter in px (default 72). */
  size?: number;
  strokeWidth?: number;
  /** Optional caption under the ring, e.g. "620 / 800 XP". */
  subLabel?: string;
}

/**
 * A circular level ring: the arc fills to the progress toward the next level
 * and the current level number sits in the center. All numbers come from the
 * backend (single source of truth) — this component only draws them.
 */
export function LevelRing({
  level,
  progressPct,
  size = 72,
  strokeWidth = 6,
  subLabel,
}: LevelRingProps) {
  const pct = Math.max(0, Math.min(100, progressPct));
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - pct / 100);
  const gradientId = `level-ring-${size}`;

  return (
    <div className="inline-flex flex-col items-center gap-1">
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="-rotate-90">
          <defs>
            <linearGradient id={gradientId} x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#22c55e" />
              <stop offset="100%" stopColor="#06b6d4" />
            </linearGradient>
          </defs>
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke="currentColor"
            strokeWidth={strokeWidth}
            className="text-muted"
          />
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke={`url(#${gradientId})`}
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            style={{ transition: 'stroke-dashoffset 0.6s ease-out' }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span
            className="font-bold leading-none text-gradient-gaming"
            style={{ fontSize: size * 0.32 }}
          >
            {level}
          </span>
          <span
            className="uppercase tracking-widest text-muted-foreground leading-none"
            style={{ fontSize: Math.max(8, size * 0.11) }}
          >
            LVL
          </span>
        </div>
      </div>
      {subLabel && (
        <span className="text-xs text-muted-foreground">{subLabel}</span>
      )}
    </div>
  );
}

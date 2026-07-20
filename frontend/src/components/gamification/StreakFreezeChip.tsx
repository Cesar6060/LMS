import { cn } from '@/lib/utils';

interface StreakFreezeChipProps {
  count: number;
  className?: string;
}

/**
 * 🧊×N chip shown next to the StreakFlame. Freezes are earned on level-up
 * (max 2) and consumed automatically when a missed day would break the streak.
 */
export function StreakFreezeChip({ count, className }: StreakFreezeChipProps) {
  return (
    <span
      title="Streak freezes — earned on level-up, used automatically to save your streak on a missed day"
      className={cn(
        'inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-sm font-semibold',
        count > 0
          ? 'border-cyan-400/40 bg-cyan-500/10 text-cyan-600 dark:text-cyan-300'
          : 'border-border text-muted-foreground opacity-60',
        className
      )}
    >
      <span aria-hidden="true">🧊</span>
      ×{count}
    </span>
  );
}

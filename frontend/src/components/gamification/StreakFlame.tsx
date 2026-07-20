import { cn } from '@/lib/utils';

interface StreakFlameProps {
  current: number;
  longest?: number;
  size?: 'sm' | 'lg';
}

/** A flame + day count for the daily streak. Greys out when the streak is 0. */
export function StreakFlame({ current, longest, size = 'sm' }: StreakFlameProps) {
  const active = current > 0;
  const flameSize = size === 'lg' ? 'text-5xl' : 'text-3xl';
  const countSize = size === 'lg' ? 'text-4xl' : 'text-2xl';

  return (
    <div className="inline-flex items-center gap-2">
      <span className={cn(flameSize, 'leading-none', !active && 'grayscale opacity-40')}>
        🔥
      </span>
      <div className="flex flex-col leading-tight">
        <span
          className={cn(
            countSize,
            'font-bold',
            active ? 'text-gradient-gaming' : 'text-muted-foreground'
          )}
        >
          {current}
        </span>
        <span className="text-xs text-muted-foreground">
          day{current === 1 ? '' : 's'}
          {typeof longest === 'number' && longest > 0 && ` · best ${longest}`}
        </span>
      </div>
    </div>
  );
}

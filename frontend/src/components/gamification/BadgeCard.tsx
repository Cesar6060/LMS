import { cn } from '@/lib/utils';
import type { BadgeInfo } from '@/types';

interface BadgeCardProps {
  badge: BadgeInfo;
}

/** A single badge tile: earned badges are bright; locked ones are greyed and
 *  show their unlock hint on hover (native tooltip). */
export function BadgeCard({ badge }: BadgeCardProps) {
  const { earned, name, description, icon } = badge;
  return (
    <div
      title={earned ? `${name} — earned` : `Locked: ${description}`}
      className={cn(
        'flex flex-col items-center gap-2 rounded-lg border p-4 text-center transition-all',
        earned
          ? 'card-gaming border-[rgba(34,197,94,0.35)] shadow-[0_0_14px_rgba(34,197,94,0.12)]'
          : 'border-border bg-muted/20 opacity-60'
      )}
    >
      <span className={cn('text-4xl leading-none', !earned && 'grayscale')}>
        {icon}
      </span>
      <span
        className={cn(
          'text-sm font-bold',
          earned ? 'text-foreground' : 'text-muted-foreground'
        )}
      >
        {name}
      </span>
      <span className="text-xs text-muted-foreground line-clamp-2">
        {description}
      </span>
    </div>
  );
}

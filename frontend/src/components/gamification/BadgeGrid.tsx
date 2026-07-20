import type { BadgeInfo } from '@/types';
import { BadgeCard } from './BadgeCard';

interface BadgeGridProps {
  badges: BadgeInfo[];
}

/** Responsive grid of all catalog badges (earned + locked). */
export function BadgeGrid({ badges }: BadgeGridProps) {
  if (badges.length === 0) {
    return <p className="text-sm text-muted-foreground">No badges yet.</p>;
  }
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
      {badges.map((badge) => (
        <BadgeCard key={badge.key} badge={badge} />
      ))}
    </div>
  );
}

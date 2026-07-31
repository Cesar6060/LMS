import { Mascot } from '@/components/gamification/Mascot';
import { useAvatarContext } from '@/contexts/AvatarContext';
import type { AvatarItem } from '@/types';

interface UnlockedItemsProps {
  /** Catalog items this celebration just made available. */
  items: AvatarItem[];
}

/**
 * The "you also unlocked" strip inside the level-up / badge-earned modals
 * (Phase 64). Renders nothing at all when the celebration unlocked no
 * cosmetics — most badges don't, and an empty section would make the modal
 * look broken.
 *
 * Each tile previews the student's CURRENT look with just this item swapped
 * in, so the reward is shown on their own Circuit rather than a stock one.
 */
export function UnlockedItems({ items }: UnlockedItemsProps) {
  const { avatar } = useAvatarContext();
  if (items.length === 0) return null;

  return (
    <div className="mt-2 border-t border-border pt-4">
      <p className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
        {items.length === 1 ? 'New item unlocked' : `${items.length} new items unlocked`}
      </p>
      <div className="flex flex-wrap justify-center gap-3">
        {items.map((item) => (
          <div key={`${item.slot}-${item.key}`} className="flex w-20 flex-col items-center gap-1">
            <div className="rounded-lg border border-primary/40 bg-primary/5 p-1">
              <Mascot
                pose="idle"
                size={52}
                customization={{ ...avatar?.equipped, [item.slot]: item.key }}
              />
            </div>
            <span className="text-center text-xs font-medium leading-tight">{item.name}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

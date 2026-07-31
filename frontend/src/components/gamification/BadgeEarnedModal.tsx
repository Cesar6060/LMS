import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/Dialog';
import { Button } from '@/components/ui/Button';
import { UnlockedItems } from './UnlockedItems';
import { itemsUnlockedByBadge } from './unlocks';
import { useAvatarContext } from '@/contexts/AvatarContext';
import type { NewBadge } from '@/types';

interface BadgeEarnedModalProps {
  open: boolean;
  badge: NewBadge | null;
  onClose: () => void;
}

/**
 * Celebratory modal shown when the student unlocks a badge. Badges that also
 * gate cosmetics (Phase 64) preview them below; the rest — first_lesson,
 * streak_7, the xp_* tiers — render exactly as they did before, because
 * `UnlockedItems` returns null on an empty list.
 */
export function BadgeEarnedModal({ open, badge, onClose }: BadgeEarnedModalProps) {
  const { avatar } = useAvatarContext();
  const unlocked = badge
    ? itemsUnlockedByBadge(avatar?.catalog ?? [], badge.key)
    : [];

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="card-gaming max-w-sm text-center">
        <DialogHeader>
          <DialogTitle className="text-2xl text-gradient-gaming">
            Badge Unlocked!
          </DialogTitle>
          <DialogDescription>
            {badge ? badge.description : ''}
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-col items-center gap-3 py-4">
          <span className="text-6xl leading-none">{badge?.icon}</span>
          <span className="text-xl font-bold">{badge?.name}</span>
        </div>
        <UnlockedItems items={unlocked} />
        <Button variant="neon" onClick={onClose} className="w-full">
          Nice!
        </Button>
      </DialogContent>
    </Dialog>
  );
}

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/Dialog';
import { Button } from '@/components/ui/Button';
import type { NewBadge } from '@/types';

interface BadgeEarnedModalProps {
  open: boolean;
  badge: NewBadge | null;
  onClose: () => void;
}

/** Celebratory modal shown when the student unlocks a badge. */
export function BadgeEarnedModal({ open, badge, onClose }: BadgeEarnedModalProps) {
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
        <Button variant="neon" onClick={onClose} className="w-full">
          Nice!
        </Button>
      </DialogContent>
    </Dialog>
  );
}

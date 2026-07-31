import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/Dialog';
import { Button } from '@/components/ui/Button';
import { LevelRing } from './LevelRing';
import { Mascot } from './Mascot';
import { UnlockedItems } from './UnlockedItems';
import { itemsUnlockedAtLevel } from './unlocks';
import { useAvatarContext } from '@/contexts/AvatarContext';

interface LevelUpModalProps {
  open: boolean;
  level: number;
  onClose: () => void;
}

/**
 * Celebratory modal shown once when the student crosses a level threshold.
 * Circuit celebrates alongside the ring, and any cosmetics this level opened
 * up are previewed underneath (Phase 64).
 */
export function LevelUpModal({ open, level, onClose }: LevelUpModalProps) {
  const { avatar } = useAvatarContext();
  const unlocked = itemsUnlockedAtLevel(avatar?.catalog ?? [], level);

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="card-gaming max-w-sm text-center">
        <DialogHeader>
          <DialogTitle className="text-2xl text-gradient-gaming">
            Level Up!
          </DialogTitle>
          <DialogDescription>
            You reached level {level}. Keep going!
          </DialogDescription>
        </DialogHeader>
        <div className="flex items-center justify-center gap-2 py-4">
          <Mascot pose="celebrate" size={104} hideBackdrop />
          <LevelRing level={level} progressPct={0} size={112} strokeWidth={9} />
        </div>
        <UnlockedItems items={unlocked} />
        <Button variant="neon" onClick={onClose} className="w-full">
          Awesome
        </Button>
      </DialogContent>
    </Dialog>
  );
}

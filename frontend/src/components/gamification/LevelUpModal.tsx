import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/Dialog';
import { Button } from '@/components/ui/Button';
import { LevelRing } from './LevelRing';

interface LevelUpModalProps {
  open: boolean;
  level: number;
  onClose: () => void;
}

/** Celebratory modal shown once when the student crosses a level threshold. */
export function LevelUpModal({ open, level, onClose }: LevelUpModalProps) {
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
        <div className="flex justify-center py-4">
          <LevelRing level={level} progressPct={0} size={120} strokeWidth={9} />
        </div>
        <Button variant="neon" onClick={onClose} className="w-full">
          Awesome
        </Button>
      </DialogContent>
    </Dialog>
  );
}

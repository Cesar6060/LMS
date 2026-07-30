import { Button } from '@/components/ui/Button';
import { Maximize, Minimize } from 'lucide-react';

interface PresentButtonProps {
  isPresenting: boolean;
  onToggle: () => void;
}

/**
 * Phase 62 — the player's fullscreen toggle, lifted out of SlideStage so it is
 * available on doc pages too. It mounts inside the fullscreen element itself
 * (the player content area), so the same control both enters and exits present
 * mode; a button in the player header would vanish the moment presenting
 * started. `z-20` puts it above the slide stage's own `z-10` content.
 */
export function PresentButton({ isPresenting, onToggle }: PresentButtonProps) {
  // No button where the Fullscreen API is unavailable (e.g. iPhone Safari) —
  // presenting can't work there.
  if (!document.fullscreenEnabled) return null;

  const label = isPresenting ? 'Exit fullscreen (Esc)' : 'Present fullscreen (F)';

  return (
    <Button
      variant="outline"
      size="sm"
      onClick={onToggle}
      className="absolute top-4 right-4 z-20 gap-2"
      aria-label={label}
      title={label}
    >
      {isPresenting ? <Minimize className="h-4 w-4" /> : <Maximize className="h-4 w-4" />}
      <span className="hidden md:inline">{isPresenting ? 'Exit' : 'Present'}</span>
    </Button>
  );
}

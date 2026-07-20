import { useCallback, useEffect, useState } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { useToast } from '@/contexts/ToastContext';
import type { GamificationDelta, NewBadge } from '@/types';
import { LevelUpModal } from './LevelUpModal';
import { BadgeEarnedModal } from './BadgeEarnedModal';

type Celebration =
  | { type: 'level'; level: number }
  | { type: 'badge'; badge: NewBadge };

/**
 * Shared gamification feedback for completion / quiz-pass flows.
 *
 * Call `celebrate(delta)` with the `gamification` field from an award
 * response: it fires a "+XP" toast immediately, then plays any level-up and
 * badge-earned modals one at a time. Everything is a no-op for instructors.
 * Render `gamificationModals` somewhere in the component tree.
 */
export function useGamificationFeedback() {
  const { user } = useAuth();
  const { show } = useToast();
  const isInstructor = !!user?.is_instructor;

  const [queue, setQueue] = useState<Celebration[]>([]);
  const [active, setActive] = useState<Celebration | null>(null);

  const celebrate = useCallback(
    (delta?: GamificationDelta | null) => {
      if (!delta || isInstructor) return;

      if (delta.xp_awarded > 0) {
        show({ message: `+${delta.xp_awarded} XP`, icon: '⚡', variant: 'xp' });
      }

      const items: Celebration[] = [];
      if (delta.leveled_up) items.push({ type: 'level', level: delta.level });
      for (const badge of delta.new_badges ?? []) {
        items.push({ type: 'badge', badge });
      }
      if (items.length) setQueue((prev) => [...prev, ...items]);
    },
    [show, isInstructor]
  );

  // Play celebrations one at a time.
  useEffect(() => {
    if (!active && queue.length) {
      setActive(queue[0]);
      setQueue((prev) => prev.slice(1));
    }
  }, [active, queue]);

  const gamificationModals = (
    <>
      <LevelUpModal
        open={active?.type === 'level'}
        level={active?.type === 'level' ? active.level : 1}
        onClose={() => setActive(null)}
      />
      <BadgeEarnedModal
        open={active?.type === 'badge'}
        badge={active?.type === 'badge' ? active.badge : null}
        onClose={() => setActive(null)}
      />
    </>
  );

  return { celebrate, gamificationModals };
}

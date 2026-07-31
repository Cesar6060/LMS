import { useCallback, useEffect, useRef, useState } from 'react';
import { useAuth } from '@/contexts/useAuth';
import { useAvatarContext } from '@/contexts/AvatarContext';
import { useToast } from '@/contexts/useToast';
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
  const { refresh: refreshAvatar } = useAvatarContext();
  const { show } = useToast();
  const isInstructor = !!user?.is_instructor;

  const [queue, setQueue] = useState<Celebration[]>([]);
  const [active, setActive] = useState<Celebration | null>(null);
  // True once a celebration has played, so the avatar refresh below fires
  // after the queue drains rather than on first mount.
  const celebrated = useRef(false);

  const celebrate = useCallback(
    (delta?: GamificationDelta | null) => {
      if (!delta || isInstructor) return;

      if (delta.xp_awarded > 0) {
        show({ message: `+${delta.xp_awarded} XP`, icon: '⚡', variant: 'xp' });
      }
      if ((delta.freezes_used ?? 0) > 0) {
        show({ message: 'Streak freeze used — streak saved!', icon: '🧊', variant: 'success' });
      }
      if ((delta.freezes_earned ?? 0) > 0) {
        show({ message: 'Streak freeze earned!', icon: '🧊', variant: 'success' });
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
      celebrated.current = true;
      setActive(queue[0]);
      setQueue((prev) => prev.slice(1));
    }
  }, [active, queue]);

  // Once every celebration has been dismissed, pull a fresh avatar block so
  // the customizer shows newly-unlocked cosmetics without a page reload. The
  // modals themselves read the static catalog, so they don't wait on this.
  useEffect(() => {
    if (!active && queue.length === 0 && celebrated.current) {
      celebrated.current = false;
      // No-op for instructors and outside the provider — refresh() already
      // guards both.
      void refreshAvatar();
    }
  }, [active, queue, refreshAvatar]);

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

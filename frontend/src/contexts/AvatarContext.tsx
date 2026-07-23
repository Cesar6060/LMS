import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  ReactNode,
} from 'react';
import { useAuth } from '@/contexts/useAuth';
import { gamificationService } from '@/services/gamification';
import type { AvatarState, AvatarUpdatePatch } from '@/types';

interface AvatarContextType {
  /** The student's avatar state; null for instructors / while loading. */
  avatar: AvatarState | null;
  /** Re-fetch the avatar block from the gamification profile. */
  refresh: () => Promise<void>;
  /** PATCH a partial update; resolves with (and stores) the fresh state. */
  update: (patch: AvatarUpdatePatch) => Promise<AvatarState>;
}

// Default lets `useAvatarContext` work outside the provider (avatar stays
// null there, so Mascot just renders its classic look).
const AvatarContext = createContext<AvatarContextType>({
  avatar: null,
  refresh: async () => {},
  update: async () => {
    throw new Error('AvatarProvider is not mounted');
  },
});

export function AvatarProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const [avatar, setAvatar] = useState<AvatarState | null>(null);

  const isStudent = !!user && !user.is_instructor;

  const refresh = useCallback(async () => {
    if (!isStudent) {
      setAvatar(null);
      return;
    }
    try {
      const profile = await gamificationService.getProfile();
      setAvatar(profile.avatar ?? null);
    } catch (err) {
      console.error('Failed to load avatar:', err);
    }
  }, [isStudent]);

  const update = useCallback(async (patch: AvatarUpdatePatch) => {
    const fresh = await gamificationService.updateAvatar(patch);
    setAvatar(fresh);
    return fresh;
  }, []);

  useEffect(() => {
    if (isStudent) {
      refresh();
    } else {
      setAvatar(null);
    }
  }, [isStudent, refresh]);

  return (
    <AvatarContext.Provider value={{ avatar, refresh, update }}>
      {children}
    </AvatarContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components -- same hook-plus-provider shape as the sibling contexts
export function useAvatarContext() {
  return useContext(AvatarContext);
}

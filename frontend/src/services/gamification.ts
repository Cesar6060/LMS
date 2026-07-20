import api from './api';
import type { AvatarState, AvatarUpdatePatch, GamificationProfile } from '../types';

export const gamificationService = {
  async getProfile(): Promise<GamificationProfile> {
    const response = await api.get<GamificationProfile>('/gamification/profile/');
    return response.data;
  },

  async updateAvatar(patch: AvatarUpdatePatch): Promise<AvatarState> {
    const response = await api.patch<AvatarState>('/gamification/avatar/', patch);
    return response.data;
  },
};

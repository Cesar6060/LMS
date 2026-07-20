import api from './api';
import type { GamificationProfile } from '../types';

export const gamificationService = {
  async getProfile(): Promise<GamificationProfile> {
    const response = await api.get<GamificationProfile>('/gamification/profile/');
    return response.data;
  },
};

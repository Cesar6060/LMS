import api from './api';
import type { UserPreferences } from '../types';

export const settingsService = {
  // Get user settings/preferences
  async getSettings(): Promise<UserPreferences> {
    const response = await api.get<UserPreferences>('/auth/settings/');
    return response.data;
  },

  // Update user settings/preferences
  async updateSettings(data: Partial<UserPreferences>): Promise<UserPreferences> {
    const response = await api.patch<UserPreferences>('/auth/settings/', data);
    return response.data;
  },

  // Upload avatar
  async uploadAvatar(file: File): Promise<UserPreferences> {
    const formData = new FormData();
    formData.append('avatar', file);
    const response = await api.post<UserPreferences>('/auth/settings/avatar/', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  // Delete avatar
  async deleteAvatar(): Promise<UserPreferences> {
    const response = await api.delete<UserPreferences>('/auth/settings/avatar/delete/');
    return response.data;
  },

  // Update profile (name)
  async updateProfile(data: { first_name?: string; last_name?: string }): Promise<void> {
    await api.patch('/auth/profile/', data);
  },
};

export default settingsService;

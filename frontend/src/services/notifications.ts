import api from './api';
import type { Notification } from '@/types';

export const notificationService = {
  async getNotifications(): Promise<Notification[]> {
    const response = await api.get('/notifications/');
    return response.data;
  },

  async getUnreadCount(): Promise<number> {
    const response = await api.get('/notifications/unread-count/');
    return response.data.count;
  },

  async markAsRead(id: number): Promise<Notification> {
    const response = await api.post(`/notifications/${id}/read/`);
    return response.data;
  },

  async markAllAsRead(): Promise<void> {
    await api.post('/notifications/mark-all-read/');
  },
};

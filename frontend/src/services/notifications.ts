import api from './api';
import type { Notification, PaginatedResponse } from '@/types';

export const notificationService = {
  // Paginated since phase 55 — the endpoint returns
  // `{count, next, previous, results}`. The bell only renders the newest page,
  // and the unread badge comes from getUnreadCount(), not from this list.
  async getNotifications(): Promise<Notification[]> {
    const response = await api.get<PaginatedResponse<Notification>>('/notifications/');
    return response.data.results;
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

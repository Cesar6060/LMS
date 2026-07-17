import api from './api';
import type { ThreadListItem, ThreadDetail, Reply } from '@/types';

export const discussionService = {
  async getCourseThreads(code: string): Promise<ThreadListItem[]> {
    const response = await api.get<ThreadListItem[]>(`/courses/${code}/threads/`);
    return response.data;
  },

  async getThread(id: number): Promise<ThreadDetail> {
    const response = await api.get<ThreadDetail>(`/threads/${id}/`);
    return response.data;
  },

  async createThread(code: string, data: { title: string; content: string }): Promise<ThreadDetail> {
    const response = await api.post<ThreadDetail>(`/courses/${code}/threads/`, data);
    return response.data;
  },

  async updateThread(id: number, data: { title: string; content: string }): Promise<ThreadDetail> {
    const response = await api.put<ThreadDetail>(`/threads/${id}/`, data);
    return response.data;
  },

  async deleteThread(id: number): Promise<void> {
    await api.delete(`/threads/${id}/`);
  },

  async togglePin(id: number): Promise<ThreadDetail> {
    const response = await api.post<ThreadDetail>(`/threads/${id}/pin/`);
    return response.data;
  },

  async toggleLock(id: number): Promise<ThreadDetail> {
    const response = await api.post<ThreadDetail>(`/threads/${id}/lock/`);
    return response.data;
  },

  async createReply(threadId: number, data: { content: string }): Promise<Reply> {
    const response = await api.post<Reply>(`/threads/${threadId}/replies/`, data);
    return response.data;
  },

  async updateReply(id: number, data: { content: string }): Promise<Reply> {
    const response = await api.put<Reply>(`/replies/${id}/`, data);
    return response.data;
  },

  async deleteReply(id: number): Promise<void> {
    await api.delete(`/replies/${id}/`);
  },
};

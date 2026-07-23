import api from './api';
import type {
  AuthResponse,
  CourseInvite,
  InviteBatchResult,
  InviteTokenInfo,
  AcceptInvitePayload,
} from '../types';

export const inviteService = {
  // ---- Instructor management (course-scoped) ----

  async createInvites(courseCode: string, emails: string[]): Promise<InviteBatchResult> {
    const response = await api.post<InviteBatchResult>(
      `/courses/courses/${courseCode}/invites/`,
      { emails }
    );
    return response.data;
  },

  async listInvites(courseCode: string): Promise<CourseInvite[]> {
    const response = await api.get<CourseInvite[]>(
      `/courses/courses/${courseCode}/invites/`
    );
    return response.data;
  },

  async revokeInvite(courseCode: string, inviteId: number): Promise<void> {
    await api.delete(`/courses/courses/${courseCode}/invites/${inviteId}/`);
  },

  // ---- Public token endpoints (accept page) ----

  async getInvite(token: string): Promise<InviteTokenInfo> {
    const response = await api.get<InviteTokenInfo>(`/courses/invites/${token}/`);
    return response.data;
  },

  async acceptInviteNewAccount(
    token: string,
    payload: AcceptInvitePayload
  ): Promise<AuthResponse> {
    const response = await api.post<AuthResponse>(
      `/courses/invites/${token}/accept/`,
      payload
    );
    // Same storage contract as authService.login() — the new student is
    // logged in the moment their account exists.
    localStorage.setItem('token', response.data.access);
    localStorage.setItem('refresh', response.data.refresh);
    return response.data;
  },

  async acceptInviteExistingAccount(token: string): Promise<void> {
    await api.post(`/courses/invites/${token}/accept/`, {});
  },
};

export default inviteService;

import api from './api';
import type {
  AuthResponse,
  CourseInvite,
  InviteBatchResult,
  InviteTokenInfo,
  AcceptInvitePayload,
  JoinWithCodeResponse,
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

  /**
   * Phase 67 — fetch a pending invite's accept URL on demand. Live tokens are
   * deliberately kept out of the roster list payload, so this is a separate
   * call made only when the instructor asks to copy a link.
   */
  async getInviteLink(courseCode: string, inviteId: number): Promise<string> {
    const response = await api.get<{ invite_url: string }>(
      `/courses/courses/${courseCode}/invites/${inviteId}/link/`
    );
    return response.data.invite_url;
  },

  // ---- Public token endpoints (accept page) ----

  /**
   * Phase 67 — redeem a course join code. Public; succeeds only when the email
   * already has a pending invite on that course. Returns the invite token so
   * the caller can hand off to the existing /invite/<token> accept flow.
   */
  async joinWithCode(joinCode: string, email: string): Promise<JoinWithCodeResponse> {
    const response = await api.post<JoinWithCodeResponse>('/courses/join/', {
      join_code: joinCode,
      email,
    });
    return response.data;
  },

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

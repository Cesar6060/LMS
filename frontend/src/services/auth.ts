import api from './api';
import type { User, AuthResponse, LoginCredentials, RegisterData } from '../types';

export const authService = {
  async login(credentials: LoginCredentials): Promise<AuthResponse> {
    const response = await api.post<AuthResponse>('/auth/login/', credentials);
    localStorage.setItem('token', response.data.access);
    localStorage.setItem('refresh', response.data.refresh);
    return response.data;
  },

  async demoLogin(): Promise<AuthResponse> {
    // The backend issues tokens for the shared demo student server-side —
    // no credentials leave the client. Same storage contract as login().
    const response = await api.post<AuthResponse>('/auth/demo-login/');
    localStorage.setItem('token', response.data.access);
    localStorage.setItem('refresh', response.data.refresh);
    return response.data;
  },

  async register(data: RegisterData): Promise<AuthResponse> {
    const response = await api.post<AuthResponse>('/auth/registration/', data);
    localStorage.setItem('token', response.data.access);
    localStorage.setItem('refresh', response.data.refresh);
    return response.data;
  },

  async logout(): Promise<void> {
    try {
      // The backend blacklists the refresh token so it can't be reused.
      await api.post('/auth/logout/', {
        refresh: localStorage.getItem('refresh'),
      });
    } finally {
      localStorage.removeItem('token');
      localStorage.removeItem('refresh');
    }
  },

  async getCurrentUser(): Promise<User> {
    const response = await api.get<User>('/auth/user/');
    return response.data;
  },

  async updateProfile(data: Partial<User>): Promise<User> {
    const response = await api.patch<User>('/auth/profile/', data);
    return response.data;
  },

  async requestPasswordReset(email: string): Promise<void> {
    await api.post('/auth/password/reset/', { email });
  },

  async resetPassword(uid: string, token: string, newPassword1: string, newPassword2: string): Promise<void> {
    await api.post('/auth/password/reset/confirm/', {
      uid,
      token,
      new_password1: newPassword1,
      new_password2: newPassword2,
    });
  },

  async changePassword(oldPassword: string, newPassword1: string, newPassword2: string): Promise<void> {
    await api.post('/auth/password/change/', {
      old_password: oldPassword,
      new_password1: newPassword1,
      new_password2: newPassword2,
    });
  },

  async verifyEmail(key: string): Promise<void> {
    await api.post('/auth/registration/verify-email/', { key });
  },

  async resendVerificationEmail(email: string): Promise<void> {
    await api.post('/auth/registration/resend-email/', { email });
  },

  getToken(): string | null {
    return localStorage.getItem('token');
  },

  isAuthenticated(): boolean {
    return !!localStorage.getItem('token');
  },
};

export default authService;

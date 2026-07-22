import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios';
import * as Sentry from '@sentry/react';

// vite.config.ts guarantees the env var is set in production builds, so the
// localhost fallback is dev/test-only.
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to add auth token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Access tokens expire after an hour, so a 401 usually just means "refresh".
// All concurrent 401s share one in-flight refresh request; each retries its
// original request once the new access token lands. Uses a bare axios call —
// going through `api` would loop the interceptor.
let refreshPromise: Promise<string> | null = null;

async function refreshAccessToken(): Promise<string> {
  const refresh = localStorage.getItem('refresh');
  if (!refresh) {
    throw new Error('No refresh token');
  }
  const response = await axios.post<{ access: string; refresh?: string }>(
    `${API_URL}/auth/token/refresh/`,
    { refresh }
  );
  localStorage.setItem('token', response.data.access);
  // ROTATE_REFRESH_TOKENS on the backend: each refresh returns a new refresh
  // token and blacklists the one just used.
  if (response.data.refresh) {
    localStorage.setItem('refresh', response.data.refresh);
  }
  return response.data.access;
}

function clearTokensAndRedirect(): void {
  localStorage.removeItem('token');
  localStorage.removeItem('refresh');
  if (window.location.pathname !== '/login') {
    // Full-page redirect, so router state is lost — pass the current location
    // as ?next= instead (LoginPage reads it as a fallback after login).
    const next = window.location.pathname + window.location.search;
    window.location.href = `/login?next=${encodeURIComponent(next)}`;
  }
}

// Response interceptor to handle auth errors
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    // Report only real incidents: 5xx and network failures. 401/403/404 are
    // normal traffic (auth redirects, permission checks, missing objects) and
    // must never reach Sentry. captureException is a no-op when Sentry is not
    // initialized (dev without VITE_SENTRY_DSN).
    if (axios.isAxiosError(error) && error.code !== 'ERR_CANCELED') {
      const status = error.response?.status;
      if (status === undefined || status >= 500) {
        Sentry.captureException(error, {
          contexts: {
            api: {
              method: error.config?.method?.toUpperCase(),
              url: error.config?.url,
              status: status ?? 'network error',
            },
          },
        });
      }
    }

    if (error.response?.status === 401) {
      const original = (error as AxiosError).config as
        | (InternalAxiosRequestConfig & { _retry?: boolean })
        | undefined;

      // A 401 from login/logout is a credentials problem, not an expired
      // access token — refreshing can't fix it. `_retry` stops a second
      // refresh attempt when the replayed request 401s again.
      const isAuthRoute =
        original?.url?.includes('/auth/login/') ||
        original?.url?.includes('/auth/logout/');

      if (original && !original._retry && !isAuthRoute && localStorage.getItem('refresh')) {
        original._retry = true;
        try {
          refreshPromise = refreshPromise ?? refreshAccessToken();
          const access = await refreshPromise;
          original.headers.Authorization = `Bearer ${access}`;
          return api(original);
        } catch {
          clearTokensAndRedirect();
        } finally {
          refreshPromise = null;
        }
      } else {
        clearTokensAndRedirect();
      }
    }
    return Promise.reject(error);
  }
);

/** True when the error is an API response with status 403 (forbidden). */
export function isForbidden(error: unknown): boolean {
  return axios.isAxiosError(error) && error.response?.status === 403;
}

export default api;

import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { SettingsPage } from './SettingsPage';
import type { GamificationProfile, User, UserPreferences } from '@/types';

const mockUseAuth = vi.hoisted(() => vi.fn());
const mockGetSettings = vi.hoisted(() => vi.fn());
const mockGetProfile = vi.hoisted(() => vi.fn());

vi.mock('@/contexts/useAuth', () => ({
  useAuth: mockUseAuth,
}));
vi.mock('@/services/settings', () => ({
  settingsService: { getSettings: mockGetSettings },
}));
vi.mock('@/services/gamification', () => ({
  gamificationService: { getProfile: mockGetProfile },
}));

function makeUser(overrides: Partial<User> = {}): User {
  return {
    id: 1,
    email: 'student@example.com',
    first_name: 'Sam',
    last_name: 'Student',
    is_instructor: false,
    is_demo: false,
    created_at: '2026-01-01T00:00:00Z',
    ...overrides,
  };
}

const preferences: UserPreferences = {
  theme: 'dark',
  timezone: 'UTC',
  avatar_url: null,
  email_announcements: true,
};

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/settings']}>
      <SettingsPage />
    </MemoryRouter>
  );
}

describe('SettingsPage', () => {
  beforeEach(() => {
    mockUseAuth.mockReset();
    mockGetSettings.mockReset().mockResolvedValue(preferences);
    mockGetProfile
      .mockReset()
      .mockResolvedValue({ is_gamified: false } as unknown as GamificationProfile);
  });

  it('disables the profile form for the demo user with a visible note', async () => {
    mockUseAuth.mockReturnValue({
      user: makeUser({ is_demo: true }),
      refreshUser: vi.fn(),
    });

    renderPage();

    expect(await screen.findByPlaceholderText('First name')).toBeDisabled();
    expect(screen.getByPlaceholderText('Last name')).toBeDisabled();
    expect(screen.getByRole('button', { name: /save changes/i })).toBeDisabled();
    expect(screen.getByRole('button', { name: /upload photo/i })).toBeDisabled();
    expect(
      screen.getAllByText("The demo account can't be edited.").length
    ).toBeGreaterThan(0);
  });

  it('keeps the profile form editable for a normal user', async () => {
    mockUseAuth.mockReturnValue({
      user: makeUser(),
      refreshUser: vi.fn(),
    });

    renderPage();

    expect(await screen.findByPlaceholderText('First name')).toBeEnabled();
    expect(screen.getByPlaceholderText('Last name')).toBeEnabled();
    expect(screen.getByRole('button', { name: /save changes/i })).toBeEnabled();
    expect(screen.getByRole('button', { name: /upload photo/i })).toBeEnabled();
    expect(
      screen.queryByText("The demo account can't be edited.")
    ).not.toBeInTheDocument();
  });
});

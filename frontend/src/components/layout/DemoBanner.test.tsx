import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { DemoBanner } from './DemoBanner';
import type { User } from '@/types';

const mockUseAuth = vi.hoisted(() => vi.fn());
vi.mock('@/contexts/useAuth', () => ({
  useAuth: mockUseAuth,
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

describe('DemoBanner', () => {
  beforeEach(() => {
    mockUseAuth.mockReset();
  });

  it('renders the banner for the shared demo account', () => {
    mockUseAuth.mockReturnValue({ user: makeUser({ is_demo: true }) });

    render(<DemoBanner />);

    const banner = screen.getByRole('status');
    expect(banner).toBeInTheDocument();
    expect(banner).toHaveTextContent(
      "You're in the shared demo — progress is visible to other visitors and resets nightly."
    );
  });

  it('renders nothing for a normal user', () => {
    mockUseAuth.mockReturnValue({ user: makeUser({ is_demo: false }) });

    render(<DemoBanner />);

    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  });

  it('renders nothing when logged out', () => {
    mockUseAuth.mockReturnValue({ user: null });

    render(<DemoBanner />);

    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  });
});

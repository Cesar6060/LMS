import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { StudentRosterPage } from './StudentRosterPage';
import type { CourseInvite } from '@/types';

const mockGetStudentRoster = vi.hoisted(() => vi.fn());
const mockListInvites = vi.hoisted(() => vi.fn());
const mockDeleteInvite = vi.hoisted(() => vi.fn());
const mockDeleteClosedInvites = vi.hoisted(() => vi.fn());

vi.mock('@/services/courses', () => ({
  courseService: {
    getStudentRoster: mockGetStudentRoster,
    removeStudent: vi.fn(),
  },
}));

vi.mock('@/services/invites', () => ({
  inviteService: {
    listInvites: mockListInvites,
    createInvites: vi.fn(),
    revokeInvite: vi.fn(),
    getInviteLink: vi.fn(),
    deleteInvite: mockDeleteInvite,
    deleteClosedInvites: mockDeleteClosedInvites,
  },
}));

// Covered by its own suite; stubbed here so the roster tests do not depend on
// the join-code endpoints.
vi.mock('@/components/course/ClassCodeCard', () => ({
  ClassCodeCard: () => <div data-testid="class-code-card" />,
}));

vi.mock('@/services/api', () => ({ isForbidden: () => false }));

function makeInvite(overrides: Partial<CourseInvite>): CourseInvite {
  return {
    id: 1,
    email: 'kid@example.com',
    status: 'pending',
    delivery: 'sent',
    email_sent_at: '2026-08-01T00:00:00Z',
    email_error: null,
    created_at: '2026-08-01T00:00:00Z',
    expires_at: '2026-08-20T00:00:00Z',
    ...overrides,
  } as CourseInvite;
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/instructor/courses/VGD101/students']}>
      <Routes>
        <Route
          path="/instructor/courses/:code/students"
          element={<StudentRosterPage />}
        />
      </Routes>
    </MemoryRouter>
  );
}

describe('StudentRosterPage invite cleanup (Phase 68)', () => {
  beforeEach(() => {
    mockGetStudentRoster.mockReset();
    mockListInvites.mockReset();
    mockDeleteInvite.mockReset();
    mockDeleteClosedInvites.mockReset();
    mockGetStudentRoster.mockResolvedValue([]);
    mockDeleteInvite.mockResolvedValue(undefined);
    mockDeleteClosedInvites.mockResolvedValue(2);
  });

  it('offers Revoke but no Delete on a pending row', async () => {
    // A misclick must never void a live invitation.
    mockListInvites.mockResolvedValue([makeInvite({ id: 7, status: 'pending' })]);

    renderPage();

    expect(await screen.findByRole('button', { name: /revoke/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^delete/i })).not.toBeInTheDocument();
  });

  it('offers Delete but no Revoke on a closed row', async () => {
    mockListInvites.mockResolvedValue([
      makeInvite({ id: 8, email: 'gone@example.com', status: 'revoked' }),
    ]);

    renderPage();

    expect(
      await screen.findByRole('button', {
        name: /delete the revoked invitation for gone@example.com/i,
      })
    ).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^revoke$/i })).not.toBeInTheDocument();
  });

  it('deletes one closed invite through the service', async () => {
    mockListInvites.mockResolvedValue([
      makeInvite({ id: 9, email: 'old@example.com', status: 'expired' }),
    ]);

    renderPage();
    fireEvent.click(
      await screen.findByRole('button', {
        name: /delete the expired invitation for old@example.com/i,
      })
    );

    await waitFor(() =>
      expect(mockDeleteInvite).toHaveBeenCalledWith('VGD101', 9)
    );
  });

  it('hides "Clear all closed" when every open invite is pending', async () => {
    mockListInvites.mockResolvedValue([makeInvite({ id: 10, status: 'pending' })]);

    renderPage();

    await screen.findByRole('button', { name: /revoke/i });
    expect(
      screen.queryByRole('button', { name: /clear all closed/i })
    ).not.toBeInTheDocument();
  });

  it('clears the closed invites after confirmation, counting only closed rows', async () => {
    mockListInvites.mockResolvedValue([
      makeInvite({ id: 11, status: 'pending' }),
      makeInvite({ id: 12, email: 'a@example.com', status: 'revoked' }),
      makeInvite({ id: 13, email: 'b@example.com', status: 'expired' }),
    ]);

    renderPage();
    const clear = await screen.findByRole('button', {
      name: /clear all closed \(2\)/i,
    });
    fireEvent.click(clear);

    // Confirmed before firing — this is a bulk destructive action.
    expect(mockDeleteClosedInvites).not.toHaveBeenCalled();
    fireEvent.click(await screen.findByRole('button', { name: /clear them/i }));

    await waitFor(() =>
      expect(mockDeleteClosedInvites).toHaveBeenCalledWith('VGD101')
    );
  });

  it('surfaces the API detail when a delete is refused', async () => {
    mockListInvites.mockResolvedValue([
      makeInvite({ id: 14, email: 'x@example.com', status: 'revoked' }),
    ]);
    mockDeleteInvite.mockRejectedValue({
      response: { data: { detail: 'This invitation is still open.' } },
    });

    renderPage();
    fireEvent.click(
      await screen.findByRole('button', {
        name: /delete the revoked invitation for x@example.com/i,
      })
    );

    expect(
      await screen.findByText('This invitation is still open.')
    ).toBeInTheDocument();
  });
});

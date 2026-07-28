import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { DiscussionsPage } from './DiscussionsPage';
import type { CourseDetail } from '@/services/courses';
import type { User } from '@/types';

const mockUseAuth = vi.hoisted(() => vi.fn());
const mockGetCourse = vi.hoisted(() => vi.fn());
const mockGetCourseThreads = vi.hoisted(() => vi.fn());

vi.mock('@/contexts/useAuth', () => ({
  useAuth: mockUseAuth,
}));
vi.mock('@/services/courses', () => ({
  courseService: { getCourse: mockGetCourse },
}));
vi.mock('@/services/discussions', () => ({
  discussionService: { getCourseThreads: mockGetCourseThreads },
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

const course = {
  id: 1,
  code: 'DEMO101',
  title: 'Demo Course',
} as unknown as CourseDetail;

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/courses/DEMO101/discussions']}>
      <Routes>
        <Route path="/courses/:code/discussions" element={<DiscussionsPage />} />
      </Routes>
    </MemoryRouter>
  );
}

describe('DiscussionsPage', () => {
  beforeEach(() => {
    mockUseAuth.mockReset();
    mockGetCourse.mockReset().mockResolvedValue(course);
    mockGetCourseThreads.mockReset().mockResolvedValue([]);
  });

  it('shows the new-thread composer button for a normal user', async () => {
    mockUseAuth.mockReturnValue({ user: makeUser() });

    renderPage();

    expect(await screen.findByRole('heading', { level: 1, name: 'Discussions' })).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: /new thread/i }).length).toBeGreaterThan(0);
  });

  it('hides the new-thread composer button for the demo user', async () => {
    mockUseAuth.mockReturnValue({ user: makeUser({ is_demo: true }) });

    renderPage();

    expect(await screen.findByRole('heading', { level: 1, name: 'Discussions' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /new thread/i })).not.toBeInTheDocument();
  });
});

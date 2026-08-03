import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ManageCoursePage } from './ManageCoursePage';

const mockGetCourse = vi.hoisted(() => vi.fn());
const mockGetCourseQuizzes = vi.hoisted(() => vi.fn());

vi.mock('@/services/courses', () => ({
  courseService: { getCourse: mockGetCourse },
}));

vi.mock('@/services/quizzes', () => ({
  quizzesService: { getCourseQuizzes: mockGetCourseQuizzes },
}));

vi.mock('@/services/api', () => ({ isForbidden: () => false }));

vi.mock('@/contexts/useAuth', () => ({
  useAuth: () => ({ user: { id: 1, email: 'instructor@test.com' } }),
}));

// Covered by its own suite; stubbed so this page's test does not depend on
// the join-code endpoints.
vi.mock('@/components/course/ClassCodeCard', () => ({
  ClassCodeCard: () => <div data-testid="class-code-card" />,
}));

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/instructor/courses/VGD101/manage']}>
      <Routes>
        <Route
          path="/instructor/courses/:code/manage"
          element={<ManageCoursePage />}
        />
      </Routes>
    </MemoryRouter>
  );
}

describe('ManageCoursePage code prominence (Phase 68)', () => {
  beforeEach(() => {
    mockGetCourse.mockReset();
    mockGetCourseQuizzes.mockReset();
    mockGetCourseQuizzes.mockResolvedValue([]);
    mockGetCourse.mockResolvedValue({
      id: 5,
      code: 'VGD101',
      title: 'Game Programming with Godot',
      description: '',
      is_active: true,
      enrollment_code: 'QBRM78BL',
      instructor: { id: 1, email: 'instructor@test.com' },
      units: [],
    });
  });

  it('renders the shared ClassCodeCard', async () => {
    // The class code is what works for a student with no account yet — which
    // on day one is every student. It must be on this page, not only on the
    // roster, and it must be the SAME component so the two cannot drift.
    renderPage();

    expect(await screen.findByTestId('class-code-card')).toBeInTheDocument();
  });

  it('keeps the enrollment code reachable but demoted', async () => {
    // Still a real second factor for an enrolled student adding another
    // course, so it stays — just not as the biggest code on the page.
    renderPage();

    expect(await screen.findByText('QBRM78BL')).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /copy enrollment code/i })
    ).toBeInTheDocument();
  });
});

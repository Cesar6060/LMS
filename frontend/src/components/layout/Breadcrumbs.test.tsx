import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { Breadcrumbs } from './Breadcrumbs';

const mockUseAuth = vi.hoisted(() => vi.fn());
vi.mock('@/contexts/useAuth', () => ({
  useAuth: mockUseAuth,
}));

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Breadcrumbs />
    </MemoryRouter>
  );
}

describe('Breadcrumbs', () => {
  beforeEach(() => {
    mockUseAuth.mockReset();
    mockUseAuth.mockReturnValue({ isAuthenticated: true });
  });

  it('renders nothing outside course routes', () => {
    renderAt('/dashboard');
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument();
  });

  it('renders nothing on the course list page', () => {
    renderAt('/courses');
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument();
  });

  it('renders nothing when unauthenticated', () => {
    mockUseAuth.mockReturnValue({ isAuthenticated: false });
    renderAt('/courses/rob201');
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument();
  });

  it('shows Courses and the uppercased code on a course detail page', () => {
    const { container } = renderAt('/courses/rob201');

    expect(screen.getByRole('navigation', { name: 'Breadcrumb' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Courses' })).toHaveAttribute(
      'href',
      '/courses'
    );
    const code = screen.getByText('ROB201');
    expect(code).toHaveAttribute('aria-current', 'page');
    expect(code.closest('a')).toBeNull();
    // Separators only between crumbs — 2 crumbs, 1 chevron, none leading
    expect(container.querySelectorAll('ol svg')).toHaveLength(1);
  });

  it('links the course crumb to the manage page on instructor routes', () => {
    const { container } = renderAt('/instructor/courses/rob201/manage');

    expect(screen.getByRole('link', { name: 'ROB201' })).toHaveAttribute(
      'href',
      '/instructor/courses/rob201/manage'
    );
    const current = screen.getByText('Manage');
    expect(current).toHaveAttribute('aria-current', 'page');
    expect(current.closest('a')).toBeNull();
    expect(container.querySelectorAll('ol svg')).toHaveLength(2);
  });

  it.each([
    ['/courses/rob201/grades', 'Grades'],
    ['/courses/rob201/quizzes', 'Quizzes'],
    ['/courses/rob201/learn', 'Learning'],
    ['/courses/rob201/announcements', 'Announcements'],
    ['/courses/rob201/discussions', 'Discussions'],
    ['/instructor/courses/rob201/lessons/5/edit', 'Edit Lesson'],
    ['/instructor/courses/rob201/students', 'Roster'],
    ['/instructor/courses/rob201/gradebook', 'Gradebook'],
  ])('labels %s as %s', (path, label) => {
    renderAt(path);
    expect(screen.getByText(label)).toHaveAttribute('aria-current', 'page');
  });
});

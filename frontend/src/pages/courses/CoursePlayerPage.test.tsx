import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { CoursePlayerPage } from './CoursePlayerPage';
import type { LessonProgress, LessonQuestionsStatus, LessonSection, User } from '@/types';

const mockUseAuth = vi.hoisted(() => vi.fn());
const mockGetCourseWithProgress = vi.hoisted(() => vi.fn());
const mockGetLesson = vi.hoisted(() => vi.fn());
const mockGetLessonProgress = vi.hoisted(() => vi.fn());
const mockGetLessonQuestionsStatus = vi.hoisted(() => vi.fn());
const mockUpdateLessonProgress = vi.hoisted(() => vi.fn());
const mockUpdateCourseActivity = vi.hoisted(() => vi.fn());
const mockResetLessonProgress = vi.hoisted(() => vi.fn());
const mockGetCourseQuizzes = vi.hoisted(() => vi.fn());

vi.mock('@/contexts/useAuth', () => ({ useAuth: mockUseAuth }));
vi.mock('@/services/courses', () => ({
  courseService: {
    getCourseWithProgress: mockGetCourseWithProgress,
    getLesson: mockGetLesson,
    getLessonProgress: mockGetLessonProgress,
    getLessonQuestionsStatus: mockGetLessonQuestionsStatus,
    updateLessonProgress: mockUpdateLessonProgress,
    updateCourseActivity: mockUpdateCourseActivity,
    resetLessonProgress: mockResetLessonProgress,
  },
}));
vi.mock('@/services/quizzes', () => ({
  quizzesService: { getCourseQuizzes: mockGetCourseQuizzes },
}));
vi.mock('@/components/gamification/useGamificationFeedback', () => ({
  useGamificationFeedback: () => ({ celebrate: vi.fn(), gamificationModals: null }),
}));
// The quiz page fetches its own questions; the player only needs a stand-in.
vi.mock('@/components/lesson/LessonQuizSection', () => ({
  LessonQuizSection: () => <div data-testid="quiz-section">Comprehension quiz</div>,
}));

const user: User = {
  id: 1,
  email: 'student@example.com',
  first_name: 'Sam',
  last_name: 'Student',
  is_instructor: false,
  is_demo: false,
  created_at: '2026-01-01T00:00:00Z',
} as User;

function makeSection(overrides: Partial<LessonSection> = {}): LessonSection {
  return {
    id: 1,
    title: 'Page one',
    content: 'Some page content.',
    video_type: 'none',
    video_id: '',
    layout: 'doc',
    image_url: null,
    image_alt: '',
    order: 1,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  };
}

const progress: LessonProgress = {
  id: 1,
  user: 1,
  lesson: 10,
  completed: false,
  completed_at: null,
  video_position: 0,
  current_section: 0,
};

const course = {
  id: 5,
  code: 'ROB101',
  title: 'Intro to Robotics',
  description: '',
  instructor: { id: 99, email: 'teacher@example.com', first_name: 'Tina', last_name: 'Teacher' },
  is_active: true,
  units: [
    {
      id: 2,
      title: 'Unit 1',
      order: 1,
      course: 5,
      lessons: [{ id: 10, title: 'What Is a Robot?', video_type: 'none' as const, video_id: null, order: 1, is_completed: false }],
    },
  ],
};

/**
 * jsdom implements no Fullscreen API at all. This fake is enough for the player:
 * requestFullscreen/exitFullscreen flip `document.fullscreenElement` and fire
 * `fullscreenchange`, which is exactly what drives `isPresenting`.
 */
function installFullscreenFake() {
  let element: Element | null = null;
  const setFullscreenElement = (next: Element | null) => {
    element = next;
    document.dispatchEvent(new Event('fullscreenchange'));
    return Promise.resolve();
  };

  Object.defineProperty(document, 'fullscreenEnabled', { value: true, configurable: true });
  Object.defineProperty(document, 'fullscreenElement', {
    get: () => element,
    configurable: true,
  });
  Element.prototype.requestFullscreen = function () {
    return setFullscreenElement(this);
  };
  document.exitFullscreen = () => setFullscreenElement(null);
}

function renderPlayer() {
  return render(
    <MemoryRouter initialEntries={['/courses/ROB101/learn/10']}>
      <Routes>
        <Route path="/courses/:code/learn/:lessonId" element={<CoursePlayerPage />} />
      </Routes>
    </MemoryRouter>
  );
}

function setLesson(sections: LessonSection[], questions?: Partial<LessonQuestionsStatus>) {
  mockGetLesson.mockResolvedValue({
    id: 10,
    title: 'What Is a Robot?',
    content: null,
    video_type: 'none',
    video_id: null,
    order: 1,
    unit: 2,
    attachments: [],
    sections,
  });
  mockGetLessonQuestionsStatus.mockResolvedValue(
    questions
      ? {
          total_questions: 3,
          answered_questions: 0,
          correct_answers: 0,
          all_correct: false,
          requires_quiz: false,
          can_complete_lesson: true,
          ...questions,
        }
      : null
  );
}

const presentButton = () => screen.queryByRole('button', { name: 'Present fullscreen (F)' });
const exitButton = () => screen.queryByRole('button', { name: 'Exit fullscreen (Esc)' });

describe('CoursePlayerPage — Present control (phase 62)', () => {
  beforeEach(() => {
    installFullscreenFake();
    mockUseAuth.mockReturnValue({ user });
    mockGetCourseWithProgress.mockReset().mockResolvedValue(course);
    mockGetCourseQuizzes.mockReset().mockResolvedValue([]);
    mockGetLessonProgress.mockReset().mockResolvedValue(progress);
    mockUpdateLessonProgress.mockReset().mockResolvedValue(progress);
    mockUpdateCourseActivity.mockReset().mockResolvedValue(undefined);
    mockResetLessonProgress.mockReset().mockResolvedValue(undefined);
    mockGetLesson.mockReset();
    mockGetLessonQuestionsStatus.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders Present on a doc page', async () => {
    setLesson([makeSection({ layout: 'doc' })]);

    renderPlayer();

    expect(await screen.findByRole('heading', { name: 'What Is a Robot?' })).toBeInTheDocument();
    expect(presentButton()).toBeInTheDocument();
  });

  it('renders Present on a slide page', async () => {
    setLesson([makeSection({ layout: 'slide', title: 'Slide one' })]);

    renderPlayer();

    expect(await screen.findByRole('heading', { name: 'What Is a Robot?' })).toBeInTheDocument();
    expect(presentButton()).toBeInTheDocument();
  });

  it('does not render Present on the quiz page', async () => {
    setLesson([makeSection()], { total_questions: 3 });

    renderPlayer();

    // Page 2 of 2 is the comprehension quiz.
    fireEvent.click(await screen.findByRole('button', { name: /next/i }));

    expect(await screen.findByTestId('quiz-section')).toBeInTheDocument();
    expect(presentButton()).not.toBeInTheDocument();
    expect(exitButton()).not.toBeInTheDocument();
  });

  it('keeps the control as Exit when paging into the quiz while presenting', async () => {
    setLesson([makeSection()], { total_questions: 3 });

    renderPlayer();

    fireEvent.click(await screen.findByRole('button', { name: 'Present fullscreen (F)' }));
    expect(exitButton()).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /next/i }));

    expect(await screen.findByTestId('quiz-section')).toBeInTheDocument();
    expect(exitButton()).toBeInTheDocument();
    expect(presentButton()).not.toBeInTheDocument();
  });

  it('flips back to Present when the browser leaves fullscreen (Esc)', async () => {
    setLesson([makeSection()]);

    renderPlayer();

    fireEvent.click(await screen.findByRole('button', { name: 'Present fullscreen (F)' }));
    expect(exitButton()).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Exit fullscreen (Esc)' }));

    await waitFor(() => expect(presentButton()).toBeInTheDocument());
  });

  it('renders no Present control where the Fullscreen API is unavailable', async () => {
    Object.defineProperty(document, 'fullscreenEnabled', { value: false, configurable: true });
    setLesson([makeSection({ layout: 'slide' })]);

    renderPlayer();

    expect(await screen.findByRole('heading', { name: 'What Is a Robot?' })).toBeInTheDocument();
    expect(presentButton()).not.toBeInTheDocument();
    expect(exitButton()).not.toBeInTheDocument();
  });

  it('keeps Mark Complete but hides the lesson title while presenting', async () => {
    setLesson([makeSection({ layout: 'slide' })]);

    renderPlayer();

    expect(await screen.findByRole('button', { name: /mark complete/i })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Present fullscreen (F)' }));

    expect(screen.getByRole('button', { name: /mark complete/i })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'What Is a Robot?' })).not.toBeInTheDocument();
  });
});

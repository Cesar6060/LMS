import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { QuizDetailPage } from './QuizDetailPage';
import type { Quiz, QuizAttempt, User } from '@/types';

const mockUseAuth = vi.hoisted(() => vi.fn());
const mockGetQuiz = vi.hoisted(() => vi.fn());
const mockGetQuizSession = vi.hoisted(() => vi.fn());
const mockStartQuizSession = vi.hoisted(() => vi.fn());
const mockAnswerQuizQuestion = vi.hoisted(() => vi.fn());

/**
 * The attempt the stubbed session flow hands back. Hoisted so the `vi.mock`
 * factory below (which runs before module init) can close over it.
 */
const submittedAttempt = vi.hoisted(() => ({
  id: 900,
  quiz: 7,
  quiz_title: 'Unit 1 Quiz',
  score: '80.00',
  passed: true,
  points_earned: '20.00',
  completed_at: '2026-08-09T12:00:00Z',
  answers: [
    {
      question: 1,
      question_text: 'What is a sensor?',
      selected_choice: 11,
      selected_choice_text: 'An input device',
      is_correct: true,
      correct_choice_text: null,
    },
  ],
}));

vi.mock('@/contexts/useAuth', () => ({ useAuth: mockUseAuth }));
vi.mock('@/services/quizzes', () => ({
  quizzesService: {
    getQuiz: mockGetQuiz,
    getQuizSession: mockGetQuizSession,
    startQuizSession: mockStartQuizSession,
    answerQuizQuestion: mockAnswerQuizQuestion,
  },
}));
vi.mock('@/components/gamification/useGamificationFeedback', () => ({
  useGamificationFeedback: () => ({ celebrate: vi.fn(), gamificationModals: null }),
}));
// The real mastery flow talks to the session endpoints question by question.
// These tests only care about what the page renders AFTER an attempt is
// submitted, so the stub exposes a single button that fires the completion.
vi.mock('@/components/quiz/QuizSessionFlow', () => ({
  QuizSessionFlow: ({ onSessionComplete }: { onSessionComplete: (a: QuizAttempt) => void }) => (
    <button onClick={() => onSessionComplete(submittedAttempt)}>Finish session (stub)</button>
  ),
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

function makeQuiz(overrides: Partial<Quiz> = {}): Quiz {
  return {
    id: 7,
    title: 'Unit 1 Quiz',
    description: 'Everything from unit 1.',
    passing_score: 70,
    points: 20,
    max_attempts: 0,
    order: 1,
    question_count: 6,
    unit: 2,
    unit_title: 'Unit 1',
    course_code: 'ROB101',
    questions: [],
    best_score: null,
    attempts_remaining: null,
    created_at: '2026-01-01T00:00:00Z',
    ...overrides,
  };
}

/**
 * Renders the destination of a Continue/back navigation, including the router
 * state — an href assertion alone would still pass against a Continue button
 * that forgot `state: { restart: true }`, which is the point of the button.
 */
function LocationProbe() {
  const location = useLocation();
  const state = location.state as { restart?: boolean } | null;
  return (
    <div data-testid="location">
      {location.pathname} restart={String(state?.restart)}
    </div>
  );
}

function renderQuizPage(search: string) {
  return render(
    <MemoryRouter initialEntries={[`/courses/ROB101/quizzes/7${search}`]}>
      <Routes>
        <Route path="/courses/:code/quizzes/:quizId" element={<QuizDetailPage />} />
        <Route path="/courses/:code/learn/:lessonId" element={<LocationProbe />} />
        <Route path="/courses/:code/learn" element={<LocationProbe />} />
        <Route path="/courses/:code" element={<LocationProbe />} />
      </Routes>
    </MemoryRouter>
  );
}

/** The top-of-page "Back to X" link (the results screen also has a back button). */
const backLink = () => screen.getAllByRole('link', { name: /^Back to / })[0];
const continueLink = () => screen.queryByRole('link', { name: /Continue to Next Lesson/i });

/** Intro screen → start → submit, landing on the results screen. */
async function submitAttempt() {
  fireEvent.click(await screen.findByRole('button', { name: 'Start Quiz' }));
  fireEvent.click(await screen.findByRole('button', { name: 'Finish session (stub)' }));
  expect(await screen.findByText('Quiz Passed!')).toBeInTheDocument();
}

describe('QuizDetailPage — unit-quiz round trip (phase 70)', () => {
  beforeEach(() => {
    mockUseAuth.mockReturnValue({ user });
    mockGetQuiz.mockReset().mockResolvedValue(makeQuiz());
    // 404 = no in-progress session, so the intro shows "Start Quiz".
    mockGetQuizSession.mockReset().mockRejectedValue({ response: { status: 404 } });
    mockStartQuizSession.mockReset();
    mockAnswerQuizQuestion.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('back link', () => {
    it('returns to the originating lesson with ?from=learn&lesson=42', async () => {
      renderQuizPage('?from=learn&lesson=42');

      expect(await screen.findByText('Unit 1 Quiz')).toBeInTheDocument();
      expect(backLink()).toHaveAttribute('href', '/courses/ROB101/learn/42');
      expect(backLink()).toHaveAccessibleName(/Lesson/);
    });

    it('degrades to the player when ?from=learn carries no lesson', async () => {
      renderQuizPage('?from=learn');

      expect(await screen.findByText('Unit 1 Quiz')).toBeInTheDocument();
      expect(backLink()).toHaveAttribute('href', '/courses/ROB101/learn');
      expect(backLink()).toHaveAccessibleName(/Learning/);
    });

    it('returns to course detail with no ?from param', async () => {
      renderQuizPage('');

      expect(await screen.findByText('Unit 1 Quiz')).toBeInTheDocument();
      expect(backLink()).toHaveAttribute('href', '/courses/ROB101');
      expect(backLink()).toHaveAccessibleName(/Course/);
    });

    // `?lesson=` is URL-bar input: parseInt would turn "12abc" into a lesson id
    // and "-1" into a navigable path.
    it.each([
      ['abc', 'abc'],
      ['-1', '-1'],
      ['0', '0'],
      ['1e3', '1e3'],
      ['12abc', '12abc'],
      [' 1 (leading space)', '%201'],
    ])('degrades to the player for a junk lesson param: %s', async (_label, raw) => {
      renderQuizPage(`?from=learn&lesson=${raw}`);

      expect(await screen.findByText('Unit 1 Quiz')).toBeInTheDocument();
      const href = backLink().getAttribute('href');
      expect(href).toBe('/courses/ROB101/learn');
      expect(href).not.toContain('NaN');
      expect(href).not.toContain('-1');
    });
  });

  describe('Continue to Next Lesson', () => {
    it('links to the next lesson and carries state.restart', async () => {
      renderQuizPage('?from=learn&lesson=11&next=20');
      await submitAttempt();

      const link = continueLink();
      expect(link).toBeInTheDocument();
      expect(link).toHaveAttribute('href', '/courses/ROB101/learn/20');

      fireEvent.click(link!);

      // The restart flag is what opens the lesson on page 1 rather than its
      // saved cursor — assert it, not just the destination.
      expect(await screen.findByTestId('location')).toHaveTextContent(
        '/courses/ROB101/learn/20 restart=true'
      );
    });

    it('renders no Continue when ?next is absent, but keeps the back link', async () => {
      renderQuizPage('?from=learn&lesson=11');
      await submitAttempt();

      expect(continueLink()).not.toBeInTheDocument();
      expect(backLink()).toHaveAttribute('href', '/courses/ROB101/learn/11');
    });

    it.each(['0', '-5', 'abc', '1e3'])(
      'renders no Continue for a junk next param: %s',
      async raw => {
        renderQuizPage(`?from=learn&lesson=11&next=${raw}`);
        await submitAttempt();

        expect(continueLink()).not.toBeInTheDocument();
        expect(backLink()).toHaveAttribute('href', '/courses/ROB101/learn/11');
      }
    );

    it('renders no Continue when the quiz belongs to another course', async () => {
      // A hand-assembled URL: the quiz is CS101's, so `next=20` names a lesson
      // in a course this link cannot reach.
      mockGetQuiz.mockResolvedValue(makeQuiz({ course_code: 'CS101' }));

      renderQuizPage('?from=learn&lesson=11&next=20');
      await submitAttempt();

      expect(continueLink()).not.toBeInTheDocument();
      expect(backLink()).toHaveAttribute('href', '/courses/ROB101/learn/11');
    });

    it('renders no Continue for ?next without from=learn', async () => {
      renderQuizPage('?next=20');
      await submitAttempt();

      expect(continueLink()).not.toBeInTheDocument();
      expect(backLink()).toHaveAttribute('href', '/courses/ROB101');
    });
  });
});

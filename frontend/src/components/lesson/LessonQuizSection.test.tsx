import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { LessonQuizSection } from './LessonQuizSection';
import type { LessonQuestion, LessonQuestionsStatus } from '@/types';

const mockGetLessonQuestions = vi.hoisted(() => vi.fn());
const mockGetLessonQuestionsStatus = vi.hoisted(() => vi.fn());

vi.mock('@/services/courses', () => ({
  courseService: {
    getLessonQuestions: mockGetLessonQuestions,
    getLessonQuestionsStatus: mockGetLessonQuestionsStatus,
    getLessonQuizSession: vi.fn(),
    startLessonQuizSession: vi.fn(),
    answerLessonQuizQuestion: vi.fn(),
  },
}));
vi.mock('@/components/gamification/useGamificationFeedback', () => ({
  useGamificationFeedback: () => ({ celebrate: vi.fn(), gamificationModals: null }),
}));
// The session flow fetches its own state; the section only needs a stand-in.
vi.mock('@/components/quiz/QuizSessionFlow', () => ({
  QuizSessionFlow: () => <div data-testid="quiz-session-flow">Session</div>,
}));

const question: LessonQuestion = {
  id: 1,
  text: 'What is a robot?',
  order: 1,
  choices: [
    { id: 1, text: 'A machine', order: 1 },
    { id: 2, text: 'A sandwich', order: 2 },
  ],
};

function makeStatus(overrides: Partial<LessonQuestionsStatus> = {}): LessonQuestionsStatus {
  return {
    total_questions: 1,
    answered_questions: 0,
    correct_answers: 0,
    all_correct: false,
    requires_quiz: true,
    can_complete_lesson: false,
    attempt_count: 0,
    has_passed: false,
    ...overrides,
  };
}

describe('LessonQuizSection', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('closes an open quiz when the lesson changes', async () => {
    mockGetLessonQuestions.mockResolvedValue([question]);
    mockGetLessonQuestionsStatus.mockResolvedValue(makeStatus());

    const { rerender } = render(<LessonQuizSection lessonId={1} />);

    fireEvent.click(await screen.findByRole('button', { name: /Start Check/ }));
    expect(screen.getByTestId('quiz-session-flow')).toBeInTheDocument();

    rerender(<LessonQuizSection lessonId={2} />);

    // Back to the start screen for the new lesson, not the previous session.
    expect(await screen.findByRole('button', { name: /Start Check/ })).toBeInTheDocument();
    expect(screen.queryByTestId('quiz-session-flow')).not.toBeInTheDocument();
  });

  it('discards a slow response for the lesson the player already left', async () => {
    const staleStatus = makeStatus({ total_questions: 9, has_passed: true });
    const freshStatus = makeStatus({ total_questions: 2 });
    let resolveStale: (status: LessonQuestionsStatus) => void = () => {};

    mockGetLessonQuestions.mockResolvedValue([question]);
    mockGetLessonQuestionsStatus.mockImplementation((id: number) =>
      id === 1
        ? new Promise<LessonQuestionsStatus>((resolve) => {
            resolveStale = resolve;
          })
        : Promise.resolve(freshStatus)
    );

    const onStatusChange = vi.fn();
    const { rerender } = render(
      <LessonQuizSection lessonId={1} onStatusChange={onStatusChange} />
    );
    rerender(<LessonQuizSection lessonId={2} onStatusChange={onStatusChange} />);

    await waitFor(() => expect(onStatusChange).toHaveBeenCalledWith(freshStatus));

    // Lesson 1's request lands late — it must not overwrite lesson 2's status.
    await act(async () => {
      resolveStale(staleStatus);
    });

    expect(onStatusChange).toHaveBeenCalledTimes(1);
    expect(onStatusChange).not.toHaveBeenCalledWith(staleStatus);
  });
});

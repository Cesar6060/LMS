import { useCallback, useEffect, useRef, useState } from 'react';
import { Button } from '@/components/ui/Button';
import { Card, CardContent } from '@/components/ui/Card';
import { Mascot } from '@/components/gamification/Mascot';
import { cn } from '@/lib/utils';
import { CheckCircle, XCircle, Loader2 } from 'lucide-react';
import type { QuizSessionState, SessionAnswerResult } from '@/types';

/** Minimal question shape shared by unit-quiz Questions and LessonQuestions. */
export interface SessionQuestion {
  id: number;
  text: string;
  choices: { id: number; text: string }[];
}

interface QuizSessionFlowProps<TResult> {
  /** Full question list (student-safe: no is_correct flags). */
  questions: SessionQuestion[];
  /** GET the in-progress session; must reject (404) when none exists. */
  getSession: () => Promise<QuizSessionState>;
  /** POST start — creates a session or resumes the existing one. */
  startSession: () => Promise<QuizSessionState>;
  /** POST one answer for grading. */
  answerQuestion: (questionId: number, choiceId: number) => Promise<SessionAnswerResult<TResult>>;
  /** Fired once when the last question masters; parent shows its completion screen. */
  onSessionComplete: (result: TResult) => void;
  /** Optional heading shown above the progress bar. */
  title?: string;
}

interface Feedback {
  isCorrect: boolean;
  correctChoiceText: string | null;
  sessionComplete: boolean;
  result?: unknown;
}

/**
 * The shared Duolingo-style mastery flow (Phase 32): one question at a time,
 * "Check" locks the answer in, instant right/wrong feedback with the mascot,
 * missed questions re-queue until everything is mastered. Resumes an
 * in-progress session on mount. Keyboard: 1–9 select, Enter check/continue.
 */
export function QuizSessionFlow<TResult>({
  questions,
  getSession,
  startSession,
  answerQuestion,
  onSessionComplete,
  title,
}: QuizSessionFlowProps<TResult>) {
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [queue, setQueue] = useState<number[]>([]);
  const [totalQuestions, setTotalQuestions] = useState(0);
  const [masteredCount, setMasteredCount] = useState(0);
  const [selectedChoiceId, setSelectedChoiceId] = useState<number | null>(null);
  const [isChecking, setIsChecking] = useState(false);
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const continueRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setIsLoading(true);
      setError('');
      try {
        let state: QuizSessionState;
        try {
          state = await getSession();
        } catch {
          // No in-progress session -> start a fresh one.
          state = await startSession();
        }
        if (cancelled) return;
        setQueue(state.remaining_question_ids);
        setTotalQuestions(state.total_questions);
        setMasteredCount(state.mastered_count);
      } catch (err) {
        console.error('Failed to start quiz session:', err);
        if (!cancelled) setError('Failed to start the quiz session. Please try again.');
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    };
    load();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const currentQuestionId = queue[0];
  const currentQuestion = questions.find((q) => q.id === currentQuestionId);

  const handleCheck = useCallback(async () => {
    if (selectedChoiceId === null || currentQuestion === undefined || isChecking || feedback) return;
    setIsChecking(true);
    try {
      const answer = await answerQuestion(currentQuestion.id, selectedChoiceId);
      setMasteredCount(totalQuestions - answer.remaining_count);
      setFeedback({
        isCorrect: answer.is_correct,
        correctChoiceText: answer.correct_choice_text,
        sessionComplete: answer.session_complete,
        result: answer.result,
      });
    } catch (err) {
      console.error('Failed to submit answer:', err);
      setError('Failed to submit your answer. Please try again.');
    } finally {
      setIsChecking(false);
    }
  }, [selectedChoiceId, currentQuestion, isChecking, feedback, answerQuestion, totalQuestions]);

  const handleContinue = useCallback(() => {
    if (!feedback) return;
    if (feedback.sessionComplete) {
      onSessionComplete(feedback.result as TResult);
      return;
    }
    setQueue((prev) => {
      const rest = prev.slice(1);
      // Missed questions come back at the end of the queue.
      return feedback.isCorrect ? rest : [...rest, prev[0]];
    });
    setSelectedChoiceId(null);
    setFeedback(null);
  }, [feedback, onSessionComplete]);

  // Keyboard shortcuts: 1–9 select a choice, Enter checks / continues.
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (isLoading || error) return;
      if (event.key === 'Enter') {
        event.preventDefault();
        if (feedback) handleContinue();
        else handleCheck();
        return;
      }
      if (!feedback && currentQuestion) {
        const index = parseInt(event.key, 10) - 1;
        if (!Number.isNaN(index) && index >= 0 && index < currentQuestion.choices.length) {
          setSelectedChoiceId(currentQuestion.choices[index].id);
        }
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [isLoading, error, feedback, currentQuestion, handleCheck, handleContinue]);

  // Focus Continue when feedback lands so Enter/Space just works.
  useEffect(() => {
    if (feedback) continueRef.current?.focus();
  }, [feedback]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (error) {
    return (
      <Card>
        <CardContent className="py-10 text-center">
          <p className="text-destructive font-medium">{error}</p>
        </CardContent>
      </Card>
    );
  }

  if (currentQuestion === undefined) {
    // The quiz was edited mid-session and the question list no longer matches.
    return (
      <Card>
        <CardContent className="py-10 text-center">
          <p className="text-destructive font-medium">
            This quiz changed while your session was in progress. Please reload the page.
          </p>
        </CardContent>
      </Card>
    );
  }

  const progressPct = totalQuestions > 0 ? Math.round((masteredCount / totalQuestions) * 100) : 0;

  return (
    <div className="max-w-2xl mx-auto">
      {/* Progress bar */}
      <div className="mb-8">
        {title && <h2 className="text-lg font-semibold mb-3">{title}</h2>}
        <div className="flex items-center gap-4">
          <div className="progress-gaming flex-1" aria-label="Quiz progress">
            <div
              className="progress-gaming-bar transition-all duration-500"
              style={{ width: `${progressPct}%` }}
            />
          </div>
          <span className="text-base font-semibold text-muted-foreground whitespace-nowrap">
            {masteredCount} / {totalQuestions}
          </span>
        </div>
      </div>

      {/* Question card */}
      <Card className="mb-6">
        <CardContent className="p-6 sm:p-8">
          <p className="text-xl sm:text-2xl font-semibold leading-snug mb-6">
            {currentQuestion.text}
          </p>
          <div className="space-y-3" role="radiogroup" aria-label="Answer choices">
            {currentQuestion.choices.map((choice, index) => {
              const isSelected = selectedChoiceId === choice.id;
              const showCorrect = feedback !== null && feedback.isCorrect && isSelected;
              const showIncorrect = feedback !== null && !feedback.isCorrect && isSelected;
              return (
                <button
                  key={choice.id}
                  type="button"
                  role="radio"
                  aria-checked={isSelected}
                  onClick={() => !feedback && setSelectedChoiceId(choice.id)}
                  disabled={feedback !== null}
                  className={cn(
                    'w-full text-left p-4 sm:p-5 rounded-xl border-2 text-base sm:text-lg transition-all duration-200 flex items-center gap-4',
                    !feedback && isSelected && 'border-primary bg-primary/10 shadow-sm',
                    !feedback && !isSelected && 'border-border bg-muted/40 hover:bg-muted hover:border-muted-foreground/30',
                    showCorrect && 'border-green-500 bg-green-50 dark:bg-green-900/20',
                    showIncorrect && 'border-red-500 bg-red-50 dark:bg-red-900/20',
                    feedback !== null && 'cursor-default'
                  )}
                >
                  <span
                    className={cn(
                      'flex-shrink-0 w-8 h-8 rounded-lg border-2 flex items-center justify-center text-sm font-bold',
                      isSelected ? 'border-primary text-primary' : 'border-muted-foreground/40 text-muted-foreground'
                    )}
                  >
                    {index + 1}
                  </span>
                  <span className="flex-1">{choice.text}</span>
                  {showCorrect && <CheckCircle className="h-6 w-6 text-green-600 flex-shrink-0" />}
                  {showIncorrect && <XCircle className="h-6 w-6 text-red-600 flex-shrink-0" />}
                </button>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* Feedback banner / Check button */}
      {feedback ? (
        <div
          className={cn(
            'rounded-xl border-2 p-5 sm:p-6 flex items-center gap-4 animate-in slide-in-from-bottom-2 fade-in duration-300',
            feedback.isCorrect
              ? 'border-green-500 bg-green-50 dark:bg-green-900/20'
              : 'border-red-500 bg-red-50 dark:bg-red-900/20'
          )}
        >
          <Mascot pose={feedback.isCorrect ? 'cheer' : 'encourage'} size={72} className="flex-shrink-0" />
          <div className="flex-1 min-w-0">
            <p
              className={cn(
                'text-lg sm:text-xl font-bold',
                feedback.isCorrect
                  ? 'text-green-700 dark:text-green-400'
                  : 'text-red-700 dark:text-red-400'
              )}
            >
              {feedback.isCorrect ? 'Correct! Nice work!' : 'Not quite!'}
            </p>
            {!feedback.isCorrect && feedback.correctChoiceText && (
              <p className="text-base text-muted-foreground mt-1">
                Correct answer: <span className="font-semibold text-foreground">{feedback.correctChoiceText}</span>
              </p>
            )}
            {!feedback.isCorrect && !feedback.sessionComplete && (
              <p className="text-sm text-muted-foreground mt-1">
                This question will come back around — you've got this!
              </p>
            )}
          </div>
          <Button
            ref={continueRef}
            size="lg"
            onClick={handleContinue}
            className={cn(
              'min-w-[130px]',
              feedback.isCorrect ? 'bg-green-600 hover:bg-green-700' : 'bg-red-600 hover:bg-red-700'
            )}
          >
            Continue
          </Button>
        </div>
      ) : (
        <div className="flex justify-end">
          <Button
            size="lg"
            onClick={handleCheck}
            disabled={selectedChoiceId === null || isChecking}
            className="min-w-[160px] text-base"
          >
            {isChecking ? <Loader2 className="h-5 w-5 animate-spin" /> : 'Check'}
          </Button>
        </div>
      )}

      <p className="text-xs text-muted-foreground text-center mt-6">
        Tip: press 1–{Math.min(currentQuestion.choices.length, 9)} to pick an answer, Enter to check and continue.
      </p>
    </div>
  );
}

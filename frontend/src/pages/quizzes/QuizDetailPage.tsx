import { useState, useEffect } from 'react';
import { useParams, Link, useSearchParams } from 'react-router';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { quizzesService } from '@/services/quizzes';
import { isForbidden } from '@/services/api';
import { AccessDenied } from '@/components/AccessDenied';
import { useAuth } from '@/contexts/AuthContext';
import type { Quiz, QuizAttempt } from '@/types';
import { useGamificationFeedback } from '@/components/gamification/useGamificationFeedback';
import { QuizSessionFlow } from '@/components/quiz/QuizSessionFlow';
import { Mascot } from '@/components/gamification/Mascot';
import { PageContainer } from '@/components/layout/PageContainer';
import { Skeleton } from '@/components/ui/Skeleton';
import { BackLink } from '@/components/layout/BackLink';
import {
  CheckCircle, XCircle, Trophy, RotateCcw,
  ChevronLeft, FileQuestion, Target, Clock, LogOut, PlayCircle
} from 'lucide-react';

export function QuizDetailPage() {
  const { code, quizId } = useParams<{ code: string; quizId: string }>();
  const { user } = useAuth();
  const { celebrate, gamificationModals } = useGamificationFeedback();
  const [searchParams] = useSearchParams();

  // When the player linked here (?from=learn), the round trip returns to
  // learning mode instead of course detail — to the originating lesson if one
  // was given (&lesson={id}), otherwise to the player itself (unit quizzes).
  const fromLearn = searchParams.get('from') === 'learn';
  const fromLesson = fromLearn ? searchParams.get('lesson') : null;
  const backTo = fromLesson
    ? `/courses/${code}/learn/${fromLesson}`
    : fromLearn
      ? `/courses/${code}/learn`
      : `/courses/${code}`;
  const backLabel = fromLesson ? 'Lesson' : fromLearn ? 'Learning' : 'Course';

  const [quiz, setQuiz] = useState<Quiz | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [forbidden, setForbidden] = useState(false);

  // Session flow state
  const [hasInProgressSession, setHasInProgressSession] = useState(false);
  const [result, setResult] = useState<QuizAttempt | null>(null);
  const [showQuiz, setShowQuiz] = useState(false);

  useEffect(() => {
    loadQuiz();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [quizId]);

  const loadQuiz = async () => {
    if (!quizId) return;
    try {
      setIsLoading(true);
      const data = await quizzesService.getQuiz(parseInt(quizId));
      setQuiz(data);
      // Surface "resume in-progress attempt" on the intro screen (404 = none).
      if (!user?.is_instructor) {
        try {
          await quizzesService.getQuizSession(parseInt(quizId));
          setHasInProgressSession(true);
        } catch {
          setHasInProgressSession(false);
        }
      }
    } catch (err) {
      if (isForbidden(err)) {
        setForbidden(true);
      } else {
        setError('Failed to load quiz');
        console.error(err);
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleSessionComplete = async (attempt: QuizAttempt) => {
    setResult(attempt);
    setShowQuiz(false);
    setHasInProgressSession(false);
    if (attempt.passed) {
      celebrate(attempt.gamification);
    }
    // Refresh attempts_remaining / best score for the result + intro screens.
    try {
      const data = await quizzesService.getQuiz(attempt.quiz);
      setQuiz(data);
    } catch (err) {
      console.error('Failed to refresh quiz:', err);
    }
  };

  const handleRetake = async () => {
    setResult(null);
    await loadQuiz();
    setShowQuiz(true);
  };

  if (isLoading) {
    return (
      <PageContainer maxWidth="max-w-4xl">
        <Skeleton className="h-4 w-32 mb-6" />
        <Skeleton className="h-9 w-2/3 mb-2" />
        <Skeleton className="h-5 w-1/3 mb-6" />
        <Skeleton className="h-40 w-full mb-4" />
        <Skeleton className="h-40 w-full" />
      </PageContainer>
    );
  }

  if (forbidden) {
    return <AccessDenied />;
  }

  if (error || !quiz) {
    return (
      <PageContainer maxWidth="max-w-4xl">
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-destructive mb-4">{error || 'Quiz not found'}</p>
            <BackLink to={backTo} label={backLabel} />
          </CardContent>
        </Card>
      </PageContainer>
    );
  }

  // Show results
  if (result) {
    const passed = result.passed;
    const canRetake = !passed && quiz.attempts_remaining !== 0;
    const firstTryCorrect = result.answers.filter(a => a.is_correct).length;
    return (
      <PageContainer maxWidth="max-w-4xl">
        {gamificationModals}
        <BackLink to={backTo} label={backLabel} className="mb-6" />

        <Card className={`mb-6 ${passed ? 'border-green-500' : 'border-red-500'}`}>
          <CardHeader className="text-center">
            <div className="flex justify-center mb-4">
              <Mascot pose={passed ? 'celebrate' : 'encourage'} size={96} />
            </div>
            <CardTitle className="text-2xl">
              {passed ? 'Quiz Passed!' : 'Mastered — But Not Passed Yet'}
            </CardTitle>
            <p className="text-muted-foreground mt-2 text-base">
              {passed
                ? 'You mastered every question and passed the quiz!'
                : `You mastered every question — nice persistence! But your first-try score is below the ${quiz.passing_score}% needed to pass.`}
            </p>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-3 gap-4 text-center mb-6">
              <div>
                <div className="text-3xl font-bold">{result.score}%</div>
                <div className="text-sm text-muted-foreground">First-Try Score</div>
              </div>
              <div>
                <div className="text-3xl font-bold">
                  {firstTryCorrect}/{result.answers.length}
                </div>
                <div className="text-sm text-muted-foreground">Right First Try</div>
              </div>
              <div>
                <div className="text-3xl font-bold">{result.points_earned}</div>
                <div className="text-sm text-muted-foreground">Points Earned</div>
              </div>
            </div>

            {/* Show attempts info */}
            {quiz.max_attempts > 0 && (
              <p className="text-sm text-muted-foreground text-center mb-4">
                {quiz.attempts_remaining === 0
                  ? 'No attempts remaining'
                  : `${quiz.attempts_remaining} attempt${quiz.attempts_remaining === 1 ? '' : 's'} remaining`}
              </p>
            )}

            <div className="flex flex-col sm:flex-row gap-3">
              {fromLearn && (
                <Button asChild className="flex-1">
                  <Link to={backTo}>
                    <ChevronLeft className="h-4 w-4 mr-2" />
                    {fromLesson ? 'Back to Lesson' : 'Back to Learning'}
                  </Link>
                </Button>
              )}
              {canRetake && (
                <Button onClick={handleRetake} className="flex-1">
                  <RotateCcw className="h-4 w-4 mr-2" />
                  Retake Quiz
                </Button>
              )}
              {!passed && quiz.attempts_remaining === 0 && (
                <p className="flex-1 self-center text-center text-sm text-destructive font-medium">
                  No attempts remaining — contact your instructor if you need another try.
                </p>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Answer Review (first-try answers — the score record) */}
        <h2 className="text-xl font-semibold mb-4">First-Try Answer Review</h2>
        <div className="space-y-4">
          {result.answers.map((answer, index) => (
            <Card key={index} className={answer.is_correct ? 'border-green-200' : 'border-red-200'}>
              <CardContent className="pt-4">
                <div className="flex items-start gap-3">
                  {answer.is_correct ? (
                    <CheckCircle className="h-5 w-5 text-green-500 mt-0.5" />
                  ) : (
                    <XCircle className="h-5 w-5 text-red-500 mt-0.5" />
                  )}
                  <div className="flex-1">
                    <p className="font-medium mb-2">{answer.question_text}</p>
                    <p className="text-sm">
                      <span className="text-muted-foreground">Your first answer: </span>
                      <span className={answer.is_correct ? 'text-green-600' : 'text-red-600'}>
                        {answer.selected_choice_text || 'No answer'}
                      </span>
                    </p>
                    {!answer.is_correct && answer.correct_choice_text && (
                      <p className="text-sm">
                        <span className="text-muted-foreground">Correct answer: </span>
                        <span className="text-green-600">{answer.correct_choice_text}</span>
                      </p>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </PageContainer>
    );
  }

  // Show quiz intro (not started)
  if (!showQuiz) {
    return (
      <PageContainer maxWidth="max-w-4xl">
        <BackLink to={backTo} label={backLabel} className="mb-6" />

        <Card>
          <CardHeader className="text-center">
            <div className="flex justify-center mb-4">
              <FileQuestion className="h-12 w-12 text-primary" />
            </div>
            <CardTitle className="text-2xl">{quiz.title}</CardTitle>
            {quiz.description && (
              <p className="text-muted-foreground mt-2">{quiz.description}</p>
            )}
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-3 gap-4 text-center mb-6 py-4 bg-muted/50 rounded-lg">
              <div>
                <FileQuestion className="h-5 w-5 mx-auto mb-1 text-muted-foreground" />
                <div className="text-lg font-semibold">{quiz.question_count}</div>
                <div className="text-xs text-muted-foreground">Questions</div>
              </div>
              <div>
                <Target className="h-5 w-5 mx-auto mb-1 text-muted-foreground" />
                <div className="text-lg font-semibold">{quiz.passing_score}%</div>
                <div className="text-xs text-muted-foreground">To Pass</div>
              </div>
              <div>
                <Trophy className="h-5 w-5 mx-auto mb-1 text-muted-foreground" />
                <div className="text-lg font-semibold">{quiz.points}</div>
                <div className="text-xs text-muted-foreground">Points</div>
              </div>
            </div>

            <p className="text-sm text-muted-foreground text-center mb-6">
              One question at a time with instant feedback. Missed questions come
              back until you master them — your score counts first tries only.
            </p>

            {quiz.best_score && (
              <div className="mb-6 p-4 rounded-lg bg-muted/50">
                <div className="flex items-center gap-2 mb-2">
                  <Clock className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm text-muted-foreground">Previous Best</span>
                </div>
                <div className="flex items-center gap-4">
                  <span className={`text-2xl font-bold ${quiz.best_score.passed ? 'text-green-600' : 'text-red-600'}`}>
                    {quiz.best_score.score}%
                  </span>
                  {quiz.best_score.passed ? (
                    <span className="text-sm text-green-600 flex items-center gap-1">
                      <CheckCircle className="h-4 w-4" /> Passed
                    </span>
                  ) : (
                    <span className="text-sm text-red-600 flex items-center gap-1">
                      <XCircle className="h-4 w-4" /> Not Passed
                    </span>
                  )}
                </div>
              </div>
            )}

            {/* Resume banner */}
            {!user?.is_instructor && hasInProgressSession && (
              <div className="mb-4 p-3 rounded-lg border border-primary/40 bg-primary/5 text-center">
                <p className="text-sm font-medium text-primary">
                  You have a quiz in progress — pick up where you left off.
                </p>
              </div>
            )}

            {/* Attempts info */}
            {!user?.is_instructor && quiz.max_attempts > 0 && (
              <div className="mb-4 p-3 rounded-lg bg-muted/50 text-center">
                <p className="text-sm">
                  <span className="font-medium">
                    {quiz.attempts_remaining === 0
                      ? 'No attempts remaining'
                      : quiz.attempts_remaining === null
                      ? 'Unlimited attempts'
                      : `${quiz.attempts_remaining} of ${quiz.max_attempts} attempts remaining`}
                  </span>
                </p>
              </div>
            )}

            {!user?.is_instructor && quiz.question_count > 0 && (
              <Button
                onClick={() => setShowQuiz(true)}
                className="w-full"
                size="lg"
                disabled={quiz.attempts_remaining === 0 && !hasInProgressSession}
              >
                {hasInProgressSession ? (
                  <>
                    <PlayCircle className="h-5 w-5 mr-2" />
                    Resume Quiz
                  </>
                ) : quiz.attempts_remaining === 0 ? (
                  'No Attempts Remaining'
                ) : quiz.best_score ? (
                  'Retake Quiz'
                ) : (
                  'Start Quiz'
                )}
              </Button>
            )}

            {quiz.question_count === 0 && (
              <p className="text-center text-muted-foreground">
                This quiz has no questions yet.
              </p>
            )}

            {user?.is_instructor && (
              <p className="text-center text-muted-foreground">
                Instructors cannot take quizzes. Switch to a student account to test.
              </p>
            )}
          </CardContent>
        </Card>
      </PageContainer>
    );
  }

  // Active mastery session
  return (
    <PageContainer maxWidth="max-w-4xl">
      {gamificationModals}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-3xl font-bold">{quiz.title}</h1>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => {
            setShowQuiz(false);
            setHasInProgressSession(true);
          }}
          className="text-muted-foreground hover:text-foreground"
          title="Your progress is saved — resume any time"
        >
          <LogOut className="h-4 w-4 mr-2" />
          Exit (progress saved)
        </Button>
      </div>

      <QuizSessionFlow<QuizAttempt>
        questions={quiz.questions ?? []}
        getSession={() => quizzesService.getQuizSession(quiz.id)}
        startSession={() => quizzesService.startQuizSession(quiz.id)}
        answerQuestion={(questionId, choiceId) =>
          quizzesService.answerQuizQuestion(quiz.id, questionId, choiceId)
        }
        onSessionComplete={handleSessionComplete}
      />
    </PageContainer>
  );
}

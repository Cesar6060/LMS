import { useState, useEffect } from 'react';
import { useParams, Link, useSearchParams } from 'react-router';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { quizzesService } from '@/services/quizzes';
import { isForbidden } from '@/services/api';
import { AccessDenied } from '@/components/AccessDenied';
import { useAuth } from '@/contexts/AuthContext';
import type { Quiz, QuizAttempt } from '@/types';
import { PageContainer } from '@/components/layout/PageContainer';
import { Skeleton } from '@/components/ui/Skeleton';
import { BackLink } from '@/components/layout/BackLink';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import {
  Loader2, CheckCircle, XCircle, Trophy, RotateCcw,
  ChevronLeft, FileQuestion, Target, Clock, LogOut
} from 'lucide-react';

export function QuizDetailPage() {
  const { code, quizId } = useParams<{ code: string; quizId: string }>();
  const { user } = useAuth();
  const [searchParams] = useSearchParams();

  // When the player linked here (?from=learn&lesson={id}), the round trip
  // returns to the lesson instead of course detail.
  const fromLesson =
    searchParams.get('from') === 'learn' ? searchParams.get('lesson') : null;
  const backTo = fromLesson
    ? `/courses/${code}/learn/${fromLesson}`
    : `/courses/${code}`;
  const backLabel = fromLesson ? 'Lesson' : 'Course';

  const [quiz, setQuiz] = useState<Quiz | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [forbidden, setForbidden] = useState(false);

  // Quiz taking state
  const [selectedAnswers, setSelectedAnswers] = useState<Record<string, number>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [result, setResult] = useState<QuizAttempt | null>(null);
  const [showQuiz, setShowQuiz] = useState(false);
  const [showExitConfirm, setShowExitConfirm] = useState(false);

  useEffect(() => {
    loadQuiz();
  }, [quizId]);

  const loadQuiz = async () => {
    if (!quizId) return;
    try {
      setIsLoading(true);
      const data = await quizzesService.getQuiz(parseInt(quizId));
      setQuiz(data);
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

  const handleSelectAnswer = (questionId: number, choiceId: number) => {
    setSelectedAnswers(prev => ({
      ...prev,
      [questionId.toString()]: choiceId
    }));
  };

  const handleSubmit = async () => {
    if (!quiz) return;

    setIsSubmitting(true);
    try {
      const attempt = await quizzesService.submitQuiz(quiz.id, selectedAnswers);
      setResult(attempt);
      // Reload quiz to update attempts_remaining
      await loadQuiz();
    } catch (err: unknown) {
      console.error('Failed to submit quiz:', err);
      const error = err as { response?: { data?: { detail?: string } } };
      setError(error.response?.data?.detail || 'Failed to submit quiz');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRetake = async () => {
    setSelectedAnswers({});
    setResult(null);
    // Reload quiz to get fresh attempts count
    await loadQuiz();
    setShowQuiz(true);
  };

  const handleStartQuiz = () => {
    setShowQuiz(true);
  };

  const handleExitQuiz = () => {
    setSelectedAnswers({});
    setShowExitConfirm(false);
    setShowQuiz(false);
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
    return (
      <PageContainer maxWidth="max-w-4xl">
        <BackLink to={backTo} label={backLabel} className="mb-6" />

        <Card className={`mb-6 ${passed ? 'border-green-500' : 'border-red-500'}`}>
          <CardHeader className="text-center">
            <div className="flex justify-center mb-4">
              {passed ? (
                <Trophy className="h-16 w-16 text-green-500" />
              ) : (
                <XCircle className="h-16 w-16 text-red-500" />
              )}
            </div>
            <CardTitle className="text-2xl">
              {passed ? 'Congratulations!' : 'Keep Trying!'}
            </CardTitle>
            <p className="text-muted-foreground mt-2">
              {passed
                ? 'You passed the quiz!'
                : `You need ${quiz.passing_score}% to pass`}
            </p>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-3 gap-4 text-center mb-6">
              <div>
                <div className="text-3xl font-bold">{result.score}%</div>
                <div className="text-sm text-muted-foreground">Score</div>
              </div>
              <div>
                <div className="text-3xl font-bold">
                  {result.answers.filter(a => a.is_correct).length}/{result.answers.length}
                </div>
                <div className="text-sm text-muted-foreground">Correct</div>
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
              {fromLesson && (
                <Button asChild className="flex-1">
                  <Link to={backTo}>
                    <ChevronLeft className="h-4 w-4 mr-2" />
                    Back to Lesson
                  </Link>
                </Button>
              )}
              <Button
                onClick={handleRetake}
                className="flex-1"
                disabled={quiz.attempts_remaining === 0}
              >
                <RotateCcw className="h-4 w-4 mr-2" />
                {quiz.attempts_remaining === 0 ? 'No Attempts Remaining' : 'Retake Quiz'}
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Answer Review */}
        <h2 className="text-xl font-semibold mb-4">Answer Review</h2>
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
                      <span className="text-muted-foreground">Your answer: </span>
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
                onClick={handleStartQuiz}
                className="w-full"
                size="lg"
                disabled={quiz.attempts_remaining === 0}
              >
                {quiz.attempts_remaining === 0
                  ? 'No Attempts Remaining'
                  : quiz.best_score
                  ? 'Retake Quiz'
                  : 'Start Quiz'}
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

  // Show quiz questions
  const allAnswered = quiz.questions && quiz.questions.length > 0 &&
    quiz.questions.every(q => selectedAnswers[q.id.toString()]);

  return (
    <PageContainer maxWidth="max-w-4xl">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-3xl font-bold">{quiz.title}</h1>
        <div className="flex items-center gap-4">
          <span className="text-sm text-muted-foreground">
            {Object.keys(selectedAnswers).length} / {quiz.question_count} answered
          </span>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowExitConfirm(true)}
            className="text-muted-foreground hover:text-foreground"
          >
            <LogOut className="h-4 w-4 mr-2" />
            Exit Quiz
          </Button>
        </div>
      </div>

      <div className="space-y-6">
        {quiz.questions?.map((question, qIndex) => (
          <Card key={question.id}>
            <CardContent className="pt-6">
              <p className="font-medium mb-4">
                <span className="text-muted-foreground mr-2">Q{qIndex + 1}.</span>
                {question.text}
              </p>
              <div className="space-y-2">
                {question.choices.map((choice) => (
                  <label
                    key={choice.id}
                    className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                      selectedAnswers[question.id.toString()] === choice.id
                        ? 'border-primary bg-primary/5'
                        : 'border-muted hover:border-primary/50'
                    }`}
                  >
                    <input
                      type="radio"
                      name={`question-${question.id}`}
                      value={choice.id}
                      checked={selectedAnswers[question.id.toString()] === choice.id}
                      onChange={() => handleSelectAnswer(question.id, choice.id)}
                      className="h-4 w-4"
                    />
                    <span>{choice.text}</span>
                  </label>
                ))}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="mt-8 flex gap-4">
        <Button
          variant="outline"
          onClick={() => setShowExitConfirm(true)}
          className="flex-1"
        >
          Cancel
        </Button>
        <Button
          onClick={handleSubmit}
          disabled={!allAnswered || isSubmitting}
          className="flex-1"
        >
          {isSubmitting ? (
            <>
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              Submitting...
            </>
          ) : (
            'Submit Quiz'
          )}
        </Button>
      </div>

      <ConfirmDialog
        open={showExitConfirm}
        onOpenChange={setShowExitConfirm}
        title="Exit Quiz?"
        confirmLabel="Exit Quiz"
        onConfirm={handleExitQuiz}
      >
        Are you sure you want to exit? Your answers will be discarded.
      </ConfirmDialog>
    </PageContainer>
  );
}

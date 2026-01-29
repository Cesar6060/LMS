import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/Dialog';
import { courseService } from '@/services/courses';
import type { LessonQuestion, LessonQuestionsStatus, QuizSubmissionResult } from '@/types';
import { CheckCircle, XCircle, HelpCircle, Loader2, AlertCircle, Trophy } from 'lucide-react';
import { cn } from '@/lib/utils';

interface LessonQuestionsProps {
  lessonId: number;
  onStatusChange?: (status: LessonQuestionsStatus) => void;
}

export function LessonQuestions({ lessonId, onStatusChange }: LessonQuestionsProps) {
  const [questions, setQuestions] = useState<LessonQuestion[]>([]);
  const [status, setStatus] = useState<LessonQuestionsStatus | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [showQuizModal, setShowQuizModal] = useState(false);
  const [selectedAnswers, setSelectedAnswers] = useState<Record<string, number>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [quizResult, setQuizResult] = useState<QuizSubmissionResult | null>(null);

  useEffect(() => {
    loadData();
  }, [lessonId]);

  const loadData = async () => {
    setIsLoading(true);
    try {
      const [questionsData, statusData] = await Promise.all([
        courseService.getLessonQuestions(lessonId),
        courseService.getLessonQuestionsStatus(lessonId)
      ]);
      setQuestions(questionsData);
      setStatus(statusData);
      onStatusChange?.(statusData);
    } catch (err) {
      console.error('Failed to load questions:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleStartQuiz = () => {
    setSelectedAnswers({});
    setQuizResult(null);
    setShowQuizModal(true);
  };

  const handleSelectAnswer = (questionId: number, choiceId: number) => {
    if (quizResult) return; // Don't allow changes after submission
    setSelectedAnswers(prev => ({
      ...prev,
      [questionId.toString()]: choiceId
    }));
  };

  const handleSubmitQuiz = async () => {
    setIsSubmitting(true);
    try {
      const result = await courseService.submitLessonQuiz(lessonId, selectedAnswers);
      setQuizResult(result);

      // Refresh status
      const newStatus = await courseService.getLessonQuestionsStatus(lessonId);
      setStatus(newStatus);
      onStatusChange?.(newStatus);
    } catch (err: unknown) {
      console.error('Failed to submit quiz:', err);
      const error = err as { response?: { data?: { error?: string } } };
      alert(error.response?.data?.error || 'Failed to submit quiz');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCloseModal = () => {
    setShowQuizModal(false);
    setQuizResult(null);
    setSelectedAnswers({});
  };

  const allQuestionsAnswered = questions.length > 0 &&
    Object.keys(selectedAnswers).length === questions.length;

  if (isLoading) {
    return (
      <Card className="mt-6">
        <CardContent className="py-8 flex justify-center">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </CardContent>
      </Card>
    );
  }

  if (!status || status.total_questions === 0) {
    return null;
  }

  return (
    <>
      <Card className="mt-6">
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2">
              <HelpCircle className="h-5 w-5" />
              Comprehension Check
            </CardTitle>
            {status.has_passed && (
              <div className="flex items-center gap-2 text-green-600">
                <Trophy className="h-5 w-5" />
                <span className="text-sm font-medium">Passed</span>
              </div>
            )}
          </div>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {/* Status info */}
            <div className="flex items-center justify-between p-4 bg-muted/50 rounded-lg">
              <div>
                <p className="font-medium">{status.total_questions} Questions</p>
                <p className="text-sm text-muted-foreground">
                  {status.max_attempts
                    ? `${status.attempt_count} of ${status.max_attempts} attempts used`
                    : `${status.attempt_count} attempt${status.attempt_count !== 1 ? 's' : ''}`
                  }
                </p>
              </div>
              <div className="text-right">
                {status.has_passed ? (
                  <div className="text-green-600">
                    <p className="font-medium">Quiz Passed!</p>
                    <p className="text-sm">You can complete this lesson</p>
                  </div>
                ) : status.can_attempt ? (
                  <Button onClick={handleStartQuiz}>
                    <HelpCircle className="h-4 w-4 mr-2" />
                    {status.attempt_count === 0 ? 'Take Quiz' : 'Retry Quiz'}
                  </Button>
                ) : (
                  <div className="text-destructive">
                    <p className="font-medium">No attempts remaining</p>
                    <p className="text-sm">Contact your instructor</p>
                  </div>
                )}
              </div>
            </div>

            {/* Previous attempt info */}
            {status.attempt_count > 0 && !status.has_passed && (
              <div className="flex items-center gap-2 p-3 bg-amber-50 dark:bg-amber-900/20 rounded-lg text-amber-800 dark:text-amber-400">
                <AlertCircle className="h-4 w-4" />
                <span className="text-sm">
                  Best score: {status.correct_answers}/{status.total_questions} correct.
                  {status.can_attempt && ' Answer all questions correctly to pass.'}
                </span>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Quiz Modal */}
      <Dialog open={showQuizModal} onOpenChange={handleCloseModal}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <HelpCircle className="h-5 w-5" />
              Comprehension Quiz
            </DialogTitle>
            <DialogDescription>
              Answer all questions correctly to complete this lesson.
              {status?.max_attempts && (
                <span className="ml-1">
                  ({status.attempts_remaining} attempt{status.attempts_remaining !== 1 ? 's' : ''} remaining)
                </span>
              )}
            </DialogDescription>
          </DialogHeader>

          <div className="flex-1 overflow-y-auto py-4 space-y-6">
            {questions.map((question, index) => {
              const resultForQuestion = quizResult?.results.find(r => r.question_id === question.id);

              return (
                <div key={question.id} className="space-y-3">
                  <p className="font-medium">
                    {index + 1}. {question.text}
                  </p>
                  <div className="space-y-2 ml-4">
                    {question.choices.map(choice => {
                      const isSelected = selectedAnswers[question.id.toString()] === choice.id;
                      const showCorrect = quizResult && resultForQuestion?.correct_choice_id === choice.id;
                      const showIncorrect = quizResult && isSelected && !resultForQuestion?.is_correct;

                      return (
                        <button
                          key={choice.id}
                          type="button"
                          onClick={() => handleSelectAnswer(question.id, choice.id)}
                          disabled={Boolean(quizResult)}
                          className={cn(
                            "w-full text-left p-3 rounded-lg border-2 transition-colors",
                            !quizResult && isSelected && "border-primary bg-primary/10",
                            !quizResult && !isSelected && "border-muted hover:border-muted-foreground/50",
                            showCorrect && "border-green-500 bg-green-50 dark:bg-green-900/20",
                            showIncorrect && "border-red-500 bg-red-50 dark:bg-red-900/20",
                            quizResult && "cursor-default"
                          )}
                        >
                          <span className="flex items-center justify-between">
                            <span>{choice.text}</span>
                            {showCorrect && <CheckCircle className="h-5 w-5 text-green-600" />}
                            {showIncorrect && <XCircle className="h-5 w-5 text-red-600" />}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              );
            })}

            {/* Results summary */}
            {quizResult && (
              <div className={cn(
                "p-4 rounded-lg",
                quizResult.passed
                  ? "bg-green-50 dark:bg-green-900/20 text-green-800 dark:text-green-400"
                  : "bg-red-50 dark:bg-red-900/20 text-red-800 dark:text-red-400"
              )}>
                <div className="flex items-center gap-2 mb-2">
                  {quizResult.passed ? (
                    <Trophy className="h-5 w-5" />
                  ) : (
                    <XCircle className="h-5 w-5" />
                  )}
                  <span className="font-medium">
                    {quizResult.passed ? 'Quiz Passed!' : 'Quiz Not Passed'}
                  </span>
                </div>
                <p className="text-sm">
                  Score: {quizResult.score}/{quizResult.total_questions} ({quizResult.percentage}%)
                </p>
                {!quizResult.passed && quizResult.attempts_remaining !== null && (
                  <p className="text-sm mt-1">
                    {quizResult.attempts_remaining > 0
                      ? `${quizResult.attempts_remaining} attempt${quizResult.attempts_remaining !== 1 ? 's' : ''} remaining`
                      : 'No attempts remaining'
                    }
                  </p>
                )}
              </div>
            )}
          </div>

          <DialogFooter>
            {quizResult ? (
              <Button onClick={handleCloseModal}>
                {quizResult.passed ? 'Done' : 'Close'}
              </Button>
            ) : (
              <>
                <Button variant="outline" onClick={handleCloseModal} disabled={isSubmitting}>
                  Cancel
                </Button>
                <Button
                  onClick={handleSubmitQuiz}
                  disabled={!allQuestionsAnswered || isSubmitting}
                >
                  {isSubmitting && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                  Submit Quiz
                </Button>
              </>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

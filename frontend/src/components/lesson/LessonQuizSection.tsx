import { useState, useEffect } from 'react';
import { Card, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { courseService } from '@/services/courses';
import type { LessonQuestion, LessonQuestionsStatus, QuizSubmissionResult } from '@/types';
import { CheckCircle, XCircle, HelpCircle, Loader2, Trophy, Target, RotateCcw } from 'lucide-react';
import { cn } from '@/lib/utils';

interface LessonQuizSectionProps {
  lessonId: number;
  onStatusChange?: (status: LessonQuestionsStatus) => void;
  onComplete?: () => void;
  isLessonCompleted?: boolean;
}

export function LessonQuizSection({ lessonId, onStatusChange, onComplete, isLessonCompleted }: LessonQuizSectionProps) {
  const [questions, setQuestions] = useState<LessonQuestion[]>([]);
  const [status, setStatus] = useState<LessonQuestionsStatus | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedAnswers, setSelectedAnswers] = useState<Record<string, number>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [quizResult, setQuizResult] = useState<QuizSubmissionResult | null>(null);
  const [showQuiz, setShowQuiz] = useState(false);

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
    setShowQuiz(true);
  };

  const handleSelectAnswer = (questionId: number, choiceId: number) => {
    if (quizResult) return;
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

      const newStatus = await courseService.getLessonQuestionsStatus(lessonId);
      setStatus(newStatus);
      onStatusChange?.(newStatus);

      if (result.passed && onComplete) {
        setTimeout(onComplete, 1500);
      }
    } catch (err: unknown) {
      console.error('Failed to submit quiz:', err);
      const error = err as { response?: { data?: { error?: string } } };
      alert(error.response?.data?.error || 'Failed to submit quiz');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRetry = () => {
    setSelectedAnswers({});
    setQuizResult(null);
  };

  const allQuestionsAnswered = questions.length > 0 &&
    Object.keys(selectedAnswers).length === questions.length;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (!status || status.total_questions === 0) {
    return null;
  }

  // Already passed - show success state
  if (status.has_passed && !showQuiz) {
    return (
      <div className="animate-in fade-in duration-500">
        <div className="text-center py-12">
          <div className="inline-flex items-center justify-center w-20 h-20 rounded-full bg-green-100 dark:bg-green-900/30 mb-6">
            <Trophy className="h-10 w-10 text-green-600 dark:text-green-400" />
          </div>
          <h3 className="text-2xl font-bold text-green-600 dark:text-green-400 mb-2">
            {isLessonCompleted ? 'Lesson Completed!' : 'Quiz Completed!'}
          </h3>
          <p className="text-muted-foreground mb-6">
            You've successfully passed the comprehension check.
          </p>
          {isLessonCompleted ? (
            <div className="inline-flex items-center gap-2 px-6 py-3 rounded-full bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400">
              <CheckCircle className="h-5 w-5" />
              <span className="font-medium">Lesson Complete</span>
            </div>
          ) : onComplete && (
            <Button
              size="lg"
              onClick={onComplete}
              className="gap-2 bg-green-600 hover:bg-green-700"
            >
              <CheckCircle className="h-5 w-5" />
              Mark Lesson Complete
            </Button>
          )}
        </div>
      </div>
    );
  }

  // Show quiz start screen
  if (!showQuiz) {
    return (
      <div className="animate-in fade-in duration-500">
        <div className="text-center py-8">
          <div className="inline-flex items-center justify-center w-20 h-20 rounded-full bg-primary/10 mb-6">
            <Target className="h-10 w-10 text-primary" />
          </div>
          <h3 className="text-2xl font-bold mb-2">Comprehension Check</h3>
          <p className="text-muted-foreground mb-8 max-w-md mx-auto">
            Test your understanding of this lesson. Answer all questions correctly to proceed.
          </p>

          <Card className="max-w-sm mx-auto mb-8">
            <CardContent className="py-6">
              <div className="grid grid-cols-2 gap-4 text-center">
                <div>
                  <p className="text-3xl font-bold text-primary">{status.total_questions}</p>
                  <p className="text-sm text-muted-foreground">Questions</p>
                </div>
                <div>
                  <p className="text-3xl font-bold text-primary">
                    {status.max_attempts ? status.attempts_remaining : '∞'}
                  </p>
                  <p className="text-sm text-muted-foreground">
                    {status.max_attempts ? 'Attempts Left' : 'Unlimited'}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>

          {status.attempt_count > 0 && (
            <p className="text-sm text-muted-foreground mb-4">
              Previous best: {status.correct_answers}/{status.total_questions} correct
            </p>
          )}

          {status.can_attempt ? (
            <Button size="lg" onClick={handleStartQuiz} className="gap-2">
              <HelpCircle className="h-5 w-5" />
              {status.attempt_count === 0 ? 'Start Quiz' : 'Try Again'}
            </Button>
          ) : (
            <div className="text-destructive">
              <p className="font-medium">No attempts remaining</p>
              <p className="text-sm">Contact your instructor for help</p>
            </div>
          )}
        </div>
      </div>
    );
  }

  // Show active quiz
  return (
    <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="max-w-2xl mx-auto">
        {/* Progress indicator */}
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-lg font-semibold">Comprehension Check</h3>
          <span className="text-sm text-muted-foreground">
            {Object.keys(selectedAnswers).length}/{questions.length} answered
          </span>
        </div>

        {/* Questions */}
        <div className="space-y-8">
          {questions.map((question, index) => {
            const resultForQuestion = quizResult?.results.find(r => r.question_id === question.id);

            return (
              <Card key={question.id} className="overflow-hidden">
                <CardContent className="p-6">
                  <p className="font-medium mb-4">
                    <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-primary/10 text-primary text-sm mr-2">
                      {index + 1}
                    </span>
                    {question.text}
                  </p>
                  <div className="space-y-2">
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
                            "w-full text-left p-4 rounded-lg border-2 transition-all duration-200",
                            !quizResult && isSelected && "border-primary bg-primary/5 shadow-sm",
                            !quizResult && !isSelected && "border-transparent bg-muted/50 hover:bg-muted hover:border-muted-foreground/20",
                            showCorrect && "border-green-500 bg-green-50 dark:bg-green-900/20",
                            showIncorrect && "border-red-500 bg-red-50 dark:bg-red-900/20",
                            quizResult && "cursor-default"
                          )}
                        >
                          <span className="flex items-center justify-between">
                            <span>{choice.text}</span>
                            {showCorrect && <CheckCircle className="h-5 w-5 text-green-600 flex-shrink-0" />}
                            {showIncorrect && <XCircle className="h-5 w-5 text-red-600 flex-shrink-0" />}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>

        {/* Results or Submit */}
        <div className="mt-8">
          {quizResult ? (
            <Card className={cn(
              "overflow-hidden",
              quizResult.passed ? "border-green-500" : "border-red-500"
            )}>
              <CardContent className="p-6">
                <div className="flex items-center gap-4">
                  <div className={cn(
                    "flex items-center justify-center w-16 h-16 rounded-full",
                    quizResult.passed
                      ? "bg-green-100 dark:bg-green-900/30"
                      : "bg-red-100 dark:bg-red-900/30"
                  )}>
                    {quizResult.passed ? (
                      <Trophy className="h-8 w-8 text-green-600 dark:text-green-400" />
                    ) : (
                      <XCircle className="h-8 w-8 text-red-600 dark:text-red-400" />
                    )}
                  </div>
                  <div className="flex-1">
                    <h4 className={cn(
                      "text-xl font-bold",
                      quizResult.passed ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"
                    )}>
                      {quizResult.passed ? 'Excellent Work!' : 'Not Quite'}
                    </h4>
                    <p className="text-muted-foreground">
                      Score: {quizResult.score}/{quizResult.total_questions} ({quizResult.percentage}%)
                    </p>
                  </div>
                  {!quizResult.passed && quizResult.attempts_remaining !== null && quizResult.attempts_remaining > 0 && (
                    <Button variant="outline" onClick={handleRetry} className="gap-2">
                      <RotateCcw className="h-4 w-4" />
                      Try Again
                    </Button>
                  )}
                </div>
                {quizResult.passed && (
                  <p className="text-sm text-green-600 dark:text-green-400 mt-4">
                    You can now mark this lesson as complete.
                  </p>
                )}
                {!quizResult.passed && quizResult.attempts_remaining === 0 && (
                  <p className="text-sm text-red-600 dark:text-red-400 mt-4">
                    No attempts remaining. Contact your instructor for help.
                  </p>
                )}
              </CardContent>
            </Card>
          ) : (
            <div className="flex justify-center">
              <Button
                size="lg"
                onClick={handleSubmitQuiz}
                disabled={!allQuestionsAnswered || isSubmitting}
                className="gap-2 min-w-[200px]"
              >
                {isSubmitting ? (
                  <Loader2 className="h-5 w-5 animate-spin" />
                ) : (
                  <CheckCircle className="h-5 w-5" />
                )}
                Submit Answers
              </Button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

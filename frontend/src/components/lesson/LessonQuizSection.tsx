import { useState, useEffect } from 'react';
import { Card, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { courseService } from '@/services/courses';
import type { LessonQuestion, LessonQuestionsStatus, LessonSessionResult } from '@/types';
import { CheckCircle, HelpCircle, Loader2, Trophy, Target } from 'lucide-react';
import { useGamificationFeedback } from '@/components/gamification/useGamificationFeedback';
import { QuizSessionFlow } from '@/components/quiz/QuizSessionFlow';
import { Mascot } from '@/components/gamification/Mascot';

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
  const [showQuiz, setShowQuiz] = useState(false);
  const [sessionResult, setSessionResult] = useState<LessonSessionResult | null>(null);
  const { celebrate, gamificationModals } = useGamificationFeedback();

  useEffect(() => {
    loadData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
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

  const handleSessionComplete = async (result: LessonSessionResult) => {
    setSessionResult(result);
    setShowQuiz(false);
    celebrate(result.gamification);
    try {
      const newStatus = await courseService.getLessonQuestionsStatus(lessonId);
      setStatus(newStatus);
      onStatusChange?.(newStatus);
    } catch (err) {
      console.error('Failed to refresh quiz status:', err);
    }
  };

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

  // Just mastered this session — celebration + mark-complete handoff.
  if (sessionResult) {
    return (
      <div className="animate-in fade-in duration-500">
        {gamificationModals}
        <div className="text-center py-10">
          <div className="flex justify-center mb-4">
            <Mascot pose="celebrate" size={110} />
          </div>
          <h3 className="text-3xl font-bold text-green-600 dark:text-green-400 mb-2">
            Mastered!
          </h3>
          <p className="text-muted-foreground mb-2">
            You answered every question correctly.
          </p>
          <p className="text-base mb-6">
            Right on the first try: <span className="font-bold">{sessionResult.score}/{sessionResult.total_questions}</span>
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

  // Already passed - show success state
  if (status.has_passed && !showQuiz) {
    return (
      <div className="animate-in fade-in duration-500">
        <div className="text-center py-12">
          <div className="inline-flex items-center justify-center w-20 h-20 rounded-full bg-green-100 dark:bg-green-900/30 mb-6">
            <Trophy className="h-10 w-10 text-green-600 dark:text-green-400" />
          </div>
          <h3 className="text-2xl font-bold text-green-600 dark:text-green-400 mb-2">
            {isLessonCompleted ? 'Lesson Completed!' : 'Check Mastered!'}
          </h3>
          <p className="text-muted-foreground mb-6">
            You've successfully passed the comprehension check.
          </p>
          {isLessonCompleted ? (
            <div className="flex flex-col items-center gap-4">
              <div className="inline-flex items-center gap-2 px-6 py-3 rounded-full bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400">
                <CheckCircle className="h-5 w-5" />
                <span className="font-medium">Lesson Complete</span>
              </div>
              <Button variant="outline" onClick={() => setShowQuiz(true)}>
                Practice Again
              </Button>
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
            One question at a time with instant feedback. Missed questions come
            back until you've mastered them all — no attempt limits.
          </p>

          <Card className="max-w-sm mx-auto mb-8">
            <CardContent className="py-6">
              <div className="text-center">
                <p className="text-3xl font-bold text-primary">{status.total_questions}</p>
                <p className="text-sm text-muted-foreground">
                  Question{status.total_questions === 1 ? '' : 's'} to master
                </p>
              </div>
            </CardContent>
          </Card>

          <Button size="lg" onClick={() => setShowQuiz(true)} className="gap-2">
            <HelpCircle className="h-5 w-5" />
            {status.attempt_count === 0 ? 'Start Check' : 'Try Again'}
          </Button>
        </div>
      </div>
    );
  }

  // Active mastery session
  return (
    <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
      {gamificationModals}
      <QuizSessionFlow<LessonSessionResult>
        title="Comprehension Check"
        questions={questions}
        getSession={() => courseService.getLessonQuizSession(lessonId)}
        startSession={() => courseService.startLessonQuizSession(lessonId)}
        answerQuestion={(questionId, choiceId) =>
          courseService.answerLessonQuizQuestion(lessonId, questionId, choiceId)
        }
        onSessionComplete={handleSessionComplete}
      />
    </div>
  );
}

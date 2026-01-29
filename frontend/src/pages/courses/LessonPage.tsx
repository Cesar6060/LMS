import { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, Link } from 'react-router';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Card, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { courseService } from '@/services/courses';
import { VideoPlayer } from '@/components/video/VideoPlayer';
import { LessonQuestions } from '@/components/lesson/LessonQuestions';
import { LessonAttachmentsList } from '@/components/lesson/LessonAttachmentsList';
import type { Lesson, LessonProgress, LessonQuestionsStatus } from '@/types';
import {
  Loader2, ChevronLeft, CheckCircle, Circle, BookOpen, FileQuestion
} from 'lucide-react';

export function LessonPage() {
  const { code, lessonId } = useParams<{ code: string; lessonId: string }>();

  const [lesson, setLesson] = useState<Lesson | null>(null);
  const [progress, setProgress] = useState<LessonProgress | null>(null);
  const [questionsStatus, setQuestionsStatus] = useState<LessonQuestionsStatus | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [isMarkingComplete, setIsMarkingComplete] = useState(false);

  // Track last saved position to avoid unnecessary API calls
  const lastSavedPositionRef = useRef<number>(0);
  // Use ref instead of state to avoid re-renders during background saves
  const isSavingRef = useRef(false);

  useEffect(() => {
    if (lessonId) {
      loadLesson();
    }
  }, [lessonId]);

  const loadLesson = async () => {
    try {
      setIsLoading(true);
      const [lessonData, progressData] = await Promise.all([
        courseService.getLesson(parseInt(lessonId!)),
        courseService.getLessonProgress(parseInt(lessonId!))
      ]);
      setLesson(lessonData);
      setProgress(progressData);
      lastSavedPositionRef.current = progressData?.video_position || 0;

      // Track course activity
      if (code) {
        courseService.updateCourseActivity(code).catch(() => {
          // Silent fail for activity tracking
        });
      }
    } catch (err: unknown) {
      const error = err as { response?: { status?: number } };
      if (error.response?.status === 403) {
        setError('You must be enrolled in this course to view this lesson.');
      } else {
        setError('Failed to load lesson');
      }
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleMarkComplete = async () => {
    if (!lesson || !progress) return;

    setIsMarkingComplete(true);
    try {
      const updated = await courseService.updateLessonProgress(lesson.id, {
        completed: !progress.completed
      });
      setProgress(updated);
    } catch (err) {
      console.error('Failed to update progress:', err);
    } finally {
      setIsMarkingComplete(false);
    }
  };

  // Save video progress (debounced - only if position changed significantly)
  // Uses refs instead of state to avoid re-renders that cause video stutter
  const handleVideoProgress = useCallback(async (position: number, _duration: number) => {
    if (!lesson || isSavingRef.current) return;

    // Only save if position changed by at least 5 seconds
    const positionDiff = Math.abs(position - lastSavedPositionRef.current);
    if (positionDiff < 5) return;

    isSavingRef.current = true;
    try {
      await courseService.updateLessonProgress(lesson.id, {
        video_position: Math.floor(position)
      });
      lastSavedPositionRef.current = position;
    } catch (err) {
      console.error('Failed to save video progress:', err);
    } finally {
      isSavingRef.current = false;
    }
  }, [lesson]);

  // Handle video ended - mark as complete
  const handleVideoEnded = useCallback(async () => {
    if (!lesson || progress?.completed) return;

    try {
      const updated = await courseService.updateLessonProgress(lesson.id, {
        completed: true
      });
      setProgress(updated);
    } catch (err) {
      console.error('Failed to mark lesson complete:', err);
    }
  }, [lesson, progress?.completed]);

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (error || !lesson) {
    return (
      <div className="container mx-auto px-4 py-8">
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <BookOpen className="h-12 w-12 text-muted-foreground mb-4" />
            <h3 className="text-lg font-semibold mb-2">Cannot access lesson</h3>
            <p className="text-muted-foreground mb-4">{error}</p>
            <Link to={`/courses/${code}`}>
              <Button>Back to Course</Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8 max-w-4xl">
      {/* Navigation */}
      <div className="flex items-center justify-between mb-6">
        <Link to={`/courses/${code}`}>
          <Button variant="ghost" size="sm">
            <ChevronLeft className="h-4 w-4 mr-1" />
            Back to Course
          </Button>
        </Link>

        <div className="flex items-center gap-4">
          {/* Required Quiz Badge */}
          {progress?.required_quiz_info && !progress?.completed && (
            <div className={`flex items-center gap-2 px-3 py-1 rounded-full text-sm ${
              progress?.required_quiz_passed
                ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400'
                : 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400'
            }`}>
              {progress?.required_quiz_passed ? (
                <>
                  <CheckCircle className="h-4 w-4" />
                  Quiz Passed
                </>
              ) : (
                <>
                  <FileQuestion className="h-4 w-4" />
                  <Link
                    to={`/quizzes/${progress.required_quiz_info.id}`}
                    className="hover:underline"
                  >
                    Complete quiz "{progress.required_quiz_info.title}" to finish this lesson
                  </Link>
                </>
              )}
            </div>
          )}

          {/* Comprehension Questions Badge */}
          {questionsStatus && questionsStatus.total_questions > 0 && !progress?.completed && (
            <div className={`flex items-center gap-2 px-3 py-1 rounded-full text-sm ${
              questionsStatus.can_complete_lesson
                ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400'
                : 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400'
            }`}>
              {questionsStatus.can_complete_lesson ? (
                <>
                  <CheckCircle className="h-4 w-4" />
                  Quiz Passed
                </>
              ) : (
                <>
                  <FileQuestion className="h-4 w-4" />
                  Complete the comprehension quiz to finish this lesson
                </>
              )}
            </div>
          )}

          {/* Only show Mark Complete button if there's no quiz requirement */}
          {!progress?.required_quiz_info && (!questionsStatus || questionsStatus.total_questions === 0) && (
            <Button
              variant={progress?.completed ? 'default' : 'outline'}
              size="sm"
              onClick={handleMarkComplete}
              disabled={isMarkingComplete}
            >
              {isMarkingComplete ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : progress?.completed ? (
                <CheckCircle className="h-4 w-4 mr-2" />
              ) : (
                <Circle className="h-4 w-4 mr-2" />
              )}
              {progress?.completed ? 'Completed' : 'Mark Complete'}
            </Button>
          )}

          {/* Show completion status when there IS a quiz requirement */}
          {(progress?.required_quiz_info || (questionsStatus && questionsStatus.total_questions > 0)) && progress?.completed && (
            <div className="flex items-center gap-2 px-3 py-1 rounded-full text-sm bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400">
              <CheckCircle className="h-4 w-4" />
              Completed
            </div>
          )}
        </div>
      </div>

      {/* Lesson Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-2">{lesson.title}</h1>
      </div>

      {/* Video Player (if applicable) */}
      {lesson.video_type === 'youtube' && lesson.video_id && (
        <div className="mb-8">
          <VideoPlayer
            videoType="youtube"
            videoId={lesson.video_id}
            initialPosition={progress?.video_position || 0}
            onProgress={handleVideoProgress}
            onEnded={handleVideoEnded}
          />
        </div>
      )}

      {/* Lesson Content */}
      {lesson.content && (
        <Card>
          <CardContent className="prose prose-neutral dark:prose-invert max-w-none py-6">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {lesson.content}
            </ReactMarkdown>
          </CardContent>
        </Card>
      )}

      {!lesson.content && lesson.video_type === 'none' && (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            No content available for this lesson.
          </CardContent>
        </Card>
      )}

      {/* Attachments */}
      <LessonAttachmentsList attachments={lesson.attachments || []} />

      {/* Lesson Questions (Comprehension Check) */}
      <div className="mt-6">
        <LessonQuestions
          lessonId={lesson.id}
          onStatusChange={setQuestionsStatus}
        />
      </div>
    </div>
  );
}

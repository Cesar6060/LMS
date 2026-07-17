import { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, Link } from 'react-router';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Card, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { courseService } from '@/services/courses';
import { useAuth } from '@/contexts/AuthContext';
import { VideoPlayer } from '@/components/video/VideoPlayer';
import { LessonQuizSection } from '@/components/lesson/LessonQuizSection';
import { LessonAttachmentsList } from '@/components/lesson/LessonAttachmentsList';
import type { Lesson, LessonProgress, LessonQuestionsStatus, Course } from '@/types';
import {
  Loader2, ChevronLeft, ChevronRight, CheckCircle, Circle, BookOpen, FileQuestion
} from 'lucide-react';

export function LessonPage() {
  const { code, lessonId } = useParams<{ code: string; lessonId: string }>();
  const { user } = useAuth();

  const [lesson, setLesson] = useState<Lesson | null>(null);
  const [course, setCourse] = useState<Course | null>(null);
  const [progress, setProgress] = useState<LessonProgress | null>(null);
  const [questionsStatus, setQuestionsStatus] = useState<LessonQuestionsStatus | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [isMarkingComplete, setIsMarkingComplete] = useState(false);

  // Section navigation state
  const [currentSectionIndex, setCurrentSectionIndex] = useState(0);

  // Track last saved position to avoid unnecessary API calls
  const lastSavedPositionRef = useRef<number>(0);
  const lastSavedSectionRef = useRef<number>(0);
  const isSavingRef = useRef(false);

  // Check if current user is the instructor
  const isCourseOwner = course && user && course.instructor.id === user.id;

  // Refs for cleanup
  const currentLessonRef = useRef<number | null>(null);
  const isCourseOwnerRef = useRef(false);

  // Update refs when values change
  useEffect(() => {
    currentLessonRef.current = lesson?.id || null;
    isCourseOwnerRef.current = !!isCourseOwner;
  }, [lesson?.id, isCourseOwner]);

  // Reset instructor progress when leaving the lesson
  useEffect(() => {
    return () => {
      if (isCourseOwnerRef.current && currentLessonRef.current) {
        courseService.resetLessonProgress(currentLessonRef.current).catch(() => {
          // Silent fail
        });
      }
    };
  }, []);

  useEffect(() => {
    if (lessonId && code) {
      loadLesson();
    }
  }, [lessonId, code]);

  const loadLesson = async () => {
    try {
      setIsLoading(true);
      setCurrentSectionIndex(0);
      const [lessonData, progressData, quizStatusData, courseData] = await Promise.all([
        courseService.getLesson(parseInt(lessonId!)),
        courseService.getLessonProgress(parseInt(lessonId!)),
        courseService.getLessonQuestionsStatus(parseInt(lessonId!)).catch(() => null),
        courseService.getCourse(code!).catch(() => null)
      ]);
      setLesson(lessonData);
      setProgress(progressData);
      setQuestionsStatus(quizStatusData);
      setCourse(courseData);
      lastSavedPositionRef.current = progressData?.video_position || 0;
      lastSavedSectionRef.current = progressData?.current_section || 0;

      // Calculate total sections for resume logic
      const contentSectionsCount = lessonData.sections?.length || 0;
      const hasQuizSection = quizStatusData && quizStatusData.total_questions > 0;
      const maxSectionIndex = contentSectionsCount + (hasQuizSection ? 1 : 0) - 1;

      // Resume at saved section
      if (progressData?.current_section !== undefined) {
        const savedSection = progressData.current_section;
        if (savedSection <= maxSectionIndex && savedSection >= 0) {
          setCurrentSectionIndex(savedSection);
        }
      }

      // Track course activity
      if (code) {
        courseService.updateCourseActivity(code).catch(() => {});
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

  // Handle section navigation
  const handleSectionChange = useCallback(async (newIndex: number) => {
    if (!lesson || isSavingRef.current) return;

    const contentSectionsCount = lesson.sections?.length || 0;
    const hasQuizSection = questionsStatus && questionsStatus.total_questions > 0;
    const maxIndex = contentSectionsCount + (hasQuizSection ? 1 : 0) - 1;

    if (newIndex < 0 || newIndex > maxIndex) return;

    setCurrentSectionIndex(newIndex);

    // Save section progress
    if (newIndex !== lastSavedSectionRef.current) {
      isSavingRef.current = true;
      try {
        await courseService.updateLessonProgress(lesson.id, {
          current_section: newIndex
        });
        lastSavedSectionRef.current = newIndex;
      } catch (err) {
        console.error('Failed to save section progress:', err);
      } finally {
        isSavingRef.current = false;
      }
    }
  }, [lesson, questionsStatus]);

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

  const handleVideoProgress = useCallback(async (position: number) => {
    if (!lesson || isSavingRef.current) return;

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

  const handleVideoEnded = useCallback(async () => {
    if (!lesson || progress?.completed) return;

    // If there are more sections, move to next section
    const contentSections = lesson.sections || [];
    const hasQuiz = questionsStatus && questionsStatus.total_questions > 0;
    const totalSections = contentSections.length + (hasQuiz ? 1 : 0);

    if (totalSections > 1 && currentSectionIndex < totalSections - 1) {
      handleSectionChange(currentSectionIndex + 1);
      return;
    }

    // Only auto-complete if no quiz required
    if (!hasQuiz) {
      try {
        const updated = await courseService.updateLessonProgress(lesson.id, {
          completed: true
        });
        setProgress(updated);
      } catch (err) {
        console.error('Failed to mark lesson complete:', err);
      }
    }
  }, [lesson, progress?.completed, questionsStatus, currentSectionIndex, handleSectionChange]);

  // Keyboard navigation
  useEffect(() => {
    const handleKeyPress = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
        return;
      }

      // Calculate total sections for keyboard navigation
      const contentSectionsCount = lesson?.sections?.length || 0;
      const hasQuizSection = questionsStatus && questionsStatus.total_questions > 0;
      const totalSectionsCount = contentSectionsCount + (hasQuizSection ? 1 : 0);

      if (e.key === 'ArrowLeft' && currentSectionIndex > 0) {
        handleSectionChange(currentSectionIndex - 1);
      } else if (e.key === 'ArrowRight' && currentSectionIndex < totalSectionsCount - 1) {
        handleSectionChange(currentSectionIndex + 1);
      }
    };

    window.addEventListener('keydown', handleKeyPress);
    return () => window.removeEventListener('keydown', handleKeyPress);
  }, [currentSectionIndex, handleSectionChange, lesson, questionsStatus]);

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

  // Section calculations
  const contentSections = lesson.sections || [];
  const hasContentSections = contentSections.length > 0;
  const hasQuiz = questionsStatus && questionsStatus.total_questions > 0;
  const totalSections = hasContentSections
    ? contentSections.length + (hasQuiz ? 1 : 0)
    : (hasQuiz ? 1 : 0);
  const hasSections = totalSections > 1;
  const isOnQuizSection = hasQuiz && currentSectionIndex === totalSections - 1;
  const currentSection = !isOnQuizSection && hasContentSections ? contentSections[currentSectionIndex] : null;
  const isLastSection = currentSectionIndex === totalSections - 1;

  // Render section content
  const renderSectionContent = () => {
    // Render quiz section
    if (isOnQuizSection) {
      return (
        <LessonQuizSection
          lessonId={lesson.id}
          onStatusChange={setQuestionsStatus}
          onComplete={handleMarkComplete}
          isLessonCompleted={progress?.completed}
        />
      );
    }

    if (currentSection) {
      // Render section content
      return (
        <div className="animate-in fade-in slide-in-from-right-4 duration-300">
          {currentSection.title && (
            <h3 className="text-xl font-semibold mb-4">{currentSection.title}</h3>
          )}

          {currentSection.video_type === 'youtube' && currentSection.video_id && (
            <div className="mb-8">
              <VideoPlayer
                videoType="youtube"
                videoId={currentSection.video_id}
                initialPosition={currentSectionIndex === 0 ? (progress?.video_position || 0) : 0}
                onProgress={handleVideoProgress}
                onEnded={handleVideoEnded}
              />
            </div>
          )}

          {currentSection.content && (
            <Card>
              <CardContent className="prose prose-neutral dark:prose-invert max-w-none py-6">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {currentSection.content}
                </ReactMarkdown>
              </CardContent>
            </Card>
          )}

          {!currentSection.content && currentSection.video_type === 'none' && (
            <Card>
              <CardContent className="py-12 text-center text-muted-foreground">
                No content available for this section.
              </CardContent>
            </Card>
          )}
        </div>
      );
    }

    // Fallback: render lesson content directly (legacy lessons without sections)
    return (
      <>
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
      </>
    );
  };

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
                    to={`/courses/${code}/quizzes/${progress.required_quiz_info.id}`}
                    className="hover:underline"
                  >
                    Complete quiz "{progress.required_quiz_info.title}" to finish this lesson
                  </Link>
                </>
              )}
            </div>
          )}

          {/* Comprehension Questions Badge - only show when NOT on quiz section */}
          {questionsStatus && questionsStatus.total_questions > 0 && !progress?.completed && !isOnQuizSection && (
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
                  <button
                    onClick={() => handleSectionChange(totalSections - 1)}
                    className="hover:underline"
                  >
                    Go to Quiz
                  </button>
                </>
              )}
            </div>
          )}

          {/* Only show Mark Complete button if there's no quiz requirement and on last section */}
          {(!hasSections || isLastSection) && !progress?.required_quiz_info && (!questionsStatus || questionsStatus.total_questions === 0) && (
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

      {/* Section Content */}
      {renderSectionContent()}

      {/* Attachments - show on last content section or quiz section */}
      {(!hasContentSections || isOnQuizSection || (!hasQuiz && isLastSection)) && (
        <LessonAttachmentsList attachments={lesson.attachments || []} />
      )}

      {/* Section Navigation Footer */}
      {hasSections && (
        <div className="mt-8 pt-6 border-t flex items-center justify-between">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => handleSectionChange(currentSectionIndex - 1)}
            disabled={currentSectionIndex === 0}
            className="gap-1"
          >
            <ChevronLeft className="h-4 w-4" />
            Previous
          </Button>

          {/* Section indicators */}
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1.5">
              {/* Content section dots */}
              {contentSections.map((_, i) => (
                <button
                  key={i}
                  onClick={() => handleSectionChange(i)}
                  className={`w-2 h-2 rounded-full transition-all ${
                    i === currentSectionIndex
                      ? 'bg-primary w-3'
                      : i < currentSectionIndex
                        ? 'bg-primary/50'
                        : 'bg-muted-foreground/30 hover:bg-muted-foreground/50'
                  }`}
                  title={`Section ${i + 1}`}
                />
              ))}
              {/* Quiz section indicator */}
              {hasQuiz && (
                <button
                  onClick={() => handleSectionChange(totalSections - 1)}
                  className={`w-2 h-2 rounded-sm transition-all ${
                    isOnQuizSection
                      ? 'bg-amber-500 w-3'
                      : currentSectionIndex < totalSections - 1
                        ? 'bg-amber-500/30 hover:bg-amber-500/50'
                        : 'bg-amber-500/50'
                  }`}
                  title="Comprehension Check"
                />
              )}
            </div>
            <span className="text-xs text-muted-foreground">
              {currentSectionIndex + 1}/{totalSections}
            </span>
          </div>

          <Button
            variant="ghost"
            size="sm"
            onClick={() => handleSectionChange(currentSectionIndex + 1)}
            disabled={isLastSection}
            className="gap-1"
          >
            Next
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      )}
    </div>
  );
}

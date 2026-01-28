import { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useNavigate, Link } from 'react-router';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Button } from '@/components/ui/Button';
import { Card, CardContent } from '@/components/ui/Card';
import { CourseSidebar } from '@/components/course/CourseSidebar';
import { VideoPlayer } from '@/components/video/VideoPlayer';
import { courseService } from '@/services/courses';
import type { LessonProgress } from '@/types';
import {
  Loader2, ChevronLeft, ChevronRight, CheckCircle, Circle,
  ArrowLeft
} from 'lucide-react';

interface LessonDetail {
  id: number;
  title: string;
  content: string | null;
  video_type: 'none' | 'youtube' | 'vimeo';
  video_id: string | null;
  order: number;
  unit: number;
}

interface LessonWithProgress {
  id: number;
  title: string;
  content?: string;
  video_type: 'none' | 'youtube' | 'vimeo';
  video_id: string | null;
  order: number;
  is_completed?: boolean;
}

interface UnitWithProgress {
  id: number;
  title: string;
  order: number;
  course: number;
  lessons: LessonWithProgress[];
}

interface CourseWithProgress {
  id: number;
  code: string;
  title: string;
  description: string;
  instructor: {
    id: number;
    email: string;
    first_name: string;
    last_name: string;
  };
  is_active: boolean;
  units: UnitWithProgress[];
}

export function CoursePlayerPage() {
  const { code, lessonId } = useParams<{ code: string; lessonId?: string }>();
  const navigate = useNavigate();

  const [course, setCourse] = useState<CourseWithProgress | null>(null);
  const [currentLesson, setCurrentLesson] = useState<LessonDetail | null>(null);
  const [progress, setProgress] = useState<LessonProgress | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isLessonLoading, setIsLessonLoading] = useState(false);
  const [error, setError] = useState('');
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(() => {
    return localStorage.getItem('coursePlayerSidebarCollapsed') === 'true';
  });
  const [isMarkingComplete, setIsMarkingComplete] = useState(false);

  // Track last saved position to avoid unnecessary API calls
  const lastSavedPositionRef = useRef<number>(0);
  const isSavingRef = useRef(false);

  // Persist sidebar state
  useEffect(() => {
    localStorage.setItem('coursePlayerSidebarCollapsed', isSidebarCollapsed.toString());
  }, [isSidebarCollapsed]);

  const findFirstIncompleteLesson = useCallback((courseData: CourseWithProgress) => {
    for (const unit of courseData.units) {
      for (const lesson of unit.lessons) {
        if (!lesson.is_completed) {
          return lesson;
        }
      }
    }
    return null;
  }, []);

  const loadCourse = useCallback(async () => {
    if (!code) return;

    try {
      setIsLoading(true);
      const courseData = await courseService.getCourseWithProgress(code);
      setCourse(courseData);

      // If no lessonId in URL, navigate to first incomplete lesson or first lesson
      if (!lessonId && courseData.units.length > 0) {
        const firstIncompleteLesson = findFirstIncompleteLesson(courseData);
        const firstLesson = courseData.units[0]?.lessons[0];
        const targetLesson = firstIncompleteLesson || firstLesson;

        if (targetLesson) {
          navigate(`/courses/${code}/learn/${targetLesson.id}`, { replace: true });
        }
      }
    } catch (err: unknown) {
      const error = err as { response?: { status?: number } };
      if (error.response?.status === 403) {
        setError('You must be enrolled in this course to access it.');
      } else {
        setError('Failed to load course');
      }
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  }, [code, lessonId, navigate, findFirstIncompleteLesson]);

  const loadLesson = useCallback(async (id: number) => {
    try {
      setIsLessonLoading(true);
      const [lessonData, progressData] = await Promise.all([
        courseService.getLesson(id),
        courseService.getLessonProgress(id)
      ]);
      setCurrentLesson(lessonData);
      setProgress(progressData);
      lastSavedPositionRef.current = progressData?.video_position || 0;

      // Track course activity
      if (code) {
        courseService.updateCourseActivity(code).catch(() => {});
      }
    } catch (err) {
      console.error('Failed to load lesson:', err);
    } finally {
      setIsLessonLoading(false);
    }
  }, [code]);

  // Load course data
  useEffect(() => {
    if (code) {
      loadCourse();
    }
  }, [code, loadCourse]);

  // Load specific lesson when lessonId changes
  useEffect(() => {
    if (lessonId && course) {
      loadLesson(parseInt(lessonId));
    }
  }, [lessonId, course?.id, loadLesson]);

  const handleLessonSelect = useCallback((id: number) => {
    navigate(`/courses/${code}/learn/${id}`);
  }, [navigate, code]);

  const handleMarkComplete = async () => {
    if (!currentLesson || !progress) return;

    setIsMarkingComplete(true);
    try {
      const updated = await courseService.updateLessonProgress(currentLesson.id, {
        completed: !progress.completed
      });
      setProgress(updated);

      // Update course state to reflect new completion
      if (course) {
        setCourse({
          ...course,
          units: course.units.map(unit => ({
            ...unit,
            lessons: unit.lessons.map(lesson =>
              lesson.id === currentLesson.id
                ? { ...lesson, is_completed: updated.completed }
                : lesson
            )
          }))
        });
      }

      // Auto-advance if marking complete
      if (updated.completed) {
        const nextLesson = getNextLesson();
        if (nextLesson) {
          setTimeout(() => handleLessonSelect(nextLesson.id), 500);
        }
      }
    } catch (err) {
      console.error('Failed to update progress:', err);
    } finally {
      setIsMarkingComplete(false);
    }
  };

  const handleVideoProgress = useCallback(async (position: number, _duration: number) => {
    if (!currentLesson || isSavingRef.current) return;

    const positionDiff = Math.abs(position - lastSavedPositionRef.current);
    if (positionDiff < 5) return;

    isSavingRef.current = true;
    try {
      await courseService.updateLessonProgress(currentLesson.id, {
        video_position: Math.floor(position)
      });
      lastSavedPositionRef.current = position;
    } catch (err) {
      console.error('Failed to save video progress:', err);
    } finally {
      isSavingRef.current = false;
    }
  }, [currentLesson]);

  const handleVideoEnded = useCallback(async () => {
    if (!currentLesson || progress?.completed) return;

    try {
      const updated = await courseService.updateLessonProgress(currentLesson.id, {
        completed: true
      });
      setProgress(updated);

      // Update course state
      if (course) {
        setCourse({
          ...course,
          units: course.units.map(unit => ({
            ...unit,
            lessons: unit.lessons.map(lesson =>
              lesson.id === currentLesson.id
                ? { ...lesson, is_completed: true }
                : lesson
            )
          }))
        });
      }

      // Auto-advance to next lesson
      if (updated.completed) {
        const allLessons = course?.units.flatMap(u => u.lessons) || [];
        const currentIndex = allLessons.findIndex(l => l.id === currentLesson.id);
        const nextLesson = currentIndex < allLessons.length - 1 ? allLessons[currentIndex + 1] : null;
        if (nextLesson) {
          setTimeout(() => navigate(`/courses/${code}/learn/${nextLesson.id}`), 500);
        }
      }
    } catch (err) {
      console.error('Failed to mark lesson complete:', err);
    }
  }, [currentLesson, progress?.completed, course, code, navigate]);

  const getPreviousLesson = () => {
    if (!course || !currentLesson) return null;

    const allLessons = course.units.flatMap(u => u.lessons);
    const currentIndex = allLessons.findIndex(l => l.id === currentLesson.id);
    return currentIndex > 0 ? allLessons[currentIndex - 1] : null;
  };

  const getNextLesson = () => {
    if (!course || !currentLesson) return null;

    const allLessons = course.units.flatMap(u => u.lessons);
    const currentIndex = allLessons.findIndex(l => l.id === currentLesson.id);
    return currentIndex < allLessons.length - 1 ? allLessons[currentIndex + 1] : null;
  };

  const previousLesson = getPreviousLesson();
  const nextLesson = getNextLesson();

  // Calculate progress
  const completedCount = course?.units.reduce(
    (acc, unit) => acc + unit.lessons.filter(l => l.is_completed).length,
    0
  ) || 0;
  const totalCount = course?.units.reduce(
    (acc, unit) => acc + unit.lessons.length,
    0
  ) || 0;
  const progressPercentage = totalCount > 0 ? (completedCount / totalCount) * 100 : 0;

  // Keyboard navigation
  useEffect(() => {
    const handleKeyPress = (e: KeyboardEvent) => {
      // Don't trigger if user is typing in an input
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
        return;
      }

      if (e.key === 'ArrowLeft' && previousLesson) {
        handleLessonSelect(previousLesson.id);
      } else if (e.key === 'ArrowRight' && nextLesson) {
        handleLessonSelect(nextLesson.id);
      }
    };

    window.addEventListener('keydown', handleKeyPress);
    return () => window.removeEventListener('keydown', handleKeyPress);
  }, [previousLesson, nextLesson, handleLessonSelect]);

  if (isLoading) {
    return (
      <div className="h-screen flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (error || !course) {
    return (
      <div className="h-screen flex items-center justify-center">
        <Card className="max-w-md">
          <CardContent className="py-8 text-center">
            <p className="text-destructive mb-4">{error || 'Course not found'}</p>
            <Link to="/courses">
              <Button>Back to Courses</Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col bg-background">
      {/* Top bar */}
      <div className="h-14 border-b bg-card flex items-center px-4 gap-4">
        <Link
          to={`/courses/${code}`}
          className="flex items-center gap-2 text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
          <span className="hidden sm:inline">Exit</span>
        </Link>

        <div className="flex-1 min-w-0">
          <h1 className="font-semibold truncate">{course.title}</h1>
        </div>

        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <span className="hidden sm:inline">
            {completedCount}/{totalCount} complete
          </span>
          <div className="w-24 h-2 bg-muted rounded-full overflow-hidden">
            <div
              className="h-full bg-primary transition-all"
              style={{ width: `${progressPercentage}%` }}
            />
          </div>
        </div>
      </div>

      {/* Main content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Sidebar */}
        <CourseSidebar
          units={course.units}
          currentLessonId={currentLesson?.id || null}
          onLessonSelect={handleLessonSelect}
          isCollapsed={isSidebarCollapsed}
          onToggleCollapse={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
          progressPercentage={progressPercentage}
          completedCount={completedCount}
          totalCount={totalCount}
        />

        {/* Content area */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {isLessonLoading ? (
            <div className="flex-1 flex items-center justify-center">
              <Loader2 className="h-8 w-8 animate-spin text-primary" />
            </div>
          ) : currentLesson ? (
            <>
              {/* Lesson content */}
              <div className="flex-1 overflow-y-auto">
                <div className="max-w-4xl mx-auto p-6">
                  {/* Lesson header */}
                  <div className="mb-6">
                    <h2 className="text-2xl font-bold mb-2">{currentLesson.title}</h2>
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
                  </div>

                  {/* Video - currently only YouTube is supported */}
                  {currentLesson.video_type === 'youtube' && currentLesson.video_id && (
                    <div className="mb-8">
                      <VideoPlayer
                        videoType="youtube"
                        videoId={currentLesson.video_id}
                        initialPosition={progress?.video_position || 0}
                        onProgress={handleVideoProgress}
                        onEnded={handleVideoEnded}
                      />
                    </div>
                  )}

                  {/* Content */}
                  {currentLesson.content && (
                    <Card>
                      <CardContent className="prose prose-neutral dark:prose-invert max-w-none py-6">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                          {currentLesson.content}
                        </ReactMarkdown>
                      </CardContent>
                    </Card>
                  )}

                  {!currentLesson.content && currentLesson.video_type === 'none' && (
                    <Card>
                      <CardContent className="py-12 text-center text-muted-foreground">
                        No content available for this lesson.
                      </CardContent>
                    </Card>
                  )}
                </div>
              </div>

              {/* Navigation footer */}
              <div className="h-16 border-t bg-card flex items-center justify-between px-6">
                <Button
                  variant="outline"
                  onClick={() => previousLesson && handleLessonSelect(previousLesson.id)}
                  disabled={!previousLesson}
                >
                  <ChevronLeft className="h-4 w-4 mr-2" />
                  Previous
                </Button>

                <p className="text-sm text-muted-foreground hidden sm:block">
                  Use arrow keys ← → to navigate
                </p>

                <Button
                  onClick={() => nextLesson && handleLessonSelect(nextLesson.id)}
                  disabled={!nextLesson}
                >
                  Next
                  <ChevronRight className="h-4 w-4 ml-2" />
                </Button>
              </div>
            </>
          ) : (
            <div className="flex-1 flex items-center justify-center text-muted-foreground">
              Select a lesson to begin
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

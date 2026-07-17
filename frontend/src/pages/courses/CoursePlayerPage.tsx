import { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useNavigate, Link } from 'react-router';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Button } from '@/components/ui/Button';
import { Card, CardContent } from '@/components/ui/Card';
import { CourseSidebar } from '@/components/course/CourseSidebar';
import { VideoPlayer } from '@/components/video/VideoPlayer';
import { LessonQuizSection } from '@/components/lesson/LessonQuizSection';
import { LessonAttachmentsList } from '@/components/lesson/LessonAttachmentsList';
import { courseService } from '@/services/courses';
import { useAuth } from '@/contexts/AuthContext';
import type { LessonProgress, LessonQuestionsStatus, LessonAttachment, LessonSection } from '@/types';
import {
  Loader2, ChevronLeft, ChevronRight, CheckCircle, Circle, FileQuestion
} from 'lucide-react';

interface LessonDetail {
  id: number;
  title: string;
  content: string | null;
  video_type: 'none' | 'youtube' | 'vimeo';
  video_id: string | null;
  order: number;
  unit: number;
  attachments?: LessonAttachment[];
  sections?: LessonSection[];
  section_count?: number;
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
  const { user } = useAuth();

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
  const [questionsStatus, setQuestionsStatus] = useState<LessonQuestionsStatus | null>(null);

  // Section navigation state
  const [currentSectionIndex, setCurrentSectionIndex] = useState(0);

  // Check if current user is the instructor
  const isCourseOwner = course && user && course.instructor.id === user.id;

  // Ref to track current lesson for cleanup
  const currentLessonRef = useRef<number | null>(null);
  const isCourseOwnerRef = useRef(false);

  // Update refs when values change
  useEffect(() => {
    currentLessonRef.current = currentLesson?.id || null;
    isCourseOwnerRef.current = !!isCourseOwner;
  }, [currentLesson?.id, isCourseOwner]);

  // Reset instructor progress when leaving the lesson
  useEffect(() => {
    return () => {
      if (isCourseOwnerRef.current && currentLessonRef.current) {
        courseService.resetLessonProgress(currentLessonRef.current).catch(() => {
          // Silent fail - instructor might have navigated away quickly
        });
      }
    };
  }, []);

  // Track last saved position to avoid unnecessary API calls
  const lastSavedPositionRef = useRef<number>(0);
  const lastSavedSectionRef = useRef<number>(0);
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
      setQuestionsStatus(null); // Reset questions status when loading new lesson
      setCurrentSectionIndex(0); // Reset section index
      const [lessonData, progressData, quizStatusData] = await Promise.all([
        courseService.getLesson(id),
        courseService.getLessonProgress(id),
        courseService.getLessonQuestionsStatus(id).catch(() => null) // May not exist
      ]);
      setCurrentLesson(lessonData);
      setProgress(progressData);
      setQuestionsStatus(quizStatusData);
      lastSavedPositionRef.current = progressData?.video_position || 0;
      lastSavedSectionRef.current = progressData?.current_section || 0;

      // Calculate total sections for resume logic
      const contentSectionsCount = lessonData.sections?.length || 0;
      const hasQuizSection = quizStatusData && quizStatusData.total_questions > 0;
      const maxSectionIndex = contentSectionsCount + (hasQuizSection ? 1 : 0) - 1;

      // Resume at saved section
      if (progressData?.current_section !== undefined) {
        const savedSection = progressData.current_section;
        if (savedSection <= maxSectionIndex) {
          setCurrentSectionIndex(savedSection);
        }
      }

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

  // Handle section navigation
  const handleSectionChange = useCallback(async (newIndex: number) => {
    if (!currentLesson || isSavingRef.current) return;

    // Calculate total sections (content + quiz if present)
    const contentSectionsCount = currentLesson.sections?.length || 0;
    const hasQuizSection = questionsStatus && questionsStatus.total_questions > 0;
    const maxIndex = contentSectionsCount + (hasQuizSection ? 1 : 0) - 1;

    if (newIndex < 0 || newIndex > maxIndex) return;

    setCurrentSectionIndex(newIndex);

    // Save section progress (debounced to avoid too many API calls)
    if (newIndex !== lastSavedSectionRef.current) {
      isSavingRef.current = true;
      try {
        await courseService.updateLessonProgress(currentLesson.id, {
          current_section: newIndex
        });
        lastSavedSectionRef.current = newIndex;
      } catch (err) {
        console.error('Failed to save section progress:', err);
      } finally {
        isSavingRef.current = false;
      }
    }
  }, [currentLesson, questionsStatus]);

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

  const handleVideoProgress = useCallback(async (position: number) => {
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

    // If there are more sections, don't auto-complete the lesson
    const sections = currentLesson.sections || [];
    if (sections.length > 1 && currentSectionIndex < sections.length - 1) {
      // Just move to next section
      handleSectionChange(currentSectionIndex + 1);
      return;
    }

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
  }, [currentLesson, progress?.completed, course, code, navigate, currentSectionIndex, handleSectionChange]);

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

  // Get current section data
  const contentSections = currentLesson?.sections || [];
  const hasContentSections = contentSections.length > 0;
  const hasQuiz = questionsStatus && questionsStatus.total_questions > 0;

  // Total sections = content sections + quiz section (if exists)
  const totalSections = hasContentSections
    ? contentSections.length + (hasQuiz ? 1 : 0)
    : (hasQuiz ? 1 : 0);
  const hasSections = totalSections > 1;

  // Determine if we're on the quiz section (last section when quiz exists)
  const isOnQuizSection = hasQuiz && currentSectionIndex === totalSections - 1;
  const currentSection = !isOnQuizSection && hasContentSections ? contentSections[currentSectionIndex] : null;
  const isLastSection = currentSectionIndex === totalSections - 1;

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

      if (e.key === 'ArrowLeft') {
        // If we have sections and not at first section, go to previous section
        if (hasSections && currentSectionIndex > 0) {
          handleSectionChange(currentSectionIndex - 1);
        } else if (previousLesson) {
          handleLessonSelect(previousLesson.id);
        }
      } else if (e.key === 'ArrowRight') {
        // If we have sections and not at last section, go to next section
        if (hasSections && currentSectionIndex < totalSections - 1) {
          handleSectionChange(currentSectionIndex + 1);
        } else if (nextLesson) {
          handleLessonSelect(nextLesson.id);
        }
      }
    };

    window.addEventListener('keydown', handleKeyPress);
    return () => window.removeEventListener('keydown', handleKeyPress);
  }, [previousLesson, nextLesson, handleLessonSelect, hasSections, currentSectionIndex, totalSections, handleSectionChange]);

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

  // Render section content
  const renderSectionContent = () => {
    // Render quiz section
    if (isOnQuizSection && currentLesson) {
      return (
        <LessonQuizSection
          lessonId={currentLesson.id}
          onStatusChange={setQuestionsStatus}
          onComplete={handleMarkComplete}
          isLessonCompleted={progress?.completed}
        />
      );
    }

    if (!currentSection) {
      // Fallback: render lesson content directly (legacy lessons without sections)
      return (
        <>
          {/* Video - currently only YouTube is supported */}
          {currentLesson?.video_type === 'youtube' && currentLesson.video_id && (
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
          {currentLesson?.content && (
            <Card>
              <CardContent className="prose prose-neutral dark:prose-invert max-w-none py-6">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {currentLesson.content}
                </ReactMarkdown>
              </CardContent>
            </Card>
          )}

          {!currentLesson?.content && currentLesson?.video_type === 'none' && (
            <Card>
              <CardContent className="py-12 text-center text-muted-foreground">
                No content available for this lesson.
              </CardContent>
            </Card>
          )}
        </>
      );
    }

    // Render section content
    return (
      <div className="animate-in fade-in slide-in-from-right-4 duration-300">
        {/* Section title */}
        {currentSection.title && (
          <h3 className="text-xl font-semibold mb-4">{currentSection.title}</h3>
        )}

        {/* Section video */}
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

        {/* Section content */}
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
  };

  return (
    <div className="h-screen flex flex-col bg-background animate-in fade-in duration-300">
      {/* Learning Mode Header */}
      <div className="h-14 border-b bg-card/95 backdrop-blur supports-[backdrop-filter]:bg-card/80 flex items-center px-4 gap-4">
        {/* Exit Learning Mode */}
        <Link to={`/courses/${code}`}>
          <Button
            variant="outline"
            size="sm"
            className="gap-2 border-primary/50 text-primary hover:bg-primary hover:text-primary-foreground transition-colors"
          >
            <ChevronLeft className="h-4 w-4" />
            <span className="hidden sm:inline">Exit</span>
          </Button>
        </Link>

        {/* Course Title */}
        <div className="flex-1 min-w-0 text-center">
          <h1 className="font-semibold truncate text-sm sm:text-base">{course.title}</h1>
        </div>

        {/* Progress */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 text-sm">
            <span className="text-muted-foreground hidden sm:inline">
              {completedCount}/{totalCount}
            </span>
            <div className="w-20 sm:w-28 h-2 bg-muted rounded-full overflow-hidden">
              <div
                className="h-full bg-primary transition-all duration-300"
                style={{ width: `${progressPercentage}%` }}
              />
            </div>
            <span className="text-xs font-medium text-primary">{Math.round(progressPercentage)}%</span>
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

                    {/* Section title (only show if section has a title) */}
                    {hasSections && totalSections > 1 && currentSection?.title && (
                      <p className="text-sm text-muted-foreground mb-2">
                        {currentSection.title}
                      </p>
                    )}

                    {/* Quiz requirement badge */}
                    {progress?.required_quiz_info && !progress?.completed && (
                      <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg mb-3 ${
                        progress?.required_quiz_passed
                          ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400'
                          : 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400'
                      }`}>
                        {progress?.required_quiz_passed ? (
                          <>
                            <CheckCircle className="h-4 w-4" />
                            <span className="text-sm font-medium">Quiz passed - Ready to complete</span>
                          </>
                        ) : (
                          <>
                            <FileQuestion className="h-4 w-4" />
                            <span className="text-sm font-medium">
                              Complete quiz "{progress.required_quiz_info.title}" to finish this lesson
                            </span>
                            <Link
                              to={`/courses/${code}/quizzes/${progress.required_quiz_info.id}`}
                              className="text-sm underline hover:no-underline ml-1"
                            >
                              Take Quiz →
                            </Link>
                          </>
                        )}
                      </div>
                    )}

                    {/* Lesson questions requirement badge - only show when NOT on quiz section */}
                    {questionsStatus && questionsStatus.total_questions > 0 && !progress?.completed && !isOnQuizSection && (
                      <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg mb-3 ${
                        questionsStatus.can_complete_lesson
                          ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400'
                          : 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400'
                      }`}>
                        {questionsStatus.can_complete_lesson ? (
                          <>
                            <CheckCircle className="h-4 w-4" />
                            <span className="text-sm font-medium">Quiz passed - Ready to mark complete</span>
                          </>
                        ) : (
                          <>
                            <FileQuestion className="h-4 w-4" />
                            <span className="text-sm font-medium">
                              Complete the comprehension quiz to finish this lesson
                            </span>
                            <button
                              onClick={() => handleSectionChange(totalSections - 1)}
                              className="text-sm underline hover:no-underline ml-1"
                            >
                              Go to Quiz →
                            </button>
                          </>
                        )}
                      </div>
                    )}

                    {/* Only show Mark Complete button if there's no quiz requirement and on last section */}
                    {(!hasSections || isLastSection) && !progress?.required_quiz_info && (!questionsStatus || questionsStatus.total_questions === 0) && (
                      <div className="flex items-center gap-3">
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
                    )}

                    {/* Show completion status when there IS a quiz requirement */}
                    {(progress?.required_quiz_info || (questionsStatus && questionsStatus.total_questions > 0)) && progress?.completed && (
                      <div className="flex items-center gap-2 text-green-600 dark:text-green-400">
                        <CheckCircle className="h-5 w-5" />
                        <span className="font-medium">Lesson Completed</span>
                      </div>
                    )}
                  </div>

                  {/* Section/Lesson content */}
                  {renderSectionContent()}

                  {/* Attachments - show on last content section or quiz section */}
                  {(!hasContentSections || isOnQuizSection || (!hasQuiz && isLastSection)) && (
                    <LessonAttachmentsList attachments={currentLesson.attachments || []} />
                  )}
                </div>
              </div>

              {/* Navigation footer */}
              <div className="h-14 border-t bg-card flex items-center justify-between px-4 sm:px-6">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    if (hasSections && currentSectionIndex > 0) {
                      handleSectionChange(currentSectionIndex - 1);
                    } else if (previousLesson) {
                      handleLessonSelect(previousLesson.id);
                    }
                  }}
                  disabled={!previousLesson && currentSectionIndex === 0}
                  className="gap-1"
                >
                  <ChevronLeft className="h-4 w-4" />
                  <span className="hidden sm:inline">Previous</span>
                </Button>

                {/* Section indicators */}
                <div className="flex items-center gap-2">
                  {hasSections && totalSections > 1 ? (
                    <>
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
                    </>
                  ) : (
                    <span className="text-xs text-muted-foreground hidden sm:block">
                      ← → to navigate
                    </span>
                  )}
                </div>

                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    if (hasSections && currentSectionIndex < totalSections - 1) {
                      handleSectionChange(currentSectionIndex + 1);
                    } else if (nextLesson) {
                      handleLessonSelect(nextLesson.id);
                    }
                  }}
                  disabled={!nextLesson && isLastSection}
                  className="gap-1"
                >
                  <span className="hidden sm:inline">Next</span>
                  <ChevronRight className="h-4 w-4" />
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

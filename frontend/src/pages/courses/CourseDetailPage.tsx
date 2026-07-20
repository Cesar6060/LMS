import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router';
import { useAuth } from '@/contexts/AuthContext';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { courseService, type CourseDetail, type AnnouncementListItem } from '@/services/courses';
import { quizzesService } from '@/services/quizzes';
import type { Quiz } from '@/types';
import {
  BookOpen, Users, ChevronRight, Play, FileText,
  Lock, CheckCircle, Settings, Megaphone, Pin,
  FileQuestion, Trophy, XCircle, MessageSquare
} from 'lucide-react';
import { EnrollmentModal } from '@/components/course/EnrollmentModal';
import { StudentGradeCard } from '@/components/course/StudentGradeCard';
import { Skeleton } from '@/components/ui/Skeleton';
import { PageContainer } from '@/components/layout/PageContainer';

interface CourseProgress {
  total_lessons: number;
  completed_lessons: number;
  progress_percentage: number;
}

interface NextLessonInfo {
  lessonId: number;
  lessonTitle: string;
  unitTitle: string;
  unitNumber: number;
  lessonNumber: number;
}

interface UnitProgress {
  unitId: number;
  unitTitle: string;
  totalLessons: number;
  completedLessons: number;
  isComplete: boolean;
}

export function CourseDetailPage() {
  const { code } = useParams<{ code: string }>();
  const { user } = useAuth();

  const [course, setCourse] = useState<CourseDetail | null>(null);
  const [progress, setProgress] = useState<CourseProgress | null>(null);
  const [announcements, setAnnouncements] = useState<AnnouncementListItem[]>([]);
  const [quizzes, setQuizzes] = useState<Quiz[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [showEnrollModal, setShowEnrollModal] = useState(false);
  const [descriptionExpanded, setDescriptionExpanded] = useState(false);

  const isCourseOwner = user?.id === course?.instructor.id;
  const isEnrolled = course?.is_enrolled || false;
  const canAccessContent = isCourseOwner || isEnrolled;

  // Compute next lesson for enrolled students
  const getNextLesson = (): NextLessonInfo | null => {
    if (!course || !isEnrolled || isCourseOwner) return null;

    // For now, we'll compute this from the course structure
    // The first incomplete lesson or the first lesson if none completed
    for (let unitIdx = 0; unitIdx < course.units.length; unitIdx++) {
      const unit = course.units[unitIdx];
      for (let lessonIdx = 0; lessonIdx < unit.lessons.length; lessonIdx++) {
        const lesson = unit.lessons[lessonIdx];
        // Check if this lesson is completed (would need progress data per lesson)
        // For now, use overall progress to estimate
        const estimatedCompleted = progress && progress.total_lessons > 0
          ? Math.floor((progress.completed_lessons / progress.total_lessons) * course.units.reduce((sum, u) => sum + u.lessons.length, 0))
          : 0;
        const currentLessonIndex = course.units.slice(0, unitIdx).reduce((sum, u) => sum + u.lessons.length, 0) + lessonIdx;

        if (currentLessonIndex >= estimatedCompleted) {
          return {
            lessonId: lesson.id,
            lessonTitle: lesson.title,
            unitTitle: unit.title,
            unitNumber: unitIdx + 1,
            lessonNumber: lessonIdx + 1,
          };
        }
      }
    }

    // All completed, return first lesson
    if (course.units.length > 0 && course.units[0].lessons.length > 0) {
      return {
        lessonId: course.units[0].lessons[0].id,
        lessonTitle: course.units[0].lessons[0].title,
        unitTitle: course.units[0].title,
        unitNumber: 1,
        lessonNumber: 1,
      };
    }

    return null;
  };

  // Compute unit progress for timeline
  const getUnitProgress = (): UnitProgress[] => {
    if (!course || !progress) return [];

    const totalLessons = course.units.reduce((sum, u) => sum + u.lessons.length, 0);
    if (totalLessons === 0) return [];

    let completedSoFar = 0;
    const lessonsPerUnit = course.units.map(u => u.lessons.length);

    return course.units.map((unit, idx) => {
      const unitLessons = unit.lessons.length;
      // Estimate completion based on overall progress
      const estimatedUnitCompleted = Math.min(
        unitLessons,
        Math.max(0, progress.completed_lessons - completedSoFar)
      );
      completedSoFar += lessonsPerUnit[idx];

      return {
        unitId: unit.id,
        unitTitle: unit.title,
        totalLessons: unitLessons,
        completedLessons: estimatedUnitCompleted,
        isComplete: estimatedUnitCompleted >= unitLessons,
      };
    });
  };

  const nextLesson = getNextLesson();
  const unitProgress = getUnitProgress();

  useEffect(() => {
    if (code) {
      loadCourse();
    }
  }, [code]);

  const loadCourse = async () => {
    try {
      setIsLoading(true);
      const data = await courseService.getCourse(code!);
      setCourse(data);

      // Load progress, announcements, and quizzes if enrolled or instructor
      if (data.is_enrolled || user?.id === data.instructor.id) {
        try {
          const [progressData, announcementsData, quizzesData] = await Promise.all([
            courseService.getCourseProgress(code!),
            courseService.getCourseAnnouncements(code!),
            quizzesService.getCourseQuizzes(code!),
          ]);
          setProgress(progressData);
          setAnnouncements(announcementsData);
          setQuizzes(quizzesData);
        } catch {
          // Progress/announcements/quizzes might not exist yet
        }

        // Track activity for enrolled students (not instructors)
        if (data.is_enrolled && user?.id !== data.instructor.id) {
          courseService.updateCourseActivity(code!).catch(() => {
            // Silent fail for activity tracking
          });
        }
      }
    } catch (err) {
      setError('Failed to load course');
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  if (isLoading) {
    return (
      <PageContainer>
        {/* Header skeleton */}
        <div className="mb-8">
          <Skeleton className="h-4 w-20 mb-2" />
          <Skeleton className="h-9 w-80 mb-2" />
          <Skeleton className="h-5 w-full max-w-2xl" />
          <div className="flex items-center gap-6 mt-4">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-4 w-20" />
            <Skeleton className="h-4 w-32" />
          </div>
        </div>

        {/* Progress card skeleton */}
        <div className="rounded-lg border bg-card p-4 mb-6">
          <div className="flex items-center justify-between">
            <div>
              <Skeleton className="h-5 w-28 mb-1" />
              <Skeleton className="h-4 w-48" />
            </div>
            <div className="text-right">
              <Skeleton className="h-8 w-12 ml-auto" />
              <Skeleton className="h-2 w-40 mt-2" />
            </div>
          </div>
        </div>

        {/* Units skeleton */}
        <div className="space-y-4">
          <Skeleton className="h-7 w-36" />
          {[1, 2, 3].map((i) => (
            <div key={i} className="rounded-lg border bg-card p-6">
              <Skeleton className="h-6 w-48 mb-4" />
              <div className="space-y-3">
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
              </div>
            </div>
          ))}
        </div>
      </PageContainer>
    );
  }

  if (error || !course) {
    return (
      <PageContainer>
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <BookOpen className="h-12 w-12 text-muted-foreground mb-4" />
            <h3 className="text-lg font-semibold mb-2">Course not found</h3>
            <p className="text-muted-foreground mb-4">{error || 'The course you are looking for does not exist.'}</p>
            <Link to="/courses">
              <Button>Back to Courses</Button>
            </Link>
          </CardContent>
        </Card>
      </PageContainer>
    );
  }

  return (
    <PageContainer>
      {/* Course Header */}
      <div className="mb-8">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-sm font-mono text-muted-foreground mb-1">{course.code}</p>
            <h1 className="text-3xl font-bold mb-2">{course.title}</h1>
            {course.description && (() => {
              const cleanDesc = course.description
                .replace(/#{1,6}\s?/g, '')
                .replace(/\*\*/g, '')
                .replace(/[-•]\s/g, '')
                .replace(/\n+/g, ' ')
                .trim();
              const isLong = cleanDesc.length > 150;
              return (
                <p className="text-muted-foreground max-w-2xl">
                  {!isLong || descriptionExpanded ? cleanDesc : cleanDesc.slice(0, 150) + '... '}
                  {isLong && (
                    <button
                      onClick={() => setDescriptionExpanded(!descriptionExpanded)}
                      className="text-primary hover:underline"
                    >
                      {descriptionExpanded ? 'Show less' : 'Read more'}
                    </button>
                  )}
                </p>
              );
            })()}
          </div>
          {isCourseOwner && (
            <Link to={`/instructor/courses/${course.code}/manage`}>
              <Button variant="outline">
                <Settings className="h-4 w-4 mr-2" />
                Manage Course
              </Button>
            </Link>
          )}
        </div>

        <div className="flex items-center gap-6 mt-4 text-sm text-muted-foreground">
          <div className="flex items-center gap-2">
            <Users className="h-4 w-4" />
            {course.student_count} students
          </div>
          <div className="flex items-center gap-2">
            <BookOpen className="h-4 w-4" />
            {course.units.length} units
          </div>
          <div>
            Instructor: {course.instructor.first_name} {course.instructor.last_name}
          </div>
        </div>

        {!canAccessContent && (
          <div className="mt-6">
            <Button onClick={() => setShowEnrollModal(true)}>
              Enroll in this Course
            </Button>
          </div>
        )}

        {isEnrolled && !isCourseOwner && (
          <div className="mt-4 flex items-center gap-2 text-green-600">
            <CheckCircle className="h-4 w-4" />
            <span className="text-sm font-medium">Enrolled</span>
          </div>
        )}
      </div>

      {/* Hero Learning CTA (for enrolled students) */}
      {isEnrolled && !isCourseOwner && course.units.length > 0 && (
        <div className="mb-8 rounded-2xl bg-gradient-to-br from-primary/10 via-primary/5 to-transparent border border-primary/20 p-8">
          <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-6">
            <div className="flex-1">
              <p className="text-sm font-medium text-primary mb-2">
                {progress && progress.completed_lessons > 0 ? 'Continue Learning' : 'Start Learning'}
              </p>
              <h2 className="text-2xl font-bold mb-2">
                {nextLesson
                  ? `Unit ${nextLesson.unitNumber}: ${nextLesson.unitTitle}`
                  : 'Begin Your Journey'}
              </h2>
              {nextLesson && (
                <p className="text-muted-foreground mb-4">
                  Next up: {nextLesson.lessonNumber}. {nextLesson.lessonTitle}
                </p>
              )}
              <Link to={`/courses/${course.code}/map`}>
                <Button size="lg" className="gap-2 bg-green-600 text-white hover:bg-green-700">
                  <Play className="h-5 w-5" />
                  Continue Learning
                </Button>
              </Link>
            </div>

            {/* Progress circle */}
            {progress && progress.total_lessons > 0 && (
              <div className="flex flex-col items-center">
                <div className="relative w-32 h-32">
                  <svg className="w-full h-full -rotate-90" viewBox="0 0 100 100">
                    <circle
                      cx="50"
                      cy="50"
                      r="40"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="8"
                      className="text-muted-foreground/20"
                    />
                    <circle
                      cx="50"
                      cy="50"
                      r="40"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="8"
                      strokeLinecap="round"
                      strokeDasharray={`${progress.progress_percentage * 2.51} 251`}
                      className="text-green-500 transition-all duration-500"
                    />
                  </svg>
                  <div className="absolute inset-0 flex flex-col items-center justify-center">
                    <span className="text-3xl font-bold text-green-500">{progress.progress_percentage}%</span>
                    <span className="text-xs text-muted-foreground">complete</span>
                  </div>
                </div>
                <p className="text-sm text-muted-foreground mt-2">
                  {progress.completed_lessons} of {progress.total_lessons} lessons
                </p>
              </div>
            )}
          </div>

          {/* Unit Progress Timeline */}
          {unitProgress.length > 1 && (
            <div className="mt-8 pt-6 border-t border-primary/10">
              <p className="text-sm font-medium text-muted-foreground mb-4">Course Progress</p>
              <div className="flex items-center gap-2">
                {unitProgress.map((unit, idx) => (
                  <div key={unit.unitId} className="flex items-center flex-1">
                    {/* Unit milestone */}
                    <Link
                      to={`/courses/${course.code}/learn`}
                      className="flex flex-col items-center group"
                    >
                      <div
                        className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium transition-all ${
                          unit.isComplete
                            ? 'bg-green-600 text-white'
                            : unit.completedLessons > 0
                            ? 'bg-green-600/20 text-green-500 border-2 border-green-600'
                            : 'bg-muted text-muted-foreground'
                        } group-hover:scale-110`}
                      >
                        {unit.isComplete ? (
                          <CheckCircle className="h-4 w-4" />
                        ) : (
                          idx + 1
                        )}
                      </div>
                      <span className="text-xs text-muted-foreground mt-1 max-w-16 truncate text-center hidden sm:block">
                        {unit.unitTitle}
                      </span>
                    </Link>
                    {/* Connector line */}
                    {idx < unitProgress.length - 1 && (
                      <div className="flex-1 h-1 mx-2 rounded-full bg-muted-foreground/20 overflow-hidden">
                        <div
                          className="h-full bg-green-600 transition-all duration-500"
                          style={{
                            width: unit.isComplete ? '100%' : unit.totalLessons > 0 ? `${(unit.completedLessons / unit.totalLessons) * 100}%` : '0%',
                          }}
                        />
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Show grade summary for enrolled students */}
      {canAccessContent && !isCourseOwner && (
        <div className="mb-6">
          <StudentGradeCard courseCode={course.code} />
        </div>
      )}

      {/* Announcements Section */}
      {canAccessContent && (
        <div className="mb-8">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-semibold flex items-center gap-2">
              <Megaphone className="h-5 w-5" />
              Announcements
            </h2>
            <Link to={`/courses/${course.code}/announcements`}>
              <Button variant="link" className="text-sm">
                {isCourseOwner ? 'Manage Announcements' : 'View All'}
                <ChevronRight className="h-4 w-4 ml-1" />
              </Button>
            </Link>
          </div>

          {announcements.length > 0 ? (
            <Card>
              <CardContent className="pt-6">
                <ul className="divide-y">
                  {announcements.slice(0, 3).map((announcement) => (
                    <li key={announcement.id}>
                      <Link
                        to={`/courses/${course.code}/announcements/${announcement.id}?from=course`}
                        className="flex items-center justify-between py-3 hover:bg-muted/50 -mx-6 px-6 transition-colors"
                      >
                        <div className="flex items-center gap-3">
                          {announcement.is_pinned ? (
                            <Pin className="h-4 w-4 text-primary" />
                          ) : (
                            <Megaphone className="h-4 w-4 text-muted-foreground" />
                          )}
                          <div>
                            <span className="font-medium">{announcement.title}</span>
                            <div className="text-sm text-muted-foreground">
                              {announcement.author_name} • {new Date(announcement.created_at).toLocaleDateString()}
                            </div>
                          </div>
                        </div>
                        <ChevronRight className="h-4 w-4 text-muted-foreground" />
                      </Link>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardContent className="py-8 text-center text-muted-foreground">
                {isCourseOwner ? (
                  <>
                    No announcements yet.{' '}
                    <Link to={`/courses/${course.code}/announcements`} className="text-primary hover:underline">
                      Create one
                    </Link>
                  </>
                ) : (
                  'No announcements yet.'
                )}
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* Discussions Section */}
      {canAccessContent && (
        <div className="mb-8">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-semibold flex items-center gap-2">
              <MessageSquare className="h-5 w-5" />
              Discussions
            </h2>
            <Link to={`/courses/${course.code}/discussions`}>
              <Button variant="link" className="text-sm">
                {isCourseOwner ? 'Manage Discussions' : 'View All'}
                <ChevronRight className="h-4 w-4 ml-1" />
              </Button>
            </Link>
          </div>

          <Card>
            <CardContent className="py-8 text-center text-muted-foreground">
              Ask questions and help your classmates.{' '}
              <Link to={`/courses/${course.code}/discussions`} className="text-primary hover:underline">
                Open discussions
              </Link>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Course Content */}
      <div className="space-y-4">
        <h2 className="text-xl font-semibold">Course Content</h2>

        {course.units.length === 0 ? (
          <Card>
            <CardContent className="py-8 text-center text-muted-foreground">
              No content available yet.
            </CardContent>
          </Card>
        ) : (
          course.units.map((unit, unitIndex) => (
            <Card key={unit.id}>
              <CardHeader className="pb-3">
                <CardTitle className="text-lg">
                  Unit {unitIndex + 1}: {unit.title}
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-0">
                {unit.lessons.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No lessons in this unit.</p>
                ) : (
                  <ul className="divide-y">
                    {unit.lessons.map((lesson, lessonIndex) => (
                      <li key={lesson.id}>
                        {canAccessContent ? (
                          <Link
                            to={`/courses/${course.code}/learn/${lesson.id}`}
                            className="flex items-center justify-between py-3 hover:bg-muted/50 -mx-6 px-6 transition-colors"
                          >
                            <div className="flex items-center gap-3">
                              {lesson.video_type !== 'none' ? (
                                <Play className="h-4 w-4 text-muted-foreground" />
                              ) : (
                                <FileText className="h-4 w-4 text-muted-foreground" />
                              )}
                              <span>
                                {unitIndex + 1}.{lessonIndex + 1} {lesson.title}
                              </span>
                            </div>
                            <ChevronRight className="h-4 w-4 text-muted-foreground" />
                          </Link>
                        ) : (
                          <div className="flex items-center justify-between py-3 text-muted-foreground">
                            <div className="flex items-center gap-3">
                              <Lock className="h-4 w-4" />
                              <span>
                                {unitIndex + 1}.{lessonIndex + 1} {lesson.title}
                              </span>
                            </div>
                          </div>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>
          ))
        )}
      </div>

      {/* Quizzes Section */}
      {canAccessContent && quizzes.length > 0 && (
        <div className="mt-8 space-y-4">
          <h2 className="text-xl font-semibold flex items-center gap-2">
            <FileQuestion className="h-5 w-5" />
            Quizzes
          </h2>

          <Card>
            <CardContent className="pt-6">
              <ul className="divide-y">
                {quizzes.map((quiz) => (
                  <li key={quiz.id}>
                    <Link
                      to={`/courses/${code}/quizzes/${quiz.id}`}
                      className="flex items-center justify-between py-3 hover:bg-muted/50 -mx-6 px-6 transition-colors"
                    >
                      <div className="flex items-center gap-3">
                        <FileQuestion className="h-4 w-4 text-muted-foreground" />
                        <div>
                          <span className="font-medium">{quiz.title}</span>
                          <div className="text-sm text-muted-foreground">
                            {quiz.unit_title} • {quiz.question_count} questions • {quiz.points} pts
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-4">
                        {quiz.best_score && (
                          <span
                            className={`text-xs px-2 py-1 rounded flex items-center gap-1 ${
                              quiz.best_score.passed
                                ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                                : 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
                            }`}
                          >
                            {quiz.best_score.passed ? (
                              <Trophy className="h-3 w-3" />
                            ) : (
                              <XCircle className="h-3 w-3" />
                            )}
                            {quiz.best_score.score}%
                          </span>
                        )}
                        <ChevronRight className="h-4 w-4 text-muted-foreground" />
                      </div>
                    </Link>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        </div>
      )}

      <EnrollmentModal
        open={showEnrollModal}
        onOpenChange={setShowEnrollModal}
        onSuccess={() => {
          setShowEnrollModal(false);
          loadCourse();
        }}
      />
    </PageContainer>
  );
}

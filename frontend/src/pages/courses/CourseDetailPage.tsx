import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router';
import { useAuth } from '@/contexts/AuthContext';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { courseService, type CourseDetail, type AnnouncementListItem } from '@/services/courses';
import { assignmentService } from '@/services/assignments';
import { quizzesService } from '@/services/quizzes';
import type { AssignmentListItem, Quiz } from '@/types';
import {
  BookOpen, Users, ChevronRight, Play, FileText,
  Lock, CheckCircle, Settings, ClipboardList, Calendar, Megaphone, Pin,
  FileQuestion, Trophy, XCircle
} from 'lucide-react';
import { EnrollmentModal } from '@/components/course/EnrollmentModal';
import { StudentGradeCard } from '@/components/course/StudentGradeCard';
import { Skeleton } from '@/components/ui/Skeleton';

interface CourseProgress {
  total_lessons: number;
  completed_lessons: number;
  progress_percentage: number;
}

export function CourseDetailPage() {
  const { code } = useParams<{ code: string }>();
  const { user } = useAuth();

  const [course, setCourse] = useState<CourseDetail | null>(null);
  const [progress, setProgress] = useState<CourseProgress | null>(null);
  const [assignments, setAssignments] = useState<AssignmentListItem[]>([]);
  const [announcements, setAnnouncements] = useState<AnnouncementListItem[]>([]);
  const [quizzes, setQuizzes] = useState<Quiz[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [showEnrollModal, setShowEnrollModal] = useState(false);

  const isInstructor = user?.id === course?.instructor.id;
  const isEnrolled = course?.is_enrolled || false;
  const canAccessContent = isInstructor || isEnrolled;

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

      // Load progress, assignments, announcements, and quizzes if enrolled or instructor
      if (data.is_enrolled || user?.id === data.instructor.id) {
        try {
          const [progressData, assignmentsData, announcementsData, quizzesData] = await Promise.all([
            courseService.getCourseProgress(code!),
            assignmentService.getCourseAssignments(code!),
            courseService.getCourseAnnouncements(code!),
            quizzesService.getCourseQuizzes(code!),
          ]);
          setProgress(progressData);
          setAssignments(assignmentsData);
          setAnnouncements(announcementsData);
          setQuizzes(quizzesData);
        } catch {
          // Progress/assignments/announcements/quizzes might not exist yet
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
      <div className="container mx-auto px-4 py-8">
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
      </div>
    );
  }

  if (error || !course) {
    return (
      <div className="container mx-auto px-4 py-8">
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
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      {/* Course Header */}
      <div className="mb-8">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-sm font-mono text-muted-foreground mb-1">{course.code}</p>
            <h1 className="text-3xl font-bold mb-2">{course.title}</h1>
            <p className="text-muted-foreground max-w-2xl">{course.description}</p>
          </div>
          {isInstructor && (
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

        {isEnrolled && !isInstructor && (
          <div className="mt-4 flex items-center gap-4">
            <div className="flex items-center gap-2 text-green-600">
              <CheckCircle className="h-4 w-4" />
              <span className="text-sm font-medium">You are enrolled in this course</span>
            </div>
            {progress && progress.total_lessons > 0 && (
              <div className="flex items-center gap-2">
                <div className="w-32 h-2 bg-muted rounded-full overflow-hidden">
                  <div
                    className="h-full bg-primary transition-all duration-300"
                    style={{ width: `${progress.progress_percentage}%` }}
                  />
                </div>
                <span className="text-sm text-muted-foreground">
                  {progress.progress_percentage}% complete
                </span>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Progress Summary Card (for enrolled users) */}
      {canAccessContent && progress && progress.total_lessons > 0 && (
        <Card className="mb-6">
          <CardContent className="py-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="font-semibold">Your Progress</h3>
                <p className="text-sm text-muted-foreground">
                  {progress.completed_lessons} of {progress.total_lessons} lessons completed
                </p>
              </div>
              <div className="text-right">
                <div className="text-2xl font-bold text-primary">
                  {progress.progress_percentage}%
                </div>
                <div className="w-40 h-2 bg-muted rounded-full overflow-hidden mt-1">
                  <div
                    className="h-full bg-primary transition-all duration-300"
                    style={{ width: `${progress.progress_percentage}%` }}
                  />
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Show grade summary for enrolled students */}
      {canAccessContent && !isInstructor && (
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
                {isInstructor ? 'Manage Announcements' : 'View All'}
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
                        to={`/courses/${course.code}/announcements/${announcement.id}`}
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
                {isInstructor ? (
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
                            to={`/courses/${course.code}/lessons/${lesson.id}`}
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

      {/* Assignments Section */}
      {canAccessContent && assignments.length > 0 && (
        <div className="mt-8 space-y-4">
          <h2 className="text-xl font-semibold flex items-center gap-2">
            <ClipboardList className="h-5 w-5" />
            Assignments
          </h2>

          <Card>
            <CardContent className="pt-6">
              <ul className="divide-y">
                {assignments.map((assignment) => (
                  <li key={assignment.id}>
                    <Link
                      to={`/assignments/${assignment.id}`}
                      className="flex items-center justify-between py-3 hover:bg-muted/50 -mx-6 px-6 transition-colors"
                    >
                      <div className="flex items-center gap-3">
                        <ClipboardList className="h-4 w-4 text-muted-foreground" />
                        <div>
                          <span className="font-medium">{assignment.title}</span>
                          <div className="text-sm text-muted-foreground">
                            {assignment.unit_title} • {assignment.max_points} pts
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-4">
                        {assignment.due_date && (
                          <div className="text-sm text-muted-foreground flex items-center gap-1">
                            <Calendar className="h-3 w-3" />
                            {new Date(assignment.due_date).toLocaleDateString()}
                          </div>
                        )}
                        {assignment.submission_status && (
                          <span
                            className={`text-xs px-2 py-1 rounded ${
                              assignment.submission_status.status === 'graded'
                                ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                                : assignment.submission_status.status === 'submitted'
                                ? 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200'
                                : 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200'
                            }`}
                          >
                            {assignment.submission_status.status === 'graded'
                              ? `${assignment.submission_status.grade}/${assignment.max_points}`
                              : assignment.submission_status.status}
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
                      to={`/quizzes/${quiz.id}`}
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
    </div>
  );
}

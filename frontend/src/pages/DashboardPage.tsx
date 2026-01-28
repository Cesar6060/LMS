import { useState, useEffect } from 'react';
import { Link } from 'react-router';
import { useAuth } from '@/contexts/AuthContext';
import { Button } from '@/components/ui/Button';
import { courseService, type InstructorCourse } from '@/services/courses';
import type { Enrollment, EnhancedDashboard } from '@/types';
import { Plus, Play, BookOpen, Users, CheckCircle2 } from 'lucide-react';
import { EnrollmentModal } from '@/components/course/EnrollmentModal';
import { Skeleton } from '@/components/ui/Skeleton';

export function DashboardPage() {
  const { user } = useAuth();
  const [enrolledCourses, setEnrolledCourses] = useState<Enrollment[]>([]);
  const [instructorCourses, setInstructorCourses] = useState<InstructorCourse[]>([]);
  const [enhancedData, setEnhancedData] = useState<EnhancedDashboard | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [showEnrollModal, setShowEnrollModal] = useState(false);

  useEffect(() => {
    loadData();
  }, [user]);

  const loadData = async () => {
    if (!user) return;
    try {
      setIsLoading(true);
      const [enhanced] = await Promise.all([
        courseService.getEnhancedDashboard(),
        user.is_instructor
          ? courseService.getInstructorCourses().then(setInstructorCourses)
          : courseService.getMyEnrollments().then(setEnrolledCourses)
      ]);
      setEnhancedData(enhanced);
    } catch (err) {
      console.error('Failed to load dashboard data:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const isInstructor = user?.is_instructor;
  const courses = isInstructor ? instructorCourses : enrolledCourses;
  const hasCourses = courses.length > 0;

  // Calculate stats for students from enhanced data
  const courseProgress = enhancedData && !enhancedData.is_instructor
    ? enhancedData.course_progress_overview
    : [];
  const totalLessons = courseProgress.reduce((sum, course) => sum + course.lessons.total, 0);
  const completedLessons = courseProgress.reduce((sum, course) => sum + course.lessons.completed, 0);

  // Get continue learning data from enhanced dashboard
  const continueLearning = enhancedData && !enhancedData.is_instructor ? enhancedData.continue_learning : null;

  if (isLoading) {
    return (
      <div className="container mx-auto px-4 py-8 max-w-6xl">
        <Skeleton className="h-44 rounded-xl mb-6" />
        <div className="grid grid-cols-3 gap-4 mb-8">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-24 rounded-lg" />
          ))}
        </div>
        <Skeleton className="h-6 w-32 mb-4" />
        <div className="space-y-3">
          {[1, 2].map((i) => (
            <Skeleton key={i} className="h-20 rounded-lg" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8 max-w-6xl">
      {/* Hero: Continue Learning */}
      {hasCourses && !isInstructor && (
        <div className="bg-gradient-to-r from-primary/10 via-primary/5 to-transparent rounded-xl p-8 mb-6">
          <p className="text-sm font-medium text-primary mb-3">Continue Learning</p>
          {continueLearning ? (
            <>
              <h2 className="text-2xl font-semibold mb-2">{continueLearning.course_title}</h2>
              <p className="text-muted-foreground mb-5">
                {continueLearning.current_lesson
                  ? `${continueLearning.current_lesson.unit_title} · ${continueLearning.current_lesson.title}`
                  : 'Start your first lesson'}
              </p>
              <div className="flex items-center gap-4">
                <Link to={`/courses/${continueLearning.course_code}/learn`}>
                  <Button size="lg">
                    <Play className="h-4 w-4 mr-2" />
                    Continue
                  </Button>
                </Link>
                <span className="text-muted-foreground">
                  {continueLearning.progress_percentage}% complete
                </span>
              </div>
            </>
          ) : (
            <>
              <h2 className="text-2xl font-semibold mb-2">Pick up where you left off</h2>
              <p className="text-muted-foreground mb-5">
                Select a course below to start learning
              </p>
            </>
          )}
        </div>
      )}

      {/* Instructor Hero */}
      {hasCourses && isInstructor && (
        <div className="bg-gradient-to-r from-primary/10 via-primary/5 to-transparent rounded-xl p-8 mb-6">
          <p className="text-sm font-medium text-primary mb-3">Welcome back</p>
          <h2 className="text-2xl font-semibold mb-2">Manage your courses</h2>
          <p className="text-muted-foreground mb-5">
            {instructorCourses.length} active course{instructorCourses.length !== 1 ? 's' : ''}
          </p>
          <Link to="/instructor/courses/new">
            <Button size="lg">
              <Plus className="h-4 w-4 mr-2" />
              Create Course
            </Button>
          </Link>
        </div>
      )}

      {/* Quick Stats */}
      {hasCourses && (
        <div className="grid grid-cols-3 gap-5 mb-8">
          <div className="bg-card border rounded-xl p-5">
            <div className="flex items-center gap-2 text-muted-foreground mb-2">
              <BookOpen className="h-5 w-5" />
              <span className="text-sm font-medium">Courses</span>
            </div>
            <p className="text-3xl font-semibold">{courses.length}</p>
          </div>
          {isInstructor ? (
            <>
              <div className="bg-card border rounded-xl p-5">
                <div className="flex items-center gap-2 text-muted-foreground mb-2">
                  <Users className="h-5 w-5" />
                  <span className="text-sm font-medium">Students</span>
                </div>
                <p className="text-3xl font-semibold">
                  {instructorCourses.reduce((sum, c) => sum + c.student_count, 0)}
                </p>
              </div>
              <div className="bg-card border rounded-xl p-5">
                <div className="flex items-center gap-2 text-muted-foreground mb-2">
                  <CheckCircle2 className="h-5 w-5" />
                  <span className="text-sm font-medium">Active</span>
                </div>
                <p className="text-3xl font-semibold">
                  {instructorCourses.filter((c) => c.student_count > 0).length}
                </p>
              </div>
            </>
          ) : (
            <>
              <div className="bg-card border rounded-xl p-5">
                <div className="flex items-center gap-2 text-muted-foreground mb-2">
                  <CheckCircle2 className="h-5 w-5" />
                  <span className="text-sm font-medium">Completed</span>
                </div>
                <p className="text-3xl font-semibold">{completedLessons}</p>
              </div>
              <div className="bg-card border rounded-xl p-5">
                <div className="flex items-center gap-2 text-muted-foreground mb-2">
                  <BookOpen className="h-5 w-5" />
                  <span className="text-sm font-medium">Lessons</span>
                </div>
                <p className="text-3xl font-semibold">{totalLessons}</p>
              </div>
            </>
          )}
        </div>
      )}

      {/* Course List Header */}
      <div className="flex items-center justify-between mb-5">
        <h2 className="text-xl font-semibold">
          {isInstructor ? 'Your Courses' : 'Enrolled Courses'}
        </h2>
        {hasCourses && (
          isInstructor ? (
            <Link to="/instructor/courses/new">
              <Button variant="outline">
                <Plus className="h-4 w-4 mr-2" />
                New Course
              </Button>
            </Link>
          ) : (
            <Button variant="outline" onClick={() => setShowEnrollModal(true)}>
              <Plus className="h-4 w-4 mr-2" />
              Join Course
            </Button>
          )
        )}
      </div>

      {/* Course List */}
      {!hasCourses ? (
        <div className="text-center py-20 border rounded-xl bg-muted/20">
          <BookOpen className="h-16 w-16 text-muted-foreground/30 mx-auto mb-4" />
          <p className="text-lg text-muted-foreground mb-5">
            {isInstructor ? 'No courses yet' : 'No courses enrolled'}
          </p>
          {isInstructor ? (
            <Link to="/instructor/courses/new">
              <Button size="lg">
                <Plus className="h-4 w-4 mr-2" />
                Create Your First Course
              </Button>
            </Link>
          ) : (
            <Button size="lg" onClick={() => setShowEnrollModal(true)}>
              <Plus className="h-4 w-4 mr-2" />
              Join Your First Course
            </Button>
          )}
        </div>
      ) : (
        <div className="space-y-4">
          {isInstructor
            ? instructorCourses.map((course) => (
                <Link
                  key={course.id}
                  to={`/courses/${course.code}`}
                  className="flex items-center justify-between p-5 bg-card border rounded-xl hover:border-primary/50 transition-colors"
                >
                  <div>
                    <h3 className="text-lg font-medium">{course.title}</h3>
                    <p className="text-muted-foreground">
                      {course.code} · {course.student_count} student{course.student_count !== 1 ? 's' : ''}
                    </p>
                  </div>
                  <Button variant="outline">
                    Manage
                  </Button>
                </Link>
              ))
            : enrolledCourses.map((enrollment) => (
                <Link
                  key={enrollment.id}
                  to={`/courses/${enrollment.course.code}`}
                  className="flex items-center justify-between p-5 bg-card border rounded-xl hover:border-primary/50 transition-colors"
                >
                  <div>
                    <h3 className="text-lg font-medium">{enrollment.course.title}</h3>
                    <p className="text-muted-foreground">
                      {enrollment.course.code} · {enrollment.course.instructor.first_name} {enrollment.course.instructor.last_name}
                    </p>
                  </div>
                  <Button variant="outline">
                    <Play className="h-4 w-4 mr-2" />
                    Learn
                  </Button>
                </Link>
              ))}
        </div>
      )}

      {/* Enrollment Modal */}
      {!isInstructor && (
        <EnrollmentModal
          open={showEnrollModal}
          onOpenChange={setShowEnrollModal}
          onSuccess={() => {
            setShowEnrollModal(false);
            loadData();
          }}
        />
      )}
    </div>
  );
}

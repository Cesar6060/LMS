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
        <div className="relative rounded-xl p-8 mb-6 overflow-hidden border border-[#22c55e]/20" style={{ background: 'linear-gradient(135deg, rgba(34, 197, 94, 0.1) 0%, rgba(6, 182, 212, 0.05) 50%, transparent 100%)' }}>
          <div className="absolute inset-0 bg-grid opacity-30" />
          <div className="relative">
            <p className="text-sm font-medium mb-3" style={{ color: '#22c55e', fontFamily: 'Orbitron, sans-serif' }}>Continue Learning</p>
          {continueLearning ? (
            <>
              <h2 className="text-2xl font-semibold mb-2">{continueLearning.course_title}</h2>
              <p className="text-muted-foreground mb-5">
                {continueLearning.current_lesson
                  ? `${continueLearning.current_lesson.unit_title} · ${continueLearning.current_lesson.title}`
                  : 'Start your first lesson'}
              </p>
              <div className="flex items-center gap-4 mb-4">
                <Link to={`/courses/${continueLearning.course_code}/learn`}>
                  <Button size="lg" variant="neon">
                    <Play className="h-4 w-4 mr-2" />
                    Continue
                  </Button>
                </Link>
              </div>
              {/* Progress Bar */}
              <div className="max-w-md">
                <div className="progress-gaming">
                  <div
                    className="progress-gaming-bar"
                    style={{ width: `${continueLearning.progress_percentage}%` }}
                  />
                </div>
                <p className="text-sm text-muted-foreground mt-2">
                  {continueLearning.progress_percentage}% complete
                </p>
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
        </div>
      )}

      {/* Instructor Hero */}
      {hasCourses && isInstructor && (
        <div className="relative rounded-xl p-8 mb-6 overflow-hidden border border-[#06b6d4]/20" style={{ background: 'linear-gradient(135deg, rgba(6, 182, 212, 0.1) 0%, rgba(34, 197, 94, 0.05) 50%, transparent 100%)' }}>
          <div className="absolute inset-0 bg-grid opacity-30" />
          <div className="relative">
            <p className="text-sm font-medium mb-3" style={{ color: '#06b6d4', fontFamily: 'Orbitron, sans-serif' }}>Welcome back</p>
            <h2 className="text-2xl font-semibold mb-2">Manage your courses</h2>
            <p className="text-muted-foreground mb-5">
              {instructorCourses.length} active course{instructorCourses.length !== 1 ? 's' : ''}
            </p>
            <Link to="/instructor/courses/new">
              <Button size="lg" variant="neon">
                <Plus className="h-4 w-4 mr-2" />
                Create Course
              </Button>
            </Link>
          </div>
        </div>
      )}

      {/* Quick Stats */}
      {hasCourses && (
        <div className="grid grid-cols-3 gap-5 mb-8">
          <div className="card-gaming rounded-xl p-5">
            <div className="flex items-center gap-2 text-muted-foreground mb-2">
              <BookOpen className="h-5 w-5" style={{ color: '#22c55e' }} />
              <span className="text-sm font-medium">Courses</span>
            </div>
            <p className="text-3xl font-semibold text-gradient-gaming">{courses.length}</p>
          </div>
          {isInstructor ? (
            <>
              <div className="card-gaming rounded-xl p-5">
                <div className="flex items-center gap-2 text-muted-foreground mb-2">
                  <Users className="h-5 w-5" style={{ color: '#06b6d4' }} />
                  <span className="text-sm font-medium">Students</span>
                </div>
                <p className="text-3xl font-semibold text-gradient-gaming">
                  {instructorCourses.reduce((sum, c) => sum + c.student_count, 0)}
                </p>
              </div>
              <div className="card-gaming rounded-xl p-5">
                <div className="flex items-center gap-2 text-muted-foreground mb-2">
                  <CheckCircle2 className="h-5 w-5" style={{ color: '#fbbf24' }} />
                  <span className="text-sm font-medium">Active</span>
                </div>
                <p className="text-3xl font-semibold text-gradient-gaming">
                  {instructorCourses.filter((c) => c.student_count > 0).length}
                </p>
              </div>
            </>
          ) : (
            <>
              <div className="card-gaming rounded-xl p-5">
                <div className="flex items-center gap-2 text-muted-foreground mb-2">
                  <CheckCircle2 className="h-5 w-5" style={{ color: '#06b6d4' }} />
                  <span className="text-sm font-medium">Completed</span>
                </div>
                <p className="text-3xl font-semibold text-gradient-gaming">{completedLessons}</p>
              </div>
              <div className="card-gaming rounded-xl p-5">
                <div className="flex items-center gap-2 text-muted-foreground mb-2">
                  <BookOpen className="h-5 w-5" style={{ color: '#fbbf24' }} />
                  <span className="text-sm font-medium">Lessons</span>
                </div>
                <p className="text-3xl font-semibold text-gradient-gaming">{totalLessons}</p>
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
        <div className="text-center py-20 card-gaming bg-grid">
          <BookOpen className="h-16 w-16 mx-auto mb-4" style={{ color: 'rgba(34, 197, 94, 0.3)' }} />
          <p className="text-lg text-muted-foreground mb-5">
            {isInstructor ? 'No courses yet' : 'No courses enrolled'}
          </p>
          {isInstructor ? (
            <Link to="/instructor/courses/new">
              <Button size="lg" variant="neon">
                <Plus className="h-4 w-4 mr-2" />
                Create Your First Course
              </Button>
            </Link>
          ) : (
            <Button size="lg" variant="neon" onClick={() => setShowEnrollModal(true)}>
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
                  className="flex items-center justify-between p-5 card-gaming"
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
                  className="flex items-center justify-between p-5 card-gaming"
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

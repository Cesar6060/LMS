import { useState, useEffect } from 'react';
import { Link } from 'react-router';
import { useAuth } from '@/contexts/AuthContext';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { courseService, type InstructorCourse } from '@/services/courses';
import type { Enrollment } from '@/types';
import {
  Gamepad2, BookOpen, GraduationCap, Users, Plus, ChevronRight
} from 'lucide-react';
import { EnrollmentModal } from '@/components/course/EnrollmentModal';
import { Skeleton, SkeletonStatCard, SkeletonCard } from '@/components/ui/Skeleton';

interface DashboardStats {
  pending_grades?: number;
  total_students?: number;
  lessons_completed?: number;
  assignments_due?: number;
  course_count: number;
}

export function DashboardPage() {
  const { user } = useAuth();
  const [enrolledCourses, setEnrolledCourses] = useState<Enrollment[]>([]);
  const [instructorCourses, setInstructorCourses] = useState<InstructorCourse[]>([]);
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [showEnrollModal, setShowEnrollModal] = useState(false);

  useEffect(() => {
    loadData();
  }, [user]);

  const loadData = async () => {
    if (!user) return;

    try {
      setIsLoading(true);
      const [statsData] = await Promise.all([
        courseService.getDashboardStats(),
        user.is_instructor
          ? courseService.getInstructorCourses().then(setInstructorCourses)
          : courseService.getMyEnrollments().then(setEnrolledCourses)
      ]);
      setStats(statsData);
    } catch (err) {
      console.error('Failed to load dashboard data:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const totalStudents = instructorCourses.reduce((sum, course) => sum + course.student_count, 0);

  if (isLoading) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="mb-8">
          <Skeleton className="h-9 w-64 mb-2" />
          <Skeleton className="h-5 w-80" />
        </div>
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3 mb-8">
          <SkeletonStatCard />
          <SkeletonStatCard />
          <SkeletonStatCard />
        </div>
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <Skeleton className="h-7 w-32" />
            <Skeleton className="h-10 w-36" />
          </div>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            <SkeletonCard />
            <SkeletonCard />
            <SkeletonCard />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold">
          Welcome back, {user?.first_name || user?.email?.split('@')[0]}!
        </h1>
        <p className="text-muted-foreground mt-2">
          {user?.is_instructor
            ? 'Manage your courses and track student progress'
            : 'Continue your learning journey'}
        </p>
      </div>

      {user?.is_instructor ? (
        // Instructor Dashboard
        <>
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3 mb-8">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">My Courses</CardTitle>
                <BookOpen className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{instructorCourses.length}</div>
                <p className="text-xs text-muted-foreground">
                  Courses you're teaching
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Total Students</CardTitle>
                <Users className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{totalStudents}</div>
                <p className="text-xs text-muted-foreground">
                  Across all your courses
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Pending Grades</CardTitle>
                <GraduationCap className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{stats?.pending_grades ?? 0}</div>
                <p className="text-xs text-muted-foreground">
                  Submissions to review
                </p>
              </CardContent>
            </Card>
          </div>

          {/* My Courses Section */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-semibold">My Courses</h2>
              <Link to="/instructor/courses/new">
                <Button>
                  <Plus className="h-4 w-4 mr-2" />
                  Create Course
                </Button>
              </Link>
            </div>

            {instructorCourses.length === 0 ? (
              <Card>
                <CardContent className="flex flex-col items-center justify-center py-12">
                  <BookOpen className="h-12 w-12 text-muted-foreground mb-4" />
                  <h3 className="text-lg font-semibold mb-2">No courses yet</h3>
                  <p className="text-muted-foreground text-center mb-4">
                    Create your first course to get started
                  </p>
                  <Link to="/instructor/courses/new">
                    <Button>
                      <Plus className="h-4 w-4 mr-2" />
                      Create Course
                    </Button>
                  </Link>
                </CardContent>
              </Card>
            ) : (
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {instructorCourses.map((course) => (
                  <Link key={course.id} to={`/courses/${course.code}`}>
                    <Card className="h-full hover:shadow-lg transition-shadow cursor-pointer">
                      <CardHeader>
                        <span className="text-sm font-mono text-muted-foreground">
                          {course.code}
                        </span>
                        <CardTitle className="line-clamp-2">{course.title}</CardTitle>
                      </CardHeader>
                      <CardContent className="flex items-center justify-between text-sm text-muted-foreground">
                        <div className="flex items-center gap-1">
                          <Users className="h-4 w-4" />
                          {course.student_count} students
                        </div>
                        <ChevronRight className="h-4 w-4" />
                      </CardContent>
                    </Card>
                  </Link>
                ))}
              </div>
            )}
          </div>
        </>
      ) : (
        // Student Dashboard
        <>
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3 mb-8">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Enrolled Courses</CardTitle>
                <BookOpen className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{enrolledCourses.length}</div>
                <p className="text-xs text-muted-foreground">
                  Active enrollments
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Lessons Completed</CardTitle>
                <GraduationCap className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{stats?.lessons_completed ?? 0}</div>
                <p className="text-xs text-muted-foreground">
                  Keep up the great work!
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Assignments Due</CardTitle>
                <Gamepad2 className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{stats?.assignments_due ?? 0}</div>
                <p className="text-xs text-muted-foreground">
                  In the next 7 days
                </p>
              </CardContent>
            </Card>
          </div>

          {/* My Courses Section */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-semibold">My Courses</h2>
              <Button onClick={() => setShowEnrollModal(true)}>
                <Plus className="h-4 w-4 mr-2" />
                Enroll with Code
              </Button>
            </div>

            {enrolledCourses.length === 0 ? (
              <Card>
                <CardContent className="flex flex-col items-center justify-center py-12">
                  <BookOpen className="h-12 w-12 text-muted-foreground mb-4" />
                  <h3 className="text-lg font-semibold mb-2">No courses yet</h3>
                  <p className="text-muted-foreground text-center mb-4">
                    Enroll in a course to begin learning
                  </p>
                  <Button onClick={() => setShowEnrollModal(true)}>
                    <Plus className="h-4 w-4 mr-2" />
                    Enroll with Code
                  </Button>
                </CardContent>
              </Card>
            ) : (
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {enrolledCourses.map((enrollment) => (
                  <Link key={enrollment.id} to={`/courses/${enrollment.course.code}`}>
                    <Card className="h-full hover:shadow-lg transition-shadow cursor-pointer">
                      <CardHeader>
                        <span className="text-sm font-mono text-muted-foreground">
                          {enrollment.course.code}
                        </span>
                        <CardTitle className="line-clamp-2">{enrollment.course.title}</CardTitle>
                        <CardDescription className="line-clamp-2">
                          {enrollment.course.description || 'No description'}
                        </CardDescription>
                      </CardHeader>
                      <CardContent className="flex items-center justify-between text-sm text-muted-foreground">
                        <span>
                          {enrollment.course.instructor.first_name} {enrollment.course.instructor.last_name}
                        </span>
                        <ChevronRight className="h-4 w-4" />
                      </CardContent>
                    </Card>
                  </Link>
                ))}
              </div>
            )}
          </div>

          <EnrollmentModal
            open={showEnrollModal}
            onOpenChange={setShowEnrollModal}
            onSuccess={() => {
              setShowEnrollModal(false);
              loadData();
            }}
          />
        </>
      )}
    </div>
  );
}

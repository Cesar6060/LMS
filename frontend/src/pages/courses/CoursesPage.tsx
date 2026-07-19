import { useState, useEffect } from 'react';
import { Link } from 'react-router';
import { useAuth } from '@/contexts/AuthContext';
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { courseService, type CourseListItem } from '@/services/courses';
import { Search, BookOpen, Users, Layers, Plus } from 'lucide-react';
import { EnrollmentModal } from '@/components/course/EnrollmentModal';
import { Skeleton, SkeletonCard } from '@/components/ui/Skeleton';
import { PageContainer } from '@/components/layout/PageContainer';

export function CoursesPage() {
  const { user } = useAuth();
  const [courses, setCourses] = useState<CourseListItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [showEnrollModal, setShowEnrollModal] = useState(false);

  useEffect(() => {
    loadCourses();
  }, []);

  const loadCourses = async () => {
    try {
      setIsLoading(true);
      const data = await courseService.listCourses();
      setCourses(data);
    } catch (err) {
      setError('Failed to load courses');
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  const filteredCourses = courses.filter(course =>
    course.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
    course.code.toLowerCase().includes(searchQuery.toLowerCase()) ||
    course.description.toLowerCase().includes(searchQuery.toLowerCase())
  );

  if (isLoading) {
    return (
      <PageContainer>
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-8">
          <div>
            <Skeleton className="h-9 w-32 mb-2" />
            <Skeleton className="h-5 w-64" />
          </div>
          <Skeleton className="h-10 w-40" />
        </div>
        <Skeleton className="h-10 w-full mb-6" />
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
        </div>
      </PageContainer>
    );
  }

  return (
    <PageContainer>
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-8">
        <div>
          <h1 className="text-3xl font-bold">
            {user?.is_instructor ? 'All Courses' : 'My Courses'}
          </h1>
          <p className="text-muted-foreground mt-1">
            {user?.is_instructor
              ? 'Browse all courses on the platform'
              : 'Courses you are enrolled in'}
          </p>
        </div>
        <div className="flex gap-2">
          {!user?.is_instructor && (
            <Button onClick={() => setShowEnrollModal(true)}>
              <Plus className="h-4 w-4 mr-2" />
              Enroll with Code
            </Button>
          )}
          {user?.is_instructor && (
            <Link to="/instructor/courses/new">
              <Button>
                <Plus className="h-4 w-4 mr-2" />
                Create Course
              </Button>
            </Link>
          )}
        </div>
      </div>

      <div className="relative mb-6">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          type="text"
          placeholder="Search courses..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="pl-10"
        />
      </div>

      {error && (
        <div className="rounded-md bg-destructive/15 p-4 text-destructive mb-6">
          {error}
        </div>
      )}

      {filteredCourses.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <BookOpen className="h-12 w-12 text-muted-foreground mb-4" />
            <h3 className="text-lg font-semibold mb-2">No courses found</h3>
            <p className="text-muted-foreground text-center mb-4">
              {searchQuery
                ? 'Try adjusting your search query'
                : user?.is_instructor
                  ? 'No courses are available yet'
                  : 'You are not enrolled in any courses yet'}
            </p>
            {!user?.is_instructor && !searchQuery && (
              <Button onClick={() => setShowEnrollModal(true)}>
                <Plus className="h-4 w-4 mr-2" />
                Enroll with Code
              </Button>
            )}
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {filteredCourses.map((course) => (
            <Link key={course.id} to={`/courses/${course.code}`}>
              <Card className="card-interactive h-full hover:border-primary/40 hover:shadow-lg transition-shadow cursor-pointer">
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-mono text-muted-foreground">
                      {course.code}
                    </span>
                  </div>
                  <CardTitle className="line-clamp-2">{course.title}</CardTitle>
                  <CardDescription className="line-clamp-2">
                    {course.description || 'No description'}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground">
                    Instructor: {course.instructor_name}
                  </p>
                </CardContent>
                <CardFooter className="flex gap-4 text-sm text-muted-foreground">
                  <div className="flex items-center gap-1">
                    <Layers className="h-4 w-4" />
                    {course.unit_count} units
                  </div>
                  <div className="flex items-center gap-1">
                    <Users className="h-4 w-4" />
                    {course.student_count} students
                  </div>
                </CardFooter>
              </Card>
            </Link>
          ))}
        </div>
      )}

      <EnrollmentModal
        open={showEnrollModal}
        onOpenChange={setShowEnrollModal}
        onSuccess={() => {
          setShowEnrollModal(false);
          loadCourses();
        }}
      />
    </PageContainer>
  );
}

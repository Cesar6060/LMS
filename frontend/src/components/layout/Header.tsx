import { useState, useEffect, useRef } from 'react';
import { Link, useNavigate, useLocation } from 'react-router';
import { LogOut, User, Gamepad2, Settings, GraduationCap, ChevronDown, ChevronRight } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { Button } from '@/components/ui/Button';
import { NotificationBell } from '@/components/notifications/NotificationBell';
import { courseService } from '@/services/courses';
import type { Enrollment } from '@/types';

export function Header() {
  const { user, logout, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [enrolledCourses, setEnrolledCourses] = useState<Enrollment[]>([]);
  const [gradesOpen, setGradesOpen] = useState(false);
  const gradesRef = useRef<HTMLDivElement>(null);

  // Load enrolled courses for grades dropdown (students only)
  useEffect(() => {
    if (isAuthenticated && user && !user.is_instructor) {
      courseService.getMyEnrollments().then(setEnrolledCourses).catch(console.error);
    } else {
      setEnrolledCourses([]);
    }
  }, [isAuthenticated, user]);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (gradesRef.current && !gradesRef.current.contains(event.target as Node)) {
        setGradesOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  // Generate breadcrumbs based on current path
  const getBreadcrumbs = () => {
    const path = location.pathname;
    const breadcrumbs: { label: string; href?: string }[] = [];

    // Match course-related routes
    const courseMatch = path.match(/\/courses\/([^/]+)/);
    if (courseMatch) {
      const courseCode = courseMatch[1];
      breadcrumbs.push({ label: 'Dashboard', href: '/dashboard' });
      breadcrumbs.push({ label: 'Courses', href: '/courses' });
      breadcrumbs.push({ label: courseCode.toUpperCase(), href: `/courses/${courseCode}` });

      // Add sub-page context
      if (path.includes('/grades')) {
        breadcrumbs.push({ label: 'Grades' });
      } else if (path.includes('/assignments')) {
        breadcrumbs.push({ label: 'Assignments' });
      } else if (path.includes('/quizzes')) {
        breadcrumbs.push({ label: 'Quizzes' });
      } else if (path.includes('/learn')) {
        breadcrumbs.push({ label: 'Learning' });
      }
    }

    return breadcrumbs;
  };

  const breadcrumbs = getBreadcrumbs();

  return (
    <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container mx-auto flex h-14 items-center px-4">
        <Link to="/" className="flex items-center space-x-2">
          <Gamepad2 className="h-6 w-6" />
          <span className="font-bold">GameDev Platform</span>
        </Link>

        {/* Breadcrumbs */}
        {breadcrumbs.length > 0 && (
          <nav className="hidden md:flex items-center ml-6 text-sm">
            {breadcrumbs.map((crumb, index) => (
              <span key={index} className="flex items-center">
                {index > 0 && <ChevronRight className="h-4 w-4 mx-1 text-muted-foreground" />}
                {crumb.href ? (
                  <Link to={crumb.href} className="text-muted-foreground hover:text-foreground transition-colors">
                    {crumb.label}
                  </Link>
                ) : (
                  <span className="text-foreground font-medium">{crumb.label}</span>
                )}
              </span>
            ))}
          </nav>
        )}

        <nav className="ml-auto flex items-center space-x-4">
          {isAuthenticated ? (
            <>
              <Link to="/dashboard">
                <Button variant="ghost" size="sm">
                  Dashboard
                </Button>
              </Link>
              <Link to="/courses">
                <Button variant="ghost" size="sm">
                  Courses
                </Button>
              </Link>
              {/* Grades Dropdown (Students only) */}
              {!user?.is_instructor && enrolledCourses.length > 0 && (
                <div className="relative" ref={gradesRef}>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setGradesOpen(!gradesOpen)}
                    className="flex items-center gap-1"
                  >
                    <GraduationCap className="h-4 w-4" />
                    Grades
                    <ChevronDown className={`h-3 w-3 transition-transform ${gradesOpen ? 'rotate-180' : ''}`} />
                  </Button>
                  {gradesOpen && (
                    <div className="absolute top-full right-0 mt-1 w-64 bg-popover border rounded-lg shadow-lg py-1 z-50">
                      <div className="px-3 py-2 text-xs font-medium text-muted-foreground border-b">
                        View grades by course
                      </div>
                      {enrolledCourses.map((enrollment) => (
                        <Link
                          key={enrollment.id}
                          to={`/courses/${enrollment.course.code}/grades`}
                          onClick={() => setGradesOpen(false)}
                          className="flex items-center justify-between px-3 py-2 hover:bg-muted transition-colors"
                        >
                          <div className="min-w-0">
                            <div className="font-medium truncate">{enrollment.course.title}</div>
                            <div className="text-xs text-muted-foreground">{enrollment.course.code}</div>
                          </div>
                          <ChevronRight className="h-4 w-4 text-muted-foreground shrink-0" />
                        </Link>
                      ))}
                    </div>
                  )}
                </div>
              )}
              <NotificationBell />
              <div className="flex items-center space-x-2 text-sm text-muted-foreground">
                {user?.preferences?.avatar_url ? (
                  <img
                    src={user.preferences.avatar_url}
                    alt="Avatar"
                    className="h-6 w-6 rounded-full object-cover"
                  />
                ) : (
                  <User className="h-4 w-4" />
                )}
                <span>{user?.first_name || user?.email}</span>
                {user?.is_instructor && (
                  <span className="rounded-full bg-primary px-2 py-0.5 text-xs text-primary-foreground">
                    Instructor
                  </span>
                )}
              </div>
              <Link to="/settings">
                <Button variant="ghost" size="sm" title="Settings">
                  <Settings className="h-4 w-4" />
                </Button>
              </Link>
              <Button variant="ghost" size="sm" onClick={handleLogout}>
                <LogOut className="h-4 w-4 mr-2" />
                Logout
              </Button>
            </>
          ) : (
            <>
              <Link to="/login">
                <Button variant="ghost" size="sm">
                  Login
                </Button>
              </Link>
              <Link to="/register">
                <Button size="sm">Register</Button>
              </Link>
            </>
          )}
        </nav>
      </div>
    </header>
  );
}

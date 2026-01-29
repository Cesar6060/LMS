import { useState, useEffect, useRef } from 'react';
import { Link, useNavigate, useLocation } from 'react-router';
import { LogOut, User, Gamepad2, Settings, ChevronDown, ChevronRight } from 'lucide-react';
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
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const userMenuRef = useRef<HTMLDivElement>(null);

  // Load enrolled courses for grades in user menu (students only)
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
      if (userMenuRef.current && !userMenuRef.current.contains(event.target as Node)) {
        setUserMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleLogout = async () => {
    setUserMenuOpen(false);
    await logout();
    navigate('/login');
  };

  // Get breadcrumb info based on current path
  const getBreadcrumbInfo = () => {
    const path = location.pathname;
    const parts: { label: string; href?: string }[] = [];

    // Course-related routes
    const courseMatch = path.match(/\/courses\/([^/]+)/);
    if (courseMatch) {
      const courseCode = courseMatch[1].toUpperCase();
      parts.push({ label: courseCode, href: `/courses/${courseMatch[1]}` });

      // Add sub-page if we're deeper
      if (path.includes('/grades')) {
        parts.push({ label: 'Grades' });
      } else if (path.includes('/assignments')) {
        parts.push({ label: 'Assignments' });
      } else if (path.includes('/quizzes')) {
        parts.push({ label: 'Quizzes' });
      } else if (path.includes('/learn')) {
        parts.push({ label: 'Learning' });
      } else if (path.includes('/announcements')) {
        parts.push({ label: 'Announcements' });
      } else if (path.includes('/manage')) {
        parts.push({ label: 'Manage' });
      } else if (path.includes('/roster')) {
        parts.push({ label: 'Roster' });
      } else if (path.includes('/gradebook')) {
        parts.push({ label: 'Gradebook' });
      }
      return parts;
    }

    // Instructor grading route
    if (path.includes('/instructor/assignments/')) {
      parts.push({ label: 'Grading' });
      return parts;
    }

    return parts.length > 0 ? parts : null;
  };

  const breadcrumbs = getBreadcrumbInfo();

  return (
    <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container mx-auto flex h-14 items-center px-4">
        {/* Logo */}
        <Link to="/" className="flex items-center space-x-2">
          <Gamepad2 className="h-6 w-6" />
          <span className="font-bold hidden sm:inline">GameDev</span>
        </Link>

        {/* Main Navigation */}
        {isAuthenticated && (
          <nav className="flex items-center ml-8 space-x-1">
            <Link
              to="/dashboard"
              className={`px-3 py-2 text-sm font-medium rounded-md transition-colors ${
                location.pathname === '/dashboard'
                  ? 'bg-muted text-foreground'
                  : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
              }`}
            >
              Dashboard
            </Link>
            <Link
              to="/courses"
              className={`px-3 py-2 text-sm font-medium rounded-md transition-colors ${
                location.pathname === '/courses' || location.pathname.startsWith('/courses/')
                  ? 'bg-muted text-foreground'
                  : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
              }`}
            >
              Courses
            </Link>
            {/* Contextual breadcrumbs */}
            {breadcrumbs && breadcrumbs.length > 0 && (
              <nav className="hidden md:flex items-center text-sm text-muted-foreground">
                {breadcrumbs.map((crumb, index) => (
                  <span key={index} className="flex items-center">
                    <ChevronRight className="h-4 w-4 mx-1" />
                    {crumb.href ? (
                      <Link
                        to={crumb.href}
                        className="hover:text-foreground transition-colors"
                      >
                        {crumb.label}
                      </Link>
                    ) : (
                      <span className="text-foreground">{crumb.label}</span>
                    )}
                  </span>
                ))}
              </nav>
            )}
          </nav>
        )}

        {/* Right Side */}
        <div className="ml-auto flex items-center space-x-2">
          {isAuthenticated ? (
            <>
              <NotificationBell />

              {/* User Menu Dropdown */}
              <div className="relative" ref={userMenuRef}>
                <button
                  onClick={() => setUserMenuOpen(!userMenuOpen)}
                  className="flex items-center space-x-2 px-2 py-1.5 rounded-md hover:bg-muted transition-colors"
                >
                  {user?.preferences?.avatar_url ? (
                    <img
                      src={user.preferences.avatar_url}
                      alt="Avatar"
                      className="h-7 w-7 rounded-full object-cover"
                    />
                  ) : (
                    <div className="h-7 w-7 rounded-full bg-muted flex items-center justify-center">
                      <User className="h-4 w-4 text-muted-foreground" />
                    </div>
                  )}
                  <span className="hidden sm:inline text-sm font-medium">
                    {user?.first_name || 'Account'}
                  </span>
                  <ChevronDown className={`h-4 w-4 text-muted-foreground transition-transform ${userMenuOpen ? 'rotate-180' : ''}`} />
                </button>

                {userMenuOpen && (
                  <div className="absolute top-full right-0 mt-1 w-56 bg-background border rounded-lg shadow-lg py-1 z-50">
                    {/* User Info */}
                    <div className="px-3 py-2 border-b">
                      <div className="font-medium">{user?.first_name} {user?.last_name}</div>
                      <div className="text-xs text-muted-foreground">{user?.email}</div>
                      {user?.is_instructor && (
                        <span className="inline-block mt-1 rounded-full bg-primary px-2 py-0.5 text-xs text-primary-foreground">
                          Instructor
                        </span>
                      )}
                    </div>

                    {/* Grades Section (Students only) */}
                    {!user?.is_instructor && enrolledCourses.length > 0 && (
                      <>
                        <div className="px-3 py-2 text-xs font-medium text-muted-foreground">
                          My Grades
                        </div>
                        {enrolledCourses.slice(0, 3).map((enrollment) => (
                          <Link
                            key={enrollment.id}
                            to={`/courses/${enrollment.course.code}/grades`}
                            onClick={() => setUserMenuOpen(false)}
                            className="flex items-center justify-between px-3 py-2 text-sm hover:bg-muted transition-colors"
                          >
                            <span className="truncate">{enrollment.course.code}</span>
                            <ChevronRight className="h-4 w-4 text-muted-foreground" />
                          </Link>
                        ))}
                        {enrolledCourses.length > 3 && (
                          <div className="px-3 py-1 text-xs text-muted-foreground">
                            +{enrolledCourses.length - 3} more courses
                          </div>
                        )}
                        <div className="border-t my-1" />
                      </>
                    )}

                    {/* Menu Items */}
                    <Link
                      to="/settings"
                      onClick={() => setUserMenuOpen(false)}
                      className="flex items-center gap-2 px-3 py-2 text-sm hover:bg-muted transition-colors"
                    >
                      <Settings className="h-4 w-4" />
                      Settings
                    </Link>
                    <button
                      onClick={handleLogout}
                      className="flex items-center gap-2 px-3 py-2 text-sm hover:bg-muted transition-colors w-full text-left text-red-600 dark:text-red-400"
                    >
                      <LogOut className="h-4 w-4" />
                      Logout
                    </button>
                  </div>
                )}
              </div>
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
        </div>
      </div>
    </header>
  );
}

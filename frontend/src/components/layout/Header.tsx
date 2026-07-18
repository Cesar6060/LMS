import { useState, useEffect } from 'react';
import { Link, useNavigate, useLocation } from 'react-router';
import {
  LogOut,
  User,
  Gamepad2,
  Settings,
  ChevronDown,
  ChevronRight,
  Menu,
  GraduationCap,
  PlusCircle,
  ClipboardList,
} from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { Button } from '@/components/ui/Button';
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
} from '@/components/ui/DropdownMenu';
import {
  Sheet,
  SheetContent,
  SheetTrigger,
  SheetTitle,
} from '@/components/ui/Sheet';
import { NotificationBell } from '@/components/notifications/NotificationBell';
import { courseService, type InstructorCourse } from '@/services/courses';
import { cn } from '@/lib/utils';
import type { Enrollment } from '@/types';

const MAX_TEACH_COURSES = 5;

function navLinkClass(active: boolean) {
  return cn(
    'relative px-4 py-2.5 text-base font-medium rounded-lg transition-colors',
    active
      ? 'bg-muted text-foreground after:absolute after:left-4 after:right-4 after:bottom-1 after:h-0.5 after:rounded-full after:bg-neon-green'
      : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
  );
}

export function Header() {
  const { user, logout, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [enrolledCourses, setEnrolledCourses] = useState<Enrollment[]>([]);
  const [taughtCourses, setTaughtCourses] = useState<InstructorCourse[]>([]);
  const [mobileOpen, setMobileOpen] = useState(false);

  // Load enrolled courses for grades in user menu (students only)
  useEffect(() => {
    if (isAuthenticated && user && !user.is_instructor) {
      courseService.getMyEnrollments().then(setEnrolledCourses).catch(console.error);
    } else {
      setEnrolledCourses([]);
    }
  }, [isAuthenticated, user]);

  // Load owned courses for the Teach menu (instructors only)
  useEffect(() => {
    if (isAuthenticated && user?.is_instructor) {
      courseService.getInstructorCourses().then(setTaughtCourses).catch(console.error);
    } else {
      setTaughtCourses([]);
    }
  }, [isAuthenticated, user]);

  // Close the mobile sheet on navigation
  useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname]);

  const handleLogout = async () => {
    setMobileOpen(false);
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

  const isDashboardActive = location.pathname === '/dashboard';
  const isCoursesActive =
    location.pathname === '/courses' || location.pathname.startsWith('/courses/');
  const isTeachActive = location.pathname.startsWith('/instructor');
  const teachOverflow = taughtCourses.length > MAX_TEACH_COURSES;

  return (
    <header className="sticky top-0 z-50 w-full header-gaming">
      <div className="container mx-auto flex h-20 items-center px-6">
        {/* Logo */}
        <Link to="/" className="flex items-center space-x-2.5 group">
          <Gamepad2 className="h-8 w-8 text-neon-green transition-all" />
          <span className="hidden sm:inline text-2xl font-bold font-gaming text-gradient-gaming">
            GameDev
          </span>
        </Link>

        {/* Main Navigation (desktop) */}
        {isAuthenticated && (
          <nav className="hidden md:flex items-center ml-8 gap-1">
            <Link to="/dashboard" className={navLinkClass(isDashboardActive)}>
              Dashboard
            </Link>
            <Link to="/courses" className={navLinkClass(isCoursesActive)}>
              Courses
            </Link>
            {user?.is_instructor && (
              <DropdownMenu>
                <DropdownMenuTrigger
                  className={cn(
                    navLinkClass(isTeachActive),
                    'flex items-center gap-1 outline-none'
                  )}
                >
                  Teach
                  <ChevronDown className="h-4 w-4" />
                </DropdownMenuTrigger>
                <DropdownMenuContent align="start" className="w-64">
                  <DropdownMenuItem asChild>
                    <Link to="/instructor/courses/new">
                      <PlusCircle className="h-4 w-4" />
                      Create Course
                    </Link>
                  </DropdownMenuItem>
                  {taughtCourses.length > 0 && (
                    <>
                      <DropdownMenuSeparator />
                      <DropdownMenuLabel>Manage</DropdownMenuLabel>
                      {taughtCourses.slice(0, MAX_TEACH_COURSES).map((course) => (
                        <DropdownMenuItem key={course.id} asChild>
                          <Link to={`/instructor/courses/${course.code}/manage`}>
                            <ClipboardList className="h-4 w-4" />
                            <span className="truncate">
                              {course.code} — {course.title}
                            </span>
                          </Link>
                        </DropdownMenuItem>
                      ))}
                      {teachOverflow && (
                        <DropdownMenuItem asChild>
                          <Link to="/courses" className="text-muted-foreground">
                            All courses…
                          </Link>
                        </DropdownMenuItem>
                      )}
                    </>
                  )}
                </DropdownMenuContent>
              </DropdownMenu>
            )}
            {/* Contextual breadcrumbs */}
            {breadcrumbs && breadcrumbs.length > 0 && (
              <nav className="hidden md:flex items-center ml-2 text-sm text-muted-foreground">
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
        <div className="ml-auto flex items-center gap-2">
          {isAuthenticated ? (
            <>
              <NotificationBell />

              {/* User Menu */}
              <DropdownMenu>
                <DropdownMenuTrigger className="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-muted transition-colors outline-none">
                  {user?.preferences?.avatar_url ? (
                    <img
                      src={user.preferences.avatar_url}
                      alt="Avatar"
                      className="h-9 w-9 rounded-full object-cover"
                    />
                  ) : (
                    <div className="h-9 w-9 rounded-full bg-muted flex items-center justify-center">
                      <User className="h-5 w-5 text-muted-foreground" />
                    </div>
                  )}
                  <span className="hidden sm:inline text-base font-medium">
                    {user?.first_name || 'Account'}
                  </span>
                  <ChevronDown className="h-4 w-4 text-muted-foreground" />
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-64">
                  {/* User Info */}
                  <div className="px-2 py-2">
                    <div className="font-medium">
                      {user?.first_name} {user?.last_name}
                    </div>
                    <div className="text-xs text-muted-foreground">{user?.email}</div>
                    {user?.is_instructor && (
                      <span className="badge-gaming mt-1.5">Instructor</span>
                    )}
                  </div>
                  <DropdownMenuSeparator />

                  {/* Grades Section (Students only) */}
                  {!user?.is_instructor && enrolledCourses.length > 0 && (
                    <>
                      <DropdownMenuLabel>My Grades</DropdownMenuLabel>
                      {enrolledCourses.slice(0, 3).map((enrollment) => (
                        <DropdownMenuItem key={enrollment.id} asChild>
                          <Link
                            to={`/courses/${enrollment.course.code}/grades`}
                            className="justify-between"
                          >
                            <span className="truncate">{enrollment.course.code}</span>
                            <ChevronRight className="h-4 w-4 text-muted-foreground" />
                          </Link>
                        </DropdownMenuItem>
                      ))}
                      {enrolledCourses.length > 3 && (
                        <div className="px-2 py-1 text-xs text-muted-foreground">
                          +{enrolledCourses.length - 3} more courses
                        </div>
                      )}
                      <DropdownMenuSeparator />
                    </>
                  )}

                  {/* Menu Items */}
                  <DropdownMenuItem asChild>
                    <Link to="/settings">
                      <Settings className="h-4 w-4" />
                      Settings
                    </Link>
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    onSelect={handleLogout}
                    className="text-red-600 dark:text-red-400 focus:text-red-600 dark:focus:text-red-400"
                  >
                    <LogOut className="h-4 w-4" />
                    Logout
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>

              {/* Mobile menu */}
              <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
                <SheetTrigger className="md:hidden p-2 rounded-lg hover:bg-muted transition-colors">
                  <Menu className="h-6 w-6" />
                  <span className="sr-only">Open menu</span>
                </SheetTrigger>
                <SheetContent side="right" className="w-72 p-0" aria-describedby={undefined}>
                  <SheetTitle className="flex items-center gap-2 px-6 py-5 border-b">
                    <Gamepad2 className="h-6 w-6 text-neon-green" />
                    <span className="font-gaming text-gradient-gaming text-lg font-bold">
                      GameDev
                    </span>
                  </SheetTitle>
                  <nav className="flex flex-col px-3 py-4">
                    <Link
                      to="/dashboard"
                      className={cn(
                        'px-3 py-3 text-base font-medium rounded-lg transition-colors',
                        isDashboardActive
                          ? 'bg-muted text-foreground'
                          : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
                      )}
                    >
                      Dashboard
                    </Link>
                    <Link
                      to="/courses"
                      className={cn(
                        'px-3 py-3 text-base font-medium rounded-lg transition-colors',
                        isCoursesActive
                          ? 'bg-muted text-foreground'
                          : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
                      )}
                    >
                      Courses
                    </Link>
                    {user?.is_instructor && (
                      <>
                        <div className="flex items-center gap-2 px-3 pt-4 pb-1 text-xs font-medium text-muted-foreground uppercase tracking-wide">
                          <GraduationCap className="h-4 w-4" />
                          Teach
                        </div>
                        <Link
                          to="/instructor/courses/new"
                          className="flex items-center gap-2 px-3 py-3 text-base font-medium rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
                        >
                          <PlusCircle className="h-5 w-5" />
                          Create Course
                        </Link>
                        {taughtCourses.slice(0, MAX_TEACH_COURSES).map((course) => (
                          <Link
                            key={course.id}
                            to={`/instructor/courses/${course.code}/manage`}
                            className="flex items-center gap-2 px-3 py-3 text-base font-medium rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
                          >
                            <ClipboardList className="h-5 w-5" />
                            <span className="truncate">{course.code}</span>
                          </Link>
                        ))}
                      </>
                    )}
                    <div className="border-t my-3" />
                    <Link
                      to="/settings"
                      className="flex items-center gap-2 px-3 py-3 text-base font-medium rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
                    >
                      <Settings className="h-5 w-5" />
                      Settings
                    </Link>
                    <button
                      onClick={handleLogout}
                      className="flex items-center gap-2 px-3 py-3 text-base font-medium rounded-lg text-red-600 dark:text-red-400 hover:bg-muted/50 transition-colors text-left"
                    >
                      <LogOut className="h-5 w-5" />
                      Logout
                    </button>
                  </nav>
                </SheetContent>
              </Sheet>
            </>
          ) : (
            <>
              <Link to="/login">
                <Button variant="ghost" size="lg" className="px-5 text-base">
                  Login
                </Button>
              </Link>
              <Link to="/register">
                <Button size="lg" className="px-5 text-base">
                  Register
                </Button>
              </Link>
            </>
          )}
        </div>
      </div>
    </header>
  );
}

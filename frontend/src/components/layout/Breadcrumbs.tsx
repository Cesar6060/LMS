import { Link, useLocation } from 'react-router';
import { ChevronRight } from 'lucide-react';
import { useAuth } from '@/contexts/useAuth';

interface Crumb {
  label: string;
  href?: string;
}

function getBreadcrumbs(path: string): Crumb[] {
  const parts: Crumb[] = [];

  // Course-related routes
  const courseMatch = path.match(/\/courses\/([^/]+)/);
  if (courseMatch) {
    const isInstructorRoute = path.startsWith('/instructor');
    const courseCode = courseMatch[1].toUpperCase();
    parts.push({ label: 'Courses', href: '/courses' });
    parts.push({
      label: courseCode,
      href: isInstructorRoute
        ? `/instructor/courses/${courseMatch[1]}/manage`
        : `/courses/${courseMatch[1]}`,
    });

    // Add sub-page if we're deeper
    if (path.includes('/grades')) {
      parts.push({ label: 'Grades' });
    } else if (path.includes('/quizzes')) {
      parts.push({ label: 'Quizzes' });
    } else if (path.includes('/learn')) {
      parts.push({ label: 'Learning' });
    } else if (path.includes('/announcements')) {
      parts.push({ label: 'Announcements' });
    } else if (path.includes('/discussions')) {
      parts.push({ label: 'Discussions' });
    } else if (path.includes('/lessons') && path.endsWith('/edit')) {
      parts.push({ label: 'Edit Lesson' });
    } else if (path.includes('/manage')) {
      parts.push({ label: 'Manage' });
    } else if (path.includes('/students')) {
      parts.push({ label: 'Roster' });
    } else if (path.includes('/gradebook')) {
      parts.push({ label: 'Gradebook' });
    }
  }

  return parts;
}

export function Breadcrumbs() {
  const { isAuthenticated } = useAuth();
  const location = useLocation();

  const crumbs = isAuthenticated ? getBreadcrumbs(location.pathname) : [];
  if (crumbs.length === 0) return null;

  return (
    <nav
      aria-label="Breadcrumb"
      className="w-full border-b border-border bg-background/70 backdrop-blur-sm"
    >
      <ol className="container mx-auto flex min-w-0 items-center px-6 py-2 max-w-7xl text-sm text-muted-foreground">
        {crumbs.map((crumb, index) => {
          const isLast = index === crumbs.length - 1;
          return (
            <li key={index} className="flex min-w-0 items-center">
              {index > 0 && (
                <ChevronRight aria-hidden="true" className="h-4 w-4 mx-1.5 shrink-0" />
              )}
              {isLast ? (
                <span
                  aria-current="page"
                  className="truncate max-w-[16rem] font-medium text-foreground"
                >
                  {crumb.label}
                </span>
              ) : crumb.href ? (
                <Link
                  to={crumb.href}
                  className="truncate max-w-[16rem] hover:text-foreground transition-colors"
                >
                  {crumb.label}
                </Link>
              ) : (
                <span className="truncate max-w-[16rem]">{crumb.label}</span>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

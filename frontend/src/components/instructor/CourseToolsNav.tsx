import { Link, useLocation } from 'react-router';
import { cn } from '@/lib/utils';

interface CourseToolsNavProps {
  courseCode: string;
  className?: string;
}

/**
 * Tab-style sub-nav shared by the instructor course tools (Manage,
 * Gradebook, Roster, Quiz editor) so they interlink laterally instead of
 * only through ManageCoursePage. Styled to match the header nav pills.
 */
export function CourseToolsNav({ courseCode, className }: CourseToolsNavProps) {
  const location = useLocation();

  const tabs = [
    { label: 'Overview', to: `/instructor/courses/${courseCode}/manage` },
    { label: 'Gradebook', to: `/instructor/courses/${courseCode}/gradebook` },
    { label: 'Roster', to: `/instructor/courses/${courseCode}/students` },
    { label: 'Quizzes', to: `/instructor/courses/${courseCode}/quizzes` },
    { label: 'Student View', to: `/courses/${courseCode}` },
  ];

  return (
    <nav
      aria-label="Course tools"
      className={cn('flex items-center gap-1 overflow-x-auto border-b pb-2', className)}
    >
      {tabs.map((tab) => {
        const active = location.pathname === tab.to;
        return (
          <Link
            key={tab.to}
            to={tab.to}
            aria-current={active ? 'page' : undefined}
            className={cn(
              'relative whitespace-nowrap px-4 py-2.5 text-base font-medium rounded-lg transition-colors',
              active
                ? 'bg-muted text-foreground after:absolute after:left-4 after:right-4 after:bottom-1 after:h-0.5 after:rounded-full after:bg-neon-green'
                : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
            )}
          >
            {tab.label}
          </Link>
        );
      })}
    </nav>
  );
}

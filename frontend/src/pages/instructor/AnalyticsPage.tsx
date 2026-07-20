import { useState, useEffect } from 'react';
import { useParams } from 'react-router';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts';
import { Card, CardContent } from '@/components/ui/Card';
import {
  analyticsService,
  type AnalyticsOverview,
  type AnalyticsQuizzes,
  type AnalyticsStudentRow,
  type ActivityDay,
} from '@/services/analytics';
import { isForbidden } from '@/services/api';
import { AccessDenied } from '@/components/AccessDenied';
import { Skeleton, SkeletonStatCard } from '@/components/ui/Skeleton';
import { PageContainer } from '@/components/layout/PageContainer';
import { BackLink } from '@/components/layout/BackLink';
import { CourseToolsNav } from '@/components/instructor/CourseToolsNav';
import {
  BarChart3, AlertCircle, AlertTriangle, CheckCircle, FileQuestion,
  ListChecks, Users, Activity,
} from 'lucide-react';

type SortField =
  | 'name' | 'progress' | 'quiz_average' | 'weighted_grade'
  | 'streak' | 'last_activity_at' | 'at_risk';
type SortDirection = 'asc' | 'desc';

/* Chart series colors: validated categorical slots (dataviz skill), light and
   dark steps swapped via CSS vars so recharts strokes follow the theme. */
const CHART_VARS =
  '[--chart-lessons:#2a78d6] [--chart-quizzes:#008300] [--chart-checks:#e87ba4] ' +
  'dark:[--chart-lessons:#3987e5] dark:[--chart-quizzes:#008300] dark:[--chart-checks:#d55181] ' +
  '[--chart-grid:#e1e0d9] dark:[--chart-grid:#2c2c2a]';

const formatPct = (value: number | null) => (value !== null ? `${value}%` : '—');

const formatDayLabel = (dateStr: string) =>
  new Date(`${dateStr}T00:00:00`).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });

const formatRelativeTime = (dateStr: string | null) => {
  if (!dateStr) return 'Never';
  const diffMs = Date.now() - new Date(dateStr).getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
  if (diffDays < 1) return 'Today';
  if (diffDays < 7) return `${diffDays} day${diffDays === 1 ? '' : 's'} ago`;
  const diffWeeks = Math.floor(diffDays / 7);
  if (diffWeeks < 5) return `${diffWeeks} week${diffWeeks === 1 ? '' : 's'} ago`;
  return new Date(dateStr).toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
  });
};

export function AnalyticsPage() {
  const { code } = useParams<{ code: string }>();

  const [overview, setOverview] = useState<AnalyticsOverview | null>(null);
  const [quizzes, setQuizzes] = useState<AnalyticsQuizzes | null>(null);
  const [students, setStudents] = useState<AnalyticsStudentRow[]>([]);
  const [activity, setActivity] = useState<ActivityDay[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [forbidden, setForbidden] = useState(false);

  const [sortField, setSortField] = useState<SortField>('at_risk');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');

  useEffect(() => {
    if (!code) return;
    const loadAnalytics = async () => {
      try {
        setIsLoading(true);
        const [overviewData, quizzesData, studentsData, activityData] = await Promise.all([
          analyticsService.getOverview(code),
          analyticsService.getQuizzes(code),
          analyticsService.getStudents(code),
          analyticsService.getActivity(code),
        ]);
        setOverview(overviewData);
        setQuizzes(quizzesData);
        setStudents(studentsData.students);
        setActivity(activityData.days);
      } catch (err) {
        if (isForbidden(err)) {
          setForbidden(true);
        } else {
          setError('Failed to load course analytics');
          console.error(err);
        }
      } finally {
        setIsLoading(false);
      }
    };
    loadAnalytics();
  }, [code]);

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      // Flag/metric columns read best "worst first"
      setSortDirection(field === 'at_risk' ? 'desc' : 'asc');
    }
  };

  const sortedStudents = [...students].sort((a, b) => {
    let comparison = 0;
    switch (sortField) {
      case 'name':
        comparison = a.student.name.localeCompare(b.student.name);
        break;
      case 'progress':
        comparison = a.progress_percentage - b.progress_percentage;
        break;
      case 'quiz_average':
        comparison = (a.quiz_average ?? -1) - (b.quiz_average ?? -1);
        break;
      case 'weighted_grade':
        comparison = (a.weighted_grade ?? -1) - (b.weighted_grade ?? -1);
        break;
      case 'streak':
        comparison = a.current_streak - b.current_streak;
        break;
      case 'last_activity_at': {
        const aTime = a.last_activity_at ? new Date(a.last_activity_at).getTime() : 0;
        const bTime = b.last_activity_at ? new Date(b.last_activity_at).getTime() : 0;
        comparison = aTime - bTime;
        break;
      }
      case 'at_risk':
        comparison = Number(a.at_risk) - Number(b.at_risk);
        break;
    }
    if (comparison === 0) return a.student.name.localeCompare(b.student.name);
    return sortDirection === 'asc' ? comparison : -comparison;
  });

  const hasActivity = activity.some(
    (d) => d.lessons_completed > 0 || d.quiz_attempts > 0 || d.lesson_check_attempts > 0
  );

  if (isLoading) {
    return (
      <PageContainer>
        <div className="mb-6">
          <Skeleton className="h-10 w-96 mb-4" />
          <Skeleton className="h-8 w-64 mb-2" />
        </div>
        <div className="grid gap-6 md:grid-cols-4 mb-8">
          <SkeletonStatCard />
          <SkeletonStatCard />
          <SkeletonStatCard />
          <SkeletonStatCard />
        </div>
        <Skeleton className="h-72 w-full mb-8" />
        <Skeleton className="h-64 w-full" />
      </PageContainer>
    );
  }

  if (forbidden) {
    return <AccessDenied />;
  }

  if (error || !overview || !quizzes) {
    return (
      <PageContainer>
        <Card>
          <CardContent className="py-12 text-center">
            <AlertCircle className="h-12 w-12 text-destructive mx-auto mb-4" />
            <h3 className="text-lg font-semibold mb-2">Error</h3>
            <p className="text-muted-foreground mb-4">{error || 'Could not load analytics'}</p>
            <BackLink to={`/instructor/courses/${code}/manage`} label="Manage Course" />
          </CardContent>
        </Card>
      </PageContainer>
    );
  }

  const sortableColumns: { field: SortField; label: string; align: 'left' | 'center' }[] = [
    { field: 'name', label: 'Student', align: 'left' },
    { field: 'progress', label: 'Progress', align: 'center' },
    { field: 'quiz_average', label: 'Quiz Avg', align: 'center' },
    { field: 'weighted_grade', label: 'Grade', align: 'center' },
    { field: 'streak', label: 'Streak', align: 'center' },
    { field: 'last_activity_at', label: 'Last Active', align: 'left' },
    { field: 'at_risk', label: 'Status', align: 'center' },
  ];

  return (
    <PageContainer>
      {/* Course tools sub-nav */}
      <CourseToolsNav courseCode={code!} className="mb-6" />

      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold flex items-center gap-2">
          <BarChart3 className="h-6 w-6" />
          Analytics
        </h1>
        <p className="text-muted-foreground">{overview.course.code} - {overview.course.title}</p>
      </div>

      {/* Overview stat cards */}
      <div className="grid gap-6 md:grid-cols-4 mb-8">
        <Card>
          <CardContent className="py-6">
            <div className="text-3xl font-bold">{overview.student_count}</div>
            <p className="text-sm text-muted-foreground mt-1">Students</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="py-6">
            <div className="text-3xl font-bold">{formatPct(overview.avg_progress_percentage)}</div>
            <p className="text-sm text-muted-foreground mt-1">Avg Progress</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="py-6">
            <div className="text-3xl font-bold">{formatPct(overview.avg_grade_percentage)}</div>
            <p className="text-sm text-muted-foreground mt-1">Avg Grade</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="py-6">
            <div className="text-3xl font-bold">{overview.active_last_7_days}</div>
            <p className="text-sm text-muted-foreground mt-1">Active Last 7 Days</p>
          </CardContent>
        </Card>
      </div>

      {/* 30-day activity trend */}
      <h2 className="text-xl font-semibold mb-3 flex items-center gap-2">
        <Activity className="h-5 w-5" />
        Activity (Last 30 Days)
      </h2>
      {hasActivity ? (
        <Card className="mb-8">
          <CardContent className={`py-6 ${CHART_VARS}`}>
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={activity} margin={{ top: 8, right: 16, bottom: 0, left: -16 }}>
                <CartesianGrid stroke="var(--chart-grid)" vertical={false} />
                <XAxis
                  dataKey="date"
                  interval={6}
                  tickFormatter={formatDayLabel}
                  tick={{ fill: '#898781', fontSize: 12 }}
                  tickLine={false}
                  axisLine={{ stroke: 'var(--chart-grid)' }}
                />
                <YAxis
                  allowDecimals={false}
                  tick={{ fill: '#898781', fontSize: 12 }}
                  tickLine={false}
                  axisLine={false}
                />
                <Tooltip
                  labelFormatter={(label) => formatDayLabel(String(label))}
                  contentStyle={{
                    backgroundColor: 'hsl(var(--card))',
                    border: '1px solid hsl(var(--border))',
                    borderRadius: 8,
                    color: 'hsl(var(--card-foreground))',
                  }}
                />
                <Legend
                  formatter={(value: string) => (
                    <span className="text-sm text-foreground">{value}</span>
                  )}
                />
                <Line
                  type="monotone"
                  dataKey="lessons_completed"
                  name="Lessons completed"
                  stroke="var(--chart-lessons)"
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 4 }}
                />
                <Line
                  type="monotone"
                  dataKey="quiz_attempts"
                  name="Quiz attempts"
                  stroke="var(--chart-quizzes)"
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 4 }}
                />
                <Line
                  type="monotone"
                  dataKey="lesson_check_attempts"
                  name="Lesson check attempts"
                  stroke="var(--chart-checks)"
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 4 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      ) : (
        <Card className="mb-8">
          <CardContent className="py-12 text-center">
            <Activity className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
            <h3 className="text-lg font-semibold mb-2">No Activity Yet</h3>
            <p className="text-muted-foreground">
              Lesson completions and quiz attempts from the last 30 days will chart here.
            </p>
          </CardContent>
        </Card>
      )}

      {/* Unit quiz performance */}
      <h2 className="text-xl font-semibold mb-3 flex items-center gap-2">
        <FileQuestion className="h-5 w-5" />
        Unit Quizzes
      </h2>
      {quizzes.unit_quizzes.length === 0 ? (
        <Card className="mb-8">
          <CardContent className="py-12 text-center">
            <FileQuestion className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
            <h3 className="text-lg font-semibold mb-2">No Unit Quizzes Yet</h3>
            <p className="text-muted-foreground">
              Quiz performance will appear here once the course has quizzes.
            </p>
          </CardContent>
        </Card>
      ) : (
        <Card className="mb-8">
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border bg-muted">
                    <th className="text-left px-4 py-3 font-semibold">Quiz</th>
                    <th className="text-left px-4 py-3 font-semibold">Unit</th>
                    <th className="text-center px-4 py-3 font-semibold">Avg Score</th>
                    <th className="text-center px-4 py-3 font-semibold">Pass Rate</th>
                    <th className="text-center px-4 py-3 font-semibold">Completion</th>
                  </tr>
                </thead>
                <tbody>
                  {quizzes.unit_quizzes.map((quiz, idx) => {
                    const belowPassing = quiz.avg_score !== null && quiz.avg_score < quiz.passing_score;
                    return (
                      <tr
                        key={quiz.id}
                        className={`border-b border-border hover:bg-muted/40 ${idx % 2 === 0 ? '' : 'bg-muted/20'}`}
                      >
                        <td className="px-4 py-3 font-medium">
                          <div className="flex items-center gap-2">
                            {quiz.title}
                            {belowPassing && (
                              <span className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded bg-red-100 text-red-700 dark:bg-red-900/50 dark:text-red-300">
                                <AlertTriangle className="h-3 w-3" />
                                Below passing ({quiz.passing_score}%)
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="px-4 py-3 text-muted-foreground">{quiz.unit_title}</td>
                        <td className={`px-4 py-3 text-center font-semibold ${belowPassing ? 'text-red-600 dark:text-red-400' : ''}`}>
                          {formatPct(quiz.avg_score)}
                        </td>
                        <td className="px-4 py-3 text-center">{formatPct(quiz.pass_rate)}</td>
                        <td className="px-4 py-3 text-center">{formatPct(quiz.completion_rate)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Lesson comprehension checks */}
      <h2 className="text-xl font-semibold mb-3 flex items-center gap-2">
        <ListChecks className="h-5 w-5" />
        Lesson Checks
      </h2>
      {quizzes.lesson_checks.length === 0 ? (
        <Card className="mb-8">
          <CardContent className="py-12 text-center">
            <ListChecks className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
            <h3 className="text-lg font-semibold mb-2">No Lesson Checks Yet</h3>
            <p className="text-muted-foreground">
              Add comprehension questions to lessons to see how students do here.
            </p>
          </CardContent>
        </Card>
      ) : (
        <Card className="mb-8">
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border bg-muted">
                    <th className="text-left px-4 py-3 font-semibold">Lesson</th>
                    <th className="text-left px-4 py-3 font-semibold">Unit</th>
                    <th className="text-center px-4 py-3 font-semibold">Attempted</th>
                    <th className="text-center px-4 py-3 font-semibold">Passed</th>
                    <th className="text-center px-4 py-3 font-semibold">Stuck</th>
                    <th className="text-center px-4 py-3 font-semibold">Avg Attempts to Pass</th>
                  </tr>
                </thead>
                <tbody>
                  {quizzes.lesson_checks.map((check, idx) => (
                    <tr
                      key={check.id}
                      className={`border-b border-border hover:bg-muted/40 ${idx % 2 === 0 ? '' : 'bg-muted/20'}`}
                    >
                      <td className="px-4 py-3 font-medium">
                        <div className="flex items-center gap-2">
                          {check.title}
                          {check.stuck_count > 0 && (
                            <span className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded bg-red-100 text-red-700 dark:bg-red-900/50 dark:text-red-300">
                              <AlertTriangle className="h-3 w-3" />
                              {check.stuck_count} stuck
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">{check.unit_title}</td>
                      <td className="px-4 py-3 text-center">{check.attempted_count}</td>
                      <td className="px-4 py-3 text-center">{check.passed_count}</td>
                      <td className={`px-4 py-3 text-center font-semibold ${check.stuck_count > 0 ? 'text-red-600 dark:text-red-400' : ''}`}>
                        {check.stuck_count}
                      </td>
                      <td className="px-4 py-3 text-center">
                        {check.avg_attempts_to_pass !== null ? check.avg_attempts_to_pass : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Students */}
      <h2 className="text-xl font-semibold mb-3 flex items-center gap-2">
        <Users className="h-5 w-5" />
        Students
      </h2>
      {students.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <Users className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
            <h3 className="text-lg font-semibold mb-2">No Students Enrolled</h3>
            <p className="text-muted-foreground">
              Student analytics will appear here once students join the course.
            </p>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b bg-muted/50">
                    {sortableColumns.map(({ field, label, align }) => (
                      <th
                        key={field}
                        className={`p-3 font-medium hover:bg-muted ${
                          align === 'center' ? 'text-center' : 'text-left'
                        }`}
                        aria-sort={
                          sortField === field
                            ? sortDirection === 'asc'
                              ? 'ascending'
                              : 'descending'
                            : undefined
                        }
                      >
                        <button
                          type="button"
                          onClick={() => handleSort(field)}
                          className={`w-full p-0 font-medium ${
                            align === 'center' ? 'text-center' : 'text-left'
                          }`}
                        >
                          {label} {sortField === field && (sortDirection === 'asc' ? '↑' : '↓')}
                        </button>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {sortedStudents.map((row) => (
                    <tr
                      key={row.student.id}
                      className={`border-b ${
                        row.at_risk
                          ? 'bg-red-50 hover:bg-red-100/70 dark:bg-red-950/30 dark:hover:bg-red-950/50'
                          : 'hover:bg-muted/30'
                      }`}
                    >
                      <td className="p-3">
                        <div className="font-medium">{row.student.name}</div>
                        <div className="text-xs text-muted-foreground">{row.student.email}</div>
                      </td>
                      <td className="p-3 text-center">
                        <div className="flex items-center justify-center gap-2">
                          <div className="w-16 h-2 bg-muted rounded-full overflow-hidden">
                            <div
                              className="h-full bg-primary"
                              style={{ width: `${row.progress_percentage}%` }}
                            />
                          </div>
                          <span className="text-xs">{row.progress_percentage}%</span>
                        </div>
                      </td>
                      <td className="p-3 text-center">{formatPct(row.quiz_average)}</td>
                      <td className="p-3 text-center font-semibold">{formatPct(row.weighted_grade)}</td>
                      <td className="p-3 text-center">
                        <span
                          className={`inline-flex items-center gap-1 font-medium ${
                            row.current_streak > 0 ? '' : 'text-muted-foreground'
                          }`}
                          title={`${row.current_streak}-day streak`}
                        >
                          <span className={row.current_streak > 0 ? '' : 'grayscale opacity-40'}>🔥</span>
                          {row.current_streak}
                        </span>
                      </td>
                      <td className="p-3">{formatRelativeTime(row.last_activity_at)}</td>
                      <td className="p-3 text-center">
                        {row.at_risk ? (
                          <span className="inline-flex items-center gap-1 text-xs font-semibold px-2 py-1 rounded bg-red-100 text-red-700 dark:bg-red-900/50 dark:text-red-300">
                            <AlertTriangle className="h-3 w-3" />
                            At Risk
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded bg-green-100 text-green-700 dark:bg-green-900/50 dark:text-green-300">
                            <CheckCircle className="h-3 w-3" />
                            On Track
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}
    </PageContainer>
  );
}

import { useState, useEffect } from 'react';
import { useParams, Link, useNavigate } from 'react-router';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { courseService } from '@/services/courses';
import { isForbidden } from '@/services/api';
import { AccessDenied } from '@/components/AccessDenied';
import type { GradeSummary } from '@/types';
import { PageContainer } from '@/components/layout/PageContainer';
import { Skeleton } from '@/components/ui/Skeleton';
import {
  ChevronLeft, Trophy, FileQuestion,
  BookOpen, CheckCircle, Clock, AlertCircle
} from 'lucide-react';

export function MyGradesPage() {
  const { code } = useParams<{ code: string }>();
  const navigate = useNavigate();
  const [grades, setGrades] = useState<GradeSummary | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [forbidden, setForbidden] = useState(false);

  useEffect(() => {
    if (code) {
      loadGrades();
    }
  }, [code]);

  const loadGrades = async () => {
    if (!code) return;
    try {
      setIsLoading(true);
      const data = await courseService.getMyGradeSummary(code);
      setGrades(data);
    } catch (err) {
      if (isForbidden(err)) {
        setForbidden(true);
      } else {
        console.error('Failed to load grades:', err);
        const status = (err as { response?: { status?: number } }).response?.status;
        if (status === 404) {
          setError('Course not found or grades endpoint unavailable.');
        } else {
          setError('Failed to load grades. Please try again.');
        }
      }
    } finally {
      setIsLoading(false);
    }
  };

  const getLetterGradeColor = (letter: string | null) => {
    if (!letter) return 'text-muted-foreground';
    switch (letter) {
      case 'A': return 'text-green-600 dark:text-green-400';
      case 'B': return 'text-blue-600 dark:text-blue-400';
      case 'C': return 'text-yellow-600 dark:text-yellow-400';
      case 'D': return 'text-orange-600 dark:text-orange-400';
      case 'F': return 'text-red-600 dark:text-red-400';
      default: return 'text-muted-foreground';
    }
  };

  const getStatusIcon = (status: string) => {
    if (status === 'graded') {
      return <CheckCircle className="h-4 w-4 text-green-500" />;
    }
    return <Clock className="h-4 w-4 text-slate-400" />;
  };

  const getScoreColor = (status: string) => {
    if (status === 'graded') {
      return 'bg-emerald-50 text-emerald-700 border border-emerald-300 dark:bg-emerald-950 dark:text-emerald-300 dark:border-emerald-700';
    }
    return 'bg-slate-50 text-slate-500 border border-slate-200 dark:bg-slate-900 dark:text-slate-400 dark:border-slate-700';
  };

  if (isLoading) {
    return (
      <PageContainer maxWidth="max-w-6xl">
        <Skeleton className="h-4 w-32 mb-6" />
        <Skeleton className="h-9 w-48 mb-2" />
        <Skeleton className="h-5 w-64 mb-6" />
        <Skeleton className="h-28 w-full mb-6" />
        <div className="grid gap-4 md:grid-cols-3 mb-6">
          <Skeleton className="h-24" />
          <Skeleton className="h-24" />
          <Skeleton className="h-24" />
        </div>
        <Skeleton className="h-64 w-full" />
      </PageContainer>
    );
  }

  if (forbidden) {
    return <AccessDenied />;
  }

  if (error || !grades) {
    return (
      <PageContainer maxWidth="max-w-6xl">
        <Card>
          <CardContent className="py-12 text-center">
            <AlertCircle className="h-12 w-12 text-destructive mx-auto mb-4" />
            <p className="text-destructive">{error || 'Failed to load grades'}</p>
            <Link to={`/courses/${code}`}>
              <Button variant="outline" className="mt-4">
                Back to Course
              </Button>
            </Link>
          </CardContent>
        </Card>
      </PageContainer>
    );
  }

  const gradeItems = grades.grade_items || [];

  return (
    <PageContainer maxWidth="max-w-6xl">
      {/* Header */}
      <Link
        to={`/courses/${code}`}
        className="inline-flex items-center gap-2 text-muted-foreground hover:text-foreground mb-6"
      >
        <ChevronLeft className="h-4 w-4" />
        Back to Course
      </Link>

      <h1 className="text-3xl font-bold mb-2">My Grades</h1>
      <p className="text-muted-foreground mb-6">{grades.course?.title || ''}</p>

      {/* Overall Grade Card */}
      <Card className="mb-6">
        <CardContent className="py-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Trophy className={`h-12 w-12 ${getLetterGradeColor(grades.overall.letter_grade)}`} />
              <div>
                <div className={`text-4xl font-bold ${getLetterGradeColor(grades.overall.letter_grade)}`}>
                  {grades.overall.percentage !== null ? `${grades.overall.percentage}%` : '--'}
                </div>
                <div className="text-muted-foreground">
                  {grades.overall.letter_grade ? `Grade: ${grades.overall.letter_grade}` : 'No grades yet'}
                </div>
              </div>
            </div>
            {grades.is_weighted && (
              <div className="text-right text-sm text-muted-foreground">
                <div>Weighted Average</div>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-3 mb-6">
        <Card>
          <CardContent className="py-4">
            <div className="text-2xl font-bold flex items-center gap-2">
              <FileQuestion className="h-5 w-5 text-purple-500" />
              {gradeItems.length}
            </div>
            <p className="text-sm text-muted-foreground">
              Quizzes
              {grades.quizzes.weight !== null && ` (${grades.quizzes.weight}%)`}
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              {grades.quizzes.earned}/{grades.quizzes.possible} pts
              {grades.quizzes.percentage !== null && ` - ${grades.quizzes.percentage}%`}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="py-4">
            <div className="text-2xl font-bold flex items-center gap-2">
              <BookOpen className="h-5 w-5 text-green-500" />
              {grades.participation.completed}/{grades.participation.total}
            </div>
            <p className="text-sm text-muted-foreground">
              Participation
              {grades.participation.weight !== null && ` (${grades.participation.weight}%)`}
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              {grades.participation.percentage !== null ? `${grades.participation.percentage}%` : '--'} of lessons completed
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="py-4">
            <div className={`text-2xl font-bold ${getLetterGradeColor(grades.overall.letter_grade)}`}>
              {grades.overall.letter_grade || '--'}
            </div>
            <p className="text-sm text-muted-foreground">Current Grade</p>
            <p className="text-xs text-muted-foreground mt-1">
              {grades.overall.percentage !== null ? `${grades.overall.percentage}%` : 'No grades yet'}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Quiz Grades Table */}
      {gradeItems.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <FileQuestion className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
            <h3 className="text-lg font-semibold mb-2">No Quizzes Yet</h3>
            <p className="text-muted-foreground">
              Grades will appear here once your instructor adds quizzes.
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
                    <th className="text-left p-3 font-medium">Quiz</th>
                    <th className="text-left p-3 font-medium">Unit</th>
                    <th className="text-center p-3 font-medium">Status</th>
                    <th className="text-center p-3 font-medium">Score</th>
                    <th className="text-center p-3 font-medium">%</th>
                  </tr>
                </thead>
                <tbody>
                  {gradeItems.map((item) => {
                    const percentage = item.points_earned !== null && item.max_points > 0
                      ? Math.round((item.points_earned / item.max_points) * 100)
                      : null;

                    return (
                      <tr
                        key={item.id}
                        className="border-b hover:bg-muted/30 cursor-pointer"
                        onClick={() => navigate(`/courses/${code}/quizzes/${item.id}`)}
                      >
                        <td className="p-3">
                          <div className="flex items-center gap-2">
                            <FileQuestion className="h-4 w-4 text-purple-500 flex-shrink-0" />
                            <Link
                              to={`/courses/${code}/quizzes/${item.id}`}
                              className="font-medium hover:text-primary transition-colors"
                              onClick={(e) => e.stopPropagation()}
                            >
                              {item.title}
                            </Link>
                          </div>
                        </td>
                        <td className="p-3 text-muted-foreground">{item.unit_title}</td>
                        <td className="p-3 text-center">
                          <div className="flex items-center justify-center gap-1">
                            {getStatusIcon(item.status)}
                            <span className="text-xs capitalize">{item.status.replace('_', ' ')}</span>
                          </div>
                        </td>
                        <td className="p-3 text-center">
                          <span className={`inline-block px-2 py-1 rounded text-xs font-medium ${getScoreColor(item.status)}`}>
                            {item.status === 'graded' && item.points_earned !== null
                              ? `${item.points_earned}/${item.max_points}`
                              : '-'}
                            {item.passed !== undefined && item.passed !== null && (
                              <span className={`ml-1 ${item.passed ? 'text-green-600' : 'text-red-600'}`}>
                                {item.passed ? 'P' : 'F'}
                              </span>
                            )}
                          </span>
                        </td>
                        <td className="p-3 text-center font-medium">
                          {percentage !== null ? `${percentage}%` : '-'}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Grade Scale Reference */}
      <Card className="mt-6">
        <CardHeader>
          <CardTitle className="text-sm font-medium">Grade Scale</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-4 text-sm">
            <div className="flex items-center gap-2">
              <span className="w-6 h-6 rounded bg-green-100 dark:bg-green-900 flex items-center justify-center text-green-700 dark:text-green-300 font-medium">A</span>
              <span className="text-muted-foreground">90-100%</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-6 h-6 rounded bg-blue-100 dark:bg-blue-900 flex items-center justify-center text-blue-700 dark:text-blue-300 font-medium">B</span>
              <span className="text-muted-foreground">80-89%</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-6 h-6 rounded bg-yellow-100 dark:bg-yellow-900 flex items-center justify-center text-yellow-700 dark:text-yellow-300 font-medium">C</span>
              <span className="text-muted-foreground">70-79%</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-6 h-6 rounded bg-orange-100 dark:bg-orange-900 flex items-center justify-center text-orange-700 dark:text-orange-300 font-medium">D</span>
              <span className="text-muted-foreground">60-69%</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-6 h-6 rounded bg-red-100 dark:bg-red-900 flex items-center justify-center text-red-700 dark:text-red-300 font-medium">F</span>
              <span className="text-muted-foreground">Below 60%</span>
            </div>
          </div>
        </CardContent>
      </Card>
    </PageContainer>
  );
}

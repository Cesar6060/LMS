import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { courseService } from '@/services/courses';
import type { GradeSummary } from '@/types';
import {
  FileQuestion, BookOpen,
  Loader2, TrendingUp, ChevronRight
} from 'lucide-react';

interface StudentGradeCardProps {
  courseCode: string;
}

export function StudentGradeCard({ courseCode }: StudentGradeCardProps) {
  const [grades, setGrades] = useState<GradeSummary | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  const loadGrades = useCallback(async () => {
    try {
      setIsLoading(true);
      const data = await courseService.getMyGradeSummary(courseCode);
      setGrades(data);
    } catch (err) {
      console.error('Failed to load grades:', err);
      setError('Failed to load grade summary');
    } finally {
      setIsLoading(false);
    }
  }, [courseCode]);

  useEffect(() => {
    loadGrades();
  }, [loadGrades]);

  const getLetterGradeColor = (letter: string | null) => {
    if (!letter) return 'text-muted-foreground';
    switch (letter) {
      case 'A': return 'text-green-600';
      case 'B': return 'text-blue-600';
      case 'C': return 'text-yellow-600';
      case 'D': return 'text-orange-600';
      case 'F': return 'text-red-600';
      default: return 'text-muted-foreground';
    }
  };

  if (isLoading) {
    return (
      <Card>
        <CardContent className="py-8">
          <div className="flex items-center justify-center">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        </CardContent>
      </Card>
    );
  }

  // Always show the card with at least a link to grades
  if (error || !grades) {
    return (
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-lg">
            <TrendingUp className="h-5 w-5" />
            My Grades
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground mb-4">
            {error || 'View your grades and progress in this course.'}
          </p>
          <Link to={`/courses/${courseCode}/grades`}>
            <Button variant="outline" className="w-full justify-between">
              View All Grades
              <ChevronRight className="h-4 w-4" />
            </Button>
          </Link>
        </CardContent>
      </Card>
    );
  }

  const hasAnyGrades = grades.quizzes.possible > 0 || grades.participation.total > 0;

  if (!hasAnyGrades) {
    return (
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-lg">
            <TrendingUp className="h-5 w-5" />
            My Grades
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground mb-4">
            No quizzes or lessons to grade yet.
          </p>
          <Link to={`/courses/${courseCode}/grades`}>
            <Button variant="outline" className="w-full justify-between">
              View All Grades
              <ChevronRight className="h-4 w-4" />
            </Button>
          </Link>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-lg">
          <TrendingUp className="h-5 w-5" />
          My Grades
        </CardTitle>
      </CardHeader>
      <CardContent>
        {/* Overall Grade - Progress Bar Style */}
        <div className="mb-4">
          <div className="flex items-baseline justify-between mb-2">
            <span className="text-sm text-muted-foreground">
              {grades.is_weighted ? 'Weighted Average' : 'Overall'}
            </span>
            <div className="flex items-baseline gap-2">
              <span className={`text-2xl font-bold ${getLetterGradeColor(grades.overall.letter_grade)}`}>
                {grades.overall.percentage !== null
                  ? `${grades.overall.percentage}%`
                  : '--'}
              </span>
              {grades.overall.letter_grade && (
                <span className={`text-lg font-semibold ${getLetterGradeColor(grades.overall.letter_grade)}`}>
                  ({grades.overall.letter_grade})
                </span>
              )}
            </div>
          </div>
          <div className="h-3 bg-muted rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all ${
                grades.overall.letter_grade === 'A' ? 'bg-green-500' :
                grades.overall.letter_grade === 'B' ? 'bg-blue-500' :
                grades.overall.letter_grade === 'C' ? 'bg-yellow-500' :
                grades.overall.letter_grade === 'D' ? 'bg-orange-500' :
                grades.overall.letter_grade === 'F' ? 'bg-red-500' : 'bg-primary'
              }`}
              style={{ width: `${grades.overall.percentage ?? 0}%` }}
            />
          </div>
        </div>

        {/* Category Breakdown */}
        <div className="space-y-3">
          {/* Quizzes */}
          {grades.quizzes.possible > 0 && (
            <div className="flex items-center justify-between text-sm">
              <div className="flex items-center gap-2 text-muted-foreground">
                <FileQuestion className="h-4 w-4 text-purple-500" />
                <span>Quizzes</span>
                {grades.quizzes.weight !== null && (
                  <span className="text-xs">({grades.quizzes.weight}%)</span>
                )}
              </div>
              <div className="font-medium">
                {grades.quizzes.percentage !== null
                  ? `${grades.quizzes.percentage}%`
                  : '--'}
                <span className="text-xs text-muted-foreground ml-1">
                  ({grades.quizzes.earned}/{grades.quizzes.possible} pts)
                </span>
              </div>
            </div>
          )}

          {/* Participation */}
          {grades.participation.total > 0 && (
            <div className="flex items-center justify-between text-sm">
              <div className="flex items-center gap-2 text-muted-foreground">
                <BookOpen className="h-4 w-4 text-green-500" />
                <span>Participation</span>
                {grades.participation.weight !== null && (
                  <span className="text-xs">({grades.participation.weight}%)</span>
                )}
              </div>
              <div className="font-medium">
                {grades.participation.percentage !== null
                  ? `${grades.participation.percentage}%`
                  : '--'}
                <span className="text-xs text-muted-foreground ml-1">
                  ({grades.participation.completed}/{grades.participation.total} lessons)
                </span>
              </div>
            </div>
          )}
        </div>

        {/* View All Grades Link */}
        <div className="mt-4 pt-4 border-t">
          <Link to={`/courses/${courseCode}/grades`}>
            <Button variant="ghost" className="w-full justify-between">
              View All Grades
              <ChevronRight className="h-4 w-4" />
            </Button>
          </Link>
        </div>
      </CardContent>
    </Card>
  );
}

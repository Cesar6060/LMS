import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router';
import { Card, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { courseService, type Gradebook } from '@/services/courses';
import { Skeleton } from '@/components/ui/Skeleton';
import { EditableGradeCell } from '@/components/gradebook/EditableGradeCell';
import { GradingConfigModal } from '@/components/course/GradingConfigModal';
import {
  ChevronLeft, Download, Table, AlertCircle, FileQuestion, ClipboardList, Settings
} from 'lucide-react';

export function GradebookPage() {
  const { code } = useParams<{ code: string }>();

  const [gradebook, setGradebook] = useState<Gradebook | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [showConfigModal, setShowConfigModal] = useState(false);

  useEffect(() => {
    if (code) {
      loadGradebook();
    }
  }, [code]);

  const loadGradebook = async () => {
    try {
      setIsLoading(true);
      const data = await courseService.getGradebook(code!);
      setGradebook(data);
    } catch (err) {
      setError('Failed to load gradebook');
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleExport = async () => {
    const token = localStorage.getItem('token');
    const exportUrl = courseService.getGradebookExportUrl(code!);

    try {
      const response = await fetch(exportUrl, {
        headers: {
          'Authorization': `Token ${token}`,
        },
      });

      if (!response.ok) throw new Error('Export failed');

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${code}_gradebook.csv`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err) {
      console.error('Export failed:', err);
    }
  };

  const getLetterGradeColor = (letter: string | null) => {
    if (!letter) return '';
    switch (letter) {
      case 'A':
        return 'text-green-600 dark:text-green-400';
      case 'B':
        return 'text-blue-600 dark:text-blue-400';
      case 'C':
        return 'text-yellow-600 dark:text-yellow-400';
      case 'D':
        return 'text-orange-600 dark:text-orange-400';
      case 'F':
        return 'text-red-600 dark:text-red-400';
      default:
        return '';
    }
  };

  const handleGradeUpdate = (studentId: number, itemId: number, itemType: string, newPoints: number) => {
    setGradebook(prev => {
      if (!prev) return prev;
      return {
        ...prev,
        students: prev.students.map(student => {
          if (student.id !== studentId) return student;
          return {
            ...student,
            grades: student.grades.map(grade => {
              if (grade.item_id !== itemId || grade.item_type !== itemType) return grade;
              return {
                ...grade,
                points_earned: newPoints,
                status: 'graded' as const,
              };
            }),
          };
        }),
      };
    });
  };

  if (isLoading) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="mb-6">
          <Skeleton className="h-4 w-32 mb-4" />
          <Skeleton className="h-8 w-64 mb-2" />
        </div>
        <Skeleton className="h-96 w-full" />
      </div>
    );
  }

  if (error || !gradebook) {
    return (
      <div className="container mx-auto px-4 py-8">
        <Card>
          <CardContent className="py-12 text-center">
            <AlertCircle className="h-12 w-12 text-destructive mx-auto mb-4" />
            <h3 className="text-lg font-semibold mb-2">Error</h3>
            <p className="text-muted-foreground mb-4">{error || 'Could not load gradebook'}</p>
            <Link to={`/courses/${code}`}>
              <Button>Back to Course</Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      {/* Header */}
      <div className="mb-8">
        <Link
          to={`/instructor/courses/${code}/manage`}
          className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground mb-4"
        >
          <ChevronLeft className="h-4 w-4 mr-1" />
          Back to Manage Course
        </Link>

        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <Table className="h-6 w-6" />
              Gradebook
            </h1>
            <p className="text-muted-foreground">{gradebook.course.code} - {gradebook.course.title}</p>
          </div>

          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setShowConfigModal(true)}>
              <Settings className="h-4 w-4 mr-2" />
              Grading Weights
            </Button>
            <Button onClick={handleExport}>
              <Download className="h-4 w-4 mr-2" />
              Export CSV
            </Button>
          </div>
        </div>
      </div>

      {/* Summary */}
      {(() => {
        const assignmentCount = gradebook.gradebook_items.filter(i => i.type === 'assignment').length;
        const quizCount = gradebook.gradebook_items.filter(i => i.type === 'quiz').length;
        return (
          <div className="grid gap-6 md:grid-cols-4 mb-8">
            <Card>
              <CardContent className="py-6">
                <div className="text-3xl font-bold">{gradebook.students.length}</div>
                <p className="text-sm text-muted-foreground mt-1">Students</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="py-6">
                <div className="text-3xl font-bold flex items-center gap-2">
                  <ClipboardList className="h-6 w-6 text-blue-500" />
                  {assignmentCount}
                </div>
                <p className="text-sm text-muted-foreground mt-1">Assignments</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="py-6">
                <div className="text-3xl font-bold flex items-center gap-2">
                  <FileQuestion className="h-6 w-6 text-purple-500" />
                  {quizCount}
                </div>
                <p className="text-sm text-muted-foreground mt-1">Quizzes</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="py-6">
                <div className="text-3xl font-bold">{gradebook.total_possible}</div>
                <p className="text-sm text-muted-foreground mt-1">Total Points</p>
              </CardContent>
            </Card>
          </div>
        );
      })()}

      {/* Legend */}
      <div className="flex flex-wrap gap-6 mb-8 text-sm">
        <div className="flex items-center gap-2">
          <ClipboardList className="h-4 w-4 text-blue-500" />
          <span>Assignment</span>
        </div>
        <div className="flex items-center gap-2">
          <FileQuestion className="h-4 w-4 text-purple-500" />
          <span>Quiz</span>
        </div>
        <div className="w-px h-4 bg-border" />
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 rounded bg-emerald-100 border border-emerald-400 dark:bg-emerald-900" />
          <span>Graded</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 rounded bg-sky-100 border border-sky-400 dark:bg-sky-900" />
          <span>Submitted (Pending)</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 rounded bg-amber-100 border border-amber-400 dark:bg-amber-900" />
          <span>Late</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 rounded bg-rose-100 border border-rose-400 dark:bg-rose-900" />
          <span>Missing</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 rounded bg-slate-100 border border-slate-300 dark:bg-slate-800" />
          <span>Not Started</span>
        </div>
      </div>

      {/* Gradebook Table */}
      {gradebook.students.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            No students enrolled in this course yet.
          </CardContent>
        </Card>
      ) : gradebook.gradebook_items.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            No assignments or quizzes created yet.
          </CardContent>
        </Card>
      ) : (
        <Card className="overflow-hidden">
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm border-collapse">
                <thead>
                  <tr className="border-b border-border bg-muted">
                    <th className="text-left px-4 py-3 font-semibold sticky left-0 bg-muted z-10 min-w-[220px] border-r border-border">
                      Student
                    </th>
                    {gradebook.gradebook_items.map((item) => (
                      <th
                        key={`${item.type}-${item.id}`}
                        className="text-center px-3 py-3 font-medium min-w-[110px]"
                        title={`${item.unit_title}: ${item.title}`}
                      >
                        <div className="flex items-center justify-center gap-1.5">
                          {item.type === 'quiz' ? (
                            <FileQuestion className="h-3.5 w-3.5 text-purple-500 flex-shrink-0" />
                          ) : (
                            <ClipboardList className="h-3.5 w-3.5 text-blue-500 flex-shrink-0" />
                          )}
                          <span className="truncate max-w-[80px]">{item.title}</span>
                        </div>
                        <div className="text-xs text-muted-foreground font-normal mt-0.5">
                          {item.max_points} pts
                        </div>
                      </th>
                    ))}
                    {/* Category Summary Columns */}
                    <th className="text-center px-3 py-3 font-semibold min-w-[90px] bg-muted border-l border-border">
                      <div className="flex items-center justify-center gap-1">
                        <ClipboardList className="h-3.5 w-3.5 text-blue-500" />
                        <span>Assign.</span>
                      </div>
                    </th>
                    <th className="text-center px-3 py-3 font-semibold min-w-[90px] bg-muted">
                      <div className="flex items-center justify-center gap-1">
                        <FileQuestion className="h-3.5 w-3.5 text-purple-500" />
                        <span>Quizzes</span>
                      </div>
                    </th>
                    <th className="text-center px-3 py-3 font-semibold min-w-[90px] bg-muted">
                      <span>Particip.</span>
                    </th>
                    <th className="text-center px-3 py-3 font-semibold min-w-[80px] bg-muted border-l border-border">
                      Average
                    </th>
                    <th className="text-center px-3 py-3 font-semibold min-w-[70px] bg-muted">
                      Grade
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {gradebook.students.map((student, idx) => (
                    <tr key={student.id} className={`border-b border-border hover:bg-muted/40 ${idx % 2 === 0 ? '' : 'bg-muted/20'}`}>
                      <td className="px-4 py-3 sticky left-0 z-10 border-r border-border bg-white dark:bg-zinc-950">
                        <div className="font-medium text-foreground">{student.name}</div>
                        <div className="text-xs text-muted-foreground">{student.email}</div>
                      </td>
                      {gradebook.gradebook_items.map((item) => {
                        const grade = student.grades.find(
                          g => g.item_id === item.id && g.item_type === item.type
                        );

                        if (!grade) {
                          return (
                            <td key={`${item.type}-${item.id}`} className="px-3 py-2 text-center">
                              <span className="inline-block px-2.5 py-1 rounded text-xs font-medium bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400">
                                -
                              </span>
                            </td>
                          );
                        }

                        // Use EditableGradeCell for both assignments and quizzes
                        return (
                          <td key={`${item.type}-${item.id}`} className="px-3 py-2 text-center">
                            <EditableGradeCell
                              itemId={item.id}
                              itemType={item.type}
                              studentId={student.id}
                              currentPoints={grade.points_earned}
                              maxPoints={item.max_points}
                              status={grade.status}
                              isLate={grade.is_late}
                              onUpdate={(newPoints) => handleGradeUpdate(student.id, item.id, item.type, newPoints)}
                            />
                          </td>
                        );
                      })}
                      {/* Category Percentages */}
                      <td className="px-3 py-2 text-center border-l border-border">
                        <span className="font-medium">
                          {student.assignments_percentage !== null ? `${student.assignments_percentage}%` : '-'}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-center">
                        <span className="font-medium">
                          {student.quizzes_percentage !== null ? `${student.quizzes_percentage}%` : '-'}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-center">
                        <span className="font-medium">
                          {student.participation_percentage !== null ? `${student.participation_percentage}%` : '-'}
                        </span>
                      </td>
                      {/* Overall Average */}
                      <td className="px-3 py-2 text-center font-semibold border-l border-border">
                        {student.percentage !== null ? `${student.percentage}%` : '-'}
                      </td>
                      <td className={`px-3 py-2 text-center font-bold text-lg ${getLetterGradeColor(student.letter_grade)}`}>
                        {student.letter_grade || '-'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      <GradingConfigModal
        courseCode={code || ''}
        isOpen={showConfigModal}
        onClose={() => setShowConfigModal(false)}
      />
    </div>
  );
}

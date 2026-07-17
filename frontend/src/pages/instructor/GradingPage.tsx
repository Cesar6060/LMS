import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { assignmentService } from '@/services/assignments';
import { isForbidden } from '@/services/api';
import { AccessDenied } from '@/components/AccessDenied';
import type { Assignment, Submission } from '@/types';
import {
  Loader2, ChevronLeft, User, Clock, CheckCircle,
  AlertCircle, FileText, RotateCcw, Paperclip, History, ChevronDown, ChevronUp,
  AlertTriangle
} from 'lucide-react';

export function GradingPage() {
  const { assignmentId } = useParams<{ assignmentId: string }>();

  const [assignment, setAssignment] = useState<Assignment | null>(null);
  const [submissions, setSubmissions] = useState<Submission[]>([]);
  const [selectedSubmission, setSelectedSubmission] = useState<Submission | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isGrading, setIsGrading] = useState(false);
  const [isAllowingResubmit, setIsAllowingResubmit] = useState(false);
  const [error, setError] = useState('');
  const [forbidden, setForbidden] = useState(false);

  // Grading form state
  const [points, setPoints] = useState('');
  const [feedback, setFeedback] = useState('');
  const [showHistory, setShowHistory] = useState(false);
  const [successMessage, setSuccessMessage] = useState('');

  useEffect(() => {
    if (assignmentId) {
      loadData();
    }
  }, [assignmentId]);

  useEffect(() => {
    if (selectedSubmission?.grade) {
      setPoints(String(selectedSubmission.grade.points));
      setFeedback(selectedSubmission.grade.feedback || '');
    } else {
      setPoints('');
      setFeedback('');
    }
    setShowHistory(false);
    setSuccessMessage('');
  }, [selectedSubmission]);

  const loadData = async () => {
    try {
      setIsLoading(true);
      const [assignmentData, submissionsData] = await Promise.all([
        assignmentService.getAssignment(parseInt(assignmentId!)),
        assignmentService.getAssignmentSubmissions(parseInt(assignmentId!)),
      ]);
      setAssignment(assignmentData);
      setSubmissions(submissionsData);
      if (submissionsData.length > 0) {
        setSelectedSubmission(submissionsData[0]);
      }
    } catch (err) {
      if (isForbidden(err)) {
        setForbidden(true);
      } else {
        setError('Failed to load assignment');
        console.error(err);
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleGrade = async () => {
    if (!selectedSubmission || !assignment) return;

    const pointsNum = parseInt(points);
    if (isNaN(pointsNum) || pointsNum < 0 || pointsNum > assignment.max_points) {
      setError(`Points must be between 0 and ${assignment.max_points}`);
      return;
    }

    setIsGrading(true);
    setError('');
    setSuccessMessage('');
    try {
      const isUpdate = !!selectedSubmission.grade;
      const updated = isUpdate
        ? await assignmentService.updateGrade(selectedSubmission.id, {
            points: pointsNum,
            feedback,
          })
        : await assignmentService.gradeSubmission(selectedSubmission.id, {
            points: pointsNum,
            feedback,
          });

      // Update local state
      setSelectedSubmission(updated);
      setSubmissions((prev) =>
        prev.map((s) => (s.id === updated.id ? updated : s))
      );

      // Show success message
      setSuccessMessage(isUpdate ? 'Grade updated successfully!' : 'Grade saved successfully!');

      // Auto-hide success message after 3 seconds
      setTimeout(() => setSuccessMessage(''), 3000);
    } catch (err) {
      setError('Failed to save grade');
      console.error(err);
    } finally {
      setIsGrading(false);
    }
  };

  const handleAllowResubmit = async () => {
    if (!selectedSubmission) return;

    setIsAllowingResubmit(true);
    setError('');
    try {
      await assignmentService.allowResubmission(selectedSubmission.id);
      // Remove from list since status is now draft
      setSubmissions((prev) =>
        prev.filter((s) => s.id !== selectedSubmission.id)
      );
      setSelectedSubmission(null);
    } catch (err) {
      setError('Failed to allow resubmission');
      console.error(err);
    } finally {
      setIsAllowingResubmit(false);
    }
  };

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return 'N/A';
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    });
  };

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (forbidden) {
    return <AccessDenied />;
  }

  if (!assignment) {
    return (
      <div className="container mx-auto px-4 py-8">
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <AlertCircle className="h-12 w-12 text-destructive mb-4" />
            <h3 className="text-lg font-semibold mb-2">Assignment not found</h3>
            <Link to="/dashboard">
              <Button>Back to Dashboard</Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      {/* Navigation */}
      <div className="mb-6">
        <Link to={`/instructor/courses/${assignment.course_code}/manage`}>
          <Button variant="ghost" size="sm">
            <ChevronLeft className="h-4 w-4 mr-1" />
            Back to Course Management
          </Button>
        </Link>
      </div>

      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-2">Grade: {assignment.title}</h1>
        <p className="text-muted-foreground">
          {submissions.length} submission{submissions.length !== 1 ? 's' : ''} •{' '}
          {submissions.filter((s) => s.status === 'graded').length} graded
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Submissions List */}
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle className="text-lg">Submissions</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {submissions.length === 0 ? (
              <div className="p-4 text-center text-muted-foreground">
                No submissions yet
              </div>
            ) : (
              <div className="divide-y">
                {submissions.map((submission) => (
                  <button
                    key={submission.id}
                    onClick={() => setSelectedSubmission(submission)}
                    className={`w-full p-4 text-left hover:bg-muted/50 transition-colors ${
                      selectedSubmission?.id === submission.id
                        ? 'bg-muted'
                        : ''
                    }`}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex items-center gap-2">
                        <User className="h-4 w-4 text-muted-foreground" />
                        <span className="font-medium">
                          {submission.student_name}
                        </span>
                      </div>
                      {submission.status === 'graded' ? (
                        <CheckCircle className="h-4 w-4 text-green-600" />
                      ) : submission.is_late ? (
                        <Clock className="h-4 w-4 text-red-600" />
                      ) : null}
                    </div>
                    <div className="mt-1 text-sm text-muted-foreground">
                      {formatDate(submission.submitted_at)}
                      {submission.is_late && (
                        <span className="ml-2 text-red-600">(Late)</span>
                      )}
                    </div>
                    {submission.grade && (
                      <div className="mt-1 text-sm font-medium">
                        {submission.final_grade !== null && submission.final_grade !== undefined
                          ? submission.final_grade
                          : submission.grade.points}/{assignment.max_points} pts
                      </div>
                    )}
                  </button>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Selected Submission */}
        {selectedSubmission ? (
          <div className="lg:col-span-2 space-y-6">
            {/* Student Info */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <User className="h-5 w-5" />
                  {selectedSubmission.student_name}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-sm text-muted-foreground">
                  <p>{selectedSubmission.student_email}</p>
                  <p>
                    Submitted: {formatDate(selectedSubmission.submitted_at)}
                    {selectedSubmission.is_late && (
                      <span className="ml-2 text-red-600 font-medium">
                        (Late)
                      </span>
                    )}
                  </p>
                </div>

                {/* Late Penalty Info */}
                {selectedSubmission.late_penalty_applied > 0 && (
                  <div className="mt-4 p-3 rounded-lg" style={{ backgroundColor: '#fef3c7', border: '1px solid #f59e0b' }}>
                    <div className="flex items-center gap-2 font-medium" style={{ color: '#92400e' }}>
                      <AlertTriangle className="h-4 w-4" />
                      <span>Late Penalty Applied</span>
                    </div>
                    <p className="text-sm mt-1" style={{ color: '#78350f' }}>
                      -{selectedSubmission.late_penalty_applied} points will be deducted from the final grade
                    </p>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Submission Content */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <FileText className="h-5 w-5" />
                  Submission
                </CardTitle>
              </CardHeader>
              <CardContent>
                {/* Files (Primary) */}
                {selectedSubmission.files && selectedSubmission.files.length > 0 && (
                  <div className="space-y-2 mb-4">
                    <p className="text-sm font-medium">Attached Files:</p>
                    {selectedSubmission.files.map((file) => (
                      <div key={file.id} className="flex items-center gap-2 p-3 bg-muted rounded-lg">
                        <Paperclip className="h-4 w-4 text-muted-foreground" />
                        <a
                          href={file.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-sm text-primary hover:underline"
                        >
                          {file.filename}
                        </a>
                      </div>
                    ))}
                  </div>
                )}
                {/* Comments */}
                {selectedSubmission.content && (
                  <div>
                    <p className="text-sm font-medium mb-2">Comments:</p>
                    <div className="bg-muted/50 rounded-lg p-4 whitespace-pre-wrap font-mono text-sm max-h-96 overflow-y-auto">
                      {selectedSubmission.content}
                    </div>
                  </div>
                )}
                {!selectedSubmission.content && (!selectedSubmission.files || selectedSubmission.files.length === 0) && (
                  <p className="text-sm text-muted-foreground">No content submitted</p>
                )}
              </CardContent>
            </Card>

            {/* Submission History */}
            {selectedSubmission.history && selectedSubmission.history.length > 0 && (
              <Card>
                <CardHeader className="pb-2">
                  <button
                    onClick={() => setShowHistory(!showHistory)}
                    className="w-full flex items-center justify-between"
                  >
                    <CardTitle className="text-lg flex items-center gap-2">
                      <History className="h-5 w-5" />
                      Previous Submissions ({selectedSubmission.history.length})
                    </CardTitle>
                    {showHistory ? (
                      <ChevronUp className="h-5 w-5 text-muted-foreground" />
                    ) : (
                      <ChevronDown className="h-5 w-5 text-muted-foreground" />
                    )}
                  </button>
                </CardHeader>
                {showHistory && (
                  <CardContent className="space-y-4">
                    {selectedSubmission.history.map((historyItem, index) => (
                      <div
                        key={historyItem.id}
                        className="border rounded-lg p-4 bg-muted/30"
                      >
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-sm font-medium">
                            Submission #{selectedSubmission.history!.length - index}
                          </span>
                          <span className="text-sm text-muted-foreground">
                            {formatDate(historyItem.submitted_at)}
                          </span>
                        </div>
                        {historyItem.content && (
                          <div className="mb-2">
                            <p className="text-xs text-muted-foreground mb-1">Comments:</p>
                            <div className="bg-background rounded p-3 whitespace-pre-wrap font-mono text-sm max-h-48 overflow-y-auto">
                              {historyItem.content}
                            </div>
                          </div>
                        )}
                        {historyItem.files_info && historyItem.files_info.length > 0 && (
                          <div className="mb-2">
                            <p className="text-xs text-muted-foreground mb-1">Attached Files:</p>
                            <div className="space-y-1">
                              {historyItem.files_info.map((filename, fileIdx) => (
                                <div key={fileIdx} className="flex items-center gap-2 p-2 bg-background rounded text-sm">
                                  <Paperclip className="h-3 w-3 text-muted-foreground" />
                                  <span>{filename}</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                        {!historyItem.content && (!historyItem.files_info || historyItem.files_info.length === 0) && (
                          <p className="text-sm text-muted-foreground mb-2">No content submitted</p>
                        )}
                        {historyItem.grade_points !== null && (
                          <div className="text-sm">
                            <span className="font-medium">
                              Grade: {historyItem.grade_points}/{assignment.max_points} pts
                            </span>
                            {historyItem.grade_feedback && (
                              <p className="text-muted-foreground mt-1">
                                Feedback: {historyItem.grade_feedback}
                              </p>
                            )}
                          </div>
                        )}
                      </div>
                    ))}
                  </CardContent>
                )}
              </Card>
            )}

            {/* Grading Form */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Grade</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div>
                      <label className="block text-sm font-medium mb-2">
                        Points (out of {assignment.max_points})
                      </label>
                      <input
                        type="number"
                        min="0"
                        max={assignment.max_points}
                        value={points}
                        onChange={(e) => setPoints(e.target.value)}
                        className="w-full px-3 py-2 border rounded-lg bg-background"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium mb-2">Late Penalty</label>
                      <div className="px-3 py-2 border rounded-lg bg-muted/50">
                        <span className={selectedSubmission.late_penalty_applied > 0 ? 'text-yellow-600' : ''}>
                          {selectedSubmission.late_penalty_applied > 0
                            ? `-${selectedSubmission.late_penalty_applied}`
                            : '0'} pts
                        </span>
                      </div>
                    </div>
                    <div>
                      <label className="block text-sm font-medium mb-2">Final Grade</label>
                      <div className="px-3 py-2 border rounded-lg bg-muted/50">
                        <span className="font-medium text-green-600">
                          {points
                            ? Math.max(0, parseInt(points) - (selectedSubmission.late_penalty_applied || 0)).toFixed(0)
                            : '—'} / {assignment.max_points}
                        </span>
                      </div>
                    </div>
                  </div>

                  {selectedSubmission.late_penalty_applied > 0 && points && (
                    <div className="p-3 bg-muted/50 rounded-lg text-sm">
                      <span className="font-medium">Grade Breakdown: </span>
                      Original: {points} pts | Penalty: -{selectedSubmission.late_penalty_applied} pts |
                      Final: {Math.max(0, parseInt(points) - (selectedSubmission.late_penalty_applied || 0))} pts
                    </div>
                  )}

                  <div>
                    <label className="block text-sm font-medium mb-2">
                      Feedback (optional)
                    </label>
                    <textarea
                      value={feedback}
                      onChange={(e) => setFeedback(e.target.value)}
                      placeholder="Enter feedback for the student..."
                      className="w-full h-32 px-3 py-2 border rounded-lg resize-y bg-background"
                    />
                  </div>

                  {error && (
                    <div className="p-3 bg-destructive/10 text-destructive rounded-lg flex items-center gap-2">
                      <AlertCircle className="h-4 w-4" />
                      {error}
                    </div>
                  )}

                  {successMessage && (
                    <div className="p-4 bg-emerald-50 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-700 rounded-lg flex items-center gap-3 font-medium">
                      <CheckCircle className="h-5 w-5 text-emerald-600 dark:text-emerald-400" />
                      {successMessage}
                    </div>
                  )}

                  <div className="flex justify-between">
                    <Button
                      variant="outline"
                      onClick={handleAllowResubmit}
                      disabled={isAllowingResubmit}
                    >
                      {isAllowingResubmit ? (
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      ) : (
                        <RotateCcw className="h-4 w-4 mr-2" />
                      )}
                      Allow Resubmission
                    </Button>
                    <Button onClick={handleGrade} disabled={isGrading || !points}>
                      {isGrading ? (
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      ) : (
                        <CheckCircle className="h-4 w-4 mr-2" />
                      )}
                      {selectedSubmission.grade ? 'Update Grade' : 'Save Grade'}
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        ) : (
          <Card className="lg:col-span-2">
            <CardContent className="py-12 text-center text-muted-foreground">
              Select a submission to grade
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}

import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, Link } from 'react-router';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { assignmentService } from '@/services/assignments';
import { isForbidden } from '@/services/api';
import { AccessDenied } from '@/components/AccessDenied';
import type { Assignment, Submission } from '@/types';
import {
  Loader2, ChevronLeft, Calendar, Award, Clock,
  FileText, Upload, CheckCircle, AlertCircle, Send, Paperclip, X, Users,
  Lock, AlertTriangle
} from 'lucide-react';

export function AssignmentDetailPage() {
  const { code, assignmentId } = useParams<{ code: string; assignmentId: string }>();

  const [assignment, setAssignment] = useState<Assignment | null>(null);
  const [submission, setSubmission] = useState<Submission | null>(null);
  const [content, setContent] = useState('');
  const [newFiles, setNewFiles] = useState<File[]>([]);
  const [filesToDelete, setFilesToDelete] = useState<number[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [forbidden, setForbidden] = useState(false);
  const [saveMessage, setSaveMessage] = useState('');

  // Auto-save refs
  const autoSaveTimeoutRef = useRef<number | null>(null);
  const lastSavedContentRef = useRef<string>('');

  useEffect(() => {
    if (assignmentId) {
      loadAssignment();
    }
  }, [assignmentId]);

  const loadAssignment = async () => {
    try {
      setIsLoading(true);
      const data = await assignmentService.getAssignment(parseInt(assignmentId!));
      setAssignment(data);
      setSubmission(data.my_submission);
      const initialContent = data.my_submission?.content || '';
      setContent(initialContent);
      lastSavedContentRef.current = initialContent;
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

  // Auto-save when content changes (debounced)
  const performAutoSave = useCallback(async (contentToSave: string) => {
    if (!assignment || isSaving || isSubmitting) return;
    if (contentToSave === lastSavedContentRef.current) return;

    setIsSaving(true);
    setSaveMessage('Saving...');
    try {
      const updated = await assignmentService.updateSubmission(assignment.id, { content: contentToSave });
      setSubmission(updated);
      lastSavedContentRef.current = contentToSave;
      setSaveMessage('Saved');
      setTimeout(() => setSaveMessage(''), 2000);
    } catch (err) {
      setSaveMessage('Failed to save');
      console.error('Auto-save failed:', err);
    } finally {
      setIsSaving(false);
    }
  }, [assignment, isSaving, isSubmitting]);

  // Debounced auto-save effect
  useEffect(() => {
    // Only auto-save if we can edit and have an assignment
    const canAutoSave = assignment && (!submission || submission.status === 'draft');
    if (!canAutoSave) return;

    // Clear previous timeout
    if (autoSaveTimeoutRef.current) {
      clearTimeout(autoSaveTimeoutRef.current);
    }

    // Set new timeout for auto-save (2 seconds after typing stops)
    autoSaveTimeoutRef.current = window.setTimeout(() => {
      performAutoSave(content);
    }, 2000);

    return () => {
      if (autoSaveTimeoutRef.current) {
        clearTimeout(autoSaveTimeoutRef.current);
      }
    };
  }, [content, assignment, submission, performAutoSave]);

  // Save on page leave (visibility change or beforeunload)
  useEffect(() => {
    const canAutoSave = assignment && (!submission || submission.status === 'draft');
    if (!canAutoSave) return;

    const saveOnLeave = () => {
      if (content !== lastSavedContentRef.current && assignment) {
        // Use sendBeacon for reliable save on page leave
        const formData = new FormData();
        formData.append('content', content);
        navigator.sendBeacon(
          `/api/assignments/assignments/${assignment.id}/my-submission/`,
          formData
        );
      }
    };

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'hidden') {
        saveOnLeave();
      }
    };

    const handleBeforeUnload = () => {
      saveOnLeave();
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    window.addEventListener('beforeunload', handleBeforeUnload);

    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      window.removeEventListener('beforeunload', handleBeforeUnload);
    };
  }, [content, assignment, submission]);

  const handleSubmit = async () => {
    if (!assignment) return;

    // First save content and files, then submit
    setIsSubmitting(true);
    setError('');
    try {
      // Save with files if present
      await assignmentService.updateSubmission(assignment.id, {
        content,
        files: newFiles.length > 0 ? newFiles : undefined,
        deleteFileIds: filesToDelete.length > 0 ? filesToDelete : undefined
      });
      const updated = await assignmentService.submitAssignment(assignment.id);
      setSubmission(updated);
      setNewFiles([]); // Clear files after successful submit
      setFilesToDelete([]);
    } catch (err: unknown) {
      const error = err as { response?: { data?: { non_field_errors?: string[]; detail?: string; error?: string } } };
      const errorMessage = error.response?.data?.non_field_errors?.[0]
        || error.response?.data?.detail
        || error.response?.data?.error
        || 'Failed to submit';
      setError(errorMessage);
      console.error(err);
    } finally {
      setIsSubmitting(false);
    }
  };

  // Calculate total files (existing + new - deleted)
  const existingFiles = submission?.files?.filter(f => !filesToDelete.includes(f.id)) || [];
  const totalFileCount = existingFiles.length + newFiles.length;
  const canAddMoreFiles = totalFileCount < 3;

  const handleAddFiles = (files: FileList | null) => {
    if (!files) return;
    const newFilesArray = Array.from(files);
    const availableSlots = 3 - totalFileCount;
    const filesToAdd = newFilesArray.slice(0, availableSlots);
    if (filesToAdd.length > 0) {
      setNewFiles(prev => [...prev, ...filesToAdd]);
    }
    if (newFilesArray.length > availableSlots) {
      setError(`Only ${availableSlots} more file(s) can be added. Maximum is 3.`);
    }
  };

  const handleRemoveNewFile = (index: number) => {
    setNewFiles(prev => prev.filter((_, i) => i !== index));
  };

  const handleDeleteExistingFile = (fileId: number) => {
    setFilesToDelete(prev => [...prev, fileId]);
  };

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return 'No due date';
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', {
      weekday: 'short',
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    });
  };

  const getDueStatus = () => {
    if (!assignment?.due_date) return null;
    const now = new Date();
    const due = new Date(assignment.due_date);
    const diff = due.getTime() - now.getTime();
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));
    const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));

    if (diff < 0) {
      return { text: 'Overdue', color: 'text-red-600', late: true };
    } else if (days === 0) {
      return { text: `Due in ${hours} hours`, color: 'text-yellow-600', late: false };
    } else if (days === 1) {
      return { text: 'Due tomorrow', color: 'text-yellow-600', late: false };
    } else {
      return { text: `Due in ${days} days`, color: 'text-muted-foreground', late: false };
    }
  };

  const formatDateShort = (dateStr: string | null) => {
    if (!dateStr) return null;
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: 'numeric',
      minute: '2-digit'
    });
  };

  const calculatePotentialPenalty = () => {
    if (!assignment?.late_penalty_percent || !dueStatus?.late || assignment?.is_closed) return null;
    if (!assignment.due_date) return null;

    const dueDate = new Date(assignment.due_date);
    const now = new Date();
    const timeLate = now.getTime() - dueDate.getTime();

    let unitsLate;
    if (assignment.late_penalty_interval === 'hour') {
      unitsLate = timeLate / (1000 * 60 * 60);
    } else {
      unitsLate = Math.ceil(timeLate / (1000 * 60 * 60 * 24));
    }

    let penaltyPercent = unitsLate * assignment.late_penalty_percent;
    if (assignment.max_late_penalty) {
      penaltyPercent = Math.min(penaltyPercent, assignment.max_late_penalty);
    }

    const penaltyPoints = (penaltyPercent / 100) * assignment.max_points;
    return {
      percent: penaltyPercent.toFixed(1),
      points: penaltyPoints.toFixed(1),
      unitsLate: Math.ceil(unitsLate)
    };
  };

  // Can edit if no submission yet OR submission is still a draft (and not closed)
  const canEdit = (!submission || submission.status === 'draft') && !assignment?.is_closed;
  const isGraded = submission?.status === 'graded';
  const dueStatus = getDueStatus();
  const potentialPenalty = calculatePotentialPenalty();

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

  if (error && !assignment) {
    return (
      <div className="container mx-auto px-4 py-8">
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <AlertCircle className="h-12 w-12 text-destructive mb-4" />
            <h3 className="text-lg font-semibold mb-2">Error</h3>
            <p className="text-muted-foreground mb-4">{error}</p>
            <Link to="/courses">
              <Button>Back to Courses</Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!assignment) return null;

  return (
    <div className="container mx-auto px-4 py-8 max-w-4xl">
      {/* Navigation */}
      <div className="mb-6">
        <Link to={`/courses/${code}`}>
          <Button variant="ghost" size="sm">
            <ChevronLeft className="h-4 w-4 mr-1" />
            Back to Course
          </Button>
        </Link>
      </div>

      {/* Assignment Header */}
      <div className="mb-8">
        <p className="text-sm text-muted-foreground mb-1">
          {assignment.course_code} &gt; {assignment.unit_title}
        </p>
        <h1 className="text-3xl font-bold mb-4">{assignment.title}</h1>

        <div className="flex flex-wrap gap-4 text-sm">
          <div className="flex items-center gap-2">
            <Award className="h-4 w-4 text-muted-foreground" />
            <span>{assignment.max_points} points</span>
          </div>
          <div className="flex items-center gap-2">
            <Calendar className="h-4 w-4 text-muted-foreground" />
            <span>{formatDate(assignment.due_date)}</span>
          </div>
          {assignment.is_closed ? (
            <div className="flex items-center gap-2 text-red-600">
              <Lock className="h-4 w-4" />
              <span>Closed</span>
            </div>
          ) : dueStatus && (
            <div className={`flex items-center gap-2 ${dueStatus.color}`}>
              <Clock className="h-4 w-4" />
              <span>{dueStatus.text}</span>
            </div>
          )}
        </div>

        {/* Availability Window Info */}
        {(assignment.available_from || assignment.available_until) && (
          <div className="mt-4 p-3 bg-muted/50 rounded-lg text-sm">
            <div className="flex flex-wrap gap-6">
              {assignment.available_from && (
                <div>
                  <span className="text-muted-foreground">Opens: </span>
                  <span>{formatDateShort(assignment.available_from)}</span>
                </div>
              )}
              {assignment.available_until && (
                <div>
                  <span className="text-muted-foreground">Closes: </span>
                  <span>{formatDateShort(assignment.available_until)}</span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Late Penalty Policy Info */}
        {assignment.late_penalty_percent && (
          <div className="mt-4 p-3 rounded-lg text-sm" style={{ backgroundColor: '#fef3c7', border: '1px solid #f59e0b' }}>
            <div className="flex items-center gap-2 font-medium" style={{ color: '#92400e' }}>
              <AlertTriangle className="h-4 w-4" />
              <span>Late Submission Policy</span>
            </div>
            <p className="mt-1" style={{ color: '#78350f' }}>
              {assignment.late_penalty_percent}% deducted per {assignment.late_penalty_interval === 'hour' ? 'hour' : 'day'} late
              {assignment.max_late_penalty && ` (max ${assignment.max_late_penalty}%)`}
            </p>
          </div>
        )}
      </div>

      {/* Assignment Description */}
      {assignment.description && (
        <Card className="mb-6">
          <CardHeader>
            <CardTitle className="text-lg">Instructions</CardTitle>
          </CardHeader>
          <CardContent className="prose prose-neutral dark:prose-invert max-w-none">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {assignment.description}
            </ReactMarkdown>
          </CardContent>
        </Card>
      )}

      {/* Grade Display */}
      {isGraded && submission?.grade && (
        <Card className="mb-6 border-2 border-green-500 bg-green-100 dark:bg-green-900/40 dark:border-green-500">
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2 text-green-800 dark:text-green-300">
              <CheckCircle className="h-5 w-5" />
              Graded
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-4 mb-4">
              <div className="text-3xl font-bold text-green-800 dark:text-green-200">
                {submission.final_grade !== null && submission.final_grade !== undefined
                  ? submission.final_grade
                  : submission.grade.points}/{assignment.max_points}
              </div>
              <div className="text-lg text-green-700 dark:text-green-300">
                ({submission.grade.percentage}%)
              </div>
            </div>
            {/* Late Penalty Applied */}
            {submission.late_penalty_applied > 0 && (
              <div className="mb-4 p-3 rounded-lg" style={{ backgroundColor: '#fef3c7', border: '1px solid #f59e0b' }}>
                <div className="text-sm">
                  <span className="font-medium" style={{ color: '#92400e' }}>Late Penalty Applied:</span>
                  <span className="ml-2" style={{ color: '#78350f' }}>-{submission.late_penalty_applied} points</span>
                </div>
                <div className="text-xs mt-1" style={{ color: '#92400e' }}>
                  Original: {submission.grade.points} pts | Penalty: -{submission.late_penalty_applied} pts | Final: {submission.final_grade} pts
                </div>
              </div>
            )}
            {submission.grade.feedback && (
              <div>
                <h4 className="font-medium mb-2 text-green-900 dark:text-green-100">Feedback</h4>
                <p className="text-green-800 dark:text-green-200 whitespace-pre-wrap">
                  {submission.grade.feedback}
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Instructor View */}
      {assignment.is_instructor && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Users className="h-5 w-5" />
              Submissions Overview
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-8 mb-6">
              <div>
                <div className="text-3xl font-bold">{assignment.submission_count ?? 0}</div>
                <p className="text-sm text-muted-foreground">Pending Review</p>
              </div>
              <div>
                <div className="text-3xl font-bold text-green-600">{assignment.graded_count ?? 0}</div>
                <p className="text-sm text-muted-foreground">Graded</p>
              </div>
            </div>
            <Link to={`/instructor/assignments/${assignment.id}/grade`}>
              <Button>
                <CheckCircle className="h-4 w-4 mr-2" />
                Grade Submissions
              </Button>
            </Link>
          </CardContent>
        </Card>
      )}

      {/* Student Submission Form */}
      {!assignment.is_instructor && (
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <FileText className="h-5 w-5" />
            Your Submission
            {assignment.is_closed ? (
              <span className="ml-auto text-sm font-normal px-2 py-1 rounded bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200">
                <Lock className="h-3 w-3 inline mr-1" />
                Closed
              </span>
            ) : submission?.status && (
              <span
                className={`ml-auto text-sm font-normal px-2 py-1 rounded ${
                  submission.status === 'draft'
                    ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200'
                    : submission.status === 'submitted'
                    ? 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200'
                    : 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                }`}
              >
                {submission.status.charAt(0).toUpperCase() + submission.status.slice(1)}
              </span>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {/* Closed Assignment Message */}
          {assignment.is_closed && !isGraded && (
            <div className="flex flex-col items-center justify-center py-8">
              <Lock className="h-12 w-12 text-red-500 mb-4" />
              <h3 className="text-lg font-semibold mb-2">Submissions Closed</h3>
              <p className="text-muted-foreground text-center max-w-md">
                This assignment is no longer accepting submissions.
                {assignment.available_until && (
                  <span className="block mt-2">
                    Submissions closed on {formatDateShort(assignment.available_until)}.
                  </span>
                )}
              </p>
            </div>
          )}

          {/* Late Penalty Warning */}
          {canEdit && potentialPenalty && (
            <div className="mb-4 p-4 rounded-lg" style={{ backgroundColor: '#fee2e2', border: '1px solid #ef4444' }}>
              <div className="flex items-start gap-3">
                <AlertTriangle className="h-5 w-5 mt-0.5" style={{ color: '#dc2626' }} />
                <div>
                  <p className="font-medium" style={{ color: '#7f1d1d' }}>Late Submission Warning</p>
                  <p className="text-sm mt-1" style={{ color: '#991b1b' }}>
                    This assignment is {potentialPenalty.unitsLate} {assignment.late_penalty_interval}(s) late.
                    Submitting now will result in a <strong>{potentialPenalty.percent}%</strong> penalty
                    ({potentialPenalty.points} points deducted from your grade).
                  </p>
                </div>
              </div>
            </div>
          )}

          {canEdit ? (
            <>
              {/* File Upload (Primary) */}
              <div className="mb-4">
                <label className="block text-sm font-medium mb-2">
                  Upload Files (max 3)
                </label>
                <p className="text-xs text-muted-foreground mb-3">
                  Accepted: Images (.png, .jpg, .gif), Documents (.pdf, .doc, .docx), Archives (.zip), Code files (.py, .js, .html, .css)
                </p>

                {/* Existing files from server */}
                {existingFiles.length > 0 && (
                  <div className="space-y-2 mb-3">
                    {existingFiles.map((file) => (
                      <div key={file.id} className="flex items-center gap-2 p-3 bg-muted rounded-lg">
                        <Paperclip className="h-4 w-4 text-muted-foreground" />
                        <span className="text-sm flex-1 truncate">{file.filename}</span>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDeleteExistingFile(file.id)}
                          className="h-8 w-8 p-0 text-destructive hover:text-destructive"
                        >
                          <X className="h-4 w-4" />
                        </Button>
                      </div>
                    ))}
                  </div>
                )}

                {/* New files to upload */}
                {newFiles.length > 0 && (
                  <div className="space-y-2 mb-3">
                    {newFiles.map((file, index) => (
                      <div key={index} className="flex items-center gap-2 p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-200 dark:border-blue-800">
                        <Paperclip className="h-4 w-4 text-blue-600" />
                        <span className="text-sm flex-1 truncate">{file.name}</span>
                        <span className="text-xs text-blue-600">(new)</span>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleRemoveNewFile(index)}
                          className="h-8 w-8 p-0"
                        >
                          <X className="h-4 w-4" />
                        </Button>
                      </div>
                    ))}
                  </div>
                )}

                {/* Upload button */}
                {canAddMoreFiles && (
                  <label className="flex items-center justify-center gap-2 p-4 border-2 border-dashed rounded-lg cursor-pointer hover:bg-muted/50 transition-colors">
                    <Upload className="h-5 w-5 text-muted-foreground" />
                    <span className="text-sm text-muted-foreground">
                      Click to upload ({3 - totalFileCount} remaining)
                    </span>
                    <input
                      type="file"
                      multiple
                      accept=".png,.jpg,.jpeg,.gif,.pdf,.doc,.docx,.zip,.py,.js,.html,.css,.txt,.json,.md"
                      className="hidden"
                      onChange={(e) => handleAddFiles(e.target.files)}
                    />
                  </label>
                )}

                {!canAddMoreFiles && (
                  <p className="text-sm text-muted-foreground">
                    Maximum 3 files reached
                  </p>
                )}
              </div>

              {/* Comments (Optional) */}
              <div className="mb-4">
                <label className="block text-sm font-medium mb-2">
                  Comments (optional)
                </label>
                <textarea
                  value={content}
                  onChange={(e) => setContent(e.target.value)}
                  placeholder="Add any notes or comments about your submission..."
                  className="w-full h-32 p-4 border rounded-lg resize-y font-mono text-sm bg-background"
                />
              </div>

              {error && (
                <div className="mt-4 p-3 bg-destructive/10 text-destructive rounded-lg flex items-center gap-2">
                  <AlertCircle className="h-4 w-4" />
                  {error}
                </div>
              )}

              <div className="mt-4 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  {saveMessage && (
                    <span className={`text-sm ${saveMessage === 'Saving...' ? 'text-muted-foreground' : saveMessage === 'Failed to save' ? 'text-destructive' : 'text-green-600'}`}>
                      {saveMessage}
                    </span>
                  )}
                </div>

                <Button
                  onClick={handleSubmit}
                  disabled={isSubmitting || (!content.trim() && totalFileCount === 0)}
                >
                  {isSubmitting ? (
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  ) : (
                    <Send className="h-4 w-4 mr-2" />
                  )}
                  Submit
                </Button>
              </div>

              {dueStatus?.late && !assignment.allow_late && (
                <div className="mt-4 p-3 bg-destructive/10 text-destructive rounded-lg">
                  This assignment is past due and no longer accepts submissions.
                </div>
              )}
            </>
          ) : (
            <div className="bg-muted/50 rounded-lg p-4">
              <p className="text-sm text-muted-foreground mb-4">
                Submitted on {submission?.submitted_at ? formatDate(submission.submitted_at) : 'N/A'}
                {submission?.is_late && (
                  <span className="ml-2 text-red-600">(Late)</span>
                )}
              </p>
              {/* Files (Primary) */}
              {submission?.files && submission.files.length > 0 && (
                <div className="space-y-2 mb-4">
                  <p className="text-sm font-medium">Attached Files:</p>
                  {submission.files.map((file) => (
                    <div key={file.id} className="flex items-center gap-2 p-3 bg-background rounded-lg border">
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
              {submission?.content && (
                <div>
                  <p className="text-sm font-medium mb-2">Comments:</p>
                  <div className="whitespace-pre-wrap font-mono text-sm bg-background rounded-lg p-3 border">
                    {submission.content}
                  </div>
                </div>
              )}
              {!submission?.content && (!submission?.files || submission.files.length === 0) && (
                <p className="text-sm text-muted-foreground">No content submitted</p>
              )}
            </div>
          )}
        </CardContent>
      </Card>
      )}
    </div>
  );
}

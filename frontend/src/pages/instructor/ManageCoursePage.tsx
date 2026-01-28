import { useState, useEffect, type FormEvent } from 'react';
import { useParams, Link, useNavigate } from 'react-router';
import { useAuth } from '@/contexts/AuthContext';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { courseService, type CourseDetail, type UnitWithLessons, type LessonListItem } from '@/services/courses';
import { assignmentService } from '@/services/assignments';
import type { AssignmentListItem } from '@/types';
import {
  Loader2, ChevronLeft, Plus, Trash2, Play, FileText,
  Copy, CheckCircle, Settings, BookOpen, ClipboardList, Table, Megaphone, Eye, Users, FileQuestion
} from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/Dialog';

/**
 * Extract YouTube video ID from various URL formats or return the ID if already extracted.
 * Supports:
 * - https://www.youtube.com/watch?v=VIDEO_ID
 * - https://youtu.be/VIDEO_ID
 * - https://www.youtube.com/embed/VIDEO_ID
 * - VIDEO_ID (already extracted)
 */
function extractYouTubeVideoId(input: string): string {
  if (!input) return '';

  const trimmed = input.trim();

  // Try to match various YouTube URL patterns
  const patterns = [
    /(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})/,
    /^([a-zA-Z0-9_-]{11})$/, // Just the ID itself
  ];

  for (const pattern of patterns) {
    const match = trimmed.match(pattern);
    if (match && match[1]) {
      return match[1];
    }
  }

  // Return as-is if no pattern matched (let backend validate)
  return trimmed;
}

type EditingUnit = { id?: number; title: string };
type EditingLesson = {
  id?: number;
  title: string;
  content: string;
  video_type: 'none' | 'youtube';
  video_id: string;
  order: number;
};
type EditingAssignment = {
  id?: number;
  title: string;
  description: string;
  max_points: number;
  due_date: string;
  allow_late: boolean;
  available_from: string;
  available_until: string;
  late_penalty_percent: number | null;
  late_penalty_interval: 'day' | 'hour';
  max_late_penalty: number | null;
};

export function ManageCoursePage() {
  const { code } = useParams<{ code: string }>();
  const { user } = useAuth();
  const navigate = useNavigate();

  const [course, setCourse] = useState<CourseDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  // Unit modal state
  const [showUnitModal, setShowUnitModal] = useState(false);
  const [editingUnit, setEditingUnit] = useState<EditingUnit | null>(null);
  const [unitLoading, setUnitLoading] = useState(false);

  // Lesson modal state
  const [showLessonModal, setShowLessonModal] = useState(false);
  const [editingLesson, setEditingLesson] = useState<EditingLesson | null>(null);
  const [selectedUnitId, setSelectedUnitId] = useState<number | null>(null);
  const [lessonLoading, setLessonLoading] = useState(false);
  const [lessonError, setLessonError] = useState('');

  // Assignment state
  const [assignments, setAssignments] = useState<AssignmentListItem[]>([]);
  const [showAssignmentModal, setShowAssignmentModal] = useState(false);
  const [editingAssignment, setEditingAssignment] = useState<EditingAssignment | null>(null);
  const [selectedUnitForAssignment, setSelectedUnitForAssignment] = useState<number | null>(null);
  const [assignmentLoading, setAssignmentLoading] = useState(false);
  const [assignmentError, setAssignmentError] = useState('');

  // Enrollment code copy state
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (code) {
      loadCourse();
    }
  }, [code]);

  const loadCourse = async () => {
    try {
      setIsLoading(true);
      const [data, assignmentsData] = await Promise.all([
        courseService.getCourse(code!),
        assignmentService.getCourseAssignments(code!),
      ]);
      setCourse(data);
      setAssignments(assignmentsData);

      // Check if user is the instructor
      if (data.instructor.id !== user?.id) {
        navigate('/courses');
      }
    } catch (err) {
      setError('Failed to load course');
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCopyEnrollmentCode = async () => {
    if (course?.enrollment_code) {
      await navigator.clipboard.writeText(course.enrollment_code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  // Unit handlers
  const openAddUnitModal = () => {
    setEditingUnit({ title: '' });
    setShowUnitModal(true);
  };

  const openEditUnitModal = (unit: UnitWithLessons) => {
    setEditingUnit({ id: unit.id, title: unit.title });
    setShowUnitModal(true);
  };

  const handleSaveUnit = async (e: FormEvent) => {
    e.preventDefault();
    if (!editingUnit || !course) return;

    setUnitLoading(true);
    try {
      if (editingUnit.id) {
        // Update existing unit
        await courseService.updateUnit(editingUnit.id, { title: editingUnit.title });
      } else {
        // Create new unit
        const nextOrder = course.units.length > 0
          ? Math.max(...course.units.map(u => u.order)) + 1
          : 1;
        await courseService.createUnit(course.code, {
          title: editingUnit.title,
          order: nextOrder,
        });
      }
      await loadCourse();
      setShowUnitModal(false);
      setEditingUnit(null);
    } catch (err) {
      console.error('Failed to save unit:', err);
    } finally {
      setUnitLoading(false);
    }
  };

  const handleDeleteUnit = async (unitId: number) => {
    if (!confirm('Are you sure you want to delete this unit? All lessons in this unit will also be deleted.')) {
      return;
    }

    try {
      await courseService.deleteUnit(unitId);
      await loadCourse();
    } catch (err) {
      console.error('Failed to delete unit:', err);
    }
  };

  // Lesson handlers
  const openAddLessonModal = (unitId: number) => {
    const unit = course?.units.find(u => u.id === unitId);
    const nextOrder = unit && unit.lessons.length > 0
      ? Math.max(...unit.lessons.map(l => l.order)) + 1
      : 1;

    setSelectedUnitId(unitId);
    setLessonError('');
    setEditingLesson({
      title: '',
      content: '',
      video_type: 'none',
      video_id: '',
      order: nextOrder,
    });
    setShowLessonModal(true);
  };

  const openEditLessonModal = (lesson: LessonListItem, unitId: number) => {
    setSelectedUnitId(unitId);
    // Only support 'youtube' or 'none' - treat any other type as 'none'
    const videoType = lesson.video_type === 'youtube' ? 'youtube' : 'none';
    setEditingLesson({
      id: lesson.id,
      title: lesson.title,
      content: lesson.content || '',
      video_type: videoType,
      video_id: lesson.video_id || '',
      order: lesson.order,
    });
    setShowLessonModal(true);
  };

  const handleSaveLesson = async (e: FormEvent) => {
    e.preventDefault();
    if (!editingLesson || !selectedUnitId) return;

    setLessonLoading(true);
    setLessonError('');
    try {
      // Extract video ID from URL if a full URL was pasted
      const videoId = editingLesson.video_type === 'youtube'
        ? extractYouTubeVideoId(editingLesson.video_id)
        : '';

      const lessonData = {
        title: editingLesson.title,
        content: editingLesson.content || '',
        video_type: editingLesson.video_type,
        video_id: videoId,
        order: editingLesson.order,
      };

      if (editingLesson.id) {
        // Update existing lesson
        await courseService.updateLesson(editingLesson.id, lessonData);
      } else {
        // Create new lesson
        await courseService.createLesson(selectedUnitId, lessonData);
      }
      await loadCourse();
      setShowLessonModal(false);
      setEditingLesson(null);
      setSelectedUnitId(null);
    } catch (err: unknown) {
      console.error('Failed to save lesson:', err);
      const error = err as { response?: { data?: { detail?: string } }; message?: string };
      setLessonError(error.response?.data?.detail || error.message || 'Failed to save lesson');
    } finally {
      setLessonLoading(false);
    }
  };

  const handleDeleteLesson = async (lessonId: number) => {
    if (!confirm('Are you sure you want to delete this lesson?')) {
      return;
    }

    try {
      await courseService.deleteLesson(lessonId);
      await loadCourse();
    } catch (err) {
      console.error('Failed to delete lesson:', err);
    }
  };

  // Assignment handlers
  const openAddAssignmentModal = (unitId: number) => {
    setSelectedUnitForAssignment(unitId);
    setAssignmentError('');
    setEditingAssignment({
      title: '',
      description: '',
      max_points: 100,
      due_date: '',
      allow_late: true,
      available_from: '',
      available_until: '',
      late_penalty_percent: null,
      late_penalty_interval: 'day',
      max_late_penalty: null,
    });
    setShowAssignmentModal(true);
  };

  const handleSaveAssignment = async (e: FormEvent) => {
    e.preventDefault();
    if (!editingAssignment) return;

    if (!selectedUnitForAssignment) {
      setAssignmentError('No unit selected. Please close this dialog and try again.');
      return;
    }

    setAssignmentLoading(true);
    setAssignmentError('');
    try {
      const assignmentData = {
        title: editingAssignment.title,
        description: editingAssignment.description,
        max_points: editingAssignment.max_points,
        due_date: editingAssignment.due_date || null,
        allow_late: editingAssignment.allow_late,
        available_from: editingAssignment.available_from || null,
        available_until: editingAssignment.available_until || null,
        late_penalty_percent: editingAssignment.late_penalty_percent,
        late_penalty_interval: editingAssignment.late_penalty_interval,
        max_late_penalty: editingAssignment.max_late_penalty,
      };

      if (editingAssignment.id) {
        await assignmentService.updateAssignment(editingAssignment.id, assignmentData);
      } else {
        await assignmentService.createAssignment(selectedUnitForAssignment, assignmentData);
      }
      await loadCourse();
      setShowAssignmentModal(false);
      setEditingAssignment(null);
      setSelectedUnitForAssignment(null);
    } catch (err: unknown) {
      console.error('Failed to save assignment:', err);
      const error = err as { response?: { data?: { detail?: string; [key: string]: unknown } }; message?: string };
      const errorData = error.response?.data;
      let errorMessage = 'Failed to save assignment';
      if (errorData?.detail) {
        errorMessage = errorData.detail;
      } else if (errorData) {
        // Handle field-specific errors
        const fieldErrors = Object.entries(errorData)
          .filter(([key]) => key !== 'detail')
          .map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join(', ') : value}`)
          .join('; ');
        if (fieldErrors) {
          errorMessage = fieldErrors;
        }
      } else if (error.message) {
        errorMessage = error.message;
      }
      setAssignmentError(errorMessage);
    } finally {
      setAssignmentLoading(false);
    }
  };

  const handleDeleteAssignment = async (assignmentId: number) => {
    if (!confirm('Are you sure you want to delete this assignment?')) {
      return;
    }

    try {
      await assignmentService.deleteAssignment(assignmentId);
      await loadCourse();
    } catch (err) {
      console.error('Failed to delete assignment:', err);
    }
  };

  // Group assignments by unit
  const getUnitAssignments = (unitId: number) => {
    return assignments.filter(a => {
      const unit = course?.units.find(u => u.title === a.unit_title);
      return unit?.id === unitId;
    });
  };

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (error || !course) {
    return (
      <div className="container mx-auto px-4 py-8">
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <BookOpen className="h-12 w-12 text-muted-foreground mb-4" />
            <h3 className="text-lg font-semibold mb-2">Course not found</h3>
            <p className="text-muted-foreground mb-4">{error}</p>
            <Link to="/courses">
              <Button>Back to Courses</Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-4">
          <Link to={`/courses/${course.code}`}>
            <Button variant="ghost" size="sm">
              <ChevronLeft className="h-4 w-4 mr-1" />
              View Course
            </Button>
          </Link>
        </div>
      </div>

      {/* Course Info */}
      <div className="mb-8">
        <div className="flex items-center gap-2 mb-2">
          <Settings className="h-5 w-5 text-muted-foreground" />
          <span className="text-sm text-muted-foreground">Managing</span>
        </div>
        <h1 className="text-3xl font-bold mb-2">{course.title}</h1>
        <p className="text-sm font-mono text-muted-foreground">{course.code}</p>
      </div>

      {/* Quick Actions */}
      <div className="grid gap-4 md:grid-cols-4 mb-8">
        <Link to={`/courses/${course.code}`}>
          <Card className="hover:shadow-md transition-shadow cursor-pointer h-full">
            <CardContent className="py-4 flex items-center gap-3">
              <Eye className="h-5 w-5 text-muted-foreground" />
              <span className="font-medium">View Course</span>
            </CardContent>
          </Card>
        </Link>
        <Link to={`/instructor/courses/${course.code}/gradebook`}>
          <Card className="hover:shadow-md transition-shadow cursor-pointer h-full">
            <CardContent className="py-4 flex items-center gap-3">
              <Table className="h-5 w-5 text-muted-foreground" />
              <span className="font-medium">Gradebook</span>
            </CardContent>
          </Card>
        </Link>
        <Link to={`/courses/${course.code}/announcements`}>
          <Card className="hover:shadow-md transition-shadow cursor-pointer h-full">
            <CardContent className="py-4 flex items-center gap-3">
              <Megaphone className="h-5 w-5 text-muted-foreground" />
              <span className="font-medium">Announcements</span>
            </CardContent>
          </Card>
        </Link>
        <Link to={`/instructor/courses/${course.code}/students`}>
          <Card className="hover:shadow-md transition-shadow cursor-pointer h-full">
            <CardContent className="py-4 flex items-center gap-3">
              <Users className="h-5 w-5 text-muted-foreground" />
              <span className="font-medium">{course.student_count} Students</span>
            </CardContent>
          </Card>
        </Link>
        <Link to={`/instructor/courses/${course.code}/quizzes`}>
          <Card className="hover:shadow-md transition-shadow cursor-pointer h-full">
            <CardContent className="py-4 flex items-center gap-3">
              <FileQuestion className="h-5 w-5 text-muted-foreground" />
              <span className="font-medium">Quizzes</span>
            </CardContent>
          </Card>
        </Link>
      </div>

      {/* Enrollment Code Card */}
      <Card className="mb-8">
        <CardHeader>
          <CardTitle className="text-lg">Enrollment Code</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-4">
            <code className="bg-muted px-4 py-2 rounded-md text-lg font-mono tracking-widest">
              {course.enrollment_code}
            </code>
            <Button variant="outline" size="sm" onClick={handleCopyEnrollmentCode}>
              {copied ? (
                <>
                  <CheckCircle className="h-4 w-4 mr-2 text-green-500" />
                  Copied!
                </>
              ) : (
                <>
                  <Copy className="h-4 w-4 mr-2" />
                  Copy
                </>
              )}
            </Button>
          </div>
          <p className="text-sm text-muted-foreground mt-2">
            Share this code with students so they can enroll in your course.
          </p>
        </CardContent>
      </Card>

      {/* Units & Lessons */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-semibold">Course Content</h2>
          <Button onClick={openAddUnitModal}>
            <Plus className="h-4 w-4 mr-2" />
            Add Unit
          </Button>
        </div>

        {course.units.length === 0 ? (
          <Card>
            <CardContent className="py-12 text-center text-muted-foreground">
              <BookOpen className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p>No units yet. Add your first unit to get started.</p>
            </CardContent>
          </Card>
        ) : (
          course.units.map((unit, unitIndex) => (
            <Card key={unit.id}>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <CardTitle className="text-lg">
                      Unit {unitIndex + 1}: {unit.title}
                    </CardTitle>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => openEditUnitModal(unit)}
                    >
                      Edit
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-destructive hover:text-destructive"
                      onClick={() => handleDeleteUnit(unit.id)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="pt-0">
                {unit.lessons.length === 0 ? (
                  <p className="text-sm text-muted-foreground py-4">
                    No lessons in this unit yet.
                  </p>
                ) : (
                  <ul className="divide-y mb-4">
                    {unit.lessons.map((lesson, lessonIndex) => (
                      <li
                        key={lesson.id}
                        className="flex items-center justify-between py-3"
                      >
                        <div className="flex items-center gap-3">
                          {lesson.video_type !== 'none' ? (
                            <Play className="h-4 w-4 text-muted-foreground" />
                          ) : (
                            <FileText className="h-4 w-4 text-muted-foreground" />
                          )}
                          <span>
                            {unitIndex + 1}.{lessonIndex + 1} {lesson.title}
                          </span>
                        </div>
                        <div className="flex items-center gap-2">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => openEditLessonModal(lesson, unit.id)}
                          >
                            Edit
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-destructive hover:text-destructive"
                            onClick={() => handleDeleteLesson(lesson.id)}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => openAddLessonModal(unit.id)}
                  >
                    <Plus className="h-4 w-4 mr-2" />
                    Add Lesson
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => openAddAssignmentModal(unit.id)}
                  >
                    <ClipboardList className="h-4 w-4 mr-2" />
                    Add Assignment
                  </Button>
                </div>

                {/* Unit Assignments */}
                {getUnitAssignments(unit.id).length > 0 && (
                  <div className="mt-4 pt-4 border-t">
                    <h4 className="text-sm font-medium mb-2 flex items-center gap-2">
                      <ClipboardList className="h-4 w-4" />
                      Assignments
                    </h4>
                    <ul className="space-y-2">
                      {getUnitAssignments(unit.id).map(assignment => (
                        <li
                          key={assignment.id}
                          className="flex items-center justify-between bg-muted/50 rounded-lg px-3 py-2"
                        >
                          <div>
                            <span className="font-medium">{assignment.title}</span>
                            <div className="text-xs text-muted-foreground">
                              {assignment.max_points} pts
                              {assignment.due_date && (
                                <span className="ml-2">
                                  Due: {new Date(assignment.due_date).toLocaleDateString()}
                                </span>
                              )}
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            <Link to={`/instructor/assignments/${assignment.id}/grade`}>
                              <Button variant="ghost" size="sm">
                                Grade
                              </Button>
                            </Link>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="text-destructive hover:text-destructive"
                              onClick={() => handleDeleteAssignment(assignment.id)}
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </CardContent>
            </Card>
          ))
        )}
      </div>

      {/* Unit Modal */}
      <Dialog open={showUnitModal} onOpenChange={setShowUnitModal}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {editingUnit?.id ? 'Edit Unit' : 'Add Unit'}
            </DialogTitle>
            <DialogDescription>
              {editingUnit?.id
                ? 'Update the unit title.'
                : 'Create a new unit for your course.'}
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleSaveUnit}>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <label htmlFor="unit-title" className="text-sm font-medium">
                  Unit Title
                </label>
                <Input
                  id="unit-title"
                  type="text"
                  placeholder="e.g., Introduction to Unity"
                  value={editingUnit?.title || ''}
                  onChange={(e) =>
                    setEditingUnit(prev => prev ? { ...prev, title: e.target.value } : null)
                  }
                  required
                />
              </div>
            </div>
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setShowUnitModal(false)}
                disabled={unitLoading}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={unitLoading}>
                {unitLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                {editingUnit?.id ? 'Save Changes' : 'Add Unit'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Lesson Modal */}
      <Dialog open={showLessonModal} onOpenChange={setShowLessonModal}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>
              {editingLesson?.id ? 'Edit Lesson' : 'Add Lesson'}
            </DialogTitle>
            <DialogDescription>
              {editingLesson?.id
                ? 'Update the lesson details.'
                : 'Create a new lesson for this unit.'}
            </DialogDescription>
          </DialogHeader>
          {lessonError && (
            <div className="bg-destructive/10 border border-destructive/20 text-destructive rounded-md px-4 py-3 text-sm">
              {lessonError}
            </div>
          )}
          <form onSubmit={handleSaveLesson}>
            <div className="space-y-4 py-4 max-h-[60vh] overflow-y-auto">
              <div className="space-y-2">
                <label htmlFor="lesson-title" className="text-sm font-medium">
                  Lesson Title
                </label>
                <Input
                  id="lesson-title"
                  type="text"
                  placeholder="e.g., Setting up your development environment"
                  value={editingLesson?.title || ''}
                  onChange={(e) =>
                    setEditingLesson(prev =>
                      prev ? { ...prev, title: e.target.value } : null
                    )
                  }
                  required
                />
              </div>

              <div className="space-y-2">
                <label htmlFor="video-type" className="text-sm font-medium">
                  Video Type
                </label>
                <select
                  id="video-type"
                  value={editingLesson?.video_type || 'none'}
                  onChange={(e) =>
                    setEditingLesson(prev =>
                      prev
                        ? { ...prev, video_type: e.target.value as 'none' | 'youtube' }
                        : null
                    )
                  }
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                >
                  <option value="none">No Video</option>
                  <option value="youtube">YouTube</option>
                </select>
              </div>

              {editingLesson?.video_type === 'youtube' && (
                <div className="space-y-2">
                  <label htmlFor="video-id" className="text-sm font-medium">
                    YouTube URL or Video ID
                  </label>
                  <Input
                    id="video-id"
                    type="text"
                    placeholder="Paste YouTube URL or video ID"
                    value={editingLesson?.video_id || ''}
                    onChange={(e) =>
                      setEditingLesson(prev =>
                        prev ? { ...prev, video_id: e.target.value } : null
                      )
                    }
                  />
                  <p className="text-xs text-muted-foreground">
                    Paste the full YouTube URL (e.g., https://www.youtube.com/watch?v=dQw4w9WgXcQ) or just the video ID
                  </p>
                </div>
              )}

              <div className="space-y-2">
                <label htmlFor="lesson-content" className="text-sm font-medium">
                  Content (Markdown)
                </label>
                <textarea
                  id="lesson-content"
                  placeholder="Write your lesson content using Markdown..."
                  value={editingLesson?.content || ''}
                  onChange={(e) =>
                    setEditingLesson(prev =>
                      prev ? { ...prev, content: e.target.value } : null
                    )
                  }
                  rows={10}
                  className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm font-mono ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                />
                <p className="text-xs text-muted-foreground">
                  Supports GitHub Flavored Markdown (headers, lists, code blocks, links, etc.)
                </p>
              </div>
            </div>
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setShowLessonModal(false)}
                disabled={lessonLoading}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={lessonLoading}>
                {lessonLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                {editingLesson?.id ? 'Save Changes' : 'Add Lesson'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Assignment Modal */}
      <Dialog open={showAssignmentModal} onOpenChange={setShowAssignmentModal}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>
              {editingAssignment?.id ? 'Edit Assignment' : 'Add Assignment'}
            </DialogTitle>
            <DialogDescription>
              {editingAssignment?.id
                ? 'Update the assignment details.'
                : 'Create a new assignment for this unit.'}
            </DialogDescription>
          </DialogHeader>
          {assignmentError && (
            <div className="bg-destructive/10 border border-destructive/20 text-destructive rounded-md px-4 py-3 text-sm">
              {assignmentError}
            </div>
          )}
          <form onSubmit={handleSaveAssignment}>
            <div className="space-y-4 py-4 max-h-[60vh] overflow-y-auto">
              <div className="space-y-2">
                <label htmlFor="assignment-title" className="text-sm font-medium">
                  Assignment Title
                </label>
                <Input
                  id="assignment-title"
                  type="text"
                  placeholder="e.g., Create a 2D Game Prototype"
                  value={editingAssignment?.title || ''}
                  onChange={(e) =>
                    setEditingAssignment(prev =>
                      prev ? { ...prev, title: e.target.value } : null
                    )
                  }
                  required
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <label htmlFor="max-points" className="text-sm font-medium">
                    Max Points
                  </label>
                  <Input
                    id="max-points"
                    type="number"
                    min="1"
                    max="1000"
                    value={editingAssignment?.max_points || 100}
                    onChange={(e) =>
                      setEditingAssignment(prev =>
                        prev ? { ...prev, max_points: parseInt(e.target.value) || 100 } : null
                      )
                    }
                  />
                </div>

                <div className="space-y-2">
                  <label htmlFor="due-date" className="text-sm font-medium">
                    Due Date (optional)
                  </label>
                  <Input
                    id="due-date"
                    type="datetime-local"
                    value={editingAssignment?.due_date || ''}
                    onChange={(e) =>
                      setEditingAssignment(prev =>
                        prev ? { ...prev, due_date: e.target.value } : null
                      )
                    }
                  />
                </div>
              </div>

              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="allow-late"
                  checked={editingAssignment?.allow_late ?? true}
                  onChange={(e) =>
                    setEditingAssignment(prev =>
                      prev ? { ...prev, allow_late: e.target.checked } : null
                    )
                  }
                  className="h-4 w-4 rounded border-gray-300"
                />
                <label htmlFor="allow-late" className="text-sm">
                  Allow late submissions
                </label>
              </div>

              {/* Availability Window */}
              <div className="border-t pt-4 mt-4">
                <h4 className="text-sm font-medium mb-3">Availability Window</h4>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <label htmlFor="available-from" className="text-sm font-medium">
                      Available From
                    </label>
                    <Input
                      id="available-from"
                      type="datetime-local"
                      value={editingAssignment?.available_from || ''}
                      onChange={(e) =>
                        setEditingAssignment(prev =>
                          prev ? { ...prev, available_from: e.target.value } : null
                        )
                      }
                    />
                    <p className="text-xs text-muted-foreground">
                      When the assignment becomes visible to students
                    </p>
                  </div>

                  <div className="space-y-2">
                    <label htmlFor="available-until" className="text-sm font-medium">
                      Available Until
                    </label>
                    <Input
                      id="available-until"
                      type="datetime-local"
                      value={editingAssignment?.available_until || ''}
                      onChange={(e) =>
                        setEditingAssignment(prev =>
                          prev ? { ...prev, available_until: e.target.value } : null
                        )
                      }
                    />
                    <p className="text-xs text-muted-foreground">
                      Submissions close after this date
                    </p>
                  </div>
                </div>
              </div>

              {/* Late Penalty Settings */}
              {editingAssignment?.allow_late && (
                <div className="border-t pt-4 mt-4">
                  <h4 className="text-sm font-medium mb-3">Late Penalty Settings</h4>
                  <div className="grid grid-cols-3 gap-4">
                    <div className="space-y-2">
                      <label htmlFor="late-penalty-percent" className="text-sm font-medium">
                        Penalty %
                      </label>
                      <Input
                        id="late-penalty-percent"
                        type="number"
                        min="0"
                        max="100"
                        step="0.5"
                        placeholder="e.g., 10"
                        value={editingAssignment?.late_penalty_percent ?? ''}
                        onChange={(e) =>
                          setEditingAssignment(prev =>
                            prev ? {
                              ...prev,
                              late_penalty_percent: e.target.value ? parseFloat(e.target.value) : null
                            } : null
                          )
                        }
                      />
                    </div>

                    <div className="space-y-2">
                      <label htmlFor="late-penalty-interval" className="text-sm font-medium">
                        Per
                      </label>
                      <select
                        id="late-penalty-interval"
                        value={editingAssignment?.late_penalty_interval || 'day'}
                        onChange={(e) =>
                          setEditingAssignment(prev =>
                            prev ? {
                              ...prev,
                              late_penalty_interval: e.target.value as 'day' | 'hour'
                            } : null
                          )
                        }
                        className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                      >
                        <option value="day">Day</option>
                        <option value="hour">Hour</option>
                      </select>
                    </div>

                    <div className="space-y-2">
                      <label htmlFor="max-late-penalty" className="text-sm font-medium">
                        Max Penalty %
                      </label>
                      <Input
                        id="max-late-penalty"
                        type="number"
                        min="0"
                        max="100"
                        step="1"
                        placeholder="e.g., 50"
                        value={editingAssignment?.max_late_penalty ?? ''}
                        onChange={(e) =>
                          setEditingAssignment(prev =>
                            prev ? {
                              ...prev,
                              max_late_penalty: e.target.value ? parseFloat(e.target.value) : null
                            } : null
                          )
                        }
                      />
                    </div>
                  </div>
                  <p className="text-xs text-muted-foreground mt-2">
                    Leave penalty blank for no late penalty. Example: 10% per day, max 50% means 5 days late = 50% penalty cap.
                  </p>
                </div>
              )}

              <div className="space-y-2">
                <label htmlFor="assignment-description" className="text-sm font-medium">
                  Instructions (Markdown)
                </label>
                <textarea
                  id="assignment-description"
                  placeholder="Write assignment instructions using Markdown..."
                  value={editingAssignment?.description || ''}
                  onChange={(e) =>
                    setEditingAssignment(prev =>
                      prev ? { ...prev, description: e.target.value } : null
                    )
                  }
                  rows={8}
                  className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm font-mono ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                />
              </div>
            </div>
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setShowAssignmentModal(false)}
                disabled={assignmentLoading}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={assignmentLoading}>
                {assignmentLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                {editingAssignment?.id ? 'Save Changes' : 'Add Assignment'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}

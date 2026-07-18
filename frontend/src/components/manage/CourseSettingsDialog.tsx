import { useState, useEffect, type FormEvent } from 'react';
import { useNavigate } from 'react-router';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/Dialog';
import { courseService, type CourseDetail } from '@/services/courses';
import { Loader2, Trash2 } from 'lucide-react';

interface CourseSettingsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  course: CourseDetail;
  onSaved: () => void;
}

export function CourseSettingsDialog({
  open,
  onOpenChange,
  course,
  onSaved,
}: CourseSettingsDialogProps) {
  const navigate = useNavigate();

  const [title, setTitle] = useState(course.title);
  const [description, setDescription] = useState(course.description || '');
  const [isActive, setIsActive] = useState(course.is_active);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState('');

  const [deleteConfirmation, setDeleteConfirmation] = useState('');
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    if (open) {
      setTitle(course.title);
      setDescription(course.description || '');
      setIsActive(course.is_active);
      setDeleteConfirmation('');
      setError('');
    }
  }, [open, course]);

  const handleSave = async (e: FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    setError('');
    try {
      await courseService.updateCourse(course.code, {
        title,
        description,
        is_active: isActive,
      });
      onOpenChange(false);
      onSaved();
    } catch (err) {
      console.error('Failed to update course:', err);
      setError('Failed to save course settings');
    } finally {
      setIsSaving(false);
    }
  };

  const handleDelete = async () => {
    if (deleteConfirmation !== course.code) return;
    setIsDeleting(true);
    setError('');
    try {
      await courseService.deleteCourse(course.code);
      navigate('/dashboard');
    } catch (err) {
      console.error('Failed to delete course:', err);
      setError('Failed to delete course');
      setIsDeleting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Course Settings</DialogTitle>
          <DialogDescription>
            Update details for {course.code} or delete the course.
          </DialogDescription>
        </DialogHeader>

        {error && (
          <div className="bg-destructive/10 border border-destructive/20 text-destructive rounded-md px-4 py-3 text-sm">
            {error}
          </div>
        )}

        <form onSubmit={handleSave}>
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <label htmlFor="course-title" className="text-sm font-medium">
                Course Title
              </label>
              <Input
                id="course-title"
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                maxLength={200}
                required
              />
            </div>

            <div className="space-y-2">
              <label htmlFor="course-description" className="text-sm font-medium">
                Description
              </label>
              <textarea
                id="course-description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={4}
                className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              />
            </div>

            <div className="flex items-center justify-between rounded-lg border p-3">
              <div>
                <p className="text-sm font-medium">Active</p>
                <p className="text-xs text-muted-foreground">
                  Inactive courses are hidden from students.
                </p>
              </div>
              <input
                type="checkbox"
                id="course-active"
                checked={isActive}
                onChange={(e) => setIsActive(e.target.checked)}
                className="h-4 w-4 rounded border-gray-300"
              />
            </div>
          </div>

          <DialogFooter className="pt-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={isSaving}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={isSaving}>
              {isSaving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Save Changes
            </Button>
          </DialogFooter>
        </form>

        {/* Danger zone */}
        <div className="mt-4 rounded-lg border border-destructive/30 p-4 space-y-3">
          <div>
            <h4 className="text-sm font-semibold text-destructive">Danger zone</h4>
            <p className="text-xs text-muted-foreground mt-1">
              Deleting a course permanently removes all its units, lessons, assignments,
              quizzes, and enrollments. Type <span className="font-mono font-semibold">{course.code}</span> to confirm.
            </p>
          </div>
          <div className="flex gap-2">
            <Input
              type="text"
              placeholder={course.code}
              value={deleteConfirmation}
              onChange={(e) => setDeleteConfirmation(e.target.value)}
              className="font-mono"
            />
            <Button
              type="button"
              variant="destructive"
              disabled={deleteConfirmation !== course.code || isDeleting}
              onClick={handleDelete}
            >
              {isDeleting ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Trash2 className="h-4 w-4" />
              )}
              <span className="ml-2">Delete</span>
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

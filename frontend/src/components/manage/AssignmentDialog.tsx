import { useState, useEffect, type FormEvent } from 'react';
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
import { assignmentService } from '@/services/assignments';
import type { Assignment } from '@/types';
import { Loader2 } from 'lucide-react';

interface AssignmentFormState {
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
}

interface AssignmentDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Unit to create in (create mode). Ignored when editing. */
  unitId: number | null;
  /** Full assignment to edit, or null to create. */
  assignment: Assignment | null;
  onSaved: () => void;
}

/** Convert an ISO datetime to the local `YYYY-MM-DDTHH:mm` format datetime-local inputs expect. */
function toDatetimeLocal(iso: string | null): string {
  if (!iso) return '';
  const date = new Date(iso);
  if (isNaN(date.getTime())) return '';
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

const emptyForm: AssignmentFormState = {
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
};

export function AssignmentDialog({
  open,
  onOpenChange,
  unitId,
  assignment,
  onSaved,
}: AssignmentDialogProps) {
  const [form, setForm] = useState<AssignmentFormState>(emptyForm);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!open) return;
    setError('');
    if (assignment) {
      setForm({
        title: assignment.title,
        description: assignment.description || '',
        max_points: assignment.max_points,
        due_date: toDatetimeLocal(assignment.due_date),
        allow_late: assignment.allow_late,
        available_from: toDatetimeLocal(assignment.available_from),
        available_until: toDatetimeLocal(assignment.available_until),
        late_penalty_percent: assignment.late_penalty_percent,
        late_penalty_interval: assignment.late_penalty_interval,
        max_late_penalty: assignment.max_late_penalty,
      });
    } else {
      setForm(emptyForm);
    }
  }, [open, assignment]);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();

    if (!assignment && !unitId) {
      setError('No unit selected. Please close this dialog and try again.');
      return;
    }

    setIsSaving(true);
    setError('');
    try {
      const data = {
        title: form.title,
        description: form.description,
        max_points: form.max_points,
        due_date: form.due_date || null,
        allow_late: form.allow_late,
        available_from: form.available_from || null,
        available_until: form.available_until || null,
        late_penalty_percent: form.late_penalty_percent,
        late_penalty_interval: form.late_penalty_interval,
        max_late_penalty: form.max_late_penalty,
      };

      if (assignment) {
        await assignmentService.updateAssignment(assignment.id, data);
      } else {
        await assignmentService.createAssignment(unitId!, data);
      }
      onOpenChange(false);
      onSaved();
    } catch (err: unknown) {
      console.error('Failed to save assignment:', err);
      const apiError = err as { response?: { data?: { detail?: string; [key: string]: unknown } }; message?: string };
      const errorData = apiError.response?.data;
      let errorMessage = 'Failed to save assignment';
      if (errorData?.detail) {
        errorMessage = errorData.detail;
      } else if (errorData) {
        const fieldErrors = Object.entries(errorData)
          .filter(([key]) => key !== 'detail')
          .map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join(', ') : value}`)
          .join('; ');
        if (fieldErrors) {
          errorMessage = fieldErrors;
        }
      } else if (apiError.message) {
        errorMessage = apiError.message;
      }
      setError(errorMessage);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>
            {assignment ? 'Edit Assignment' : 'Add Assignment'}
          </DialogTitle>
          <DialogDescription>
            {assignment
              ? 'Update the assignment details.'
              : 'Create a new assignment for this unit.'}
          </DialogDescription>
        </DialogHeader>
        {error && (
          <div className="bg-destructive/10 border border-destructive/20 text-destructive rounded-md px-4 py-3 text-sm">
            {error}
          </div>
        )}
        <form onSubmit={handleSubmit}>
          <div className="space-y-4 py-4 max-h-[60vh] overflow-y-auto">
            <div className="space-y-2">
              <label htmlFor="assignment-title" className="text-sm font-medium">
                Assignment Title
              </label>
              <Input
                id="assignment-title"
                type="text"
                placeholder="e.g., Create a 2D Game Prototype"
                value={form.title}
                onChange={(e) => setForm(prev => ({ ...prev, title: e.target.value }))}
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
                  value={form.max_points}
                  onChange={(e) =>
                    setForm(prev => ({ ...prev, max_points: parseInt(e.target.value) || 100 }))
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
                  value={form.due_date}
                  onChange={(e) => setForm(prev => ({ ...prev, due_date: e.target.value }))}
                />
              </div>
            </div>

            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="allow-late"
                checked={form.allow_late}
                onChange={(e) => setForm(prev => ({ ...prev, allow_late: e.target.checked }))}
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
                    value={form.available_from}
                    onChange={(e) =>
                      setForm(prev => ({ ...prev, available_from: e.target.value }))
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
                    value={form.available_until}
                    onChange={(e) =>
                      setForm(prev => ({ ...prev, available_until: e.target.value }))
                    }
                  />
                  <p className="text-xs text-muted-foreground">
                    Submissions close after this date
                  </p>
                </div>
              </div>
            </div>

            {/* Late Penalty Settings */}
            {form.allow_late && (
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
                      value={form.late_penalty_percent ?? ''}
                      onChange={(e) =>
                        setForm(prev => ({
                          ...prev,
                          late_penalty_percent: e.target.value ? parseFloat(e.target.value) : null,
                        }))
                      }
                    />
                  </div>

                  <div className="space-y-2">
                    <label htmlFor="late-penalty-interval" className="text-sm font-medium">
                      Per
                    </label>
                    <select
                      id="late-penalty-interval"
                      value={form.late_penalty_interval}
                      onChange={(e) =>
                        setForm(prev => ({
                          ...prev,
                          late_penalty_interval: e.target.value as 'day' | 'hour',
                        }))
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
                      value={form.max_late_penalty ?? ''}
                      onChange={(e) =>
                        setForm(prev => ({
                          ...prev,
                          max_late_penalty: e.target.value ? parseFloat(e.target.value) : null,
                        }))
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
                value={form.description}
                onChange={(e) => setForm(prev => ({ ...prev, description: e.target.value }))}
                rows={8}
                className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm font-mono ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              />
            </div>
          </div>
          <DialogFooter>
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
              {assignment ? 'Save Changes' : 'Add Assignment'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

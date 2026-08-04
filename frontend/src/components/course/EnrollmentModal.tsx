import { useState, type FormEvent } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/Dialog';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { courseService } from '@/services/courses';
import { Loader2, CheckCircle } from 'lucide-react';

interface EnrollmentModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess?: () => void;
}

export function EnrollmentModal({ open, onOpenChange, onSuccess }: EnrollmentModalProps) {
  const [code, setCode] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const [enrolledCourse, setEnrolledCourse] = useState<string | null>(null);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      const enrollment = await courseService.enrollWithCode(code);
      setSuccess(true);
      setEnrolledCourse(enrollment.course.title);
      setTimeout(() => {
        onSuccess?.();
        resetForm();
      }, 1500);
    } catch (err: unknown) {
      const error = err as {
        response?: { data?: { enrollment_code?: string[]; detail?: string } };
      };
      // `detail` first (Phase 68): a correct code with no pending invitation
      // now comes back as 403 {'detail': ...} naming the invitation
      // requirement, and that is the one message that tells a legitimate
      // student what to do next. Behind a generic fallback it would read as
      // "wrong code" and send them re-typing it forever.
      if (error.response?.data?.detail) {
        setError(error.response.data.detail);
      } else if (error.response?.data?.enrollment_code) {
        setError(error.response.data.enrollment_code[0]);
      } else {
        setError('Failed to enroll. Please check the code and try again.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const resetForm = () => {
    setCode('');
    setError('');
    setSuccess(false);
    setEnrolledCourse(null);
  };

  const handleOpenChange = (open: boolean) => {
    if (!open) {
      resetForm();
    }
    onOpenChange(open);
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent>
        {success ? (
          <div className="flex flex-col items-center py-6">
            <CheckCircle className="h-12 w-12 text-green-500 mb-4" />
            <DialogTitle className="text-center mb-2">Enrolled Successfully!</DialogTitle>
            <DialogDescription className="text-center">
              You are now enrolled in {enrolledCourse}
            </DialogDescription>
          </div>
        ) : (
          <>
            <DialogHeader>
              <DialogTitle>Enroll in a Course</DialogTitle>
              <DialogDescription>
                Enter the enrollment code provided by your instructor to join a course.
              </DialogDescription>
            </DialogHeader>
            <form onSubmit={handleSubmit}>
              <div className="space-y-4 py-4">
                {error && (
                  <div className="rounded-md bg-destructive/15 p-3 text-sm text-destructive">
                    {error}
                  </div>
                )}
                <div className="space-y-2">
                  <label htmlFor="enrollment-code" className="text-sm font-medium">
                    Enrollment Code
                  </label>
                  <Input
                    id="enrollment-code"
                    type="text"
                    placeholder="e.g., ABC12XYZ"
                    value={code}
                    onChange={(e) => setCode(e.target.value.toUpperCase())}
                    maxLength={8}
                    required
                    className="text-center text-lg tracking-widest font-mono"
                  />
                  <p className="text-xs text-muted-foreground">
                    The code is 8 characters and is not case-sensitive.
                  </p>
                </div>
              </div>
              <DialogFooter>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => handleOpenChange(false)}
                  disabled={isLoading}
                >
                  Cancel
                </Button>
                <Button type="submit" disabled={isLoading || code.length < 8}>
                  {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  Enroll
                </Button>
              </DialogFooter>
            </form>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

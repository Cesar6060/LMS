import { useState, useEffect } from 'react';
import { X, Megaphone, Check } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { courseService, type InstructorCourse } from '@/services/courses';

interface MakeAnnouncementModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  courses: InstructorCourse[];
  onSuccess: () => void;
}

export function MakeAnnouncementModal({
  open,
  onOpenChange,
  courses,
  onSuccess,
}: MakeAnnouncementModalProps) {
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [selectedCourses, setSelectedCourses] = useState<number[]>([]);
  const [isPinned, setIsPinned] = useState(false);
  const [sendEmail, setSendEmail] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [successCount, setSuccessCount] = useState(0);

  // Reset form when modal opens
  useEffect(() => {
    if (open) {
      setTitle('');
      setContent('');
      setSelectedCourses([]);
      setIsPinned(false);
      setSendEmail(true);
      setError('');
      setSuccessCount(0);
    }
  }, [open]);

  const toggleCourse = (courseId: number) => {
    setSelectedCourses(prev =>
      prev.includes(courseId)
        ? prev.filter(id => id !== courseId)
        : [...prev, courseId]
    );
  };

  const selectAllCourses = () => {
    if (selectedCourses.length === courses.length) {
      setSelectedCourses([]);
    } else {
      setSelectedCourses(courses.map(c => c.id));
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    const trimmedTitle = title.trim();
    const trimmedContent = content.trim();

    if (!trimmedTitle) {
      setError('Please enter a title for your announcement');
      return;
    }
    if (!trimmedContent) {
      setError('Please enter the announcement content');
      return;
    }
    if (selectedCourses.length === 0) {
      setError('Please select at least one course');
      return;
    }

    setIsSubmitting(true);
    setError('');
    setSuccessCount(0);

    try {
      // Post announcement to each selected course
      let successfulPosts = 0;
      const errors: string[] = [];

      for (const courseId of selectedCourses) {
        const course = courses.find(c => c.id === courseId);
        if (!course) continue;

        try {
          await courseService.createAnnouncement(course.code, {
            title: trimmedTitle,
            content: trimmedContent,
            is_pinned: isPinned,
            send_email: sendEmail,
          });
          successfulPosts++;
          setSuccessCount(successfulPosts);
        } catch {
          errors.push(course.code);
        }
      }

      if (errors.length > 0) {
        setError(`Failed to post to: ${errors.join(', ')}`);
      }

      if (successfulPosts > 0) {
        // Wait a moment to show success, then close
        setTimeout(() => {
          onSuccess();
          onOpenChange(false);
        }, 500);
      }
    } catch (err) {
      console.error('Failed to create announcements:', err);
      setError('Failed to create announcements. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={() => !isSubmitting && onOpenChange(false)}
      />

      {/* Modal - Email compose style */}
      <div className="relative bg-card border border-border rounded-xl shadow-xl w-full max-w-xl mx-4 h-[600px] max-h-[85vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-border">
          <div className="flex items-center gap-2">
            <Megaphone className="h-5 w-5 text-accent" />
            <h2 className="text-lg font-semibold">Make Announcement</h2>
          </div>
          <button
            onClick={() => !isSubmitting && onOpenChange(false)}
            className="p-1 rounded hover:bg-muted transition-colors"
            disabled={isSubmitting}
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Form - Email-style layout */}
        <form onSubmit={handleSubmit} className="flex-1 flex flex-col overflow-hidden">
          {/* Error Message */}
          {error && (
            <div className="mx-4 mt-4 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
              {error}
            </div>
          )}

          {/* Success Message */}
          {successCount > 0 && (
            <div className="mx-4 mt-4 p-3 rounded-lg bg-green-500/10 border border-green-500/20 text-green-400 text-sm">
              Posted to {successCount} course{successCount !== 1 ? 's' : ''}!
            </div>
          )}

          {/* Email-style fields */}
          <div className="border-b border-border">
            {/* To: Course Selection */}
            <div className="flex items-start px-4 py-3 border-b border-border/50">
              <label className="text-sm text-muted-foreground w-16 pt-2 flex-shrink-0">To:</label>
              <div className="flex-1">
                <div className="flex flex-wrap gap-2 mb-2">
                  {selectedCourses.map((courseId) => {
                    const course = courses.find(c => c.id === courseId);
                    if (!course) return null;
                    return (
                      <span
                        key={courseId}
                        className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-accent/10 border border-accent/30 text-sm"
                      >
                        {course.code}
                        <button
                          type="button"
                          onClick={() => toggleCourse(courseId)}
                          className="hover:text-red-400 transition-colors"
                        >
                          <X className="h-3 w-3" />
                        </button>
                      </span>
                    );
                  })}
                  {selectedCourses.length === 0 && (
                    <span className="text-sm text-muted-foreground">Select courses below...</span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={selectAllCourses}
                    className="text-xs text-accent hover:underline"
                  >
                    {selectedCourses.length === courses.length ? 'Clear All' : 'Select All'}
                  </button>
                  <span className="text-muted-foreground">·</span>
                  <div className="flex flex-wrap gap-1.5">
                    {courses.filter(c => !selectedCourses.includes(c.id)).map((course) => (
                      <button
                        key={course.id}
                        type="button"
                        onClick={() => toggleCourse(course.id)}
                        className="text-xs px-2 py-0.5 rounded border border-border hover:border-accent/50 hover:bg-accent/5 transition-colors"
                      >
                        + {course.code}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            {/* Subject */}
            <div className="flex items-center px-4 py-3">
              <label className="text-sm text-muted-foreground w-16 flex-shrink-0">Subject:</label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Announcement title..."
                className="flex-1 bg-transparent focus:outline-none text-sm"
                disabled={isSubmitting}
                maxLength={200}
              />
            </div>
          </div>

          {/* Message Body */}
          <div className="flex-1 overflow-y-auto p-4">
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="Write your announcement here..."
              className="w-full h-full min-h-[200px] bg-transparent focus:outline-none resize-none text-sm leading-relaxed"
              disabled={isSubmitting}
            />
          </div>

          {/* Options Bar */}
          <div className="px-4 py-3 border-t border-border flex items-center gap-6 text-sm">
            <label className="flex items-center gap-2 cursor-pointer">
              <div
                className={`w-4 h-4 rounded border-2 flex items-center justify-center transition-colors ${
                  isPinned
                    ? 'bg-accent border-accent'
                    : 'border-muted-foreground'
                }`}
                onClick={() => setIsPinned(!isPinned)}
              >
                {isPinned && <Check className="h-2.5 w-2.5 text-white" />}
              </div>
              <span className="text-muted-foreground">Pin to top</span>
            </label>

            <label className="flex items-center gap-2 cursor-pointer">
              <div
                className={`w-4 h-4 rounded border-2 flex items-center justify-center transition-colors ${
                  sendEmail
                    ? 'bg-accent border-accent'
                    : 'border-muted-foreground'
                }`}
                onClick={() => setSendEmail(!sendEmail)}
              >
                {sendEmail && <Check className="h-2.5 w-2.5 text-white" />}
              </div>
              <span className="text-muted-foreground">Send email notification</span>
            </label>

            <span className="text-xs text-muted-foreground ml-auto">Markdown supported</span>
          </div>
        </form>

        {/* Actions */}
        <div className="flex justify-end gap-3 p-4 border-t border-border">
          <Button
            type="button"
            variant="ghost"
            onClick={() => onOpenChange(false)}
            disabled={isSubmitting}
          >
            Cancel
          </Button>
          <Button
            onClick={handleSubmit}
            variant="neon"
            disabled={isSubmitting || !title.trim() || !content.trim() || selectedCourses.length === 0}
          >
            {isSubmitting ? 'Posting...' : `Post to ${selectedCourses.length || 0} Course${selectedCourses.length !== 1 ? 's' : ''}`}
          </Button>
        </div>
      </div>
    </div>
  );
}

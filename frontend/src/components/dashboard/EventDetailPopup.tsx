import { X, Pencil, Trash2, Bell, Clock, BookOpen, Calendar } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import type { CalendarEvent } from '@/types';

interface EventDetailPopupProps {
  event: CalendarEvent;
  onClose: () => void;
  onEdit: () => void;
  onDelete: () => void;
  isDeleting?: boolean;
}

export function EventDetailPopup({
  event,
  onClose,
  onEdit,
  onDelete,
  isDeleting,
}: EventDetailPopupProps) {
  const formatTime = (time: string | null) => {
    if (!time) return null;
    const [hours, minutes] = time.split(':').map(Number);
    const ampm = hours >= 12 ? 'PM' : 'AM';
    const hour12 = hours % 12 || 12;
    return `${hour12}:${String(minutes).padStart(2, '0')} ${ampm}`;
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr + 'T00:00:00');
    return date.toLocaleDateString('en-US', {
      weekday: 'long',
      month: 'long',
      day: 'numeric',
      year: 'numeric',
    });
  };

  const getColorStyles = (color: string) => {
    const colors: Record<string, { bg: string; bgLight: string; text: string; border: string }> = {
      blue: { bg: 'bg-blue-500', bgLight: 'bg-blue-500/10', text: 'text-blue-400', border: 'border-blue-500/30' },
      green: { bg: 'bg-green-500', bgLight: 'bg-green-500/10', text: 'text-green-400', border: 'border-green-500/30' },
      amber: { bg: 'bg-amber-500', bgLight: 'bg-amber-500/10', text: 'text-amber-400', border: 'border-amber-500/30' },
      red: { bg: 'bg-red-500', bgLight: 'bg-red-500/10', text: 'text-red-400', border: 'border-red-500/30' },
      purple: { bg: 'bg-purple-500', bgLight: 'bg-purple-500/10', text: 'text-purple-400', border: 'border-purple-500/30' },
    };
    return colors[color] || colors.blue;
  };

  const colorStyles = getColorStyles(event.color);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200"
        onClick={onClose}
      />

      {/* Popup */}
      <div className="relative bg-card rounded-2xl shadow-2xl w-full max-w-md overflow-hidden animate-in zoom-in-95 fade-in duration-200 border border-border/50">
        {/* Color accent bar */}
        <div className={`h-1.5 ${colorStyles.bg}`} />

        {/* Close button - absolute positioned */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-1.5 rounded-full hover:bg-muted/80 transition-colors z-10"
        >
          <X className="h-4 w-4 text-muted-foreground" />
        </button>

        {/* Header section */}
        <div className="px-6 pt-5 pb-4">
          <div className="flex items-start gap-4">
            {/* Icon */}
            <div className={`p-3 rounded-xl ${colorStyles.bgLight} ${colorStyles.border} border`}>
              <Bell className={`h-6 w-6 ${colorStyles.text}`} />
            </div>

            {/* Title & Type */}
            <div className="flex-1 min-w-0 pr-8">
              <div className={`inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium ${colorStyles.bgLight} ${colorStyles.text} mb-1.5`}>
                Reminder
              </div>
              <h3 className="text-xl font-semibold text-foreground leading-tight truncate">
                {event.title}
              </h3>
            </div>
          </div>
        </div>

        {/* Details section */}
        <div className="px-6 pb-5 space-y-3">
          {/* Date */}
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-muted/50 flex items-center justify-center">
              <Calendar className="h-4 w-4 text-muted-foreground" />
            </div>
            <div>
              <p className="text-sm font-medium text-foreground">{formatDate(event.date)}</p>
            </div>
          </div>

          {/* Time */}
          {event.time && (
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-muted/50 flex items-center justify-center">
                <Clock className="h-4 w-4 text-muted-foreground" />
              </div>
              <div>
                <p className="text-sm font-medium text-foreground">
                  {formatTime(event.time)}
                  {event.end_time && (
                    <span className="text-muted-foreground"> — {formatTime(event.end_time)}</span>
                  )}
                </p>
              </div>
            </div>
          )}

          {/* Course */}
          {event.course_code && (
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-muted/50 flex items-center justify-center">
                <BookOpen className="h-4 w-4 text-muted-foreground" />
              </div>
              <div>
                <p className="text-sm font-medium text-foreground">{event.course_code}</p>
              </div>
            </div>
          )}

          {/* Description */}
          {event.description && (
            <div className="mt-4 pt-4 border-t border-border/50">
              <p className="text-sm text-muted-foreground leading-relaxed whitespace-pre-wrap">
                {event.description}
              </p>
            </div>
          )}
        </div>

        {/* Actions footer */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-border/50 bg-muted/20">
          <Button
            variant="ghost"
            size="sm"
            onClick={onDelete}
            disabled={isDeleting}
            className="text-red-400 hover:text-red-300 hover:bg-red-500/10"
          >
            <Trash2 className="h-4 w-4 mr-2" />
            {isDeleting ? 'Deleting...' : 'Delete'}
          </Button>
          <Button
            variant="default"
            size="sm"
            onClick={onEdit}
            disabled={isDeleting}
            className={`${colorStyles.bg} hover:opacity-90`}
          >
            <Pencil className="h-4 w-4 mr-2" />
            Edit Reminder
          </Button>
        </div>
      </div>
    </div>
  );
}

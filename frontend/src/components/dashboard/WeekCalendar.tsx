import { useState, useEffect } from 'react';
import { ChevronLeft, ChevronRight, Plus, Bell } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { courseService } from '@/services/courses';
import { EventDetailPopup } from './EventDetailPopup';
import type { CalendarEvent, InstructorReminder } from '@/types';

interface WeekCalendarProps {
  onAddReminder: (date: string) => void;
  onEditReminder: (reminder: InstructorReminder) => void;
}

export function WeekCalendar({ onAddReminder, onEditReminder }: WeekCalendarProps) {
  const [currentDate, setCurrentDate] = useState(new Date());
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedEvent, setSelectedEvent] = useState<CalendarEvent | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  // Get the start of the week (Sunday)
  const getWeekStart = (date: Date) => {
    const d = new Date(date);
    const day = d.getDay();
    d.setDate(d.getDate() - day);
    d.setHours(0, 0, 0, 0);
    return d;
  };

  const weekStart = getWeekStart(currentDate);
  const weekDays = Array.from({ length: 7 }, (_, i) => {
    const d = new Date(weekStart);
    d.setDate(d.getDate() + i);
    return d;
  });

  const formatDate = (date: Date) => date.toISOString().split('T')[0];

  useEffect(() => {
    loadEvents();
  }, [currentDate]);

  const loadEvents = async () => {
    try {
      setIsLoading(true);
      const startDate = formatDate(weekStart);
      const endDate = formatDate(weekDays[6]);
      const response = await courseService.getInstructorCalendar(startDate, endDate);
      setEvents(response.events);
    } catch (err) {
      console.error('Failed to load calendar events:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const goToPreviousWeek = () => {
    const d = new Date(currentDate);
    d.setDate(d.getDate() - 7);
    setCurrentDate(d);
  };

  const goToNextWeek = () => {
    const d = new Date(currentDate);
    d.setDate(d.getDate() + 7);
    setCurrentDate(d);
  };

  const goToToday = () => {
    setCurrentDate(new Date());
  };

  const getEventsForDate = (date: Date) => {
    const dateStr = formatDate(date);
    const dayEvents = events.filter(e => e.date === dateStr);

    // Sort by time: events with time first (chronologically), then events without time
    return dayEvents.sort((a, b) => {
      if (a.time && b.time) {
        return a.time.localeCompare(b.time);
      }
      if (a.time && !b.time) return -1;
      if (!a.time && b.time) return 1;
      return 0;
    });
  };

  // Format time for display (convert 24h to 12h format)
  const formatTime = (time: string | null) => {
    if (!time) return null;
    const [hours, minutes] = time.split(':').map(Number);
    const ampm = hours >= 12 ? 'PM' : 'AM';
    const hour12 = hours % 12 || 12;
    return `${hour12}:${String(minutes).padStart(2, '0')} ${ampm}`;
  };

  // Track which days are expanded
  const [expandedDays, setExpandedDays] = useState<Set<string>>(new Set());

  const toggleDayExpanded = (dateStr: string) => {
    setExpandedDays(prev => {
      const next = new Set(prev);
      if (next.has(dateStr)) {
        next.delete(dateStr);
      } else {
        next.add(dateStr);
      }
      return next;
    });
  };

  const isToday = (date: Date) => {
    const today = new Date();
    return date.toDateString() === today.toDateString();
  };

  const handleEventClick = (event: CalendarEvent) => {
    setSelectedEvent(event);
  };

  const handleEditFromPopup = async () => {
    if (!selectedEvent?.reminder_id) return;
    try {
      const reminder = await courseService.getReminder(selectedEvent.reminder_id);
      setSelectedEvent(null);
      onEditReminder(reminder);
    } catch (err) {
      console.error('Failed to load reminder:', err);
    }
  };

  const handleDeleteFromPopup = async () => {
    if (!selectedEvent?.reminder_id) return;
    setIsDeleting(true);
    try {
      await courseService.deleteReminder(selectedEvent.reminder_id);
      setSelectedEvent(null);
      loadEvents(); // Refresh calendar
    } catch (err) {
      console.error('Failed to delete reminder:', err);
    } finally {
      setIsDeleting(false);
    }
  };

  const getEventIcon = (type: CalendarEvent['type']) => {
    switch (type) {
      case 'reminder':
        return <Bell className="h-3 w-3" />;
      default:
        return null;
    }
  };

  const getEventColorClass = (color: string) => {
    switch (color) {
      case 'green':
        return 'bg-green-500/20 border-green-500/50 text-green-400';
      case 'amber':
        return 'bg-amber-500/20 border-amber-500/50 text-amber-400';
      case 'red':
        return 'bg-red-500/20 border-red-500/50 text-red-400';
      case 'purple':
        return 'bg-purple-500/20 border-purple-500/50 text-purple-400';
      case 'blue':
      default:
        return 'bg-blue-500/20 border-blue-500/50 text-blue-400';
    }
  };

  const monthYear = weekStart.toLocaleDateString('en-US', { month: 'long', year: 'numeric' });

  return (
    <div className="card-gaming rounded-xl p-5">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <h3 className="text-lg font-semibold">{monthYear}</h3>
          <Button variant="ghost" size="sm" onClick={goToToday}>
            Today
          </Button>
        </div>
        <div className="flex items-center gap-1">
          <Button variant="ghost" size="sm" onClick={goToPreviousWeek}>
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <Button variant="ghost" size="sm" onClick={goToNextWeek}>
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Week Grid */}
      <div className="grid grid-cols-7 gap-1">
        {/* Day Headers */}
        {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map((day) => (
          <div key={day} className="text-center text-xs text-muted-foreground py-2 font-medium">
            {day}
          </div>
        ))}

        {/* Day Cells */}
        {weekDays.map((date) => {
          const dayEvents = getEventsForDate(date);
          const dateStr = formatDate(date);
          const today = isToday(date);

          return (
            <div
              key={dateStr}
              className={`min-h-[140px] p-2 rounded-lg border transition-colors ${
                today
                  ? 'border-primary/50 bg-primary/5'
                  : 'border-border/50 hover:border-border'
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <span
                  className={`text-sm font-medium ${
                    today ? 'text-primary' : 'text-muted-foreground'
                  }`}
                >
                  {date.getDate()}
                </span>
                <button
                  onClick={() => onAddReminder(dateStr)}
                  className="opacity-0 group-hover:opacity-100 hover:opacity-100 p-1 rounded hover:bg-muted transition-opacity"
                  title="Add reminder"
                >
                  <Plus className="h-3 w-3 text-muted-foreground" />
                </button>
              </div>

              {/* Events */}
              <div className="space-y-1">
                {(expandedDays.has(dateStr) ? dayEvents : dayEvents.slice(0, 4)).map((event) => (
                  <div
                    key={event.id}
                    onClick={() => handleEventClick(event)}
                    className={`text-xs px-1.5 py-1 rounded border cursor-pointer hover:opacity-80 ${getEventColorClass(event.color)}`}
                    title={`${event.title}${event.time ? ` at ${formatTime(event.time)}` : ''}`}
                  >
                    <div className="flex items-center gap-1">
                      {getEventIcon(event.type)}
                      {event.time && (
                        <span className="font-medium opacity-75 whitespace-nowrap">{formatTime(event.time)}</span>
                      )}
                      <span className="truncate flex-1">{event.title}</span>
                    </div>
                  </div>
                ))}
                {dayEvents.length > 4 && (
                  <button
                    onClick={() => toggleDayExpanded(dateStr)}
                    className="w-full text-xs text-muted-foreground hover:text-foreground py-0.5 rounded hover:bg-muted/50 transition-colors"
                  >
                    {expandedDays.has(dateStr) ? 'Show less' : `+${dayEvents.length - 4} more`}
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Loading Overlay */}
      {isLoading && (
        <div className="absolute inset-0 bg-background/50 flex items-center justify-center rounded-xl">
          <div className="animate-spin h-6 w-6 border-2 border-primary border-t-transparent rounded-full" />
        </div>
      )}

      {/* Event Detail Popup */}
      {selectedEvent && (
        <EventDetailPopup
          event={selectedEvent}
          onClose={() => setSelectedEvent(null)}
          onEdit={handleEditFromPopup}
          onDelete={handleDeleteFromPopup}
          isDeleting={isDeleting}
        />
      )}
    </div>
  );
}

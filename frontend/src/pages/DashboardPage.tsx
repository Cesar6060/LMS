import { useState, useEffect } from 'react';
import { Link } from 'react-router';
import { useAuth } from '@/contexts/AuthContext';
import { Button } from '@/components/ui/Button';
import { courseService, type InstructorCourse } from '@/services/courses';
import type { Enrollment, EnhancedDashboard, InstructorReminder, UpcomingDeadline, CourseProgressItem } from '@/types';
import { Plus, Play, BookOpen, Users, CheckCircle2, Clock, AlertCircle, ChevronRight, Megaphone, FileText, CalendarClock, Trophy, Target } from 'lucide-react';
import { EnrollmentModal } from '@/components/course/EnrollmentModal';
import { Skeleton } from '@/components/ui/Skeleton';
import { WeekCalendar } from '@/components/dashboard/WeekCalendar';
import { AddReminderModal } from '@/components/dashboard/AddReminderModal';
import { MakeAnnouncementModal } from '@/components/dashboard/MakeAnnouncementModal';

export function DashboardPage() {
  const { user } = useAuth();
  const [enrolledCourses, setEnrolledCourses] = useState<Enrollment[]>([]);
  const [instructorCourses, setInstructorCourses] = useState<InstructorCourse[]>([]);
  const [enhancedData, setEnhancedData] = useState<EnhancedDashboard | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [showEnrollModal, setShowEnrollModal] = useState(false);
  const [showReminderModal, setShowReminderModal] = useState(false);
  const [reminderDate, setReminderDate] = useState<string>('');
  const [editingReminder, setEditingReminder] = useState<InstructorReminder | null>(null);
  const [calendarKey, setCalendarKey] = useState(0);
  const [showAnnouncementModal, setShowAnnouncementModal] = useState(false);

  useEffect(() => {
    loadData();
  }, [user]);

  const loadData = async () => {
    if (!user) return;
    try {
      setIsLoading(true);
      const [enhanced] = await Promise.all([
        courseService.getEnhancedDashboard(),
        user.is_instructor
          ? courseService.getInstructorCourses().then(setInstructorCourses)
          : courseService.getMyEnrollments().then(setEnrolledCourses)
      ]);
      setEnhancedData(enhanced);
    } catch (err) {
      console.error('Failed to load dashboard data:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const isInstructor = user?.is_instructor;
  const courses = isInstructor ? instructorCourses : enrolledCourses;
  const hasCourses = courses.length > 0;

  // Calculate stats for students from enhanced data
  const courseProgress = enhancedData && !enhancedData.is_instructor
    ? enhancedData.course_progress_overview
    : [];
  const totalLessons = courseProgress.reduce((sum, course) => sum + course.lessons.total, 0);
  const completedLessons = courseProgress.reduce((sum, course) => sum + course.lessons.completed, 0);

  // Get continue learning data from enhanced dashboard
  const continueLearning = enhancedData && !enhancedData.is_instructor ? enhancedData.continue_learning : null;

  // Get upcoming deadlines for students
  const upcomingDeadlines: UpcomingDeadline[] = enhancedData && !enhancedData.is_instructor
    ? enhancedData.upcoming_deadlines
    : [];

  // Get course progress overview for students
  const courseProgressOverview: CourseProgressItem[] = enhancedData && !enhancedData.is_instructor
    ? enhancedData.course_progress_overview
    : [];

  // Helper to get urgency color based on due date
  const getDeadlineUrgency = (dueDate: string) => {
    const now = new Date();
    const due = new Date(dueDate);
    const hoursUntilDue = (due.getTime() - now.getTime()) / (1000 * 60 * 60);

    if (hoursUntilDue < 0) return { color: 'text-red-500', bg: 'bg-red-500/10', border: 'border-red-500/30', label: 'Overdue' };
    if (hoursUntilDue < 24) return { color: 'text-red-500', bg: 'bg-red-500/10', border: 'border-red-500/30', label: 'Due today' };
    if (hoursUntilDue < 72) return { color: 'text-amber-500', bg: 'bg-amber-500/10', border: 'border-amber-500/30', label: 'Due soon' };
    return { color: 'text-muted-foreground', bg: 'bg-muted/50', border: 'border-border', label: '' };
  };

  // Format relative time for deadlines
  const formatDeadline = (dueDate: string) => {
    const now = new Date();
    const due = new Date(dueDate);
    const diffMs = due.getTime() - now.getTime();
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

    if (diffMs < 0) {
      const overdueDays = Math.abs(diffDays);
      return overdueDays === 0 ? 'Overdue' : `${overdueDays}d overdue`;
    }
    if (diffHours < 1) return 'Less than 1 hour';
    if (diffHours < 24) return `${diffHours}h left`;
    if (diffDays === 1) return 'Tomorrow';
    if (diffDays < 7) return `${diffDays} days left`;
    return due.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  };

  const handleAddReminder = (date: string) => {
    setEditingReminder(null);
    setReminderDate(date);
    setShowReminderModal(true);
  };

  const handleEditReminder = (reminder: InstructorReminder) => {
    setEditingReminder(reminder);
    setReminderDate('');
    setShowReminderModal(true);
  };

  if (isLoading) {
    return (
      <div className="container mx-auto px-4 py-8 max-w-6xl">
        <Skeleton className="h-44 rounded-xl mb-6" />
        <div className="grid grid-cols-3 gap-4 mb-8">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-24 rounded-lg" />
          ))}
        </div>
        <Skeleton className="h-6 w-32 mb-4" />
        <div className="space-y-3">
          {[1, 2].map((i) => (
            <Skeleton key={i} className="h-20 rounded-lg" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8 max-w-6xl">
      {/* Hero: Continue Learning - Students */}
      {hasCourses && !isInstructor && (
        <div className="relative rounded-xl p-8 mb-6 overflow-hidden border border-[#22c55e]/20" style={{ background: 'linear-gradient(135deg, rgba(34, 197, 94, 0.1) 0%, rgba(6, 182, 212, 0.05) 50%, transparent 100%)' }}>
          <div className="absolute inset-0 bg-grid opacity-30" />
          <div className="relative">
            <p className="text-sm font-medium mb-3" style={{ color: '#22c55e', fontFamily: 'Orbitron, sans-serif' }}>Continue Learning</p>
          {continueLearning ? (
            <>
              <h2 className="text-2xl font-semibold mb-2">{continueLearning.course_title}</h2>
              <p className="text-muted-foreground mb-5">
                {continueLearning.current_lesson
                  ? `${continueLearning.current_lesson.unit_title} · ${continueLearning.current_lesson.title}`
                  : 'Start your first lesson'}
              </p>
              <div className="flex items-center gap-4 mb-4">
                <Link to={`/courses/${continueLearning.course_code}/learn`}>
                  <Button size="lg" variant="neon">
                    <Play className="h-4 w-4 mr-2" />
                    Continue
                  </Button>
                </Link>
              </div>
              {/* Progress Bar */}
              <div className="max-w-md">
                <div className="progress-gaming">
                  <div
                    className="progress-gaming-bar"
                    style={{ width: `${continueLearning.progress_percentage}%` }}
                  />
                </div>
                <p className="text-sm text-muted-foreground mt-2">
                  {continueLearning.progress_percentage}% complete
                </p>
              </div>
            </>
          ) : (
            <>
              <h2 className="text-2xl font-semibold mb-2">Pick up where you left off</h2>
              <p className="text-muted-foreground mb-5">
                Select a course below to start learning
              </p>
            </>
          )}
          </div>
        </div>
      )}

      {/* Hero: Make Announcement - Instructors */}
      {hasCourses && isInstructor && (
        <div className="relative rounded-xl p-8 mb-6 overflow-hidden border border-[#06b6d4]/20" style={{ background: 'linear-gradient(135deg, rgba(6, 182, 212, 0.1) 0%, rgba(34, 197, 94, 0.05) 50%, transparent 100%)' }}>
          <div className="absolute inset-0 bg-grid opacity-30" />
          <div className="relative">
            <p className="text-sm font-medium mb-3" style={{ color: '#06b6d4', fontFamily: 'Orbitron, sans-serif' }}>Quick Actions</p>
            <h2 className="text-2xl font-semibold mb-2">Post an Announcement</h2>
            <p className="text-muted-foreground mb-5">
              Keep your students informed with course updates and important news
            </p>
            {instructorCourses.length > 0 && (
              <Button size="lg" variant="neon" onClick={() => setShowAnnouncementModal(true)}>
                <Megaphone className="h-4 w-4 mr-2" />
                Make Announcement
              </Button>
            )}
          </div>
        </div>
      )}

      {/* Student Quick Stats */}
      {hasCourses && !isInstructor && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
          <div className="card-gaming rounded-xl p-5">
            <div className="flex items-center gap-2 text-muted-foreground mb-2">
              <BookOpen className="h-5 w-5" style={{ color: '#22c55e' }} />
              <span className="text-sm font-medium">Courses</span>
            </div>
            <p className="text-3xl font-semibold text-gradient-gaming">{courses.length}</p>
          </div>
          <div className="card-gaming rounded-xl p-5">
            <div className="flex items-center gap-2 text-muted-foreground mb-2">
              <CheckCircle2 className="h-5 w-5" style={{ color: '#06b6d4' }} />
              <span className="text-sm font-medium">Completed</span>
            </div>
            <p className="text-3xl font-semibold text-gradient-gaming">{completedLessons}<span className="text-lg text-muted-foreground">/{totalLessons}</span></p>
          </div>
          <div className="card-gaming rounded-xl p-5">
            <div className="flex items-center gap-2 text-muted-foreground mb-2">
              <CalendarClock className="h-5 w-5" style={{ color: '#f59e0b' }} />
              <span className="text-sm font-medium">Due Soon</span>
            </div>
            <p className="text-3xl font-semibold text-gradient-gaming">{upcomingDeadlines.filter(d => {
              const hours = (new Date(d.due_date).getTime() - Date.now()) / (1000 * 60 * 60);
              return hours >= 0 && hours < 72;
            }).length}</p>
          </div>
          <div className="card-gaming rounded-xl p-5">
            <div className="flex items-center gap-2 text-muted-foreground mb-2">
              <Target className="h-5 w-5" style={{ color: '#8b5cf6' }} />
              <span className="text-sm font-medium">Progress</span>
            </div>
            <p className="text-3xl font-semibold text-gradient-gaming">
              {totalLessons > 0 ? Math.round((completedLessons / totalLessons) * 100) : 0}%
            </p>
          </div>
        </div>
      )}

      {/* Upcoming Deadlines - Students */}
      {hasCourses && !isInstructor && upcomingDeadlines.length > 0 && (
        <div className="mb-8">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-semibold flex items-center gap-2">
              <CalendarClock className="h-5 w-5 text-amber-500" />
              Upcoming Deadlines
            </h2>
            <span className="text-sm text-muted-foreground">
              {upcomingDeadlines.length} item{upcomingDeadlines.length !== 1 ? 's' : ''}
            </span>
          </div>
          <div className="grid gap-3">
            {upcomingDeadlines.slice(0, 5).map((deadline) => {
              const urgency = getDeadlineUrgency(deadline.due_date);
              return (
                <Link
                  key={`${deadline.type}-${deadline.id}`}
                  to={deadline.type === 'assignment'
                    ? `/courses/${deadline.course_code}/assignments/${deadline.id}`
                    : `/courses/${deadline.course_code}/quizzes/${deadline.id}`
                  }
                  className={`flex items-center justify-between p-4 card-gaming border ${urgency.border} hover:border-[#22c55e]/50 transition-colors`}
                >
                  <div className="flex items-center gap-4">
                    <div className={`h-10 w-10 rounded-full ${urgency.bg} flex items-center justify-center`}>
                      {deadline.type === 'assignment' ? (
                        <FileText className={`h-5 w-5 ${urgency.color}`} />
                      ) : (
                        <Trophy className={`h-5 w-5 ${urgency.color}`} />
                      )}
                    </div>
                    <div>
                      <p className="font-medium">{deadline.title}</p>
                      <p className="text-sm text-muted-foreground">
                        {deadline.course_code} · {deadline.max_points} pts
                        {deadline.has_draft && (
                          <span className="ml-2 text-amber-500">(Draft saved)</span>
                        )}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="text-right">
                      <p className={`text-sm font-medium ${urgency.color}`}>
                        {formatDeadline(deadline.due_date)}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {new Date(deadline.due_date).toLocaleDateString('en-US', {
                          month: 'short',
                          day: 'numeric',
                          hour: 'numeric',
                          minute: '2-digit'
                        })}
                      </p>
                    </div>
                    <ChevronRight className="h-5 w-5 text-muted-foreground" />
                  </div>
                </Link>
              );
            })}
          </div>
        </div>
      )}

      {/* Course Progress Overview - Students */}
      {hasCourses && !isInstructor && courseProgressOverview.length > 0 && (
        <div className="mb-8">
          <h2 className="text-xl font-semibold mb-4">Course Progress</h2>
          <div className="grid gap-4">
            {courseProgressOverview.map((course) => (
              <Link
                key={course.course_code}
                to={`/courses/${course.course_code}`}
                className="card-gaming p-5 hover:border-[#22c55e]/50 transition-colors"
              >
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <h3 className="font-semibold">{course.course_title}</h3>
                    <p className="text-sm text-muted-foreground">{course.course_code}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-2xl font-bold text-gradient-gaming">{course.overall_percentage}%</p>
                    <p className="text-xs text-muted-foreground">Overall</p>
                  </div>
                </div>

                {/* Progress Bars */}
                <div className="space-y-3">
                  {/* Lessons Progress */}
                  <div>
                    <div className="flex items-center justify-between text-sm mb-1">
                      <span className="text-muted-foreground flex items-center gap-1.5">
                        <BookOpen className="h-3.5 w-3.5" />
                        Lessons
                      </span>
                      <span className="font-medium">{course.lessons.completed}/{course.lessons.total}</span>
                    </div>
                    <div className="h-2 bg-muted rounded-full overflow-hidden">
                      <div
                        className="h-full bg-gradient-to-r from-[#22c55e] to-[#06b6d4] transition-all duration-500"
                        style={{ width: `${course.lessons.percentage}%` }}
                      />
                    </div>
                  </div>

                  {/* Assignments Progress */}
                  {course.assignments.total > 0 && (
                    <div>
                      <div className="flex items-center justify-between text-sm mb-1">
                        <span className="text-muted-foreground flex items-center gap-1.5">
                          <FileText className="h-3.5 w-3.5" />
                          Assignments
                        </span>
                        <span className="font-medium">{course.assignments.completed}/{course.assignments.total}</span>
                      </div>
                      <div className="h-2 bg-muted rounded-full overflow-hidden">
                        <div
                          className="h-full bg-gradient-to-r from-[#f59e0b] to-[#ef4444] transition-all duration-500"
                          style={{ width: `${course.assignments.percentage}%` }}
                        />
                      </div>
                    </div>
                  )}

                  {/* Quizzes Progress */}
                  {course.quizzes.total > 0 && (
                    <div>
                      <div className="flex items-center justify-between text-sm mb-1">
                        <span className="text-muted-foreground flex items-center gap-1.5">
                          <Trophy className="h-3.5 w-3.5" />
                          Quizzes
                        </span>
                        <span className="font-medium">{course.quizzes.passed}/{course.quizzes.total} passed</span>
                      </div>
                      <div className="h-2 bg-muted rounded-full overflow-hidden">
                        <div
                          className="h-full bg-gradient-to-r from-[#8b5cf6] to-[#ec4899] transition-all duration-500"
                          style={{ width: `${course.quizzes.percentage}%` }}
                        />
                      </div>
                    </div>
                  )}
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* Instructor Week Calendar */}
      {hasCourses && isInstructor && (
        <div className="mb-8">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-semibold">This Week</h2>
            <Button variant="outline" size="sm" onClick={() => handleAddReminder(new Date().toISOString().split('T')[0])}>
              <Plus className="h-4 w-4 mr-1" />
              Add Reminder
            </Button>
          </div>
          <WeekCalendar key={calendarKey} onAddReminder={handleAddReminder} onEditReminder={handleEditReminder} />
        </div>
      )}

      {/* Pending Submissions - Instructor Only */}
      {isInstructor && enhancedData?.is_instructor && enhancedData.recent_submissions.length > 0 && (
        <div className="mb-8">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-semibold flex items-center gap-2">
              <AlertCircle className="h-5 w-5 text-amber-500" />
              Needs Grading
            </h2>
            <span className="text-sm text-muted-foreground">
              {enhancedData.recent_submissions.length} pending
            </span>
          </div>
          <div className="space-y-3">
            {enhancedData.recent_submissions.slice(0, 3).map((submission) => (
              <Link
                key={submission.id}
                to={`/instructor/assignments/${submission.assignment_id}/grade`}
                className="flex items-center justify-between p-4 card-gaming hover:border-amber-500/50 transition-colors"
              >
                <div className="flex items-center gap-4">
                  <div className="h-10 w-10 rounded-full bg-amber-500/10 flex items-center justify-center">
                    <Clock className="h-5 w-5 text-amber-500" />
                  </div>
                  <div>
                    <p className="font-medium">{submission.assignment_title}</p>
                    <p className="text-sm text-muted-foreground">
                      {submission.student_name} · {submission.course_code}
                      {submission.is_late && (
                        <span className="ml-2 text-red-500">(Late)</span>
                      )}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-sm text-muted-foreground">
                    {submission.submitted_at && new Date(submission.submitted_at).toLocaleDateString('en-US', {
                      month: 'short',
                      day: 'numeric',
                      hour: 'numeric',
                      minute: '2-digit'
                    })}
                  </span>
                  <ChevronRight className="h-5 w-5 text-muted-foreground" />
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* Course List Header */}
      <div className="flex items-center justify-between mb-5">
        <h2 className="text-xl font-semibold">
          {isInstructor ? 'Your Courses' : 'Enrolled Courses'}
        </h2>
        {hasCourses && (
          isInstructor ? (
            <Link to="/instructor/courses/new">
              <Button variant="outline">
                <Plus className="h-4 w-4 mr-2" />
                New Course
              </Button>
            </Link>
          ) : (
            <Button variant="outline" onClick={() => setShowEnrollModal(true)}>
              <Plus className="h-4 w-4 mr-2" />
              Join Course
            </Button>
          )
        )}
      </div>

      {/* Course List */}
      {!hasCourses ? (
        <div className="text-center py-20 card-gaming bg-grid">
          <BookOpen className="h-16 w-16 mx-auto mb-4" style={{ color: 'rgba(34, 197, 94, 0.3)' }} />
          <p className="text-lg text-muted-foreground mb-5">
            {isInstructor ? 'No courses yet' : 'No courses enrolled'}
          </p>
          {isInstructor ? (
            <Link to="/instructor/courses/new">
              <Button size="lg" variant="neon">
                <Plus className="h-4 w-4 mr-2" />
                Create Your First Course
              </Button>
            </Link>
          ) : (
            <Button size="lg" variant="neon" onClick={() => setShowEnrollModal(true)}>
              <Plus className="h-4 w-4 mr-2" />
              Join Your First Course
            </Button>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {isInstructor
            ? instructorCourses.map((course) => (
                <Link
                  key={course.id}
                  to={`/courses/${course.code}`}
                  className="card-gaming p-6 flex flex-col hover:border-[#22c55e]/50 transition-colors"
                >
                  <div className="flex-1">
                    <h3 className="text-lg font-semibold mb-2">{course.title}</h3>
                    <p className="text-sm text-muted-foreground mb-1">{course.code}</p>
                    <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
                      <Users className="h-4 w-4" />
                      <span>{course.student_count} student{course.student_count !== 1 ? 's' : ''}</span>
                    </div>
                  </div>
                  <div className="mt-4 pt-4 border-t border-border">
                    <Button variant="outline" className="w-full">
                      Manage
                    </Button>
                  </div>
                </Link>
              ))
            : enrolledCourses.map((enrollment) => (
                <Link
                  key={enrollment.id}
                  to={`/courses/${enrollment.course.code}`}
                  className="card-gaming p-6 flex flex-col hover:border-[#22c55e]/50 transition-colors"
                >
                  <div className="flex-1">
                    <h3 className="text-lg font-semibold mb-2">{enrollment.course.title}</h3>
                    <p className="text-sm text-muted-foreground mb-1">{enrollment.course.code}</p>
                    <p className="text-sm text-muted-foreground">
                      {enrollment.course.instructor.first_name} {enrollment.course.instructor.last_name}
                    </p>
                  </div>
                  <div className="mt-4 pt-4 border-t border-border">
                    <Button variant="outline" className="w-full">
                      <Play className="h-4 w-4 mr-2" />
                      Continue
                    </Button>
                  </div>
                </Link>
              ))}
        </div>
      )}

      {/* Enrollment Modal */}
      {!isInstructor && (
        <EnrollmentModal
          open={showEnrollModal}
          onOpenChange={setShowEnrollModal}
          onSuccess={() => {
            setShowEnrollModal(false);
            loadData();
          }}
        />
      )}

      {/* Add Reminder Modal */}
      {isInstructor && (
        <AddReminderModal
          open={showReminderModal}
          onOpenChange={(open) => {
            setShowReminderModal(open);
            if (!open) setEditingReminder(null);
          }}
          defaultDate={reminderDate}
          courses={instructorCourses}
          editingReminder={editingReminder}
          onSuccess={() => {
            setCalendarKey(k => k + 1); // Trigger calendar reload
          }}
        />
      )}

      {/* Make Announcement Modal */}
      {isInstructor && (
        <MakeAnnouncementModal
          open={showAnnouncementModal}
          onOpenChange={setShowAnnouncementModal}
          courses={instructorCourses}
          onSuccess={() => {
            // Optionally reload data or show success toast
          }}
        />
      )}
    </div>
  );
}

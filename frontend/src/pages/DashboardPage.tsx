import { useState, useEffect } from 'react';
import { Link } from 'react-router';
import { useAuth } from '@/contexts/AuthContext';
import { Button } from '@/components/ui/Button';
import { courseService, type InstructorCourse } from '@/services/courses';
import type { Enrollment, EnhancedDashboard, InstructorReminder, CourseProgressItem } from '@/types';
import { Plus, Play, BookOpen, Users, CheckCircle2, Megaphone, Trophy, Target } from 'lucide-react';
import { EnrollmentModal } from '@/components/course/EnrollmentModal';
import { Skeleton } from '@/components/ui/Skeleton';
import { WeekCalendar } from '@/components/dashboard/WeekCalendar';
import { AddReminderModal } from '@/components/dashboard/AddReminderModal';
import { MakeAnnouncementModal } from '@/components/dashboard/MakeAnnouncementModal';
import { PageContainer } from '@/components/layout/PageContainer';

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

  // Get course progress overview for students
  const courseProgressOverview: CourseProgressItem[] = enhancedData && !enhancedData.is_instructor
    ? enhancedData.course_progress_overview
    : [];

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
      <PageContainer maxWidth="max-w-6xl">
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
      </PageContainer>
    );
  }

  return (
    <PageContainer maxWidth="max-w-6xl">
      {/* Hero: Continue Learning - Students */}
      {hasCourses && !isInstructor && (
        <div className="relative rounded-xl p-8 mb-6 overflow-hidden border border-primary/20" style={{ background: 'linear-gradient(135deg, rgba(34, 197, 94, 0.1) 0%, rgba(6, 182, 212, 0.05) 50%, transparent 100%)' }}>
          <div className="absolute inset-0 bg-grid opacity-30" />
          <div className="relative">
            <p className="text-sm font-semibold uppercase tracking-wider text-primary mb-3">Continue Learning</p>
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
        <div className="relative rounded-xl p-8 mb-6 overflow-hidden border border-accent/20" style={{ background: 'linear-gradient(135deg, rgba(6, 182, 212, 0.1) 0%, rgba(34, 197, 94, 0.05) 50%, transparent 100%)' }}>
          <div className="absolute inset-0 bg-grid opacity-30" />
          <div className="relative">
            <p className="text-sm font-semibold uppercase tracking-wider text-accent mb-3">Quick Actions</p>
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
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 mb-8">
          <div className="card-gaming rounded-xl p-5">
            <div className="flex items-center gap-2 text-muted-foreground mb-2">
              <BookOpen className="h-5 w-5 text-primary" />
              <span className="text-sm font-medium">Courses</span>
            </div>
            <p className="text-3xl font-semibold text-gradient-gaming">{courses.length}</p>
          </div>
          <div className="card-gaming rounded-xl p-5">
            <div className="flex items-center gap-2 text-muted-foreground mb-2">
              <CheckCircle2 className="h-5 w-5 text-accent" />
              <span className="text-sm font-medium">Completed</span>
            </div>
            <p className="text-3xl font-semibold text-gradient-gaming">{completedLessons}<span className="text-lg text-muted-foreground">/{totalLessons}</span></p>
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

      {/* Course Progress Overview - Students */}
      {hasCourses && !isInstructor && courseProgressOverview.length > 0 && (
        <div className="mb-8">
          <h2 className="text-xl font-semibold mb-4">Course Progress</h2>
          <div className="grid gap-4">
            {courseProgressOverview.map((course) => (
              <Link
                key={course.course_code}
                to={`/courses/${course.course_code}`}
                className="card-gaming card-interactive p-5 hover:border-primary/50 transition-colors"
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
                        className="h-full bg-gradient-to-r from-primary to-accent transition-all duration-500"
                        style={{ width: `${course.lessons.percentage}%` }}
                      />
                    </div>
                  </div>

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
                  className="card-gaming card-interactive p-6 flex flex-col hover:border-primary/50 transition-colors"
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
                  className="card-gaming card-interactive p-6 flex flex-col hover:border-primary/50 transition-colors"
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
    </PageContainer>
  );
}

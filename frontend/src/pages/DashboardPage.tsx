import { useState, useEffect, useCallback } from 'react';
import { Link, useNavigate } from 'react-router';
import { useAuth } from '@/contexts/useAuth';
import { Button } from '@/components/ui/Button';
import { courseService, type InstructorCourse } from '@/services/courses';
import { gamificationService } from '@/services/gamification';
import type { Enrollment, EnhancedDashboard, InstructorReminder, CourseProgressItem, GamificationProfile } from '@/types';
import { Plus, Play, BookOpen, Users, Megaphone, Trophy, Map as MapIcon } from 'lucide-react';
import { DashboardHero } from '@/components/gamification/DashboardHero';
import { AvatarCustomizerModal } from '@/components/gamification/AvatarCustomizerModal';
import { EnrollmentModal } from '@/components/course/EnrollmentModal';
import { Skeleton } from '@/components/ui/Skeleton';
import { WeekCalendar } from '@/components/dashboard/WeekCalendar';
import { AddReminderModal } from '@/components/dashboard/AddReminderModal';
import { MakeAnnouncementModal } from '@/components/dashboard/MakeAnnouncementModal';
import { PageContainer } from '@/components/layout/PageContainer';

export function DashboardPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
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
  const [gameProfile, setGameProfile] = useState<GamificationProfile | null>(null);
  const [showCustomizer, setShowCustomizer] = useState(false);

  const loadData = useCallback(async () => {
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
      // Gamification tiles are student-only; instructors get an inert payload.
      if (!user.is_instructor) {
        gamificationService
          .getProfile()
          .then(setGameProfile)
          .catch((err) => console.error('Failed to load gamification profile:', err));
      }
    } catch (err) {
      console.error('Failed to load dashboard data:', err);
    } finally {
      setIsLoading(false);
    }
  }, [user]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const isInstructor = user?.is_instructor;
  const courses = isInstructor ? instructorCourses : enrolledCourses;
  const hasCourses = courses.length > 0;

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
      {/* Student hero: backdrop scene + mascot + XP/streak + trophy case (Phase 34) */}
      {!isInstructor && gameProfile?.is_gamified && (
        <>
          <DashboardHero
            profile={gameProfile}
            firstName={user?.first_name}
            hasEnrollments={hasCourses}
            onCustomize={() => setShowCustomizer(true)}
            onEnroll={() => setShowEnrollModal(true)}
          />
          <AvatarCustomizerModal open={showCustomizer} onOpenChange={setShowCustomizer} />
        </>
      )}

      {/* Continue Learning card - Students (standalone, below the hero) */}
      {hasCourses && !isInstructor && (
        <div className="relative rounded-xl p-8 mb-8 overflow-hidden border border-primary/20" style={{ background: 'linear-gradient(135deg, rgba(34, 197, 94, 0.1) 0%, rgba(6, 182, 212, 0.05) 50%, transparent 100%)' }}>
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
                  <Link to={`/courses/${continueLearning.course_code}/map`}>
                    <Button size="lg" variant="neon">
                      <Play className="h-4 w-4 mr-2" />
                      Continue Learning
                    </Button>
                  </Link>
                </div>
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
      <div id="course-list" className="flex items-center justify-between mb-5">
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
                    <Button
                      variant="outline"
                      className="w-full"
                      onClick={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        navigate(`/instructor/courses/${course.code}/manage`);
                      }}
                    >
                      Manage
                    </Button>
                  </div>
                </Link>
              ))
            : enrolledCourses.map((enrollment) => {
                const progress = courseProgressOverview.find(
                  (course) => course.course_code === enrollment.course.code
                );
                return (
                  <Link
                    key={enrollment.id}
                    to={`/courses/${enrollment.course.code}`}
                    className="card-gaming card-interactive p-6 flex flex-col hover:border-primary/50 transition-colors"
                  >
                    <div className="flex-1">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <h3 className="text-lg font-semibold mb-2">{enrollment.course.title}</h3>
                          <p className="text-sm text-muted-foreground mb-1">{enrollment.course.code}</p>
                          <p className="text-sm text-muted-foreground">
                            {enrollment.course.instructor.first_name} {enrollment.course.instructor.last_name}
                          </p>
                        </div>
                        {progress && (
                          <div className="text-right flex-shrink-0">
                            <p className="text-2xl font-bold text-gradient-gaming">{progress.overall_percentage}%</p>
                            <p className="text-xs text-muted-foreground">Overall</p>
                          </div>
                        )}
                      </div>
                      {progress && (
                        <div className="space-y-3 mt-4">
                          <div>
                            <div className="flex items-center justify-between text-sm mb-1">
                              <span className="text-muted-foreground flex items-center gap-1.5">
                                <BookOpen className="h-3.5 w-3.5" />
                                Lessons
                              </span>
                              <span className="font-medium">{progress.lessons.completed}/{progress.lessons.total}</span>
                            </div>
                            <div className="h-2 bg-muted rounded-full overflow-hidden">
                              <div
                                className="h-full bg-gradient-to-r from-primary to-accent transition-all duration-500"
                                style={{ width: `${progress.lessons.percentage}%` }}
                              />
                            </div>
                          </div>
                          {progress.quizzes.total > 0 && (
                            <div>
                              <div className="flex items-center justify-between text-sm mb-1">
                                <span className="text-muted-foreground flex items-center gap-1.5">
                                  <Trophy className="h-3.5 w-3.5" />
                                  Quizzes
                                </span>
                                <span className="font-medium">{progress.quizzes.passed}/{progress.quizzes.total} passed</span>
                              </div>
                              <div className="h-2 bg-muted rounded-full overflow-hidden">
                                <div
                                  className="h-full bg-gradient-to-r from-[#8b5cf6] to-[#ec4899] transition-all duration-500"
                                  style={{ width: `${progress.quizzes.percentage}%` }}
                                />
                              </div>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                    <div className="mt-4 pt-4 border-t border-border flex gap-2">
                      <Button variant="outline" className="flex-1">
                        View Course
                      </Button>
                      <Button
                        variant="outline"
                        className="flex-1"
                        onClick={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          navigate(`/courses/${enrollment.course.code}/map`);
                        }}
                      >
                        <MapIcon className="h-4 w-4 mr-2" />
                        Map
                      </Button>
                    </div>
                  </Link>
                );
              })}
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

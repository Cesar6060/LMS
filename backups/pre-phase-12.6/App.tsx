import { Routes, Route, Navigate } from 'react-router';
import { useAuth } from '@/contexts/AuthContext';
import { Header } from '@/components/layout/Header';
import { LoginPage } from '@/pages/auth/LoginPage';
import { RegisterPage } from '@/pages/auth/RegisterPage';
import { ForgotPasswordPage } from '@/pages/auth/ForgotPasswordPage';
import { ResetPasswordPage } from '@/pages/auth/ResetPasswordPage';
import { VerifyEmailPage } from '@/pages/auth/VerifyEmailPage';
import { DashboardPage } from '@/pages/DashboardPage';
import { CoursesPage } from '@/pages/courses/CoursesPage';
import { CourseDetailPage } from '@/pages/courses/CourseDetailPage';
import { LessonPage } from '@/pages/courses/LessonPage';
import { CreateCoursePage } from '@/pages/instructor/CreateCoursePage';
import { ManageCoursePage } from '@/pages/instructor/ManageCoursePage';
import { AssignmentDetailPage } from '@/pages/assignments/AssignmentDetailPage';
import { GradingPage } from '@/pages/instructor/GradingPage';
import { GradebookPage } from '@/pages/instructor/GradebookPage';
import { StudentRosterPage } from '@/pages/instructor/StudentRosterPage';
import { AnnouncementsPage } from '@/pages/announcements/AnnouncementsPage';
import { AnnouncementDetailPage } from '@/pages/announcements/AnnouncementDetailPage';
import { QuizDetailPage } from '@/pages/quizzes/QuizDetailPage';
import { QuizEditorPage } from '@/pages/instructor/QuizEditorPage';
import { MyGradesPage } from '@/pages/student/MyGradesPage';
import { SettingsPage } from '@/pages/SettingsPage';
import { NotFoundPage } from '@/pages/NotFoundPage';
import { Loader2 } from 'lucide-react';

// Protected route wrapper
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}

// Public route wrapper (redirects to dashboard if logged in)
function PublicRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />;
  }

  return <>{children}</>;
}

// Instructor-only route wrapper
function InstructorRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading, user } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (!user?.is_instructor) {
    return <Navigate to="/dashboard" replace />;
  }

  return <>{children}</>;
}

function App() {
  return (
    <div className="min-h-screen bg-background">
      <Header />
      <main>
        <Routes>
          {/* Public routes */}
          <Route
            path="/login"
            element={
              <PublicRoute>
                <LoginPage />
              </PublicRoute>
            }
          />
          <Route
            path="/register"
            element={
              <PublicRoute>
                <RegisterPage />
              </PublicRoute>
            }
          />
          <Route
            path="/forgot-password"
            element={
              <PublicRoute>
                <ForgotPasswordPage />
              </PublicRoute>
            }
          />
          <Route
            path="/reset-password"
            element={
              <PublicRoute>
                <ResetPasswordPage />
              </PublicRoute>
            }
          />
          <Route
            path="/verify-email"
            element={<VerifyEmailPage />}
          />

          {/* Protected routes */}
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <DashboardPage />
              </ProtectedRoute>
            }
          />

          {/* Course routes */}
          <Route
            path="/courses"
            element={
              <ProtectedRoute>
                <CoursesPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/courses/:code"
            element={
              <ProtectedRoute>
                <CourseDetailPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/courses/:code/lessons/:lessonId"
            element={
              <ProtectedRoute>
                <LessonPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/courses/:code/announcements"
            element={
              <ProtectedRoute>
                <AnnouncementsPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/courses/:code/announcements/:announcementId"
            element={
              <ProtectedRoute>
                <AnnouncementDetailPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/courses/:code/grades"
            element={
              <ProtectedRoute>
                <MyGradesPage />
              </ProtectedRoute>
            }
          />

          {/* Assignment routes */}
          <Route
            path="/assignments/:assignmentId"
            element={
              <ProtectedRoute>
                <AssignmentDetailPage />
              </ProtectedRoute>
            }
          />

          {/* Settings route */}
          <Route
            path="/settings"
            element={
              <ProtectedRoute>
                <SettingsPage />
              </ProtectedRoute>
            }
          />

          {/* Quiz route */}
          <Route
            path="/quizzes/:quizId"
            element={
              <ProtectedRoute>
                <QuizDetailPage />
              </ProtectedRoute>
            }
          />

          {/* Instructor routes */}
          <Route
            path="/instructor/courses/new"
            element={
              <InstructorRoute>
                <CreateCoursePage />
              </InstructorRoute>
            }
          />
          <Route
            path="/instructor/courses/:code/manage"
            element={
              <InstructorRoute>
                <ManageCoursePage />
              </InstructorRoute>
            }
          />
          <Route
            path="/instructor/assignments/:assignmentId/grade"
            element={
              <InstructorRoute>
                <GradingPage />
              </InstructorRoute>
            }
          />
          <Route
            path="/instructor/courses/:code/gradebook"
            element={
              <InstructorRoute>
                <GradebookPage />
              </InstructorRoute>
            }
          />
          <Route
            path="/instructor/courses/:code/students"
            element={
              <InstructorRoute>
                <StudentRosterPage />
              </InstructorRoute>
            }
          />
          <Route
            path="/instructor/courses/:code/quizzes"
            element={
              <InstructorRoute>
                <QuizEditorPage />
              </InstructorRoute>
            }
          />

          {/* Default redirect */}
          <Route path="/" element={<Navigate to="/dashboard" replace />} />

          {/* 404 */}
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </main>
    </div>
  );
}

export default App;

import { Routes, Route, Navigate, useLocation, useParams, useSearchParams } from 'react-router';
import * as Sentry from '@sentry/react';
import { useAuth } from '@/contexts/AuthContext';
import { AvatarProvider } from '@/contexts/AvatarContext';
import { AccessDenied } from '@/components/AccessDenied';
import { Layout } from '@/components/layout/Layout';
import { LoginPage } from '@/pages/auth/LoginPage';
import { ForgotPasswordPage } from '@/pages/auth/ForgotPasswordPage';
import { ResetPasswordPage } from '@/pages/auth/ResetPasswordPage';
import { VerifyEmailPage } from '@/pages/auth/VerifyEmailPage';
import { DashboardPage } from '@/pages/DashboardPage';
import { CoursesPage } from '@/pages/courses/CoursesPage';
import { CourseDetailPage } from '@/pages/courses/CourseDetailPage';
import { CoursePlayerPage } from '@/pages/courses/CoursePlayerPage';
import { CourseMapPage } from '@/pages/courses/CourseMapPage';
import { CreateCoursePage } from '@/pages/instructor/CreateCoursePage';
import { ManageCoursePage } from '@/pages/instructor/ManageCoursePage';
import { LessonEditorPage } from '@/pages/instructor/LessonEditorPage';
import { GradebookPage } from '@/pages/instructor/GradebookPage';
import { StudentRosterPage } from '@/pages/instructor/StudentRosterPage';
import { AnnouncementsPage } from '@/pages/announcements/AnnouncementsPage';
import { AnnouncementDetailPage } from '@/pages/announcements/AnnouncementDetailPage';
import { DiscussionsPage } from '@/pages/discussions/DiscussionsPage';
import { ThreadDetailPage } from '@/pages/discussions/ThreadDetailPage';
import { QuizDetailPage } from '@/pages/quizzes/QuizDetailPage';
import { QuizEditorPage } from '@/pages/instructor/QuizEditorPage';
import { AnalyticsPage } from '@/pages/instructor/AnalyticsPage';
import { MyGradesPage } from '@/pages/student/MyGradesPage';
import { SettingsPage } from '@/pages/SettingsPage';
import { NotFoundPage } from '@/pages/NotFoundPage';
import { Loader2 } from 'lucide-react';

// Route-aware Sentry instrumentation: transactions get parameterized route
// names (/courses/:code) instead of raw URLs. No-op when Sentry is not
// initialized, so dev behaves exactly like plain <Routes>.
const SentryRoutes = Sentry.withSentryReactRouterV7Routing(Routes);

// Protected route wrapper
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
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
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (!user?.is_instructor) {
    return <AccessDenied message="This page is only available to instructors." />;
  }

  return <>{children}</>;
}

// /verify-email: logged-in users legitimately open links carrying a key
// (verification is optional + login-on-confirmation), so only bounce
// authenticated visitors when there is no key to consume.
function VerifyEmailRoute() {
  const { isAuthenticated, isLoading } = useAuth();
  const [searchParams] = useSearchParams();

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (isAuthenticated && !searchParams.get('key')) {
    return <Navigate to="/dashboard" replace />;
  }

  return <VerifyEmailPage />;
}

// Legacy lesson URL — the standalone lesson page was retired in favor of the
// course player; old links (and old notification URLs) redirect there.
function LegacyLessonRedirect() {
  const { code, lessonId } = useParams();
  return <Navigate to={`/courses/${code}/learn/${lessonId}`} replace />;
}

function App() {
  return (
    <AvatarProvider>
    <Layout>
        <SentryRoutes>
          {/* Public routes */}
          <Route
            path="/login"
            element={
              <PublicRoute>
                <LoginPage />
              </PublicRoute>
            }
          />
          {/* Public self-registration is removed — the live site is a demo and
              visitors sign in with the shared demo account. /register redirects
              to the login page so old links don't 404. */}
          <Route path="/register" element={<Navigate to="/login" replace />} />
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
            element={<VerifyEmailRoute />}
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
            element={<LegacyLessonRedirect />}
          />
          <Route
            path="/courses/:code/learn"
            element={
              <ProtectedRoute>
                <CoursePlayerPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/courses/:code/learn/:lessonId"
            element={
              <ProtectedRoute>
                <CoursePlayerPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/courses/:code/map"
            element={
              <ProtectedRoute>
                <CourseMapPage />
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
            path="/courses/:code/discussions"
            element={
              <ProtectedRoute>
                <DiscussionsPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/courses/:code/discussions/:threadId"
            element={
              <ProtectedRoute>
                <ThreadDetailPage />
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

          {/* Quiz routes - nested under course */}
          <Route
            path="/courses/:code/quizzes/:quizId"
            element={
              <ProtectedRoute>
                <QuizDetailPage />
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
            path="/instructor/courses/:code/lessons/:lessonId/edit"
            element={
              <InstructorRoute>
                <LessonEditorPage />
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
          <Route
            path="/instructor/courses/:code/analytics"
            element={
              <InstructorRoute>
                <AnalyticsPage />
              </InstructorRoute>
            }
          />

          {/* Default redirect */}
          <Route path="/" element={<Navigate to="/dashboard" replace />} />

          {/* 404 */}
          <Route path="*" element={<NotFoundPage />} />
        </SentryRoutes>
    </Layout>
    </AvatarProvider>
  );
}

export default App;

import { lazy, Suspense } from 'react';
import { Routes, Route, Navigate, useLocation, useParams, useSearchParams } from 'react-router';
import * as Sentry from '@sentry/react';
import { useAuth } from '@/contexts/useAuth';
import { AvatarProvider } from '@/contexts/AvatarContext';
import { AccessDenied } from '@/components/AccessDenied';
import { Layout } from '@/components/layout/Layout';
import { PageLoader } from '@/components/PageLoader';

// Pages are lazy-loaded so each route ships as its own chunk; contexts,
// layout, and route guards stay eager. Pages use named exports, hence the
// .then() remapping to the default export lazy() expects.
const LoginPage = lazy(() => import('@/pages/auth/LoginPage').then((m) => ({ default: m.LoginPage })));
const AcceptInvitePage = lazy(() => import('@/pages/auth/AcceptInvitePage').then((m) => ({ default: m.AcceptInvitePage })));
const TermsPage = lazy(() => import('@/pages/legal/TermsPage').then((m) => ({ default: m.TermsPage })));
const PrivacyPage = lazy(() => import('@/pages/legal/PrivacyPage').then((m) => ({ default: m.PrivacyPage })));
const ForgotPasswordPage = lazy(() => import('@/pages/auth/ForgotPasswordPage').then((m) => ({ default: m.ForgotPasswordPage })));
const ResetPasswordPage = lazy(() => import('@/pages/auth/ResetPasswordPage').then((m) => ({ default: m.ResetPasswordPage })));
const VerifyEmailPage = lazy(() => import('@/pages/auth/VerifyEmailPage').then((m) => ({ default: m.VerifyEmailPage })));
const DashboardPage = lazy(() => import('@/pages/DashboardPage').then((m) => ({ default: m.DashboardPage })));
const CoursesPage = lazy(() => import('@/pages/courses/CoursesPage').then((m) => ({ default: m.CoursesPage })));
const CourseDetailPage = lazy(() => import('@/pages/courses/CourseDetailPage').then((m) => ({ default: m.CourseDetailPage })));
const CoursePlayerPage = lazy(() => import('@/pages/courses/CoursePlayerPage').then((m) => ({ default: m.CoursePlayerPage })));
const CourseMapPage = lazy(() => import('@/pages/courses/CourseMapPage').then((m) => ({ default: m.CourseMapPage })));
const CreateCoursePage = lazy(() => import('@/pages/instructor/CreateCoursePage').then((m) => ({ default: m.CreateCoursePage })));
const ManageCoursePage = lazy(() => import('@/pages/instructor/ManageCoursePage').then((m) => ({ default: m.ManageCoursePage })));
const LessonEditorPage = lazy(() => import('@/pages/instructor/LessonEditorPage').then((m) => ({ default: m.LessonEditorPage })));
const GradebookPage = lazy(() => import('@/pages/instructor/GradebookPage').then((m) => ({ default: m.GradebookPage })));
const StudentRosterPage = lazy(() => import('@/pages/instructor/StudentRosterPage').then((m) => ({ default: m.StudentRosterPage })));
const AnnouncementsPage = lazy(() => import('@/pages/announcements/AnnouncementsPage').then((m) => ({ default: m.AnnouncementsPage })));
const AnnouncementDetailPage = lazy(() => import('@/pages/announcements/AnnouncementDetailPage').then((m) => ({ default: m.AnnouncementDetailPage })));
const DiscussionsPage = lazy(() => import('@/pages/discussions/DiscussionsPage').then((m) => ({ default: m.DiscussionsPage })));
const ThreadDetailPage = lazy(() => import('@/pages/discussions/ThreadDetailPage').then((m) => ({ default: m.ThreadDetailPage })));
const QuizDetailPage = lazy(() => import('@/pages/quizzes/QuizDetailPage').then((m) => ({ default: m.QuizDetailPage })));
const QuizEditorPage = lazy(() => import('@/pages/instructor/QuizEditorPage').then((m) => ({ default: m.QuizEditorPage })));
const AnalyticsPage = lazy(() => import('@/pages/instructor/AnalyticsPage').then((m) => ({ default: m.AnalyticsPage })));
const MyGradesPage = lazy(() => import('@/pages/student/MyGradesPage').then((m) => ({ default: m.MyGradesPage })));
const SettingsPage = lazy(() => import('@/pages/SettingsPage').then((m) => ({ default: m.SettingsPage })));
const NotFoundPage = lazy(() => import('@/pages/NotFoundPage').then((m) => ({ default: m.NotFoundPage })));

// Route-aware Sentry instrumentation: transactions get parameterized route
// names (/courses/:code) instead of raw URLs. No-op when Sentry is not
// initialized, so dev behaves exactly like plain <Routes>.
const SentryRoutes = Sentry.withSentryReactRouterV7Routing(Routes);

// Protected route wrapper
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return <PageLoader />;
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
    return <PageLoader />;
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
    return <PageLoader />;
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
    return <PageLoader />;
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
      <Suspense fallback={<PageLoader />}>
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
          {/* Invite accept page: reachable both logged-out (create account /
              log in first) and logged-in (existing account auto-accepts), so
              it deliberately has no guard. */}
          <Route path="/invite/:token" element={<AcceptInvitePage />} />
          {/* Legal pages — public, linked from Login and AcceptInvite. */}
          <Route path="/terms" element={<TermsPage />} />
          <Route path="/privacy" element={<PrivacyPage />} />

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
      </Suspense>
    </Layout>
    </AvatarProvider>
  );
}

export default App;

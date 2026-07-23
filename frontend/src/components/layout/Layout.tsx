import { type ReactNode } from 'react';
import { useLocation } from 'react-router';
import { useAuth } from '@/contexts/useAuth';
import { Header } from '@/components/layout/Header';
import { AnimatedBackground } from '@/components/ui/AnimatedBackground';

interface LayoutProps {
  children: ReactNode;
}

export function Layout({ children }: LayoutProps) {
  const location = useLocation();
  const { isAuthenticated } = useAuth();

  // Hide header in learning mode (CoursePlayerPage has its own header) and
  // on the course map (full-page backdrop scene with its own HUD header)
  const isLearningMode = location.pathname.match(/\/courses\/[^/]+\/(learn|map)/);

  // Auth pages handle their own background
  const isAuthPage = ['/login', '/register', '/forgot-password', '/reset-password', '/verify-email'].some(
    path => location.pathname.startsWith(path)
  );

  // Show animated background for logged-in pages (not auth pages, not learning mode)
  const showAnimatedBg = isAuthenticated && !isAuthPage && !isLearningMode;

  return (
    <div className="min-h-screen bg-background">
      {!isLearningMode && <Header />}
      {showAnimatedBg && (
        <AnimatedBackground
          fixed={true}
          showMouseGlow={false}
          showParticles={true}
          showOrbs={true}
          showGrid={true}
        />
      )}
      <main className="relative z-10">{children}</main>
    </div>
  );
}

import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router';
import { Button } from '@/components/ui/Button';
import { Card, CardContent } from '@/components/ui/Card';
import { BackdropScene } from '@/components/gamification/BackdropScene';
import { CourseMapPath } from '@/components/gamification/CourseMapPath';
import { getSceneTheme } from '@/components/gamification/backdrop';
import { useAvatarContext } from '@/contexts/AvatarContext';
import { courseService } from '@/services/courses';
import { gamificationService } from '@/services/gamification';
import { cn } from '@/lib/utils';
import type { CourseMap, GamificationProfile } from '@/types';
import { ChevronLeft, Loader2 } from 'lucide-react';

/**
 * Duolingo-style course map (Phase 35): the course as a winding vertical
 * path of lesson/boss nodes over the student's equipped backdrop scene.
 * Gating here is purely visual — the player's free navigation is untouched.
 */
export function CourseMapPage() {
  const { code } = useParams<{ code: string }>();
  const { avatar } = useAvatarContext();
  const [map, setMap] = useState<CourseMap | null>(null);
  const [profile, setProfile] = useState<GamificationProfile | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!code) return;
    let cancelled = false;
    (async () => {
      try {
        setIsLoading(true);
        setError('');
        const [mapData, profileData] = await Promise.all([
          courseService.getCourseMap(code),
          // Instructors get an inert payload; a failure just hides the HUD.
          gamificationService.getProfile().catch(() => null),
        ]);
        if (cancelled) return;
        setMap(mapData);
        setProfile(profileData);
      } catch (err: unknown) {
        const e = err as { response?: { status?: number } };
        if (!cancelled) {
          setError(
            e.response?.status === 403
              ? 'You must be enrolled in this course to view its map.'
              : 'Failed to load course map'
          );
        }
        console.error(err);
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [code]);

  // Same fallback rule as the dashboard hero: plain/none/unknown keys land
  // on the default gradient scene, so the page is never unstyled.
  const backdropKey = avatar?.equipped.backdrop ?? 'plain';
  const scene = getSceneTheme(backdropKey);
  const streak = profile?.is_gamified ? (profile.current_streak ?? 0) : null;

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (error || !map) {
    return (
      <div className="flex min-h-screen items-center justify-center px-4">
        <Card className="max-w-md">
          <CardContent className="py-8 text-center">
            <p className="text-destructive mb-4">{error || 'Course not found'}</p>
            <Link to="/dashboard">
              <Button>Back to Dashboard</Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      {/* Full-page equipped backdrop; content scrolls over it. */}
      <div className="fixed inset-0">
        <BackdropScene backdrop={backdropKey} />
      </div>

      <div className="relative">
        {/* Compact HUD header */}
        <header
          className={cn(
            'sticky top-0 z-20 border-b backdrop-blur-md',
            scene.dark
              ? 'border-white/10 bg-slate-950/50'
              : 'border-border bg-background/70'
          )}
        >
          <div className="mx-auto flex max-w-3xl items-center gap-3 px-4 py-3 sm:gap-4">
            <Link to={`/courses/${code}`}>
              <Button
                variant="outline"
                className={cn('gap-2', scene.button)}
                aria-label="Back to Course"
                title="Back to Course"
              >
                <ChevronLeft className="h-4 w-4" />
                <span className="hidden sm:inline">Back to Course</span>
              </Button>
            </Link>
            <h1
              className={cn(
                'min-w-0 flex-1 truncate text-lg font-semibold sm:text-xl',
                scene.dark && 'text-slate-100'
              )}
            >
              {map.course_title}
            </h1>
            <p
              className={cn(
                'font-gaming text-2xl font-bold leading-none sm:text-3xl',
                scene.numeral
              )}
              style={{ textShadow: 'none' }}
              title={`${map.completed_nodes} of ${map.total_nodes} steps complete`}
            >
              {map.completed_nodes}/{map.total_nodes}
            </p>
            {streak !== null && (
              <div className="flex items-center gap-1.5">
                <span
                  className={cn(
                    'text-2xl leading-none',
                    streak === 0 && 'grayscale opacity-40'
                  )}
                  aria-hidden="true"
                >
                  🔥
                </span>
                <span
                  className={cn(
                    'font-gaming text-2xl font-bold leading-none sm:text-3xl',
                    streak > 0 ? scene.numeral : scene.label
                  )}
                  style={{ textShadow: 'none' }}
                  title={`${streak}-day streak`}
                >
                  {streak}
                </span>
              </div>
            )}
          </div>
        </header>

        {/* The skill path */}
        <main className="px-4 pb-24 pt-2">
          <CourseMapPath units={map.units} courseCode={map.course_code} scene={scene} />
        </main>
      </div>
    </div>
  );
}

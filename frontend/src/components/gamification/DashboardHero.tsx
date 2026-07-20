import { Link } from 'react-router';
import { Button } from '@/components/ui/Button';
import { Mascot } from '@/components/gamification/Mascot';
import { BackdropScene } from '@/components/gamification/BackdropScene';
import { getSceneTheme } from '@/components/gamification/backdrop';
import { StreakFreezeChip } from '@/components/gamification/StreakFreezeChip';
import { useAvatarContext } from '@/contexts/AvatarContext';
import { cn } from '@/lib/utils';
import { Paintbrush, Plus, Trophy } from 'lucide-react';
import type { GamificationProfile } from '@/types';

interface DashboardHeroProps {
  profile: GamificationProfile;
  firstName?: string;
  /** Whether the student has any enrollments (drives the empty-state CTA). */
  hasEnrollments: boolean;
  onCustomize: () => void;
  onEnroll: () => void;
}

/**
 * The single student dashboard hero (Phase 34, layout per Claude Design
 * "Student Dashboard" 1a): equipped avatar backdrop as the container
 * background, with every container/button restyled from the scene's own
 * palette (see `getSceneTheme`) so the hero reads as one composition.
 * Trophy case behind the mascot shows unearned badges as black silhouettes;
 * Continue Learning lives in its own card below the hero.
 */
export function DashboardHero({
  profile,
  firstName,
  hasEnrollments,
  onCustomize,
  onEnroll,
}: DashboardHeroProps) {
  const { avatar } = useAvatarContext();
  const name = avatar?.mascot_name ?? 'Circuit';
  const level = profile.level ?? 1;
  const progressPct = profile.level_progress_pct ?? 0;
  const xpIntoLevel = profile.xp_into_level ?? 0;
  const levelSpan = profile.level_span ?? 100;
  const allBadges = profile.all_badges ?? [];

  const backdropKey = avatar?.equipped.backdrop ?? 'plain';
  const scene = getSceneTheme(backdropKey);
  const textShadow = {
    textShadow: scene.dark
      ? '0 1px 3px rgba(0, 0, 0, 0.6)'
      : '0 1px 3px hsl(var(--background) / 0.7)',
  };

  return (
    <div className="relative mb-8 overflow-hidden rounded-xl border border-primary/20">
      <BackdropScene backdrop={backdropKey} />
      <div className="relative p-5 pb-16 sm:p-8 sm:pb-16">
        {/* Corners: level/XP left, streak right — no containers; big Orbitron
            gradient numerals matching the Trophy Case treatment */}
        <div className="flex items-start justify-between gap-3" style={textShadow}>
          <div>
            <p
              className={cn(
                'font-gaming text-2xl font-bold uppercase leading-none sm:text-3xl',
                scene.numeral
              )}
              style={{ textShadow: 'none' }}
            >
              Lv {level}
            </p>
            <div className={cn('progress-gaming mt-2 w-28 sm:w-40', scene.track)}>
              <div className="progress-gaming-bar" style={{ width: `${progressPct}%` }} />
            </div>
            <p className={cn('mt-1 text-sm font-medium', scene.label)}>
              {xpIntoLevel} / {levelSpan} XP
            </p>
          </div>
          <div className="flex items-center gap-2.5">
            <span
              className={cn(
                'text-4xl leading-none',
                (profile.current_streak ?? 0) === 0 && 'grayscale opacity-40'
              )}
              aria-hidden="true"
            >
              🔥
            </span>
            <div className="flex flex-col text-left leading-tight">
              <span
                className={cn(
                  'font-gaming text-2xl font-bold leading-none sm:text-3xl',
                  (profile.current_streak ?? 0) > 0
                    ? scene.numeral
                    : scene.dark
                      ? scene.label
                      : 'text-muted-foreground'
                )}
                style={{ textShadow: 'none' }}
              >
                {profile.current_streak ?? 0}
              </span>
              <span className={cn('mt-0.5 text-sm font-medium', scene.label)}>
                day{(profile.current_streak ?? 0) === 1 ? '' : 's'}
                {typeof profile.longest_streak === 'number' &&
                  profile.longest_streak > 0 &&
                  ` · best ${profile.longest_streak}`}
              </span>
            </div>
            <StreakFreezeChip count={profile.streak_freezes ?? 0} />
          </div>
        </div>

        <div className="mt-3 flex flex-col items-center text-center">
          {/* Trophy-case shelf standing behind the mascot */}
          {allBadges.length > 0 && (
            <div className="relative z-0 w-full max-w-2xl" style={textShadow}>
              <div className="mb-4 flex items-center justify-center gap-3 sm:gap-4">
                <span className="h-px w-10 bg-gradient-to-r from-transparent to-amber-400/70 sm:w-20" />
                <span
                  className="flex items-center gap-2 bg-gradient-to-b from-amber-200 via-yellow-400 to-amber-600 bg-clip-text font-gaming text-lg font-bold uppercase tracking-[0.18em] text-transparent drop-shadow-[0_1px_2px_rgba(0,0,0,0.45)] sm:text-xl"
                  style={{ textShadow: 'none' }}
                >
                  <Trophy className="h-5 w-5 text-amber-400 sm:h-6 sm:w-6" />
                  Trophy Case
                </span>
                <span className="h-px w-10 bg-gradient-to-l from-transparent to-amber-400/70 sm:w-20" />
                <Link
                  to="/settings?tab=achievements"
                  className={cn('text-sm font-medium hover:underline', scene.accent)}
                >
                  View all
                </Link>
              </div>
              <div className="flex flex-wrap items-end justify-center gap-x-4 gap-y-3">
                {allBadges.map((badge) => (
                  <div
                    key={badge.key}
                    title={
                      badge.earned
                        ? `${badge.name} — earned`
                        : `Locked: ${badge.description}`
                    }
                    className="flex w-14 flex-col items-center"
                  >
                    <span
                      className={cn(
                        'flex h-12 w-12 items-center justify-center rounded-lg text-3xl leading-none backdrop-blur-sm',
                        badge.earned
                          ? 'border border-amber-300/50 bg-amber-300/15'
                          : scene.dark
                            ? 'bg-white/30'
                            : 'bg-muted-foreground/15'
                      )}
                    >
                      {/* Unearned badges render as black silhouettes. */}
                      <span
                        aria-hidden="true"
                        style={badge.earned ? undefined : { filter: 'brightness(0)' }}
                      >
                        {badge.icon}
                      </span>
                    </span>
                    {/* Pedestal stand under each trophy */}
                    <span
                      className={cn(
                        'mt-1 h-1.5 w-10 rounded-sm',
                        badge.earned
                          ? 'bg-gradient-to-b from-amber-300 to-amber-500'
                          : scene.dark
                            ? 'bg-white/30'
                            : 'bg-muted-foreground/30'
                      )}
                    />
                  </div>
                ))}
              </div>
              {/* Shelf the trophies stand on */}
              <div className="mx-auto mt-1.5 h-2 max-w-xl rounded-full bg-gradient-to-r from-transparent via-amber-500/70 to-transparent" />
            </div>
          )}

          {/* Mascot with speech-bubble greeting (design 1a) */}
          <div className="mt-6 flex flex-col items-center justify-center gap-3 sm:flex-row sm:items-start sm:gap-0">
            <div className="text-center">
              <Mascot pose="idle" size={150} hideBackdrop />
              <div
                className={cn(
                  'mt-1 font-gaming text-xl font-bold uppercase tracking-[0.14em] sm:text-2xl',
                  scene.numeral
                )}
                style={{ textShadow: 'none' }}
              >
                {name}
              </div>
            </div>
            <div className="relative max-w-md sm:ml-8 sm:mt-7">
              {/* Thought-bubble dots pointing at the mascot */}
              <span
                className={cn(
                  'absolute -left-7 top-10 hidden h-2.5 w-2.5 rounded-full border sm:block',
                  scene.bubble
                )}
              />
              <span
                className={cn(
                  'absolute -left-4 top-5 hidden h-4 w-4 rounded-full border sm:block',
                  scene.bubble
                )}
              />
              <div
                className={cn(
                  'rounded-[28px] border px-6 py-4 text-left backdrop-blur-sm',
                  scene.bubble
                )}
              >
                <p className="text-[17px] leading-relaxed">
                  Welcome back{firstName ? `, ${firstName}` : ''}! Ready for today's quest?
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Empty-state CTA: only when the student has no enrollments */}
        {!hasEnrollments && (
          <div
            className={cn(
              'mt-6 flex flex-col items-center gap-3 text-center',
              scene.dark && 'text-zinc-100'
            )}
            style={textShadow}
          >
            <p className="text-lg font-medium">
              You're not enrolled in any courses yet — join one to begin earning XP
            </p>
            <Button size="lg" variant="neon" onClick={onEnroll}>
              <Plus className="mr-2 h-4 w-4" />
              Join a Course
            </Button>
          </div>
        )}

        {/* Customize pinned to the hero corner (design 1a) */}
        <Button
          variant="outline"
          onClick={onCustomize}
          className={cn('absolute bottom-5 right-5', scene.button)}
        >
          <Paintbrush className="mr-2 h-4 w-4" />
          Customize
        </Button>
      </div>
    </div>
  );
}

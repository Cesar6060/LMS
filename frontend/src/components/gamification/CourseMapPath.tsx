import { Link } from 'react-router';
import { Check, Crown, Lock, Star } from 'lucide-react';
import { Mascot } from '@/components/gamification/Mascot';
import type { SceneTheme } from '@/components/gamification/backdrop';
import { cn } from '@/lib/utils';
import type { CourseMapNode, CourseMapUnit } from '@/types';

/** Vertical space per node; leaves room for the disc plus its title. */
const ROW_H = 124;
/** Horizontal swing of the serpentine, in 0-100 viewBox units. */
const AMPLITUDE = 24;

/** Serpentine x position (percent): 50 → 74 → 50 → 26 → 50 … The global
 *  node index keeps the winding continuous across unit boundaries. */
function nodeX(globalIndex: number): number {
  return 50 + AMPLITUDE * Math.sin((globalIndex * Math.PI) / 2);
}

function nodeY(localIndex: number): number {
  return localIndex * ROW_H + ROW_H / 2;
}

interface MapNodeProps {
  node: CourseMapNode;
  /** x percent / y px of the disc center inside the unit stretch. */
  x: number;
  y: number;
  courseCode: string;
  scene: SceneTheme;
}

/**
 * One stop on the course map. Lock state is visual only — locked nodes just
 * aren't links; every lesson/quiz stays freely reachable from the player.
 */
function MapNode({ node, x, y, courseCode, scene }: MapNodeProps) {
  const isBoss = node.node_type === 'quiz';
  const isCompleted = node.state === 'completed';
  const isCurrent = node.state === 'current';
  const isLocked = node.state === 'locked';
  const size = isBoss ? 80 : 64;

  const textShadow = {
    textShadow: scene.dark
      ? '0 1px 3px rgba(0, 0, 0, 0.6)'
      : '0 1px 3px hsl(var(--background) / 0.7)',
  };

  // Completed nodes go bright gold (like earned trophy tiles); boss nodes
  // keep a gold accent regardless of scene; the rest are scene-tinted.
  const discClass = cn(
    'relative flex items-center justify-center rounded-full border-4 shadow-lg transition-transform',
    isCompleted &&
      'border-amber-300 bg-gradient-to-b from-amber-300 to-amber-500 text-amber-950',
    !isCompleted &&
      isBoss &&
      cn(
        'border-amber-400/80 text-amber-400',
        scene.dark ? 'bg-slate-950/70 backdrop-blur-sm' : 'bg-card'
      ),
    !isCompleted &&
      !isBoss &&
      !isLocked &&
      (scene.dark
        ? 'border-white/60 bg-white/15 text-white backdrop-blur-sm'
        : 'border-primary/60 bg-card text-primary'),
    isLocked &&
      cn(
        'opacity-70',
        scene.dark
          ? 'border-white/25 bg-white/10 text-white/45 backdrop-blur-sm'
          : 'border-muted-foreground/30 bg-muted/70 text-muted-foreground/60'
      ),
    isCurrent && 'scale-110'
  );

  const icon = isLocked ? (
    <Lock className={cn(isBoss ? 'h-8 w-8' : 'h-6 w-6')} />
  ) : isBoss ? (
    <Crown className="h-9 w-9" fill={isCompleted ? 'currentColor' : 'none'} />
  ) : isCompleted ? (
    <Check className="h-7 w-7" strokeWidth={3.5} />
  ) : (
    <Star className="h-6 w-6" fill="currentColor" />
  );

  const disc = (
    <span className={discClass} style={{ width: size, height: size }}>
      {isCurrent && (
        <>
          <span
            className={cn(
              'absolute -inset-2 rounded-full border-4 border-current animate-ping',
              scene.accent
            )}
            aria-hidden="true"
          />
          <span
            className={cn(
              'absolute -inset-2 rounded-full border-2 border-current',
              scene.accent
            )}
            aria-hidden="true"
          />
        </>
      )}
      {icon}
    </span>
  );

  return (
    <div
      className="absolute flex w-32 -translate-x-1/2 -translate-y-1/2 flex-col items-center"
      style={{ left: `${x}%`, top: y }}
    >
      {/* Circuit stands beside the current node, on the roomier side. */}
      {isCurrent && (
        <div
          className={cn(
            'absolute top-1/2 -translate-y-[65%]',
            x > 50 ? '-left-20' : '-right-20'
          )}
          aria-hidden="true"
        >
          <Mascot pose="cheer" size={72} hideBackdrop />
        </div>
      )}

      {isLocked ? (
        <span
          className="cursor-not-allowed"
          title="Complete the previous lesson to unlock"
          aria-disabled="true"
        >
          {disc}
        </span>
      ) : (
        <Link
          to={
            node.node_type === 'lesson'
              ? `/courses/${courseCode}/learn/${node.id}`
              : `/courses/${courseCode}/quizzes/${node.id}`
          }
          title={node.title}
          className="rounded-full hover:scale-105 transition-transform"
        >
          {disc}
        </Link>
      )}

      <span
        className={cn(
          'mt-2 w-full truncate text-center text-sm font-medium',
          isLocked
            ? scene.label
            : scene.dark
              ? 'text-slate-100'
              : 'text-foreground'
        )}
        style={textShadow}
      >
        {node.title}
      </span>
      {isBoss && node.best_score !== null && (
        <span
          className={cn('text-xs font-semibold', scene.dark ? 'text-amber-300' : 'text-amber-600')}
          style={textShadow}
        >
          Best {Math.round(node.best_score)}%
        </span>
      )}
    </div>
  );
}

interface UnitStretchProps {
  nodes: CourseMapNode[];
  startIndex: number;
  courseCode: string;
  scene: SceneTheme;
}

/** One unit's run of nodes with its winding SVG connector behind them. */
function UnitStretch({ nodes, startIndex, courseCode, scene }: UnitStretchProps) {
  const height = nodes.length * ROW_H;

  return (
    <div className="relative" style={{ height }}>
      <svg
        className="absolute inset-0 h-full w-full"
        viewBox={`0 0 100 ${height}`}
        preserveAspectRatio="none"
        aria-hidden="true"
      >
        {nodes.slice(0, -1).map((node, i) => {
          const x1 = nodeX(startIndex + i);
          const x2 = nodeX(startIndex + i + 1);
          const y1 = nodeY(i);
          const y2 = nodeY(i + 1);
          // Segments behind a completed node light up in the scene accent.
          const lit = node.state === 'completed';
          return (
            <path
              key={`${node.node_type}-${node.id}`}
              d={`M ${x1} ${y1} C ${x1} ${y1 + ROW_H / 2}, ${x2} ${y2 - ROW_H / 2}, ${x2} ${y2}`}
              fill="none"
              stroke="currentColor"
              strokeWidth={lit ? 5 : 4}
              strokeLinecap="round"
              vectorEffect="non-scaling-stroke"
              className={cn(
                lit ? scene.accent : scene.dark ? 'text-white/25' : 'text-foreground/15'
              )}
            />
          );
        })}
      </svg>
      {nodes.map((node, i) => (
        <MapNode
          key={`${node.node_type}-${node.id}`}
          node={node}
          x={nodeX(startIndex + i)}
          y={nodeY(i)}
          courseCode={courseCode}
          scene={scene}
        />
      ))}
    </div>
  );
}

interface CourseMapPathProps {
  units: CourseMapUnit[];
  courseCode: string;
  scene: SceneTheme;
}

/**
 * The Duolingo-style skill path (Phase 35): a single vertical scroll of
 * winding nodes, Orbitron unit header bands between unit stretches.
 */
export function CourseMapPath({ units, courseCode, scene }: CourseMapPathProps) {
  let globalIndex = 0;
  const sections = units
    .filter((unit) => unit.nodes.length > 0)
    .map((unit) => {
      const startIndex = globalIndex;
      globalIndex += unit.nodes.length;
      return { unit, startIndex };
    });

  return (
    <div className="mx-auto w-full max-w-md">
      {sections.map(({ unit, startIndex }) => (
        <section key={unit.id}>
          <header className="my-6 flex items-center gap-3 sm:gap-4">
            <span
              className={cn(
                'h-px flex-1 bg-gradient-to-r from-transparent to-current opacity-60',
                scene.accent
              )}
            />
            <h2
              className={cn(
                'font-gaming text-lg font-bold uppercase tracking-[0.14em] sm:text-xl',
                scene.numeral
              )}
              style={{ textShadow: 'none' }}
            >
              {unit.title}
            </h2>
            <span
              className={cn(
                'h-px flex-1 bg-gradient-to-l from-transparent to-current opacity-60',
                scene.accent
              )}
            />
          </header>
          <UnitStretch
            nodes={unit.nodes}
            startIndex={startIndex}
            courseCode={courseCode}
            scene={scene}
          />
        </section>
      ))}
    </div>
  );
}

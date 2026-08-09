/**
 * The course player's Next/Previous chain (phase 70).
 *
 * Before this module the player walked `units.flatMap(u => u.lessons)`, which
 * had three problems: it stepped straight over every unit quiz (reachable only
 * from the sidebar), it walked into units the instructor had locked (the API
 * withholds a locked unit's lessons from students but still sends them to the
 * course owner), and a stale lesson id produced `findIndex` → -1, so "Next"
 * silently jumped to lesson 1.
 *
 * The chain here is one explicit, ordered list of nodes — lessons and unit
 * quizzes interleaved — so all three cases are decidable and testable without
 * mounting the player. Kept pure in the shape of `lib/courseProgress.ts`: no
 * React, no service imports, minimal input interfaces.
 *
 * Node identity is `kind` + `id`, never `id` alone: lessons and quizzes are
 * separate tables and their ids collide freely. This is the same reason
 * `course_map` keys its cursor on a composite `current_node_id`
 * (`backend/courses/serializers.py:1093`).
 */

/** The subset of a lesson the chain needs. */
export interface ChainLesson {
  id: number;
  title: string;
}

/** The subset of a unit the chain needs. */
export interface ChainUnit {
  id: number;
  title: string;
  lessons: ChainLesson[];
  /**
   * Phase 66 — locked by the instructor. Locked units are dropped from the
   * chain for EVERYONE, the course owner included: the owner still receives
   * `lessons[]` for a locked unit (`UnitSerializer.to_representation`), so
   * without this check their Next walks into content they just locked.
   */
  is_locked?: boolean;
}

/** The subset of a unit-wide quiz the chain needs. */
export interface ChainQuiz {
  id: number;
  title: string;
  /** Absent on a course-level quiz that belongs to no unit — those are skipped. */
  unit?: number;
  order: number;
}

export type ChainNode = {
  kind: 'lesson' | 'quiz';
  id: number;
  title: string;
  unitId: number;
  unitTitle: string;
};

/**
 * Flatten the course into the order Next/Previous walk.
 *
 * Units come in payload order (the API already sorts by `unit.order`); within a
 * unit, its lessons in payload order, then its quizzes sorted by `order`. So the
 * last lesson of a unit is followed by that unit's quiz, and the quiz by the
 * next unit's first lesson — which is what a student expects at a unit boundary
 * and what the sidebar has always shown.
 */
export function buildChain(units: ChainUnit[], quizzes: ChainQuiz[]): ChainNode[] {
  const chain: ChainNode[] = [];

  for (const unit of units) {
    if (unit.is_locked) continue;

    for (const lesson of unit.lessons) {
      chain.push({
        kind: 'lesson',
        id: lesson.id,
        title: lesson.title,
        unitId: unit.id,
        unitTitle: unit.title,
      });
    }

    const unitQuizzes = quizzes
      .filter(quiz => quiz.unit === unit.id)
      // Copy before sorting — `quizzes` is React state and must not be mutated.
      .slice()
      .sort((a, b) => a.order - b.order);

    for (const quiz of unitQuizzes) {
      chain.push({
        kind: 'quiz',
        id: quiz.id,
        title: quiz.title,
        unitId: unit.id,
        unitTitle: unit.title,
      });
    }
  }

  return chain;
}

function indexOfNode(chain: ChainNode[], kind: ChainNode['kind'], id: number): number {
  return chain.findIndex(node => node.kind === kind && node.id === id);
}

/**
 * The node after the given one, or null at the end of the course.
 *
 * Returns null — never the first node — when the current node is not in the
 * chain at all (a stale id, or a lesson inside a unit that has since been
 * locked). The old `findIndex` code answered `-1 + 1 = 0` there and jumped the
 * student back to lesson 1.
 */
export function getNextNode(
  chain: ChainNode[],
  kind: ChainNode['kind'],
  id: number
): ChainNode | null {
  const index = indexOfNode(chain, kind, id);
  if (index === -1) return null;
  return chain[index + 1] ?? null;
}

/** The node before the given one, or null at the start of the course. */
export function getPreviousNode(
  chain: ChainNode[],
  kind: ChainNode['kind'],
  id: number
): ChainNode | null {
  const index = indexOfNode(chain, kind, id);
  if (index <= 0) return null;
  return chain[index - 1];
}

import { describe, expect, it } from 'vitest';
import {
  buildChain,
  getNextNode,
  getPreviousNode,
  type ChainNode,
  type ChainQuiz,
  type ChainUnit,
} from './playerNavigation';

/**
 * Phase 70. Before this module the player walked `units.flatMap(u => u.lessons)`:
 * unit quizzes were stepped over entirely, locked units were walked into (the
 * API still sends their lessons to the course owner), and a stale lesson id
 * gave `findIndex` → -1 so "Next" answered `-1 + 1 = 0` and jumped the student
 * back to lesson 1. The absent-node and locked-unit tests below are the ones
 * that failed under that flat list.
 */

function unit(id: number, title: string, lessons: Array<[number, string]>): ChainUnit {
  return {
    id,
    title,
    lessons: lessons.map(([lessonId, lessonTitle]) => ({ id: lessonId, title: lessonTitle })),
  };
}

/**
 * Phase 66. A unit the instructor locked. Students receive it with
 * `lessons: []` (the backend withholds them); the course owner receives the
 * full list — both shapes must be dropped from the chain, so the check cannot
 * lean on the empty list alone.
 */
function lockedUnit(
  id: number,
  title: string,
  lessons: Array<[number, string]> = []
): ChainUnit {
  return { ...unit(id, title, lessons), is_locked: true };
}

function quiz(id: number, title: string, unitId: number | undefined, order = 0): ChainQuiz {
  return { id, title, unit: unitId, order };
}

/**
 * The shape every boundary test walks: two units with a quiz each, then a
 * third with none. Chain order is lesson 10, 11, quiz 100, lesson 20, quiz 200,
 * lesson 30 — six nodes, three unit boundaries of two different kinds.
 */
function courseUnits(): ChainUnit[] {
  return [
    unit(1, 'Unit One', [[10, 'L1'], [11, 'L2']]),
    unit(2, 'Unit Two', [[20, 'L3']]),
    unit(3, 'Unit Three', [[30, 'L4']]),
  ];
}

function courseQuizzes(): ChainQuiz[] {
  return [quiz(100, 'Unit One Quiz', 1), quiz(200, 'Unit Two Quiz', 2)];
}

/** `kind:id` pairs, the readable form of a chain for order assertions. */
function ids(chain: ChainNode[]): string[] {
  return chain.map(node => `${node.kind}:${node.id}`);
}

describe('buildChain', () => {
  it('returns an empty chain for a course with no units', () => {
    expect(buildChain([], [])).toEqual([]);
  });

  it('returns an empty chain when the only unit has neither lessons nor a quiz', () => {
    expect(buildChain([unit(1, 'Empty', [])], [])).toEqual([]);
  });

  it('keeps a unit that has a quiz but no lessons', () => {
    // Real shape for a unit that is assessment-only; the quiz is still a node.
    const chain = buildChain([unit(1, 'Assessment', [])], [quiz(100, 'Unit One Quiz', 1)]);
    expect(ids(chain)).toEqual(['quiz:100']);
  });

  it('chains a unit with no quiz as lessons alone', () => {
    const chain = buildChain([unit(1, 'Unit One', [[10, 'L1'], [11, 'L2']])], []);
    expect(ids(chain)).toEqual(['lesson:10', 'lesson:11']);
  });

  it('puts each unit’s quiz after that unit’s lessons', () => {
    expect(ids(buildChain(courseUnits(), courseQuizzes()))).toEqual([
      'lesson:10',
      'lesson:11',
      'quiz:100',
      'lesson:20',
      'quiz:200',
      'lesson:30',
    ]);
  });

  it('carries the owning unit onto every node', () => {
    const chain = buildChain(courseUnits(), courseQuizzes());

    expect(chain[2]).toEqual({
      kind: 'quiz',
      id: 100,
      title: 'Unit One Quiz',
      unitId: 1,
      unitTitle: 'Unit One',
    });
    expect(chain[3]).toEqual({
      kind: 'lesson',
      id: 20,
      title: 'L3',
      unitId: 2,
      unitTitle: 'Unit Two',
    });
  });

  it('starts at unit 2 when the first unit is locked', () => {
    // The instructor view: the locked unit still carries its lessons.
    const units = [
      lockedUnit(1, 'Locked Unit', [[10, 'L1']]),
      unit(2, 'Unit Two', [[20, 'L2']]),
    ];
    const chain = buildChain(units, [quiz(100, 'Locked Unit Quiz', 1), quiz(200, 'Unit Two Quiz', 2)]);

    expect(ids(chain)).toEqual(['lesson:20', 'quiz:200']);
  });

  it('ends at the previous unit’s last node when the last unit is locked', () => {
    const units = [
      unit(1, 'Unit One', [[10, 'L1']]),
      lockedUnit(2, 'Locked Unit', [[20, 'L2']]),
    ];
    const chain = buildChain(units, [quiz(100, 'Unit One Quiz', 1), quiz(200, 'Locked Unit Quiz', 2)]);

    expect(ids(chain)).toEqual(['lesson:10', 'quiz:100']);
  });

  it('drops a locked unit the student sees with no lessons', () => {
    const units = [
      unit(1, 'Unit One', [[10, 'L1']]),
      lockedUnit(2, 'Locked Unit'),
      unit(3, 'Unit Three', [[30, 'L3']]),
    ];
    expect(ids(buildChain(units, []))).toEqual(['lesson:10', 'lesson:30']);
  });

  it('returns an empty chain when every unit is locked', () => {
    expect(buildChain([lockedUnit(1, 'Locked Unit', [[10, 'L1']])], [])).toEqual([]);
  });

  it('gives a lesson and a quiz sharing a numeric id two distinct nodes', () => {
    // Lessons and quizzes are separate tables, so id 7 can be both. Keying on
    // `id` alone collapses these two rows — the reason node identity is
    // `kind` + `id` and the reason course_map uses a composite cursor.
    const chain = buildChain([unit(1, 'Unit One', [[7, 'Lesson seven']])], [quiz(7, 'Quiz seven', 1)]);

    expect(chain).toHaveLength(2);
    expect(chain[0]).toMatchObject({ kind: 'lesson', id: 7, title: 'Lesson seven' });
    expect(chain[1]).toMatchObject({ kind: 'quiz', id: 7, title: 'Quiz seven' });
  });

  it('chains several quizzes in one unit by order, not payload order', () => {
    const quizzes = [
      quiz(102, 'Third', 1, 2),
      quiz(100, 'First', 1, 0),
      quiz(101, 'Second', 1, 1),
    ];
    const chain = buildChain([unit(1, 'Unit One', [[10, 'L1']])], quizzes);

    expect(ids(chain)).toEqual(['lesson:10', 'quiz:100', 'quiz:101', 'quiz:102']);
    expect(chain.map(node => node.title)).toEqual(['L1', 'First', 'Second', 'Third']);
  });

  it('excludes a course-level quiz that belongs to no unit', () => {
    const quizzes = [quiz(999, 'Final exam', undefined, 0), quiz(100, 'Unit One Quiz', 1)];
    const chain = buildChain([unit(1, 'Unit One', [[10, 'L1']])], quizzes);

    expect(ids(chain)).toEqual(['lesson:10', 'quiz:100']);
  });

  it('does not mutate the quizzes it was given', () => {
    // `quizzes` is React state in the player; sorting it in place would
    // reorder the caller's array under it.
    const quizzes = [quiz(102, 'Third', 1, 2), quiz(100, 'First', 1, 0), quiz(101, 'Second', 1, 1)];
    const before = quizzes.map(q => q.id);

    buildChain([unit(1, 'Unit One', [[10, 'L1']])], quizzes);

    expect(quizzes.map(q => q.id)).toEqual(before);
    expect(before).toEqual([102, 100, 101]);
  });
});

describe('getNextNode', () => {
  it('steps from a lesson to the next lesson in the same unit', () => {
    const chain = buildChain(courseUnits(), courseQuizzes());
    expect(getNextNode(chain, 'lesson', 10)).toMatchObject({ kind: 'lesson', id: 11 });
  });

  it('steps from the last lesson of unit 1 to unit 1’s quiz', () => {
    // The unit boundary the old flat list skipped: the quiz was reachable only
    // from the sidebar.
    const chain = buildChain(courseUnits(), courseQuizzes());
    expect(getNextNode(chain, 'lesson', 11)).toMatchObject({
      kind: 'quiz',
      id: 100,
      unitId: 1,
    });
  });

  it('steps from unit 1’s quiz to unit 2’s first lesson', () => {
    const chain = buildChain(courseUnits(), courseQuizzes());
    expect(getNextNode(chain, 'quiz', 100)).toMatchObject({
      kind: 'lesson',
      id: 20,
      unitId: 2,
    });
  });

  it('steps from unit 1’s quiz to unit 3 when unit 2 is locked', () => {
    const units = [
      unit(1, 'Unit One', [[10, 'L1']]),
      lockedUnit(2, 'Locked Unit', [[20, 'L2']]),
      unit(3, 'Unit Three', [[30, 'L3']]),
    ];
    const chain = buildChain(units, [quiz(100, 'Unit One Quiz', 1), quiz(200, 'Locked Unit Quiz', 2)]);

    expect(getNextNode(chain, 'quiz', 100)).toMatchObject({
      kind: 'lesson',
      id: 30,
      unitId: 3,
    });
  });

  it('returns null at the very last node', () => {
    const chain = buildChain(courseUnits(), courseQuizzes());
    expect(getNextNode(chain, 'lesson', 30)).toBeNull();
  });

  it('returns null for a node that is not in the chain', () => {
    // The regression: `findIndex` → -1 used to answer chain[0], silently
    // sending the student to lesson 1 on a stale or locked-away id.
    const chain = buildChain(courseUnits(), courseQuizzes());
    expect(getNextNode(chain, 'lesson', 9999)).toBeNull();
  });

  it('returns null for a lesson whose unit has since been locked', () => {
    const chain = buildChain([lockedUnit(1, 'Locked Unit', [[10, 'L1']])], []);
    expect(getNextNode(chain, 'lesson', 10)).toBeNull();
  });

  it('returns null out of an empty chain rather than reading chain[0]', () => {
    expect(getNextNode([], 'lesson', 10)).toBeNull();
  });

  it('tells a lesson and a quiz with the same id apart', () => {
    const units = [unit(1, 'Unit One', [[7, 'Lesson seven']]), unit(2, 'Unit Two', [[20, 'L2']])];
    const chain = buildChain(units, [quiz(7, 'Quiz seven', 1)]);

    expect(getNextNode(chain, 'lesson', 7)).toMatchObject({ kind: 'quiz', id: 7 });
    expect(getNextNode(chain, 'quiz', 7)).toMatchObject({ kind: 'lesson', id: 20 });
  });
});

describe('getPreviousNode', () => {
  it('steps back from a lesson to the previous lesson in the same unit', () => {
    const chain = buildChain(courseUnits(), courseQuizzes());
    expect(getPreviousNode(chain, 'lesson', 11)).toMatchObject({ kind: 'lesson', id: 10 });
  });

  it('steps back from unit 2’s first lesson to unit 1’s quiz', () => {
    const chain = buildChain(courseUnits(), courseQuizzes());
    expect(getPreviousNode(chain, 'lesson', 20)).toMatchObject({ kind: 'quiz', id: 100 });
  });

  it('steps back from unit 1’s quiz to that unit’s last lesson', () => {
    const chain = buildChain(courseUnits(), courseQuizzes());
    expect(getPreviousNode(chain, 'quiz', 100)).toMatchObject({ kind: 'lesson', id: 11 });
  });

  it('steps back over a locked unit', () => {
    const units = [
      unit(1, 'Unit One', [[10, 'L1']]),
      lockedUnit(2, 'Locked Unit', [[20, 'L2']]),
      unit(3, 'Unit Three', [[30, 'L3']]),
    ];
    const chain = buildChain(units, []);

    expect(getPreviousNode(chain, 'lesson', 30)).toMatchObject({ kind: 'lesson', id: 10 });
  });

  it('returns null at the very first node', () => {
    const chain = buildChain(courseUnits(), courseQuizzes());
    expect(getPreviousNode(chain, 'lesson', 10)).toBeNull();
  });

  it('returns null for a node that is not in the chain', () => {
    // Guards the same -1 arithmetic from the other side: -1 - 1 = -2 would
    // read undefined, and a bare `index - 1` on index 0 would wrap.
    const chain = buildChain(courseUnits(), courseQuizzes());
    expect(getPreviousNode(chain, 'quiz', 9999)).toBeNull();
  });

  it('returns null out of an empty chain', () => {
    expect(getPreviousNode([], 'lesson', 10)).toBeNull();
  });

  it('tells a lesson and a quiz with the same id apart', () => {
    const units = [unit(1, 'Unit One', [[10, 'L1'], [7, 'Lesson seven']])];
    const chain = buildChain(units, [quiz(7, 'Quiz seven', 1)]);

    expect(getPreviousNode(chain, 'lesson', 7)).toMatchObject({ kind: 'lesson', id: 10 });
    expect(getPreviousNode(chain, 'quiz', 7)).toMatchObject({ kind: 'lesson', id: 7 });
  });
});

describe('next and previous are mirrors', () => {
  it('undoes a step across each unit boundary', () => {
    const chain = buildChain(courseUnits(), courseQuizzes());

    for (const node of chain) {
      const next = getNextNode(chain, node.kind, node.id);
      if (!next) continue;
      expect(getPreviousNode(chain, next.kind, next.id)).toEqual(node);
    }
  });

  it('walks the whole chain forward and back to where it started', () => {
    const chain = buildChain(courseUnits(), courseQuizzes());

    const forward: ChainNode[] = [chain[0]];
    let cursor = chain[0];
    for (let next = getNextNode(chain, cursor.kind, cursor.id); next; ) {
      forward.push(next);
      cursor = next;
      next = getNextNode(chain, cursor.kind, cursor.id);
    }
    expect(forward).toEqual(chain);

    const backward: ChainNode[] = [cursor];
    for (let prev = getPreviousNode(chain, cursor.kind, cursor.id); prev; ) {
      backward.push(prev);
      cursor = prev;
      prev = getPreviousNode(chain, cursor.kind, cursor.id);
    }
    expect(backward.reverse()).toEqual(chain);
    expect(cursor).toEqual(chain[0]);
  });

  it('mirrors across a locked unit too', () => {
    const units = [
      unit(1, 'Unit One', [[10, 'L1']]),
      lockedUnit(2, 'Locked Unit', [[20, 'L2']]),
      unit(3, 'Unit Three', [[30, 'L3']]),
    ];
    const chain = buildChain(units, [quiz(100, 'Unit One Quiz', 1)]);

    const next = getNextNode(chain, 'quiz', 100);
    expect(next).toMatchObject({ kind: 'lesson', id: 30 });
    expect(getPreviousNode(chain, next!.kind, next!.id)).toMatchObject({ kind: 'quiz', id: 100 });
  });
});

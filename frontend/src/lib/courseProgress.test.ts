import { describe, expect, it } from 'vitest';
import { getNextLesson, getUnitProgress, type ProgressUnit } from './courseProgress';

/**
 * Phase 55 (C7). Before this, both helpers estimated from the course-wide
 * progress percentage: "completed 2 of 3" was assumed to mean the *first two*.
 * The out-of-order tests below are the ones that failed under that estimate.
 */

function unit(id: number, title: string, lessons: Array<[number, string, boolean]>): ProgressUnit {
  return {
    id,
    title,
    lessons: lessons.map(([lessonId, lessonTitle, done]) => ({
      id: lessonId,
      title: lessonTitle,
      is_completed: done,
    })),
  };
}

/**
 * Phase 66. A unit the instructor locked. Students receive it with
 * `lessons: []` (the backend withholds them); the instructor receives the full
 * list — both shapes must be stepped over, so the helper cannot lean on the
 * empty list alone.
 */
function lockedUnit(
  id: number,
  title: string,
  lessons: Array<[number, string, boolean]> = []
): ProgressUnit {
  return { ...unit(id, title, lessons), is_locked: true };
}

describe('getNextLesson', () => {
  it('returns null when the course has no units', () => {
    expect(getNextLesson([])).toBeNull();
  });

  it('returns null when every unit is empty', () => {
    expect(getNextLesson([unit(1, 'Empty', [])])).toBeNull();
  });

  it('returns the first lesson when nothing is completed', () => {
    const units = [unit(1, 'Unit One', [[10, 'L1', false], [11, 'L2', false]])];
    expect(getNextLesson(units)).toEqual({
      lessonId: 10,
      lessonTitle: 'L1',
      unitTitle: 'Unit One',
      unitNumber: 1,
      lessonNumber: 1,
    });
  });

  it('picks lesson 2 for a student who completed lessons 1 and 3', () => {
    // The regression this item exists for. Two of three lessons are done, so
    // the old percentage estimate pointed at lesson 3 — which is complete.
    const units = [
      unit(1, 'Unit One', [
        [10, 'L1', true],
        [11, 'L2', false],
        [12, 'L3', true],
      ]),
    ];

    expect(getNextLesson(units)).toMatchObject({
      lessonId: 11,
      lessonTitle: 'L2',
      lessonNumber: 2,
    });
  });

  it('crosses into the next unit when the first unit is finished', () => {
    const units = [
      unit(1, 'Unit One', [[10, 'L1', true]]),
      unit(2, 'Unit Two', [[20, 'L2', false]]),
    ];

    expect(getNextLesson(units)).toEqual({
      lessonId: 20,
      lessonTitle: 'L2',
      unitTitle: 'Unit Two',
      unitNumber: 2,
      lessonNumber: 1,
    });
  });

  it('skips an empty unit in the middle', () => {
    const units = [
      unit(1, 'Unit One', [[10, 'L1', true]]),
      unit(2, 'Empty', []),
      unit(3, 'Unit Three', [[30, 'L3', false]]),
    ];
    expect(getNextLesson(units)).toMatchObject({ lessonId: 30, unitNumber: 3 });
  });

  it('reports an incomplete lesson in an earlier unit before a later one', () => {
    const units = [
      unit(1, 'Unit One', [[10, 'L1', true], [11, 'L2', false]]),
      unit(2, 'Unit Two', [[20, 'L3', false]]),
    ];
    expect(getNextLesson(units)).toMatchObject({ lessonId: 11, unitNumber: 1 });
  });

  it('falls back to the first lesson once the whole course is complete', () => {
    const units = [
      unit(1, 'Unit One', [[10, 'L1', true]]),
      unit(2, 'Unit Two', [[20, 'L2', true]]),
    ];
    expect(getNextLesson(units)).toMatchObject({ lessonId: 10, unitNumber: 1 });
  });

  it('treats a missing is_completed as not completed', () => {
    const units: ProgressUnit[] = [
      { id: 1, title: 'Unit One', lessons: [{ id: 10, title: 'L1' }] },
    ];
    expect(getNextLesson(units)).toMatchObject({ lessonId: 10 });
  });

  it('skips a locked unit even when its lessons came through', () => {
    // The instructor view: locked unit 2 still carries lessons. Resuming into
    // it would 403 for a student, so unit 3 is the answer either way.
    const units = [
      unit(1, 'Unit One', [[10, 'L1', true]]),
      lockedUnit(2, 'Locked Unit', [[20, 'L2', false]]),
      unit(3, 'Unit Three', [[30, 'L3', false]]),
    ];
    expect(getNextLesson(units)).toMatchObject({ lessonId: 30, unitNumber: 3 });
  });

  it('numbers the unit by its real position, past a locked one', () => {
    // Locked units still occupy a slot in the course's "Unit N" numbering.
    const units = [
      lockedUnit(1, 'Locked Unit', [[10, 'L1', false]]),
      unit(2, 'Unit Two', [[20, 'L2', false]]),
    ];
    expect(getNextLesson(units)).toMatchObject({
      lessonId: 20,
      unitTitle: 'Unit Two',
      unitNumber: 2,
      lessonNumber: 1,
    });
  });

  it('returns null when every unit with lessons is locked', () => {
    expect(getNextLesson([lockedUnit(1, 'Locked Unit', [[10, 'L1', false]])])).toBeNull();
  });

  it('falls back past a locked unit once the unlocked course is complete', () => {
    // All-complete fallback must not hand back a locked unit's first lesson.
    const units = [
      lockedUnit(1, 'Locked Unit', [[10, 'L1', true]]),
      unit(2, 'Unit Two', [[20, 'L2', true]]),
    ];
    expect(getNextLesson(units)).toMatchObject({ lessonId: 20, unitNumber: 2 });
  });

  it('ignores a locked unit the student sees with no lessons', () => {
    const units = [
      unit(1, 'Unit One', [[10, 'L1', true]]),
      lockedUnit(2, 'Locked Unit'),
      unit(3, 'Unit Three', [[30, 'L3', false]]),
    ];
    expect(getNextLesson(units)).toMatchObject({ lessonId: 30, unitNumber: 3 });
  });
});

describe('getUnitProgress', () => {
  it('returns an empty list for an empty course', () => {
    expect(getUnitProgress([])).toEqual([]);
  });

  it('counts completions per unit rather than spreading a total', () => {
    const units = [
      unit(1, 'Unit One', [[10, 'L1', true], [11, 'L2', false]]),
      unit(2, 'Unit Two', [[20, 'L3', true], [21, 'L4', true]]),
    ];

    expect(getUnitProgress(units)).toEqual([
      {
        unitId: 1,
        unitTitle: 'Unit One',
        unitNumber: 1,
        totalLessons: 2,
        completedLessons: 1,
        isComplete: false,
      },
      {
        unitId: 2,
        unitTitle: 'Unit Two',
        unitNumber: 2,
        totalLessons: 2,
        completedLessons: 2,
        isComplete: true,
      },
    ]);
  });

  it('credits a later unit finished before an earlier one', () => {
    // Under the old running-total estimate, completing only unit two's lessons
    // was credited to unit one.
    const units = [
      unit(1, 'Unit One', [[10, 'L1', false], [11, 'L2', false]]),
      unit(2, 'Unit Two', [[20, 'L3', true], [21, 'L4', true]]),
    ];

    const progress = getUnitProgress(units);
    expect(progress[0]).toMatchObject({ completedLessons: 0, isComplete: false });
    expect(progress[1]).toMatchObject({ completedLessons: 2, isComplete: true });
  });

  it('does not mark an empty unit complete', () => {
    expect(getUnitProgress([unit(1, 'Empty', [])])[0]).toMatchObject({
      totalLessons: 0,
      completedLessons: 0,
      isComplete: false,
    });
  });

  it('drops a locked unit from the list entirely', () => {
    // Locked units are out of every progress denominator (phase 66), so a
    // student who finished everything unlocked reads as fully done.
    const units = [
      unit(1, 'Unit One', [[10, 'L1', true]]),
      lockedUnit(2, 'Locked Unit', [[20, 'L2', false]]),
    ];

    expect(getUnitProgress(units)).toEqual([
      {
        unitId: 1,
        unitTitle: 'Unit One',
        unitNumber: 1,
        totalLessons: 1,
        completedLessons: 1,
        isComplete: true,
      },
    ]);
  });

  it('drops a locked unit the student sees with no lessons', () => {
    // Left in, it would read as a permanently incomplete 0/0 unit.
    const progress = getUnitProgress([unit(1, 'Unit One', [[10, 'L1', true]]), lockedUnit(2, 'Locked Unit')]);
    expect(progress).toHaveLength(1);
    expect(progress[0]).toMatchObject({ unitId: 1, isComplete: true });
  });

  it('returns an empty list when every unit is locked', () => {
    expect(getUnitProgress([lockedUnit(1, 'Locked Unit', [[10, 'L1', false]])])).toEqual([]);
  });
});

describe('getUnitProgress numbering', () => {
  /**
   * The timeline used to render the index into the FILTERED array, so a locked
   * unit 2 made unit 3's dot read "2" while its card read "Unit 3" — three
   * numbers for one unit on the same page.
   */
  it('numbers units by their real position, leaving a gap for a locked unit', () => {
    const result = getUnitProgress([
      unit(1, 'One', [[10, 'a', true]]),
      lockedUnit(2, 'Two', [[20, 'b', false]]),
      unit(3, 'Three', [[30, 'c', false]]),
      unit(4, 'Four', [[40, 'd', false]]),
    ]);

    expect(result.map(u => u.unitNumber)).toEqual([1, 3, 4]);
    expect(result.map(u => u.unitTitle)).toEqual(['One', 'Three', 'Four']);
  });

  it('agrees with getNextLesson on the unit number', () => {
    const units = [
      unit(1, 'One', [[10, 'a', true]]),
      lockedUnit(2, 'Two', [[20, 'b', false]]),
      unit(3, 'Three', [[30, 'c', false]]),
    ];

    const next = getNextLesson(units);
    const progress = getUnitProgress(units);
    const row = progress.find(u => u.unitId === 3);

    expect(next?.unitNumber).toBe(3);
    expect(row?.unitNumber).toBe(3);
  });

  it('numbers from 1 when the first unit is the locked one', () => {
    const result = getUnitProgress([
      lockedUnit(1, 'One', [[10, 'a', false]]),
      unit(2, 'Two', [[20, 'b', false]]),
    ]);

    expect(result.map(u => u.unitNumber)).toEqual([2]);
  });
});

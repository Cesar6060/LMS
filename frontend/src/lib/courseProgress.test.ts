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
        totalLessons: 2,
        completedLessons: 1,
        isComplete: false,
      },
      {
        unitId: 2,
        unitTitle: 'Unit Two',
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
});

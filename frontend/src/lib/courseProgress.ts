/**
 * Course-progress helpers driven by real per-lesson completion.
 *
 * Phase 55 (C7): the course-detail page used to *estimate* both of these by
 * spreading the course-wide progress percentage across the flat lesson list —
 * "For now, we'll compute this from the course structure". That pointed at the
 * wrong lesson for any student who completed lessons out of order (finish 1 and
 * 3, and it would call 3 the next lesson because two lessons were done). The
 * course-detail payload now carries `is_completed` per lesson, so both answers
 * are read rather than inferred.
 *
 * Kept here as pure functions so they are unit-testable without mounting the
 * page — see courseProgress.test.ts.
 */

/** The subset of a lesson these helpers need. */
export interface ProgressLesson {
  id: number;
  title: string;
  is_completed?: boolean;
}

/** The subset of a unit these helpers need. */
export interface ProgressUnit {
  id: number;
  title: string;
  lessons: ProgressLesson[];
  /**
   * Phase 66 — the instructor locked this unit. Its lessons are unreachable
   * (every endpoint under it 403s for students), so both helpers step over it:
   * it is never the "next lesson" and never lands in a progress denominator.
   */
  is_locked?: boolean;
}

export interface NextLessonInfo {
  lessonId: number;
  lessonTitle: string;
  unitTitle: string;
  unitNumber: number;
  lessonNumber: number;
}

export interface UnitProgress {
  unitId: number;
  unitTitle: string;
  totalLessons: number;
  completedLessons: number;
  isComplete: boolean;
}

/**
 * The first lesson the student has not completed, in course order.
 *
 * Locked units are skipped entirely — pointing "Continue" at a lesson the
 * backend 403s would strand the student. `unitNumber` still counts locked units
 * so it matches the "Unit 3: …" heading the course page prints.
 *
 * Returns the first lesson of the course when everything is done (the page
 * offers it as a re-read), and null when the course has no lessons at all.
 */
export function getNextLesson(units: ProgressUnit[]): NextLessonInfo | null {
  for (let unitIdx = 0; unitIdx < units.length; unitIdx++) {
    const unit = units[unitIdx];
    if (unit.is_locked) continue;
    for (let lessonIdx = 0; lessonIdx < unit.lessons.length; lessonIdx++) {
      const lesson = unit.lessons[lessonIdx];
      if (!lesson.is_completed) {
        return {
          lessonId: lesson.id,
          lessonTitle: lesson.title,
          unitTitle: unit.title,
          unitNumber: unitIdx + 1,
          lessonNumber: lessonIdx + 1,
        };
      }
    }
  }

  // Everything complete — fall back to the first lesson in the course.
  for (let unitIdx = 0; unitIdx < units.length; unitIdx++) {
    const unit = units[unitIdx];
    if (unit.is_locked) continue;
    if (unit.lessons.length > 0) {
      return {
        lessonId: unit.lessons[0].id,
        lessonTitle: unit.lessons[0].title,
        unitTitle: unit.title,
        unitNumber: unitIdx + 1,
        lessonNumber: 1,
      };
    }
  }

  return null;
}

/**
 * Per-unit completion counts, from the lessons actually completed.
 *
 * Locked units are dropped from the result rather than reported as 0/0: they
 * are out of every progress denominator (phase 66), and a student who finishes
 * everything currently unlocked should read 100%.
 */
export function getUnitProgress(units: ProgressUnit[]): UnitProgress[] {
  return units.filter(unit => !unit.is_locked).map(unit => {
    const completedLessons = unit.lessons.filter(l => l.is_completed).length;
    return {
      unitId: unit.id,
      unitTitle: unit.title,
      totalLessons: unit.lessons.length,
      completedLessons,
      // An empty unit is not "complete" — there is nothing to have finished.
      isComplete: unit.lessons.length > 0 && completedLessons === unit.lessons.length,
    };
  });
}

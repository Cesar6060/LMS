import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useParams, useNavigate, useLocation, Link } from 'react-router';
import { Button } from '@/components/ui/Button';
import { Card, CardContent } from '@/components/ui/Card';
import { CourseSidebar } from '@/components/course/CourseSidebar';
import { VideoPlayer } from '@/components/video/VideoPlayer';
import { LessonQuizSection } from '@/components/lesson/LessonQuizSection';
import { LessonAttachmentsList } from '@/components/lesson/LessonAttachmentsList';
import { LessonMarkdown } from '@/components/lesson/LessonMarkdown';
import { SlideStage } from '@/components/lesson/SlideStage';
import { PresentButton } from '@/components/lesson/PresentButton';
import { courseService } from '@/services/courses';
import { quizzesService } from '@/services/quizzes';
import { useAuth } from '@/contexts/useAuth';
import { buildChain, getNextNode, getPreviousNode } from '@/lib/playerNavigation';
import { useGamificationFeedback } from '@/components/gamification/useGamificationFeedback';
import type { LessonProgress, LessonQuestionsStatus, LessonAttachment, LessonSection, Quiz } from '@/types';
import {
  Loader2, ChevronLeft, ChevronRight, CheckCircle, Circle, FileQuestion, Map as MapIcon, Lock
} from 'lucide-react';

interface LessonDetail {
  id: number;
  title: string;
  content: string | null;
  video_type: 'none' | 'youtube';
  video_id: string | null;
  order: number;
  unit: number;
  attachments?: LessonAttachment[];
  sections?: LessonSection[];
  section_count?: number;
}

interface LessonWithProgress {
  id: number;
  title: string;
  content?: string;
  video_type: 'none' | 'youtube';
  video_id: string | null;
  order: number;
  is_completed?: boolean;
}

// Phase 53: sections are the sole content model. A lesson with no sections has
// no content page — unless it also has no quiz, in which case a single
// empty-state page is shown so navigation still works. This single source of
// truth must be used by BOTH render and the resume/navigation helpers, or
// quiz-only lessons desync (the quiz page becomes unreachable).
function contentPageCountFor(sectionCount: number, hasQuiz: boolean): number {
  return sectionCount > 0 ? sectionCount : (hasQuiz ? 0 : 1);
}

interface UnitWithProgress {
  id: number;
  title: string;
  order: number;
  course: number;
  lessons: LessonWithProgress[];
  /** Phase 66 — locked by the instructor; students get `lessons: []`. */
  is_locked?: boolean;
  /** Total lessons in the unit, sent even when `lessons` is withheld. */
  lesson_count?: number;
}

interface CourseWithProgress {
  id: number;
  code: string;
  title: string;
  description: string;
  instructor: {
    id: number;
    email: string;
    first_name: string;
    last_name: string;
  };
  is_active: boolean;
  units: UnitWithProgress[];
}

export function CoursePlayerPage() {
  const { code, lessonId } = useParams<{ code: string; lessonId?: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const { user } = useAuth();

  // Phase 70: how the student got here decides whether we resume.
  //
  // A SEQUENTIAL arrival — Next, `→`, auto-advance after completion, "Continue
  // to next lesson" off a unit quiz — always opens the lesson at page 1. A
  // DIRECT arrival — sidebar click, pasted URL, dashboard or course-map entry —
  // still resumes at the saved page. Without this split, finishing a lesson on
  // its comprehension-quiz page pins that lesson's cursor to the quiz forever,
  // so walking into it from the previous lesson opened the quiz.
  //
  // History-entry state rather than a ref: a ref is consumed twice under
  // StrictMode's double-invoked effects and would silently resume in dev only.
  const restart = (location.state as { restart?: boolean } | null)?.restart === true;
  // Read through a ref so the lesson-load effect does not depend on it: the
  // flag is CONSUMED on the first page turn (see `handleSectionChange`), and a
  // dep would turn that consumption into a reload that resumed the very cursor
  // the restart was there to ignore.
  const restartRef = useRef(restart);
  restartRef.current = restart;
  const { celebrate, gamificationModals } = useGamificationFeedback();

  const [course, setCourse] = useState<CourseWithProgress | null>(null);
  const [quizzes, setQuizzes] = useState<Quiz[]>([]);
  const [currentLesson, setCurrentLesson] = useState<LessonDetail | null>(null);
  const [progress, setProgress] = useState<LessonProgress | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isLessonLoading, setIsLessonLoading] = useState(false);
  // Phase 66: set when the requested lesson sits in a locked unit. Without it a
  // pasted URL fell through to the neutral "Select a lesson to begin" state,
  // which reads like an app glitch rather than an answer.
  const [lockedNotice, setLockedNotice] = useState('');
  const [error, setError] = useState('');
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(() => {
    return localStorage.getItem('coursePlayerSidebarCollapsed') === 'true';
  });
  const [isMarkingComplete, setIsMarkingComplete] = useState(false);
  const [questionsStatus, setQuestionsStatus] = useState<LessonQuestionsStatus | null>(null);

  // Section navigation state
  const [currentSectionIndex, setCurrentSectionIndex] = useState(0);
  // Phase 60: which way the last page change went — picks the transition side.
  const [navDirection, setNavDirection] = useState<'forward' | 'backward'>('forward');
  // Phase 60: fullscreen present mode (slide pages). Mirrors the browser's
  // fullscreen state via the fullscreenchange listener below, so Esc works.
  const [isPresenting, setIsPresenting] = useState(false);
  const playerContentRef = useRef<HTMLDivElement | null>(null);

  // Check if current user is the instructor
  const isCourseOwner = course && user && course.instructor.id === user.id;

  // Ref to track current lesson for cleanup
  const currentLessonRef = useRef<number | null>(null);
  const isCourseOwnerRef = useRef(false);

  // Update refs when values change
  useEffect(() => {
    currentLessonRef.current = currentLesson?.id || null;
    isCourseOwnerRef.current = !!isCourseOwner;
  }, [currentLesson?.id, isCourseOwner]);

  // Reset instructor progress when leaving the lesson
  useEffect(() => {
    return () => {
      if (isCourseOwnerRef.current && currentLessonRef.current) {
        courseService.resetLessonProgress(currentLessonRef.current).catch(() => {
          // Silent fail - instructor might have navigated away quickly
        });
      }
    };
  }, []);

  // Track last saved position to avoid unnecessary API calls
  const lastSavedPositionRef = useRef<number>(0);
  // Phase 70: the cursor baseline is per LESSON. A bare index was wrong — a
  // write settling after a lesson change rewrote the baseline the new lesson
  // had just seeded, and the new lesson's own cursor was then swallowed as a
  // no-op.
  const lastSavedSectionRef = useRef<{ lessonId: number; index: number } | null>(null);
  const isSavingRef = useRef(false);
  // Phase 70: the newest page turn still owed to the server while a save is in
  // flight. Page turns coalesce onto it instead of being dropped. It carries
  // its lesson id: parking a bare index wrote lesson B's cursor onto lesson A.
  const pendingSectionRef = useRef<{ lessonId: number; index: number } | null>(null);

  // Persist sidebar state
  useEffect(() => {
    localStorage.setItem('coursePlayerSidebarCollapsed', isSidebarCollapsed.toString());
  }, [isSidebarCollapsed]);

  // Phase 70: one explicit node chain — lessons and unit quizzes interleaved,
  // locked units dropped — drives Previous/Next, the arrow keys and every
  // auto-advance. See lib/playerNavigation.ts for why it is not a flat lesson
  // list any more.
  const chain = useMemo(
    () => buildChain(course?.units ?? [], quizzes),
    [course, quizzes]
  );
  // The same chain WITH locked units, used only to place a current lesson that
  // is not navigable itself. The sidebar still offers a locked unit's lessons
  // to the course owner, and landing on one used to kill Next and Previous
  // both — trapping the owner inside the unit they had just locked.
  const fullChain = useMemo(
    () => buildChain(course?.units ?? [], quizzes, { includeLocked: true }),
    [course, quizzes]
  );
  const previousNode = currentLesson
    ? getPreviousNode(chain, 'lesson', currentLesson.id, fullChain)
    : null;
  const nextNode = currentLesson
    ? getNextNode(chain, 'lesson', currentLesson.id, fullChain)
    : null;

  // Phase 66: never resume into a locked unit. A student's locked unit arrives
  // with `lessons: []` so it drops out anyway, but the instructor still gets its
  // lessons — and every lesson endpoint under it 403s for everyone else, so the
  // skip is explicit rather than a side effect of the empty list.
  const findFirstIncompleteLesson = useCallback((courseData: CourseWithProgress) => {
    for (const unit of courseData.units) {
      if (unit.is_locked) continue;
      for (const lesson of unit.lessons) {
        if (!lesson.is_completed) {
          return lesson;
        }
      }
    }
    return null;
  }, []);

  // Phase 70: depends on `code` ONLY. It used to take `lessonId` as well (for
  // the first-incomplete redirect below), which meant every lesson change
  // refetched the whole course, flipped `isLoading`, and dropped the player
  // into the full-page spinner — the visible flash between lessons, and the
  // reason the child components got away with never resetting their own state.
  const loadCourse = useCallback(async () => {
    if (!code) return;

    try {
      setIsLoading(true);
      const [courseData, quizData] = await Promise.all([
        courseService.getCourseWithProgress(code),
        quizzesService.getCourseQuizzes(code).catch(() => [] as Quiz[]),
      ]);
      setCourse(courseData);
      setQuizzes(quizData);
    } catch (err: unknown) {
      const error = err as { response?: { status?: number } };
      if (error.response?.status === 403) {
        setError('You must be enrolled in this course to access it.');
      } else {
        setError('Failed to load course');
      }
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  }, [code]);

  // Phase 70: incremented on every lesson request; a response whose token is no
  // longer current is dropped. Two quick lesson changes used to race, and the
  // LATER-resolving response won — committing one lesson's sections and section
  // cursor while the URL pointed at the other.
  const lessonRequestRef = useRef(0);

  const loadLesson = useCallback(async (id: number, isRestart: boolean) => {
    const requestId = ++lessonRequestRef.current;
    const isStale = () => lessonRequestRef.current !== requestId;

    try {
      setIsLessonLoading(true);
      setLockedNotice('');
      setQuestionsStatus(null); // Reset questions status when loading new lesson
      setCurrentSectionIndex(0); // Reset section index
      setNavDirection('forward'); // New lesson always enters forward
      const [lessonData, progressData, quizStatusData] = await Promise.all([
        courseService.getLesson(id),
        courseService.getLessonProgress(id),
        courseService.getLessonQuestionsStatus(id).catch(() => null) // May not exist
      ]);
      if (isStale()) return;
      setCurrentLesson(lessonData);
      setProgress(progressData);
      setQuestionsStatus(quizStatusData);
      lastSavedPositionRef.current = progressData?.video_position || 0;
      // Seeded from the SERVER value even on a restart, so restarting at page 1
      // and then turning a page still writes `current_section` rather than
      // being swallowed by the equality guard in `saveSectionProgress`.
      lastSavedSectionRef.current = { lessonId: id, index: progressData?.current_section || 0 };
      // Anything still parked belongs to the lesson we just left, and is
      // deliberately NOT discarded: the entry names its own lesson, so the
      // in-flight request's drain still writes it to the right row. Clearing
      // it here would silently lose that student's last page turn.

      // Calculate total pages for resume logic (phase 53: sections are content).
      // Phase 54: the comprehension quiz is its own page whenever the lesson has
      // questions — whether or not passing is *required* (see `quizGates`). This
      // keeps optional-practice questions reachable in the player.
      const hasQuizSection = !!(quizStatusData && quizStatusData.total_questions > 0);
      const contentPageCount = contentPageCountFor(
        lessonData.sections?.length || 0, hasQuizSection);
      const maxSectionIndex = contentPageCount + (hasQuizSection ? 1 : 0) - 1;

      // Resume at the saved section — but ONLY on a direct arrival. A sequential
      // arrival opens at page 1 (phase 70; see `restart` above).
      //
      // Phase 70 amendment (2026-08-09, spec §9): …and never onto the
      // comprehension-quiz page. `current_section` is pinned wherever the
      // student last stopped and nothing ever clears it, so once a lesson has
      // been paged to the end its cursor is the quiz page FOREVER, and every
      // later sidebar click reopened the quiz instead of the lesson. The end of
      // a lesson is not a place to resume to. A genuinely half-read lesson
      // still reopens where it was left; the quiz stays reachable through the
      // amber quiz dot in the footer (always rendered when a quiz exists) and,
      // on gated lessons, the banner's jump link.
      if (!isRestart && progressData?.current_section !== undefined) {
        const savedSection = progressData.current_section;
        const savedIsQuizPage = hasQuizSection && savedSection === maxSectionIndex;
        if (savedSection <= maxSectionIndex && !savedIsQuizPage) {
          setCurrentSectionIndex(savedSection);
        }
      }

      // Track course activity
      if (code) {
        courseService.updateCourseActivity(code).catch(() => {});
      }
    } catch (err) {
      if (isStale()) return;
      const error = err as { response?: { status?: number; data?: { detail?: string } } };
      // Phase 70: clear on EVERY failure, not just 403. The whole-course refetch
      // used to unmount this subtree behind the full-page spinner; now that it
      // doesn't, a failed load left the PREVIOUS lesson rendered and highlighted
      // while the URL said otherwise, with Next/Previous still walking from it.
      setCurrentLesson(null);
      if (error.response?.status === 403) {
        setLockedNotice(
          error.response.data?.detail || 'This unit is locked by your instructor.'
        );
      }
      console.error('Failed to load lesson:', err);
    } finally {
      // A superseded request must not clear the newer request's spinner.
      if (!isStale()) setIsLessonLoading(false);
    }
  }, [code]);

  // Load course data
  useEffect(() => {
    if (code) {
      loadCourse();
    }
  }, [code, loadCourse]);

  // No lessonId in the URL → land on the first incomplete lesson (phase 70:
  // split out of `loadCourse` so that function no longer depends on lessonId).
  // A bare /learn entry is a DIRECT arrival, so it resumes — no `restart`.
  useEffect(() => {
    if (lessonId || !course || course.units.length === 0) return;

    const firstIncompleteLesson = findFirstIncompleteLesson(course);
    // Fallback (everything complete): first lesson of the first *unlocked*
    // unit — unit 1 being locked must not strand the player on a 403.
    const firstLesson = course.units.find(
      unit => !unit.is_locked && unit.lessons.length > 0
    )?.lessons[0];
    const targetLesson = firstIncompleteLesson || firstLesson;

    if (targetLesson) {
      navigate(`/courses/${code}/learn/${targetLesson.id}`, { replace: true });
    }
  }, [lessonId, course, code, navigate, findFirstIncompleteLesson]);

  // Phase 70: a lesson that belongs to a DIFFERENT course must not render under
  // this course's code, sidebar and progress bar. Reachable by hand-editing the
  // quiz page's `?next=`, by a stale bookmark, or by typing a lesson id — and
  // for a student enrolled in both courses the API answers 200, so nothing
  // downstream catches it. Checked against `course.units`, which lists every
  // unit including locked ones, so a locked unit's lesson still falls through
  // to its 403 and the phase-66 lock notice rather than being called foreign.
  useEffect(() => {
    if (!course || !currentLesson) return;
    if (course.units.some(unit => unit.id === currentLesson.unit)) return;

    navigate(`/courses/${code}/learn`, { replace: true });
  }, [course, currentLesson, code, navigate]);

  // Load specific lesson when lessonId changes. Depends on the primitive
  // courseId (not the course object) so lesson reloads only when the course
  // actually changes, not on every course-object refresh.
  const courseId = course?.id;
  useEffect(() => {
    if (lessonId && courseId !== undefined) {
      loadLesson(parseInt(lessonId), restartRef.current);
    }
  }, [lessonId, courseId, loadLesson]);

  /**
   * Go to a lesson. `restart` is explicit at every call site rather than
   * inferred: sequential moves pass `true` (open at page 1), direct picks pass
   * `false` (resume the saved page). It deliberately does NOT default to true —
   * a new call site should resume, which is the pre-phase-70 behaviour.
   */
  const goToLesson = useCallback((id: number, options: { restart: boolean }) => {
    navigate(`/courses/${code}/learn/${id}`, { state: { restart: options.restart } });
  }, [navigate, code]);

  const handleLessonSelect = useCallback((id: number) => {
    // The sidebar is a direct pick — resume where the student left off.
    goToLesson(id, { restart: false });
  }, [goToLesson]);

  const handleQuizSelect = useCallback((quizId: number) => {
    // Unit quizzes are taken on the quiz page; ?from=learn returns here after.
    // Phase 70: `lesson` is where the back link goes (bare /learn re-ran the
    // first-incomplete redirect and dropped the student somewhere else), and
    // `next` powers the "Continue to next lesson" button on the results screen.
    const params = new URLSearchParams({ from: 'learn' });
    if (currentLesson) params.set('lesson', String(currentLesson.id));
    const afterQuiz = getNextNode(chain, 'quiz', quizId, fullChain);
    // Only a lesson is offered as "next": a quiz followed by another quiz has
    // no forward lesson to continue to, and neither does the last node.
    if (afterQuiz?.kind === 'lesson') params.set('next', String(afterQuiz.id));
    navigate(`/courses/${code}/quizzes/${quizId}?${params.toString()}`);
  }, [navigate, code, currentLesson, chain, fullChain]);

  /**
   * Move to the next node in the chain — the shared forward step used by the
   * Next button, `→`, and both auto-advance paths. Routes on node kind: a
   * lesson opens at page 1, a unit quiz opens its quiz page.
   */
  const goToNextNode = useCallback(() => {
    if (!nextNode) return;
    if (nextNode.kind === 'quiz') {
      handleQuizSelect(nextNode.id);
    } else {
      goToLesson(nextNode.id, { restart: true });
    }
  }, [nextNode, handleQuizSelect, goToLesson]);

  /**
   * Step back one node. Deliberately NOT a restart: the spec's sequential list
   * is Next / `→` / auto-advance only, and `restart` defaults to resume. Going
   * backwards to page 1 of a lesson the student has already read would make it
   * impossible to get back to where they were.
   */
  const goToPreviousNode = useCallback(() => {
    if (!previousNode) return;
    if (previousNode.kind === 'quiz') {
      handleQuizSelect(previousNode.id);
    } else {
      goToLesson(previousNode.id, { restart: false });
    }
  }, [previousNode, handleQuizSelect, goToLesson]);

  /**
   * Persist the page cursor, coalescing writes.
   *
   * Phase 70: this used to live inside `handleSectionChange` behind an
   * `if (isSavingRef.current) return` at the very top of that function — so a
   * second `→` while the previous PATCH was in flight was silently dropped and
   * the page did not turn at all. The cursor now moves first (see
   * `handleSectionChange`) and only the *save* waits: the newest turn parks in
   * `pendingSectionRef` and is flushed when the in-flight request settles.
   *
   * The parked entry carries its lesson id, and the drain always re-reads it,
   * because a turn can be parked in one lesson and flushed after the student
   * has already moved to another.
   */
  const saveSectionProgress = useCallback(async (lessonIdToSave: number, index: number) => {
    if (isSavingRef.current) {
      // Something is already writing — this, or a video-position save, which
      // shares `isSavingRef`. Park it; whichever request is in flight drains
      // the queue when it settles (both `finally` blocks call `flushPending`).
      pendingSectionRef.current = { lessonId: lessonIdToSave, index };
      return;
    }

    let target: { lessonId: number; index: number } | null = { lessonId: lessonIdToSave, index };
    while (target !== null) {
      const saved = lastSavedSectionRef.current;
      if (saved && saved.lessonId === target.lessonId && saved.index === target.index) {
        // Already stored — nothing to write, but a newer turn may have queued.
        target = pendingSectionRef.current;
        pendingSectionRef.current = null;
        continue;
      }

      isSavingRef.current = true;
      const writing = target;
      try {
        await courseService.updateLessonProgress(writing.lessonId, {
          current_section: writing.index
        });
        lastSavedSectionRef.current = writing;
      } catch (err) {
        console.error('Failed to save section progress:', err);
      } finally {
        isSavingRef.current = false;
      }

      // A failed write does not retry: `target` moves on either way, so this
      // loop always drains rather than spinning on a dead endpoint.
      target = pendingSectionRef.current;
      pendingSectionRef.current = null;
    }
  }, []);

  /**
   * Drain a page turn that parked behind an in-flight request.
   *
   * `handleVideoProgress` shares `isSavingRef`, so without this a turn taken
   * during a video-position save was parked and then never written at all —
   * the same silent drop this phase set out to kill, just moved from the UI to
   * persistence.
   */
  const flushPendingSection = useCallback(() => {
    const pending = pendingSectionRef.current;
    if (!pending || isSavingRef.current) return;
    pendingSectionRef.current = null;
    void saveSectionProgress(pending.lessonId, pending.index);
  }, [saveSectionProgress]);

  // Handle section navigation
  const handleSectionChange = useCallback((newIndex: number) => {
    if (!currentLesson) return;

    // Calculate total pages (phase 53: sections are content, + quiz if present)
    const hasQuizSection = !!(questionsStatus && questionsStatus.total_questions > 0);
    const contentPageCount = contentPageCountFor(
      currentLesson.sections?.length || 0, hasQuizSection);
    const maxIndex = contentPageCount + (hasQuizSection ? 1 : 0) - 1;

    if (newIndex < 0 || newIndex > maxIndex) return;

    // The UI always advances — never gated on the network (phase 70).
    setNavDirection(newIndex >= currentSectionIndex ? 'forward' : 'backward');
    setCurrentSectionIndex(newIndex);

    // Consume the sequential-arrival flag. React Router keeps location state in
    // `history.state`, so it is NOT one-shot: without this, refreshing (or
    // Back-ing onto) a lesson entered via Next would snap the student back to
    // page 1 forever, which is the resume rule inverted. It stays armed until
    // the first turn, though — before that the server cursor is still the stale
    // one this phase exists to ignore, so page 1 is the right answer on reload.
    if (restartRef.current) {
      restartRef.current = false;
      navigate(`/courses/${code}/learn/${currentLesson.id}`, { replace: true, state: null });
    }

    void saveSectionProgress(currentLesson.id, newIndex);
  }, [currentLesson, questionsStatus, currentSectionIndex, saveSectionProgress, navigate, code]);

  // Phase 60: fullscreen present mode targets the player content area (header
  // and sidebar live outside it, so they disappear while presenting; the
  // prev/next footer and dots live inside it and stay).
  const togglePresent = useCallback(() => {
    const el = playerContentRef.current;
    if (!el) return;
    if (document.fullscreenElement === el) {
      document.exitFullscreen().catch(() => {});
    } else {
      // Optional call: iOS Safari has no Element.requestFullscreen, and a bare
      // call would throw synchronously (uncaught by .catch).
      el.requestFullscreen?.().catch(() => {});
    }
  }, []);

  useEffect(() => {
    // Present mode = OUR element is fullscreen. A student fullscreening the
    // embedded YouTube player must not flip the presenting UI.
    const onFullscreenChange = () =>
      setIsPresenting(document.fullscreenElement === playerContentRef.current);
    document.addEventListener('fullscreenchange', onFullscreenChange);
    return () => document.removeEventListener('fullscreenchange', onFullscreenChange);
  }, []);

  const handleMarkComplete = async () => {
    if (!currentLesson || !progress) return;

    setIsMarkingComplete(true);
    try {
      const updated = await courseService.updateLessonProgress(currentLesson.id, {
        completed: !progress.completed
      });
      setProgress(updated);

      // Update course state to reflect new completion
      if (course) {
        setCourse({
          ...course,
          units: course.units.map(unit => ({
            ...unit,
            lessons: unit.lessons.map(lesson =>
              lesson.id === currentLesson.id
                ? { ...lesson, is_completed: updated.completed }
                : lesson
            )
          }))
        });
      }

      // Gamification feedback (+XP toast, level-up / badge modals). Only fires
      // on the not-completed -> completed transition, which is when the
      // backend attaches a `gamification` delta.
      if (updated.completed) {
        celebrate(updated.gamification);
      }

      // Auto-advance if marking complete. Sequential, so the next lesson opens
      // at page 1 (phase 70) — and a unit's last lesson advances to its quiz.
      if (updated.completed) {
        setTimeout(goToNextNode, 500);
      }
    } catch (err) {
      console.error('Failed to update progress:', err);
    } finally {
      setIsMarkingComplete(false);
    }
  };

  const handleVideoProgress = useCallback(async (position: number) => {
    if (!currentLesson || isSavingRef.current) return;

    const positionDiff = Math.abs(position - lastSavedPositionRef.current);
    if (positionDiff < 5) return;

    isSavingRef.current = true;
    try {
      await courseService.updateLessonProgress(currentLesson.id, {
        video_position: Math.floor(position)
      });
      lastSavedPositionRef.current = position;
    } catch (err) {
      console.error('Failed to save video progress:', err);
    } finally {
      isSavingRef.current = false;
      // A page turn taken while this was in flight parked instead of writing.
      flushPendingSection();
    }
  }, [currentLesson, flushPendingSection]);

  const handleVideoEnded = useCallback(async () => {
    if (!currentLesson || progress?.completed) return;

    // Page count including an appended comprehension-quiz page.
    const hasQuizSection = !!(questionsStatus && questionsStatus.total_questions > 0);
    const contentPageCount = contentPageCountFor(
      currentLesson.sections?.length || 0, hasQuizSection);
    const totalPages = contentPageCount + (hasQuizSection ? 1 : 0);

    // Not on the final page yet → advance one page (never skip a later quiz).
    if (currentSectionIndex < totalPages - 1) {
      handleSectionChange(currentSectionIndex + 1);
      return;
    }

    // On the final page with a quiz gate: the quiz page completes the lesson,
    // so don't auto-complete here (the backend would reject completed:true).
    if (hasQuizSection) return;

    try {
      const updated = await courseService.updateLessonProgress(currentLesson.id, {
        completed: true
      });
      setProgress(updated);
      celebrate(updated.gamification);

      // Update course state
      if (course) {
        setCourse({
          ...course,
          units: course.units.map(unit => ({
            ...unit,
            lessons: unit.lessons.map(lesson =>
              lesson.id === currentLesson.id
                ? { ...lesson, is_completed: true }
                : lesson
            )
          }))
        });
      }

      // Auto-advance to the next node. Phase 70: this used to re-derive its own
      // flat lesson list here — ignoring locked units and unit quizzes, and
      // diverging from the Next button. It calls the shared helper now.
      if (updated.completed) {
        setTimeout(goToNextNode, 500);
      }
    } catch (err) {
      console.error('Failed to mark lesson complete:', err);
    }
  }, [currentLesson, progress?.completed, course, currentSectionIndex, handleSectionChange, questionsStatus, celebrate, goToNextNode]);

  // Get current section data
  const contentSections = currentLesson?.sections || [];
  const hasContentSections = contentSections.length > 0;
  // Phase 54: `hasQuiz` = the lesson has a comprehension-quiz PAGE (questions
  // exist) — it's always shown so students can take it. `quizGates` = passing it
  // is REQUIRED to complete (the `requires_quiz` toggle). Rendering/navigation
  // key off `hasQuiz`; completion gating keys off `quizGates`.
  const hasQuiz = !!(questionsStatus && questionsStatus.total_questions > 0);
  const quizGates = hasQuiz && !!questionsStatus?.requires_quiz;

  // Phase 53: sections are the sole content model (see contentPageCountFor).
  const contentPageCount = contentPageCountFor(contentSections.length, !!hasQuiz);

  // Total pages = content pages + quiz page (if a comprehension quiz exists)
  const totalSections = contentPageCount + (hasQuiz ? 1 : 0);
  const hasSections = totalSections > 1;

  // Determine if we're on the quiz section (last section when quiz exists)
  const isOnQuizSection = hasQuiz && currentSectionIndex === totalSections - 1;
  const currentSection = !isOnQuizSection && hasContentSections ? contentSections[currentSectionIndex] : null;
  const isLastSection = currentSectionIndex === totalSections - 1;
  // Phase 60: slide-layout pages swap the scrolling document for a slide stage
  // that fills the content area (overflow scrolls inside the stage).
  const isSlidePage = currentSection?.layout === 'slide';

  // Phase 62: Mark Complete (or the completed badge) is the one part of the
  // lesson header that survives present mode, so the header block only
  // collapses when neither is showing — otherwise its margin would leave a gap
  // above the stage while presenting.
  const showMarkComplete = (!hasSections || isLastSection) && !quizGates;
  const showCompletedBadge = quizGates && !!progress?.completed;
  const headerHasContent = !isPresenting || showMarkComplete || showCompletedBadge;

  // Calculate progress
  const completedCount = course?.units.reduce(
    (acc, unit) => acc + unit.lessons.filter(l => l.is_completed).length,
    0
  ) || 0;
  const totalCount = course?.units.reduce(
    (acc, unit) => acc + unit.lessons.length,
    0
  ) || 0;
  const progressPercentage = totalCount > 0 ? (completedCount / totalCount) * 100 : 0;

  // Keyboard navigation
  useEffect(() => {
    const handleKeyPress = (e: KeyboardEvent) => {
      // Don't trigger if user is typing in an input
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
        return;
      }

      // Phase 70: the footer buttons disappear behind the lesson spinner but
      // this listener does not. An arrow arriving mid-load ran against the
      // OUTGOING lesson — turning its page, writing its cursor, and landing the
      // student on page 2 of the lesson they were arriving at.
      if (isLessonLoading && (e.key === 'ArrowLeft' || e.key === 'ArrowRight')) {
        return;
      }

      if (e.key === 'ArrowLeft') {
        // If we have sections and not at first section, go to previous section
        if (hasSections && currentSectionIndex > 0) {
          handleSectionChange(currentSectionIndex - 1);
        } else {
          goToPreviousNode();
        }
      } else if (e.key === 'ArrowRight') {
        // If we have sections and not at last section, go to next section
        if (hasSections && currentSectionIndex < totalSections - 1) {
          handleSectionChange(currentSectionIndex + 1);
        } else {
          goToNextNode();
        }
      } else if (e.key === 'f' || e.key === 'F') {
        // Phase 62: present from any lesson page except the quiz (projecting it
        // spoils the answers); always allow exiting, including from the quiz.
        // Never hijack browser shortcuts (Cmd/Ctrl+F find-in-page).
        if (e.metaKey || e.ctrlKey || e.altKey) return;
        // Never present a lesson that hasn't loaded — the button is absent in
        // that state, so F would fullscreen a bare spinner with no visible exit.
        if ((!isOnQuizSection || isPresenting) && !isLessonLoading) {
          e.preventDefault();
          togglePresent();
        }
      }
    };

    window.addEventListener('keydown', handleKeyPress);
    return () => window.removeEventListener('keydown', handleKeyPress);
  }, [goToPreviousNode, goToNextNode, hasSections, currentSectionIndex, totalSections, handleSectionChange, isOnQuizSection, isPresenting, isLessonLoading, togglePresent]);

  // Phase 70: the second clause covers the frame between "course loaded" and
  // the first-incomplete redirect landing. That redirect used to run inside
  // `loadCourse`, so it batched with `setIsLoading(false)`; now that it is its
  // own post-paint effect, a bare /learn would flash "Select a lesson to begin"
  // for one frame without this.
  if (isLoading || (!lessonId && course && course.units.length > 0)) {
    return (
      <div className="h-screen flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (error || !course) {
    return (
      <div className="h-screen flex items-center justify-center">
        <Card className="max-w-md">
          <CardContent className="py-8 text-center">
            <p className="text-destructive mb-4">{error || 'Course not found'}</p>
            <Link to="/courses">
              <Button>Back to Courses</Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Render section content
  const renderSectionContent = () => {
    // Render quiz section
    if (isOnQuizSection && currentLesson) {
      return (
        <LessonQuizSection
          lessonId={currentLesson.id}
          onStatusChange={setQuestionsStatus}
          onComplete={handleMarkComplete}
          isLessonCompleted={progress?.completed}
        />
      );
    }

    if (!currentSection) {
      // Phase 53: sections are the sole content model — lesson-level
      // content/video is no longer rendered. A lesson with no sections shows an
      // empty state (quiz-only lessons render the quiz page instead).
      return (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            No content available for this lesson yet.
          </CardContent>
        </Card>
      );
    }

    const sectionVideo =
      currentSection.video_type === 'youtube' && currentSection.video_id ? (
        <VideoPlayer
          videoType="youtube"
          videoId={currentSection.video_id}
          initialPosition={currentSectionIndex === 0 ? (progress?.video_position || 0) : 0}
          onProgress={handleVideoProgress}
          onEnded={handleVideoEnded}
        />
      ) : null;

    // Phase 60: slide-layout page — PowerPoint-style stage instead of the
    // scrolling document card.
    if (currentSection.layout === 'slide') {
      return (
        <SlideStage
          slideKey={`${currentLesson?.id}-${currentSectionIndex}`}
          title={currentSection.title}
          content={currentSection.content}
          video={sectionVideo}
          image={
            currentSection.image_url
              ? { url: currentSection.image_url, alt: currentSection.image_alt }
              : undefined
          }
          direction={navDirection}
        />
      );
    }

    // Render section content (doc layout — unchanged scrolling document).
    // Keyed so the entry transition replays on every page change.
    return (
      <div
        key={`${currentLesson?.id}-${currentSectionIndex}`}
        className={`animate-in fade-in duration-300 ${
          navDirection === 'forward' ? 'slide-in-from-right-4' : 'slide-in-from-left-4'
        }`}
      >
        {/* Section title */}
        {currentSection.title && (
          <h3 className="text-xl font-semibold mb-4">{currentSection.title}</h3>
        )}

        {/* Section video */}
        {sectionVideo && (
          <div className="mb-8 mx-auto w-full max-w-[calc((100vh-15rem)*1.7778)]">
            {sectionVideo}
          </div>
        )}

        {/* Section content. Phase 61: an imported slide image renders at the
            top of the doc card, so flipping a slide page to doc never shows
            an empty page. */}
        {(currentSection.content || currentSection.image_url) && (
          <Card>
            <CardContent className="py-6">
              {currentSection.image_url && (
                <img
                  src={currentSection.image_url}
                  alt={currentSection.image_alt}
                  className="mb-6 w-full rounded-md border"
                />
              )}
              {currentSection.content && (
                <LessonMarkdown content={currentSection.content} />
              )}
            </CardContent>
          </Card>
        )}

        {!currentSection.content && !currentSection.image_url && currentSection.video_type === 'none' && (
          <Card>
            <CardContent className="py-12 text-center text-muted-foreground">
              No content available for this page.
            </CardContent>
          </Card>
        )}
      </div>
    );
  };

  return (
    <div className="h-screen flex flex-col bg-background animate-in fade-in duration-300">
      {gamificationModals}
      {/* Learning Mode Header */}
      <div className="h-16 border-b bg-card/95 backdrop-blur supports-[backdrop-filter]:bg-card/80 flex items-center px-6 gap-4">
        {/* Exit Learning Mode */}
        <Link to={`/courses/${code}`}>
          <Button
            variant="outline"
            className="gap-2 border-primary/50 text-primary hover:bg-primary hover:text-primary-foreground transition-colors"
            aria-label="Back to Course"
            title="Back to Course"
          >
            <ChevronLeft className="h-4 w-4" />
            <span className="hidden sm:inline">Back to Course</span>
          </Button>
        </Link>

        {/* Course Map (Phase 35) */}
        <Link to={`/courses/${code}/map`}>
          <Button
            variant="outline"
            className="gap-2"
            aria-label="Course Map"
            title="Course Map"
          >
            <MapIcon className="h-4 w-4" />
            <span className="hidden sm:inline">Map</span>
          </Button>
        </Link>

        {/* Course Title */}
        <div className="flex-1 min-w-0 text-center">
          <h1 className="font-semibold truncate text-base sm:text-lg">{course.title}</h1>
        </div>

        {/* Progress */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 text-sm">
            <span className="text-muted-foreground hidden sm:inline">
              {completedCount}/{totalCount}
            </span>
            <div className="w-28 sm:w-40 h-2.5 bg-muted rounded-full overflow-hidden">
              <div
                className="h-full bg-primary transition-all duration-300"
                style={{ width: `${progressPercentage}%` }}
              />
            </div>
            <span className="text-sm font-medium text-primary">{Math.round(progressPercentage)}%</span>
          </div>
        </div>
      </div>

      {/* Main content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Sidebar */}
        <CourseSidebar
          units={course.units}
          quizzes={quizzes}
          currentLessonId={currentLesson?.id || null}
          onLessonSelect={handleLessonSelect}
          onQuizSelect={handleQuizSelect}
          isCollapsed={isSidebarCollapsed}
          onToggleCollapse={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
          progressPercentage={progressPercentage}
          completedCount={completedCount}
          totalCount={totalCount}
        />

        {/* Content area — the fullscreen target for present mode (header and
            sidebar sit outside it, so presenting hides them; the nav footer
            stays). bg-background so fullscreen isn't black. `relative` is the
            positioning context for the floating Present button (phase 62). */}
        <div ref={playerContentRef} className="relative flex-1 flex flex-col overflow-hidden bg-background">
          {isLessonLoading ? (
            <div className="flex-1 flex items-center justify-center">
              <Loader2 className="h-8 w-8 animate-spin text-primary" />
            </div>
          ) : currentLesson ? (
            <>
              {/* Phase 62: the Present toggle sits inside the fullscreen
                  element (so one control both enters and exits) and outside
                  the scroll container (so it stays pinned on long doc pages).
                  Hidden on the quiz page — projecting it spoils the answers —
                  but kept as Exit if the class paged into the quiz while
                  already presenting. */}
              {(!isOnQuizSection || isPresenting) && (
                <PresentButton isPresenting={isPresenting} onToggle={togglePresent} />
              )}

              {/* Lesson content. Slide pages: no page scroll — the stage fills
                  the area and long content scrolls inside it (phase 60). */}
              <div className={isSlidePage ? 'flex-1 overflow-hidden' : 'flex-1 overflow-y-auto'}>
                <div className={`w-full px-6 py-6 lg:px-10 lg:py-8 ${isSlidePage ? 'h-full flex flex-col' : ''}`}>
                  {/* Lesson header. Phase 62: presenting hides the title,
                      section subtitle and quiz badge so the page gets the whole
                      screen, but Mark Complete survives — a student used to
                      have to leave fullscreen to finish the lesson. The whole
                      block (and its margin) collapses when nothing survives. */}
                  <div className={headerHasContent ? 'mb-6' : 'hidden'}>
                    {/* pr-* keeps a long title clear of the floating Present
                        button, which overlaps this corner (phase 62). */}
                    {!isPresenting && (
                      <h2 className="text-3xl font-bold mb-2 pr-14 md:pr-32">{currentLesson.title}</h2>
                    )}

                    {/* Section title (only show if section has a title) */}
                    {!isPresenting && hasSections && totalSections > 1 && currentSection?.title && (
                      <p className="text-sm text-muted-foreground mb-2">
                        {currentSection.title}
                      </p>
                    )}

                    {/* Lesson questions requirement badge - only when the quiz
                        gates completion, and not while on the quiz page itself */}
                    {!isPresenting && quizGates && !progress?.completed && !isOnQuizSection && (
                      <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg mb-3 ${
                        questionsStatus.can_complete_lesson
                          ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400'
                          : 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400'
                      }`}>
                        {questionsStatus.can_complete_lesson ? (
                          <>
                            <CheckCircle className="h-4 w-4" />
                            <span className="text-sm font-medium">Quiz passed - Ready to mark complete</span>
                            {/* Phase 70 amendment: the Mark Lesson Complete
                                button lives on the quiz page, and resume no
                                longer lands there — without this jump the
                                passed-but-uncompleted state was a dead end
                                announcing an action it offered no way to take. */}
                            <button
                              onClick={() => handleSectionChange(totalSections - 1)}
                              className="text-sm underline hover:no-underline ml-1"
                            >
                              Mark Complete →
                            </button>
                          </>
                        ) : (
                          <>
                            <FileQuestion className="h-4 w-4" />
                            <span className="text-sm font-medium">
                              Complete the comprehension quiz to finish this lesson
                            </span>
                            <button
                              onClick={() => handleSectionChange(totalSections - 1)}
                              className="text-sm underline hover:no-underline ml-1"
                            >
                              Go to Quiz →
                            </button>
                          </>
                        )}
                      </div>
                    )}

                    {/* Show Mark Complete on the last page unless the quiz gates
                        completion (then completion happens via the quiz page). When
                        the quiz is optional practice, completion stays available here. */}
                    {showMarkComplete && (
                      <div className="flex items-center gap-3">
                        <Button
                          variant={progress?.completed ? 'default' : 'outline'}
                          size="sm"
                          onClick={handleMarkComplete}
                          disabled={isMarkingComplete}
                        >
                          {isMarkingComplete ? (
                            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                          ) : progress?.completed ? (
                            <CheckCircle className="h-4 w-4 mr-2" />
                          ) : (
                            <Circle className="h-4 w-4 mr-2" />
                          )}
                          {progress?.completed ? 'Completed' : 'Mark Complete'}
                        </Button>
                      </div>
                    )}

                    {/* Show completion status when the quiz gates completion (the
                        Mark Complete button is hidden in that case) */}
                    {showCompletedBadge && (
                      <div className="flex items-center gap-2 text-green-600 dark:text-green-400">
                        <CheckCircle className="h-5 w-5" />
                        <span className="font-medium">Lesson Completed</span>
                      </div>
                    )}
                  </div>

                  {/* Section/Lesson content */}
                  {isSlidePage ? (
                    <div className="flex-1 min-h-0">{renderSectionContent()}</div>
                  ) : (
                    renderSectionContent()
                  )}

                  {/* Attachments - show on last content section or quiz section
                      (hidden while presenting so the stage keeps the screen) */}
                  {!isPresenting &&
                    (!hasContentSections || isOnQuizSection || (!hasQuiz && isLastSection)) && (
                    <LessonAttachmentsList
                      attachments={currentLesson.attachments || []}
                      capHeight={isSlidePage}
                    />
                  )}
                </div>
              </div>

              {/* Navigation footer */}
              <div className="h-16 border-t bg-card flex items-center justify-between px-6">
                <Button
                  variant="ghost"
                  onClick={() => {
                    if (hasSections && currentSectionIndex > 0) {
                      handleSectionChange(currentSectionIndex - 1);
                    } else {
                      goToPreviousNode();
                    }
                  }}
                  disabled={!previousNode && currentSectionIndex === 0}
                  className="gap-1"
                >
                  <ChevronLeft className="h-4 w-4" />
                  <span className="hidden sm:inline">Previous</span>
                </Button>

                {/* Section indicators */}
                <div className="flex items-center gap-2">
                  {hasSections && totalSections > 1 ? (
                    <>
                      <div className="flex items-center gap-1.5">
                        {/* Content section dots */}
                        {contentSections.map((_, i) => (
                          <button
                            key={i}
                            onClick={() => handleSectionChange(i)}
                            className={`w-2.5 h-2.5 rounded-full transition-all ${
                              i === currentSectionIndex
                                ? 'bg-primary w-4'
                                : i < currentSectionIndex
                                  ? 'bg-primary/50'
                                  : 'bg-muted-foreground/30 hover:bg-muted-foreground/50'
                            }`}
                            title={`Page ${i + 1}`}
                          />
                        ))}
                        {/* Quiz section indicator */}
                        {hasQuiz && (
                          <button
                            onClick={() => handleSectionChange(totalSections - 1)}
                            className={`w-2.5 h-2.5 rounded-sm transition-all ${
                              isOnQuizSection
                                ? 'bg-amber-500 w-4'
                                : currentSectionIndex < totalSections - 1
                                  ? 'bg-amber-500/30 hover:bg-amber-500/50'
                                  : 'bg-amber-500/50'
                            }`}
                            title="Comprehension Check"
                          />
                        )}
                      </div>
                      {/* Tagged because the header carries a lessons-complete
                          counter in the same "n/m" shape (phase 70 tests). */}
                      <span
                        data-testid="page-indicator"
                        className="text-sm text-muted-foreground"
                      >
                        {currentSectionIndex + 1}/{totalSections}
                      </span>
                    </>
                  ) : (
                    <span className="text-sm text-muted-foreground hidden sm:block">
                      ← → to navigate
                    </span>
                  )}
                </div>

                <Button
                  variant="ghost"
                  onClick={() => {
                    if (hasSections && currentSectionIndex < totalSections - 1) {
                      handleSectionChange(currentSectionIndex + 1);
                    } else {
                      goToNextNode();
                    }
                  }}
                  disabled={!nextNode && isLastSection}
                  className="gap-1"
                >
                  <span className="hidden sm:inline">Next</span>
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            </>
          ) : (
            <div className="flex-1 flex items-center justify-center p-8">
              {lockedNotice ? (
                <div className="max-w-md text-center">
                  <Lock className="h-10 w-10 mx-auto mb-4 text-amber-600 dark:text-amber-400" />
                  <p className="text-lg font-semibold mb-2">{lockedNotice}</p>
                  <p className="text-base text-muted-foreground">
                    Pick an unlocked lesson from the sidebar to keep going.
                  </p>
                </div>
              ) : (
                <span className="text-muted-foreground">Select a lesson to begin</span>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { CoursePlayerPage } from './CoursePlayerPage';
import type { LessonProgress, LessonQuestionsStatus, LessonSection, User } from '@/types';

const mockUseAuth = vi.hoisted(() => vi.fn());
const mockGetCourseWithProgress = vi.hoisted(() => vi.fn());
const mockGetLesson = vi.hoisted(() => vi.fn());
const mockGetLessonProgress = vi.hoisted(() => vi.fn());
const mockGetLessonQuestionsStatus = vi.hoisted(() => vi.fn());
const mockUpdateLessonProgress = vi.hoisted(() => vi.fn());
const mockUpdateCourseActivity = vi.hoisted(() => vi.fn());
const mockResetLessonProgress = vi.hoisted(() => vi.fn());
const mockGetCourseQuizzes = vi.hoisted(() => vi.fn());

vi.mock('@/contexts/useAuth', () => ({ useAuth: mockUseAuth }));
vi.mock('@/services/courses', () => ({
  courseService: {
    getCourseWithProgress: mockGetCourseWithProgress,
    getLesson: mockGetLesson,
    getLessonProgress: mockGetLessonProgress,
    getLessonQuestionsStatus: mockGetLessonQuestionsStatus,
    updateLessonProgress: mockUpdateLessonProgress,
    updateCourseActivity: mockUpdateCourseActivity,
    resetLessonProgress: mockResetLessonProgress,
  },
}));
vi.mock('@/services/quizzes', () => ({
  quizzesService: { getCourseQuizzes: mockGetCourseQuizzes },
}));
vi.mock('@/components/gamification/useGamificationFeedback', () => ({
  useGamificationFeedback: () => ({ celebrate: vi.fn(), gamificationModals: null }),
}));
// The quiz page fetches its own questions; the player only needs a stand-in.
vi.mock('@/components/lesson/LessonQuizSection', () => ({
  LessonQuizSection: () => <div data-testid="quiz-section">Comprehension quiz</div>,
}));
// A YouTube embed cannot run in jsdom. The stub exposes the one callback the
// player's save path cares about, so a video-position write can be triggered.
vi.mock('@/components/video/VideoPlayer', () => ({
  VideoPlayer: ({ onProgress }: { onProgress?: (position: number) => void }) => (
    <button data-testid="video-progress" onClick={() => onProgress?.(120)}>tick</button>
  ),
}));

const user: User = {
  id: 1,
  email: 'student@example.com',
  first_name: 'Sam',
  last_name: 'Student',
  is_instructor: false,
  is_demo: false,
  created_at: '2026-01-01T00:00:00Z',
} as User;

function makeSection(overrides: Partial<LessonSection> = {}): LessonSection {
  return {
    id: 1,
    title: 'Page one',
    content: 'Some page content.',
    video_type: 'none',
    video_id: '',
    layout: 'doc',
    image_url: null,
    image_alt: '',
    order: 1,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  };
}

const progress: LessonProgress = {
  id: 1,
  user: 1,
  lesson: 10,
  completed: false,
  completed_at: null,
  video_position: 0,
  current_section: 0,
};

const course = {
  id: 5,
  code: 'ROB101',
  title: 'Intro to Robotics',
  description: '',
  instructor: { id: 99, email: 'teacher@example.com', first_name: 'Tina', last_name: 'Teacher' },
  is_active: true,
  units: [
    {
      id: 2,
      title: 'Unit 1',
      order: 1,
      course: 5,
      lessons: [{ id: 10, title: 'What Is a Robot?', video_type: 'none' as const, video_id: null, order: 1, is_completed: false }],
    },
  ],
};

/**
 * jsdom implements no Fullscreen API at all. This fake is enough for the player:
 * requestFullscreen/exitFullscreen flip `document.fullscreenElement` and fire
 * `fullscreenchange`, which is exactly what drives `isPresenting`.
 */
function installFullscreenFake() {
  let element: Element | null = null;
  const setFullscreenElement = (next: Element | null) => {
    element = next;
    document.dispatchEvent(new Event('fullscreenchange'));
    return Promise.resolve();
  };

  Object.defineProperty(document, 'fullscreenEnabled', { value: true, configurable: true });
  Object.defineProperty(document, 'fullscreenElement', {
    get: () => element,
    configurable: true,
  });
  Element.prototype.requestFullscreen = function () {
    return setFullscreenElement(this);
  };
  document.exitFullscreen = () => setFullscreenElement(null);

  // What Esc actually does: the browser drops out of fullscreen and fires the
  // event without any of our code being called.
  return { browserExit: () => void setFullscreenElement(null) };
}

function renderPlayer() {
  return render(
    <MemoryRouter initialEntries={['/courses/ROB101/learn/10']}>
      <Routes>
        <Route path="/courses/:code/learn/:lessonId" element={<CoursePlayerPage />} />
      </Routes>
    </MemoryRouter>
  );
}

function setLesson(sections: LessonSection[], questions?: Partial<LessonQuestionsStatus>) {
  mockGetLesson.mockResolvedValue({
    id: 10,
    title: 'What Is a Robot?',
    content: null,
    video_type: 'none',
    video_id: null,
    order: 1,
    unit: 2,
    attachments: [],
    sections,
  });
  mockGetLessonQuestionsStatus.mockResolvedValue(
    questions
      ? {
          total_questions: 3,
          answered_questions: 0,
          correct_answers: 0,
          all_correct: false,
          requires_quiz: false,
          can_complete_lesson: true,
          ...questions,
        }
      : null
  );
}

let fullscreen: ReturnType<typeof installFullscreenFake>;

const presentButton = () => screen.queryByRole('button', { name: 'Present fullscreen (F)' });
const exitButton = () => screen.queryByRole('button', { name: 'Exit fullscreen (Esc)' });

describe('CoursePlayerPage — Present control (phase 62)', () => {
  beforeEach(() => {
    fullscreen = installFullscreenFake();
    mockUseAuth.mockReturnValue({ user });
    mockGetCourseWithProgress.mockReset().mockResolvedValue(course);
    mockGetCourseQuizzes.mockReset().mockResolvedValue([]);
    mockGetLessonProgress.mockReset().mockResolvedValue(progress);
    mockUpdateLessonProgress.mockReset().mockResolvedValue(progress);
    mockUpdateCourseActivity.mockReset().mockResolvedValue(undefined);
    mockResetLessonProgress.mockReset().mockResolvedValue(undefined);
    mockGetLesson.mockReset();
    mockGetLessonQuestionsStatus.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders Present on a doc page', async () => {
    setLesson([makeSection({ layout: 'doc' })]);

    renderPlayer();

    expect(await screen.findByRole('heading', { name: 'What Is a Robot?' })).toBeInTheDocument();
    expect(presentButton()).toBeInTheDocument();
  });

  it('renders Present on a slide page', async () => {
    setLesson([makeSection({ layout: 'slide', title: 'Slide one' })]);

    renderPlayer();

    expect(await screen.findByRole('heading', { name: 'What Is a Robot?' })).toBeInTheDocument();
    expect(presentButton()).toBeInTheDocument();
  });

  it('does not render Present on the quiz page', async () => {
    setLesson([makeSection()], { total_questions: 3 });

    renderPlayer();

    // Page 2 of 2 is the comprehension quiz.
    fireEvent.click(await screen.findByRole('button', { name: /next/i }));

    expect(await screen.findByTestId('quiz-section')).toBeInTheDocument();
    expect(presentButton()).not.toBeInTheDocument();
    expect(exitButton()).not.toBeInTheDocument();
  });

  it('keeps the control as Exit when paging into the quiz while presenting', async () => {
    setLesson([makeSection()], { total_questions: 3 });

    renderPlayer();

    fireEvent.click(await screen.findByRole('button', { name: 'Present fullscreen (F)' }));
    expect(exitButton()).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /next/i }));

    expect(await screen.findByTestId('quiz-section')).toBeInTheDocument();
    expect(exitButton()).toBeInTheDocument();
    expect(presentButton()).not.toBeInTheDocument();
  });

  it('flips back to Present when the browser leaves fullscreen on its own (Esc)', async () => {
    setLesson([makeSection()]);

    renderPlayer();

    fireEvent.click(await screen.findByRole('button', { name: 'Present fullscreen (F)' }));
    expect(exitButton()).toBeInTheDocument();

    // Esc never routes through our code: the browser clears fullscreenElement
    // and fires the event unprompted, which only the listener can catch.
    fullscreen.browserExit();

    await waitFor(() => expect(presentButton()).toBeInTheDocument());
  });

  it('exits when the Exit button is clicked', async () => {
    setLesson([makeSection()]);

    renderPlayer();

    fireEvent.click(await screen.findByRole('button', { name: 'Present fullscreen (F)' }));
    fireEvent.click(screen.getByRole('button', { name: 'Exit fullscreen (Esc)' }));

    await waitFor(() => expect(presentButton()).toBeInTheDocument());
  });

  it('presents on F from a doc page, but not from the quiz page or with a modifier', async () => {
    setLesson([makeSection({ layout: 'doc' })], { total_questions: 3 });

    renderPlayer();
    await screen.findByRole('heading', { name: 'What Is a Robot?' });

    // Cmd+F must stay browser find-in-page.
    fireEvent.keyDown(window, { key: 'f', metaKey: true });
    expect(exitButton()).not.toBeInTheDocument();

    fireEvent.keyDown(window, { key: 'f' });
    expect(exitButton()).toBeInTheDocument();

    // Leaving present mode on the quiz page, F must not put it back.
    fullscreen.browserExit();
    await waitFor(() => expect(presentButton()).toBeInTheDocument());

    fireEvent.click(screen.getByRole('button', { name: /next/i }));
    expect(await screen.findByTestId('quiz-section')).toBeInTheDocument();

    fireEvent.keyDown(window, { key: 'f' });
    expect(exitButton()).not.toBeInTheDocument();
  });

  it('renders no Present control where the Fullscreen API is unavailable', async () => {
    Object.defineProperty(document, 'fullscreenEnabled', { value: false, configurable: true });
    setLesson([makeSection({ layout: 'slide' })]);

    renderPlayer();

    expect(await screen.findByRole('heading', { name: 'What Is a Robot?' })).toBeInTheDocument();
    expect(presentButton()).not.toBeInTheDocument();
    expect(exitButton()).not.toBeInTheDocument();
  });

  it('keeps Mark Complete but hides the lesson title while presenting', async () => {
    setLesson([makeSection({ layout: 'slide' })]);

    renderPlayer();

    expect(await screen.findByRole('button', { name: /mark complete/i })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Present fullscreen (F)' }));

    expect(screen.getByRole('button', { name: /mark complete/i })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'What Is a Robot?' })).not.toBeInTheDocument();
  });
});

describe('CoursePlayerPage locked unit (phase 66)', () => {
  beforeEach(() => {
    mockUseAuth.mockReturnValue({ user });
    mockGetCourseWithProgress.mockResolvedValue(course);
    mockGetLessonProgress.mockResolvedValue(progress);
    mockGetLessonQuestionsStatus.mockResolvedValue(null);
    mockGetCourseQuizzes.mockResolvedValue([]);
    mockUpdateCourseActivity.mockResolvedValue(undefined);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('explains the lock when the lesson 403s instead of showing the neutral empty state', async () => {
    // What a pasted URL for a locked unit's lesson actually returns.
    mockGetLesson.mockRejectedValue({
      response: { status: 403, data: { detail: 'This unit is locked by your instructor.' } },
    });

    renderPlayer();

    expect(
      await screen.findByText('This unit is locked by your instructor.')
    ).toBeInTheDocument();
    expect(screen.queryByText('Select a lesson to begin')).not.toBeInTheDocument();
  });

  it('falls back to the generic message when the 403 carries no detail', async () => {
    mockGetLesson.mockRejectedValue({ response: { status: 403 } });

    renderPlayer();

    expect(
      await screen.findByText('This unit is locked by your instructor.')
    ).toBeInTheDocument();
  });

  it('keeps the neutral empty state for a non-403 failure', async () => {
    mockGetLesson.mockRejectedValue({ response: { status: 500 } });

    renderPlayer();

    expect(await screen.findByText('Select a lesson to begin')).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Phase 70 — lesson-to-lesson transitions
//
// Nothing here existed before phase 70: the player's own tests covered Present
// mode and locked units, and not one of them walked from one lesson to the
// next. The reported bug — advancing into a lesson you already finished opens
// its comprehension-quiz page instead of page 1 — lived in that gap.
// ---------------------------------------------------------------------------

/** Shape of the multi-unit course these tests walk through. */
const LESSON_SHAPES: Record<number, { title: string; unit: number; sections: number; questions: number }> = {
  10: { title: 'What Is a Robot?', unit: 2, sections: 2, questions: 0 },
  11: { title: 'Sensors', unit: 2, sections: 2, questions: 3 },
  20: { title: 'Actuators', unit: 3, sections: 1, questions: 0 },
  30: { title: 'Autonomy', unit: 4, sections: 1, questions: 0 },
};

function lessonStub(id: number, order: number) {
  return {
    id,
    title: LESSON_SHAPES[id].title,
    video_type: 'none' as const,
    video_id: null,
    order,
    is_completed: false,
  };
}

function makeQuiz(id: number, unit: number, title: string, order = 1) {
  return {
    id,
    title,
    unit,
    order,
    description: '',
    passing_score: 70,
    points: 20,
    max_attempts: 0,
    question_count: 6,
    unit_title: '',
    course_code: 'ROB101',
    best_score: null,
    created_at: '2026-01-01T00:00:00Z',
  };
}

/** Unit 1 has two lessons and a unit quiz; units 2 and 3 have one lesson each. */
const multiUnitCourse = {
  ...course,
  units: [
    { id: 2, title: 'Unit 1', order: 1, course: 5, lessons: [lessonStub(10, 1), lessonStub(11, 2)] },
    { id: 3, title: 'Unit 2', order: 2, course: 5, lessons: [lessonStub(20, 1)] },
    { id: 4, title: 'Unit 3', order: 3, course: 5, lessons: [lessonStub(30, 1)] },
  ],
};

const unitOneQuiz = makeQuiz(100, 2, 'Unit 1 Quiz');

/**
 * Wire per-lesson responses. `savedSections` is what the server reports as each
 * lesson's `current_section` — the cursor the old player restored on EVERY
 * arrival, sequential ones included.
 */
function wireLessons(
  savedSections: Record<number, number> = {},
  quizStatus: Partial<LessonQuestionsStatus> = {}
) {
  mockGetLesson.mockImplementation(async (id: number) => ({
    id,
    title: LESSON_SHAPES[id].title,
    content: null,
    video_type: 'none',
    video_id: null,
    order: 1,
    unit: LESSON_SHAPES[id].unit,
    attachments: [],
    sections: Array.from({ length: LESSON_SHAPES[id].sections }, (_, i) =>
      makeSection({ id: id * 100 + i, title: `${LESSON_SHAPES[id].title} — page ${i + 1}` })
    ),
  }));
  mockGetLessonProgress.mockImplementation(async (id: number) => ({
    ...progress,
    lesson: id,
    current_section: savedSections[id] ?? 0,
  }));
  mockGetLessonQuestionsStatus.mockImplementation(async (id: number) =>
    LESSON_SHAPES[id].questions > 0
      ? {
          total_questions: LESSON_SHAPES[id].questions,
          answered_questions: 0,
          correct_answers: 0,
          all_correct: false,
          requires_quiz: false,
          can_complete_lesson: true,
          ...quizStatus,
        }
      : null
  );
}

/** Renders the URL a quiz link navigated to, so the round-trip params are assertable. */
function LocationProbe() {
  const location = useLocation();
  return <div data-testid="location">{location.pathname + location.search}</div>;
}

/**
 * Exposes the history entry's `restart` flag. It rides alongside the player
 * rather than on its own route because the thing under test is whether the
 * player CLEARS the flag off the entry it is currently sitting on.
 */
function RestartProbe() {
  const location = useLocation();
  const state = location.state as { restart?: boolean } | null;
  return <div data-testid="restart-state">{String(state?.restart === true)}</div>;
}

function renderAt(entry: string) {
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <Routes>
        <Route
          path="/courses/:code/learn/:lessonId"
          element={<><CoursePlayerPage /><RestartProbe /></>}
        />
        <Route path="/courses/:code/learn" element={<LocationProbe />} />
        <Route path="/courses/:code/quizzes/:quizId" element={<LocationProbe />} />
      </Routes>
    </MemoryRouter>
  );
}

/** The `current_section` PATCHes only, as `[lessonId, index]` pairs. */
function sectionWrites(): [number, number][] {
  return (mockUpdateLessonProgress.mock.calls as unknown[][])
    .filter(call => 'current_section' in (call[1] as Record<string, unknown>))
    .map(call => [call[0] as number, (call[1] as { current_section: number }).current_section]);
}

/** A promise the test releases by hand, for holding a request open. */
function gate() {
  let release!: () => void;
  const promise = new Promise<void>(resolve => { release = resolve; });
  return { promise, release };
}

/** The "3/5" page counter in the nav footer. */
const pageIndicator = () => screen.getByTestId('page-indicator');
const nextButton = () => screen.getByRole('button', { name: /next/i });

describe('CoursePlayerPage — lesson transitions (phase 70)', () => {
  beforeEach(() => {
    mockUseAuth.mockReturnValue({ user });
    mockGetCourseWithProgress.mockReset().mockResolvedValue(multiUnitCourse);
    mockGetCourseQuizzes.mockReset().mockResolvedValue([unitOneQuiz]);
    mockUpdateLessonProgress.mockReset().mockResolvedValue(progress);
    mockUpdateCourseActivity.mockReset().mockResolvedValue(undefined);
    mockResetLessonProgress.mockReset().mockResolvedValue(undefined);
    mockGetLesson.mockReset();
    mockGetLessonProgress.mockReset();
    mockGetLessonQuestionsStatus.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('opens the next lesson at page 1 even when its saved cursor is the quiz page', async () => {
    // THE REPORTED BUG. Lesson 11 was finished on its comprehension quiz, so
    // the server still reports current_section = 2 (the quiz page of 3). The
    // old player restored that on arrival, whichever way the student arrived.
    wireLessons({ 11: 2 });

    renderAt('/courses/ROB101/learn/10');

    expect(await screen.findByRole('heading', { name: 'What Is a Robot?' })).toBeInTheDocument();
    expect(pageIndicator()).toHaveTextContent('1/2');

    fireEvent.click(nextButton());
    expect(pageIndicator()).toHaveTextContent('2/2');

    // Last page of lesson 10 → Next crosses into lesson 11.
    fireEvent.click(nextButton());

    expect(await screen.findByRole('heading', { name: 'Sensors' })).toBeInTheDocument();
    expect(pageIndicator()).toHaveTextContent('1/3');
    expect(screen.queryByTestId('quiz-section')).not.toBeInTheDocument();
  });

  it('opens the next lesson at page 1 even when its saved cursor is mid-lesson', async () => {
    // The mid-lesson variant of the test above, and the one that actually pins
    // the sequential gate: a quiz-page cursor is now declined on EVERY arrival
    // (see below), so only a resumable cursor can tell Next apart from a click.
    wireLessons({ 11: 1 });

    renderAt('/courses/ROB101/learn/10');
    await screen.findByRole('heading', { name: 'What Is a Robot?' });

    fireEvent.click(nextButton());
    fireEvent.click(nextButton());

    expect(await screen.findByRole('heading', { name: 'Sensors' })).toBeInTheDocument();
    expect(pageIndicator()).toHaveTextContent('1/3');
  });

  it('still resumes a mid-lesson page when the lesson is picked from the sidebar', async () => {
    wireLessons({ 11: 1 });

    renderAt('/courses/ROB101/learn/10');
    await screen.findByRole('heading', { name: 'What Is a Robot?' });

    fireEvent.click(screen.getByRole('button', { name: /Sensors/ }));

    expect(await screen.findByRole('heading', { name: 'Sensors' })).toBeInTheDocument();
    expect(pageIndicator()).toHaveTextContent('2/3');
  });

  it('still resumes a mid-lesson page on a direct visit to the lesson URL', async () => {
    wireLessons({ 11: 1 });

    renderAt('/courses/ROB101/learn/11');

    expect(await screen.findByRole('heading', { name: 'Sensors' })).toBeInTheDocument();
    expect(pageIndicator()).toHaveTextContent('2/3');
  });

  it('declines to resume onto the comprehension quiz from the sidebar', async () => {
    // Reported after the first cut shipped. `current_section` is pinned at
    // whatever page the student last stopped on and is never cleared, so once a
    // lesson has been paged to the end, EVERY later sidebar click reopened its
    // quiz. The end of a lesson is not a resume point.
    wireLessons({ 11: 2 });

    renderAt('/courses/ROB101/learn/10');
    await screen.findByRole('heading', { name: 'What Is a Robot?' });

    fireEvent.click(screen.getByRole('button', { name: /Sensors/ }));

    expect(await screen.findByRole('heading', { name: 'Sensors' })).toBeInTheDocument();
    expect(pageIndicator()).toHaveTextContent('1/3');
    expect(screen.queryByTestId('quiz-section')).not.toBeInTheDocument();
  });

  it('declines to resume onto the comprehension quiz on a direct visit', async () => {
    wireLessons({ 11: 2 });

    renderAt('/courses/ROB101/learn/11');

    expect(await screen.findByRole('heading', { name: 'Sensors' })).toBeInTheDocument();
    expect(pageIndicator()).toHaveTextContent('1/3');
    expect(screen.queryByTestId('quiz-section')).not.toBeInTheDocument();
  });

  it('clamps a saved cursor that is beyond the last page', async () => {
    // A lesson that shrank after the cursor was written (a removed section, a
    // deleted quiz). The clamp predates the amendment but the amendment made it
    // the sole guard for this case, and nothing else covered it.
    wireLessons({ 11: 7 });

    renderAt('/courses/ROB101/learn/11');

    expect(await screen.findByRole('heading', { name: 'Sensors' })).toBeInTheDocument();
    expect(pageIndicator()).toHaveTextContent('1/3');
  });

  it('keeps the quiz one click away on a gated lesson after declining its cursor', async () => {
    // The declined landing must not orphan the quiz. Gated, not yet passed:
    // the amber banner's "Go to Quiz →" is the route.
    wireLessons({ 11: 2 }, { requires_quiz: true, can_complete_lesson: false });

    renderAt('/courses/ROB101/learn/11');
    await screen.findByRole('heading', { name: 'Sensors' });
    expect(pageIndicator()).toHaveTextContent('1/3');

    fireEvent.click(screen.getByRole('button', { name: 'Go to Quiz →' }));

    expect(await screen.findByTestId('quiz-section')).toBeInTheDocument();
    expect(pageIndicator()).toHaveTextContent('3/3');
  });

  it('offers a route to Mark Complete when the check is passed but the lesson is not', async () => {
    // Passed-but-uncompleted was a dead end after the amendment: the banner
    // announced "Ready to mark complete" but the Mark Lesson Complete button
    // lives on the quiz page resume no longer lands on. The banner now jumps.
    wireLessons({ 11: 2 }, { requires_quiz: true, can_complete_lesson: true, all_correct: true });

    renderAt('/courses/ROB101/learn/11');
    await screen.findByRole('heading', { name: 'Sensors' });
    expect(pageIndicator()).toHaveTextContent('1/3');
    expect(screen.getByText('Quiz passed - Ready to mark complete')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Mark Complete →' }));

    expect(await screen.findByTestId('quiz-section')).toBeInTheDocument();
    expect(pageIndicator()).toHaveTextContent('3/3');
  });

  it('lands on page 1 when Mark Complete auto-advances', async () => {
    wireLessons({ 11: 2 });
    mockUpdateLessonProgress.mockResolvedValue({ ...progress, completed: true });

    renderAt('/courses/ROB101/learn/10');
    await screen.findByRole('heading', { name: 'What Is a Robot?' });

    fireEvent.click(nextButton()); // last page — Mark Complete appears here
    fireEvent.click(screen.getByRole('button', { name: /mark complete/i }));

    // Auto-advance is deliberately delayed 500ms so the completion lands first.
    expect(
      await screen.findByRole('heading', { name: 'Sensors' }, { timeout: 3000 })
    ).toBeInTheDocument();
    expect(pageIndicator()).toHaveTextContent('1/3');
  });

  it('goes to the unit quiz — with the round-trip params — off the last lesson of a unit', async () => {
    wireLessons();

    renderAt('/courses/ROB101/learn/11');
    await screen.findByRole('heading', { name: 'Sensors' });

    // 1/3 → 2/3 → 3/3 (the comprehension quiz page), then out of the lesson.
    fireEvent.keyDown(window, { key: 'ArrowRight' });
    fireEvent.keyDown(window, { key: 'ArrowRight' });
    expect(pageIndicator()).toHaveTextContent('3/3');

    fireEvent.keyDown(window, { key: 'ArrowRight' });

    // `lesson` is where the back link returns; `next` is unit 2's first lesson.
    expect(await screen.findByTestId('location')).toHaveTextContent(
      '/courses/ROB101/quizzes/100?from=learn&lesson=11&next=20'
    );
  });

  it('skips a locked unit for the course owner, who still receives its lessons', async () => {
    // The instructor gets full `lessons[]` for a unit they locked, so without
    // the is_locked check their Next walks straight into locked content.
    mockUseAuth.mockReturnValue({ user: { ...user, id: 99, is_instructor: true } });
    mockGetCourseWithProgress.mockResolvedValue({
      ...multiUnitCourse,
      units: multiUnitCourse.units.map(unit =>
        unit.id === 3 ? { ...unit, is_locked: true } : unit
      ),
    });
    mockGetCourseQuizzes.mockResolvedValue([]); // no unit quiz — a pure lesson skip
    wireLessons();

    renderAt('/courses/ROB101/learn/11');
    await screen.findByRole('heading', { name: 'Sensors' });

    fireEvent.keyDown(window, { key: 'ArrowRight' });
    fireEvent.keyDown(window, { key: 'ArrowRight' });
    expect(pageIndicator()).toHaveTextContent('3/3');

    fireEvent.click(nextButton());

    // Unit 2's "Actuators" is locked — Next lands on unit 3's "Autonomy".
    expect(await screen.findByRole('heading', { name: 'Autonomy' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Actuators' })).not.toBeInTheDocument();
  });

  it('turns two pages on two fast presses while the first save is still in flight', async () => {
    wireLessons();
    // The section PATCH never settles — exactly the window in which the second
    // press used to be swallowed by the isSavingRef guard.
    mockUpdateLessonProgress.mockImplementation(() => new Promise(() => {}));

    renderAt('/courses/ROB101/learn/11');
    await screen.findByRole('heading', { name: 'Sensors' });
    expect(pageIndicator()).toHaveTextContent('1/3');

    fireEvent.keyDown(window, { key: 'ArrowRight' });
    fireEvent.keyDown(window, { key: 'ArrowRight' });

    expect(pageIndicator()).toHaveTextContent('3/3');
  });

  // -------------------------------------------------------------------------
  // Defects found by the phase-70 adversarial pass. Each of these failed
  // against the first cut of the fix.
  // -------------------------------------------------------------------------

  it('writes a coalesced page turn to the lesson it was made in', async () => {
    // The parked turn used to be a bare index, written with the lesson id
    // captured by whichever call was already in flight — so lesson 11's cursor
    // landed on lesson 10, and lesson 11 was never written at all.
    wireLessons();
    const inFlight = gate();
    mockUpdateLessonProgress.mockImplementation(async () => {
      await inFlight.promise;
      return progress;
    });

    renderAt('/courses/ROB101/learn/10');
    await screen.findByRole('heading', { name: 'What Is a Robot?' });

    fireEvent.click(nextButton());                                   // lesson 10 → page 2, PATCH held
    fireEvent.click(screen.getByRole('button', { name: /Sensors/ })); // sidebar → lesson 11
    await screen.findByRole('heading', { name: 'Sensors' });
    fireEvent.keyDown(window, { key: 'ArrowRight' });                 // lesson 11 → page 2, parks

    await act(async () => { inFlight.release(); });

    await waitFor(() => {
      expect(sectionWrites()).toEqual([[10, 1], [11, 1]]);
    });
  });

  it('still writes a page turn that parked behind a video-position save', async () => {
    // `handleVideoProgress` shares `isSavingRef` but never drained the queue,
    // so this turn was parked and then silently forgotten — the UI advanced and
    // the server never heard about it.
    wireLessons();
    mockGetLesson.mockImplementation(async (id: number) => ({
      id,
      title: LESSON_SHAPES[id].title,
      content: null,
      video_type: 'none',
      video_id: null,
      order: 1,
      unit: LESSON_SHAPES[id].unit,
      attachments: [],
      sections: [
        makeSection({ id: 1, title: 'Page one', video_type: 'youtube', video_id: 'abc123' }),
        makeSection({ id: 2, title: 'Page two' }),
      ],
    }));
    const inFlight = gate();
    mockUpdateLessonProgress.mockImplementation(async () => {
      await inFlight.promise;
      return progress;
    });

    renderAt('/courses/ROB101/learn/11');
    await screen.findByRole('heading', { name: 'Sensors' });

    fireEvent.click(screen.getByTestId('video-progress')); // video PATCH held open
    fireEvent.keyDown(window, { key: 'ArrowRight' });      // page turn parks behind it
    expect(pageIndicator()).toHaveTextContent('2/3');

    await act(async () => { inFlight.release(); });

    await waitFor(() => {
      expect(sectionWrites()).toEqual([[11, 1]]);
    });
  });

  it('ignores an arrow key pressed while the next lesson is still loading', async () => {
    // The footer buttons vanish behind the lesson spinner; this listener does
    // not. The stray press used to run against the OUTGOING lesson and leave
    // the student on page 2 of the lesson they were arriving at.
    wireLessons({ 11: 2 });
    const lessonEleven = gate();
    const realGetLesson = mockGetLesson.getMockImplementation()!;
    mockGetLesson.mockImplementation(async (id: number) => {
      if (id === 11) await lessonEleven.promise;
      return realGetLesson(id);
    });

    renderAt('/courses/ROB101/learn/10');
    await screen.findByRole('heading', { name: 'What Is a Robot?' });

    fireEvent.keyDown(window, { key: 'ArrowRight' }); // 1/2 → 2/2
    fireEvent.keyDown(window, { key: 'ArrowRight' }); // crosses into lesson 11
    fireEvent.keyDown(window, { key: 'ArrowRight' }); // arrives mid-load — must do nothing

    await act(async () => { lessonEleven.release(); });

    expect(await screen.findByRole('heading', { name: 'Sensors' })).toBeInTheDocument();
    expect(pageIndicator()).toHaveTextContent('1/3');
    // …and nothing was written against the lesson that was being left.
    expect(sectionWrites().filter(([lessonId]) => lessonId === 10)).toEqual([[10, 1]]);
  });

  it('consumes the sequential-arrival flag on the first page turn', async () => {
    // React Router keeps location state in history.state, so the flag is not
    // one-shot: left armed, a refresh or a later Back onto this entry would
    // snap the student to page 1 forever.
    wireLessons({ 11: 2 });

    renderAt('/courses/ROB101/learn/10');
    await screen.findByRole('heading', { name: 'What Is a Robot?' });

    fireEvent.click(nextButton());
    fireEvent.click(nextButton());
    await screen.findByRole('heading', { name: 'Sensors' });

    // Armed on arrival: a reload before the student moves should still open at
    // page 1, because the stored cursor is the stale one we are ignoring.
    expect(screen.getByTestId('restart-state')).toHaveTextContent('true');

    fireEvent.click(nextButton()); // first turn under the student's own steam

    await waitFor(() => {
      expect(screen.getByTestId('restart-state')).toHaveTextContent('false');
    });
    expect(pageIndicator()).toHaveTextContent('2/3');
  });

  it('resumes rather than restarts when stepping backwards', async () => {
    // Previous is not in the spec's sequential list, and `restart` defaults to
    // resume. Sending it back to page 1 made it impossible to return to where
    // the student had been reading.
    wireLessons({ 10: 1 });

    renderAt('/courses/ROB101/learn/11');
    await screen.findByRole('heading', { name: 'Sensors' });
    expect(pageIndicator()).toHaveTextContent('1/3');

    fireEvent.click(screen.getByRole('button', { name: /previous/i }));

    expect(await screen.findByRole('heading', { name: 'What Is a Robot?' })).toBeInTheDocument();
    expect(pageIndicator()).toHaveTextContent('2/2');
  });

  it('bounces a lesson belonging to another course back into this one', async () => {
    // Reachable by hand-editing the quiz page's ?next=, or by a stale bookmark.
    // For a student enrolled in both courses the API answers 200, so nothing
    // downstream catches it and the foreign lesson renders under this course's
    // code, sidebar and progress bar.
    wireLessons();
    const realGetLesson = mockGetLesson.getMockImplementation()!;
    mockGetLesson.mockImplementation(async (id: number) => {
      if (id !== 777) return realGetLesson(id);
      return {
        id: 777,
        title: 'A Lesson From JAVA101',
        content: null,
        video_type: 'none',
        video_id: null,
        order: 1,
        unit: 999, // not a unit of ROB101
        attachments: [],
        sections: [makeSection({ id: 1 })],
      };
    });
    mockGetLessonProgress.mockResolvedValue({ ...progress, lesson: 777, current_section: 0 });
    mockGetLessonQuestionsStatus.mockResolvedValue(null);

    renderAt('/courses/ROB101/learn/777');

    // Bounced out to bare /learn, which re-runs this course's own
    // first-incomplete redirect.
    expect(await screen.findByTestId('location')).toHaveTextContent('/courses/ROB101/learn');
    expect(screen.queryByRole('heading', { name: 'A Lesson From JAVA101' })).not.toBeInTheDocument();
  });
});

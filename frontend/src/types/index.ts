// Phase 11: User preferences types
export interface UserPreferences {
  theme: 'light' | 'dark' | 'system';
  timezone: string;
  avatar_url: string | null;
  email_announcements: boolean;
}

export interface User {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  is_instructor: boolean;
  created_at: string;
  preferences?: UserPreferences;
}

export interface AuthResponse {
  access: string;
  refresh: string;
  user: User;
}

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface RegisterData {
  email: string;
  password1: string;
  password2: string;
  first_name?: string;
  last_name?: string;
}

// Phase 2: Course types
export interface Course {
  id: number;
  code: string;
  title: string;
  description: string;
  instructor: User;
  enrollment_code?: string;
  is_active: boolean;
  created_at: string;
}

export interface Unit {
  id: number;
  course: number;
  title: string;
  order: number;
  lessons?: Lesson[];
}

export interface RequiredQuizInfo {
  id: number;
  title: string;
  passing_score: number;
}

export interface LessonAttachment {
  id: number;
  filename: string;
  file_type: string;
  file_size: number;
  url: string;
  uploaded_at: string;
}

// Phase 17: Lesson Sections (Slide Deck)
export interface LessonSection {
  id: number;
  title: string;
  content: string;
  video_type: 'none' | 'youtube' | 'vimeo';
  video_id: string;
  order: number;
  created_at: string;
  updated_at: string;
}

export interface Lesson {
  id: number;
  unit: number;
  title: string;
  content: string | null;
  order: number;
  video_type: 'none' | 'youtube' | 'vimeo';
  video_id: string | null;
  required_quiz?: number | null;
  required_quiz_info?: RequiredQuizInfo | null;
  max_quiz_attempts?: number | null;
  question_count?: number;
  attachments?: LessonAttachment[];
  attachment_count?: number;
  sections?: LessonSection[];
  section_count?: number;
}

export interface Enrollment {
  id: number;
  user: number;
  course: Course;
  enrolled_at: string;
}

// Phase 3: Progress types
export interface LessonProgress {
  id: number;
  user: number;
  lesson: number;
  completed: boolean;
  completed_at: string | null;
  video_position: number;
  current_section: number;
  required_quiz_passed?: boolean | null;
  required_quiz_info?: RequiredQuizInfo | null;
  lesson_questions_status?: LessonQuestionsStatus | null;
  gamification?: GamificationDelta;
}

// Phase 5: Notification types
export interface Notification {
  id: number;
  recipient: number;
  type: 'enrollment' | 'new_lesson' | 'announcement' | 'reply' | 'badge_earned';
  title: string;
  message: string;
  is_read: boolean;
  created_at: string;
  related_url?: string;
}

// Phase 12: Quiz types
export interface Choice {
  id: number;
  text: string;
  is_correct?: boolean; // Only visible to instructors
  order: number;
}

export interface Question {
  id: number;
  text: string;
  order: number;
  choices: Choice[];
}

export interface Quiz {
  id: number;
  title: string;
  description: string;
  passing_score: number;
  points: number;
  max_attempts: number; // 0 = unlimited
  order: number;
  question_count: number;
  unit?: number;
  unit_title: string;
  course_code: string;
  questions?: Question[];
  best_score?: {
    score: number;
    passed: boolean;
    completed_at: string;
  } | null;
  attempt_count?: number;
  attempts_remaining?: number | null; // null = unlimited
  created_at: string;
  updated_at?: string;
}

export interface AttemptAnswer {
  question: number;
  question_text: string;
  selected_choice: number | null;
  selected_choice_text: string | null;
  is_correct: boolean;
  correct_choice_text: string | null;
}

export interface QuizAttempt {
  id: number;
  quiz: number;
  quiz_title: string;
  score: string;
  passed: boolean;
  points_earned: string;
  completed_at: string;
  answers: AttemptAnswer[];
  gamification?: GamificationDelta;
}

// Gradebook types
export interface GradebookItem {
  id: number;
  title: string;
  unit_title: string;
  max_points: number;
  type: 'quiz';
}

export interface StudentGradeItem {
  item_id: number;
  item_type: 'quiz';
  points_earned: number | null;
  status: 'graded' | 'not_started';
  passed?: boolean;  // Only when graded
  score_percentage?: number;  // Only when graded
}

export interface GradingConfig {
  quizzes_weight: number;
  participation_weight: number;
}

export interface StudentGradeDetailItem {
  id: number;
  type: 'quiz';
  title: string;
  unit_title: string;
  max_points: number;
  points_earned: number | null;
  status: 'graded' | 'not_started';
  passed?: boolean | null;
}

export interface GradeSummary {
  course?: {
    code: string;
    title: string;
  };
  quizzes: {
    earned: number;
    possible: number;
    percentage: number | null;
    weight: number | null;
  };
  participation: {
    completed: number;
    total: number;
    percentage: number | null;
    weight: number | null;
  };
  overall: {
    percentage: number | null;
    letter_grade: string | null;
  };
  is_weighted: boolean;
  grade_items?: StudentGradeDetailItem[];
}

// Phase 13: Enhanced Dashboard types
export interface ContinueLearning {
  course_code: string;
  course_title: string;
  current_lesson: {
    id: number;
    title: string;
    unit_title: string;
  } | null;
  progress_percentage: number;
  completed_lessons: number;
  total_lessons: number;
  last_activity_at: string | null;
}

export interface CourseProgressItem {
  course_code: string;
  course_title: string;
  overall_percentage: number;
  lessons: {
    completed: number;
    total: number;
    percentage: number;
  };
  quizzes: {
    passed: number;
    total: number;
    percentage: number;
  };
}

export interface InstructorCourseProgress {
  course_code: string;
  course_title: string;
  student_count: number;
}

export interface EnhancedDashboardStudent {
  continue_learning: ContinueLearning | null;
  course_progress_overview: CourseProgressItem[];
  is_instructor: false;
}

export interface EnhancedDashboardInstructor {
  course_progress_overview: InstructorCourseProgress[];
  is_instructor: true;
}

export type EnhancedDashboard = EnhancedDashboardStudent | EnhancedDashboardInstructor;

// API Error response
export interface APIError {
  detail?: string;
  non_field_errors?: string[];
  [key: string]: string | string[] | undefined;
}

// Phase 15: Lesson Questions (Mini Comprehension Quizzes)
export interface LessonQuestionChoice {
  id: number;
  text: string;
  is_correct?: boolean; // Only visible to instructors
  order: number;
}

export interface LessonQuestion {
  id: number;
  lesson?: number;
  text: string;
  order: number;
  choices: LessonQuestionChoice[];
  created_at?: string;
  updated_at?: string;
}

export interface LessonQuestionsStatus {
  total_questions: number;
  answered_questions: number;
  correct_answers: number;
  all_correct: boolean;
  can_complete_lesson: boolean;
  attempt_count: number;
  max_attempts: number | null;
  attempts_remaining: number | null;
  can_attempt: boolean;
  has_passed: boolean;
}

export interface QuizSubmissionResult {
  attempt_number: number;
  score: number;
  total_questions: number;
  percentage: number;
  passed: boolean;
  results: Array<{
    question_id: number;
    is_correct: boolean;
    selected_choice_id: number | null;
    correct_choice_id: number | null;
  }>;
  attempts_remaining: number | null;
  can_complete_lesson: boolean;
  gamification?: GamificationDelta;
}

export interface AnswerQuestionResult {
  is_correct: boolean;
  correct_choice_id: number | null;
  correct_choice_text: string | null;
}

// Instructor Calendar & Reminders
export interface InstructorReminder {
  id: number;
  course: number | null;
  course_code: string | null;
  course_title: string | null;
  title: string;
  description: string;
  date: string;
  time: string | null;
  end_time: string | null;
  color: 'blue' | 'green' | 'amber' | 'red' | 'purple';
  created_at: string;
  updated_at: string;
}

export interface CalendarEvent {
  id: string;
  type: 'reminder';
  title: string;
  description?: string;
  course_code: string | null;
  date: string;
  time: string | null;
  end_time?: string | null;
  color: string;
  url?: string;
  reminder_id?: number;
}

export interface CalendarResponse {
  start_date: string;
  end_date: string;
  events: CalendarEvent[];
}

// Phase 13: Discussion types
export interface Reply {
  id: number;
  author: User;
  content: string;
  created_at: string;
  updated_at: string;
}

export interface ThreadListItem {
  id: number;
  title: string;
  author: User;
  author_name: string;
  is_pinned: boolean;
  is_locked: boolean;
  reply_count: number;
  last_activity: string;
  created_at: string;
}

export interface ThreadDetail {
  id: number;
  course_code: string;
  title: string;
  content: string;
  author: User;
  is_pinned: boolean;
  is_locked: boolean;
  created_at: string;
  updated_at: string;
  replies: Reply[];
}

// ============================================================
// Phase 30: Gamification
// ============================================================

/** A badge in the catalog, annotated with this user's earned state. */
export interface BadgeInfo {
  key: string;
  name: string;
  description: string;
  icon: string;
  criteria_type: string;
  threshold: number | null;
  order: number;
  earned: boolean;
  earned_at: string | null;
}

/** A newly-earned badge, as surfaced in an award delta. */
export interface NewBadge {
  key: string;
  name: string;
  description: string;
  icon: string;
}

// ============================================================
// Phase 33: Circuit avatar customization
// ============================================================

export type AvatarSlot = 'color' | 'headgear' | 'eyes' | 'accessory' | 'backdrop';

/** A cosmetic item in the code catalog, annotated with unlock state. */
export interface AvatarItem {
  key: string;
  slot: AvatarSlot;
  name: string;
  description: string;
  required_level: number;
  unlocked: boolean;
}

/** The equipped item key per slot. */
export type AvatarEquipped = Record<AvatarSlot, string>;

/** The avatar block on the gamification profile. */
export interface AvatarState {
  mascot_name: string;
  equipped: AvatarEquipped;
  catalog: AvatarItem[];
}

/** Partial body for PATCH /gamification/avatar/. */
export type AvatarUpdatePatch = Partial<AvatarEquipped> & {
  mascot_name?: string;
};

/** The full read-endpoint payload. Fields beyond `is_gamified` are
 *  present only for students. */
export interface GamificationProfile {
  is_gamified: boolean;
  total_xp?: number;
  level?: number;
  level_floor_xp?: number;
  next_level_xp?: number;
  xp_into_level?: number;
  level_span?: number;
  level_progress_pct?: number;
  current_streak?: number;
  longest_streak?: number;
  last_activity_date?: string | null;
  streak_freezes?: number;
  badges?: BadgeInfo[];
  all_badges?: BadgeInfo[];
  avatar?: AvatarState;
}

/** The delta returned by completion / quiz-pass endpoints. */
export interface GamificationDelta {
  xp_awarded: number;
  total_xp: number;
  level: number;
  leveled_up: boolean;
  new_badges: NewBadge[];
  current_streak: number;
  streak_freezes?: number;
  freezes_earned?: number;
  freezes_used?: number;
}

// ============================================================
// Phase 32: Duolingo-style quiz mastery sessions
// ============================================================

/** Per-question progress inside a mastery session. */
export interface SessionQuestionStatus {
  question_id: number;
  answered: boolean;
  first_try_correct: boolean | null;
  mastered: boolean;
}

/** Resume/progress state for an in-progress mastery session
 *  (shared shape between unit quizzes and lesson checks). */
export interface QuizSessionState {
  attempt_id: number;
  quiz_id?: number;
  lesson_id?: number;
  status: 'in_progress' | 'completed';
  questions: SessionQuestionStatus[];
  remaining_question_ids: number[];
  total_questions: number;
  mastered_count: number;
  answered_count: number;
}

/** Finalize payload for a lesson-check mastery session. */
export interface LessonSessionResult {
  attempt_number: number;
  score: number;
  total_questions: number;
  percentage: number;
  passed: boolean;
  can_complete_lesson: boolean;
  gamification?: GamificationDelta;
}

/** Response for one graded answer in a mastery session. `result` is present
 *  only when this answer completed the session. */
export interface SessionAnswerResult<TResult = QuizAttempt | LessonSessionResult> {
  is_correct: boolean;
  correct_choice_id: number | null;
  correct_choice_text: string | null;
  remaining_count: number;
  session_complete: boolean;
  result?: TResult;
}

export type QuizSessionAnswerResult = SessionAnswerResult<QuizAttempt>;
export type LessonSessionAnswerResult = SessionAnswerResult<LessonSessionResult>;

// ============================================================
// Phase 35: Duolingo-style course map
// ============================================================

/** Visual-only gating state; no route is actually blocked. */
export type NodeState = 'completed' | 'current' | 'unlocked' | 'locked';

export interface CourseMapLessonNode {
  node_type: 'lesson';
  id: number;
  title: string;
  order: number;
  state: NodeState;
}

/** Unit quiz as a "boss" node at the end of its unit's stretch. */
export interface CourseMapQuizNode {
  node_type: 'quiz';
  id: number;
  title: string;
  order: number;
  state: NodeState;
  passing_score: number;
  /** Highest attempt %, null if never attempted. */
  best_score: number | null;
}

export type CourseMapNode = CourseMapLessonNode | CourseMapQuizNode;

export interface CourseMapUnit {
  id: number;
  title: string;
  order: number;
  nodes: CourseMapNode[];
}

export interface CourseMap {
  course_code: string;
  course_title: string;
  total_nodes: number;
  completed_nodes: number;
  /** Composite "<node_type>-<id>" key (lesson and quiz ids can collide). */
  current_node_id: string | null;
  units: CourseMapUnit[];
}

// Phase 51: Course invite types
export type CourseInviteStatus = 'pending' | 'accepted' | 'expired' | 'revoked';

export interface CourseInvite {
  id: number;
  email: string;
  status: CourseInviteStatus;
  created_at: string;
  expires_at: string;
}

export type InviteOutcome = 'invited' | 'resent' | 'already_enrolled' | 'invalid';

export interface InviteOutcomeRow {
  email: string;
  status: InviteOutcome;
}

export interface InviteBatchResult {
  results: InviteOutcomeRow[];
}

export interface InviteTokenInfo {
  course_title: string | null;
  course_code: string | null;
  email_masked: string | null;
  status: CourseInviteStatus | 'invalid';
  account_exists: boolean;
}

export interface AcceptInvitePayload {
  first_name: string;
  last_name: string;
  password: string;
  agree_terms: boolean;
}

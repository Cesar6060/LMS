// Phase 11: User preferences types
export interface UserPreferences {
  theme: 'light' | 'dark' | 'system';
  timezone: string;
  avatar_url: string | null;
  email_announcements: boolean;
  email_grades: boolean;
  email_submissions: boolean;
  email_due_reminders: boolean;
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
  key: string;
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
}

// Phase 4: Assignment types
export interface AssignmentListItem {
  id: number;
  title: string;
  max_points: number;
  due_date: string | null;
  order: number;
  unit: number;
  course_code: string;
  unit_title: string;
  submission_status: {
    status: 'draft' | 'submitted' | 'graded';
    grade: number | null;
  } | null;
  // Phase 10: Availability fields
  available_from: string | null;
  available_until: string | null;
  is_available: boolean;
  is_closed: boolean;
}

export interface Assignment {
  id: number;
  title: string;
  description: string;
  max_points: number;
  due_date: string | null;
  order: number;
  allow_late: boolean;
  course_code: string;
  unit_title: string;
  my_submission: Submission | null;
  submission_count?: number;
  graded_count?: number;
  is_instructor: boolean;
  created_at: string;
  updated_at: string;
  // Phase 10: Availability fields
  available_from: string | null;
  available_until: string | null;
  is_available: boolean;
  is_closed: boolean;
  // Phase 10: Late penalty fields
  late_penalty_percent: number | null;
  late_penalty_interval: 'day' | 'hour';
  max_late_penalty: number | null;
}

export interface Grade {
  id: number;
  points: number;
  feedback: string;
  grader: number;
  grader_name: string | null;
  percentage: number;
  graded_at: string;
  updated_at: string;
}

export interface SubmissionFile {
  id: number;
  filename: string;
  url: string;
  uploaded_at: string;
}

export interface SubmissionHistory {
  id: number;
  content: string;
  files_info: string[];
  submitted_at: string;
  grade_points: number | null;
  grade_feedback: string;
  archived_at: string;
}

export interface Submission {
  id: number;
  assignment: number;
  student: number;
  student_name: string;
  student_email: string;
  content: string;
  file: string | null;
  files: SubmissionFile[];
  status: 'draft' | 'submitted' | 'graded';
  is_late: boolean;
  submitted_at: string | null;
  created_at: string;
  updated_at: string;
  grade: Grade | null;
  history?: SubmissionHistory[];
  // Phase 10: Late penalty fields
  late_penalty_applied: number;
  final_grade: number | null;
}

// Phase 5: Notification types
export interface Notification {
  id: number;
  recipient: number;
  type: 'enrollment' | 'submission' | 'grade' | 'new_lesson' | 'new_assignment' | 'resubmission' | 'announcement';
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
}

// Gradebook types
export interface GradebookItem {
  id: number;
  title: string;
  unit_title: string;
  max_points: number;
  due_date: string | null;
  type: 'assignment' | 'quiz';
}

export interface StudentGradeItem {
  item_id: number;
  item_type: 'assignment' | 'quiz';
  points_earned: number | null;
  status: 'graded' | 'submitted' | 'missing' | 'not_started';
  is_late: boolean;
  late_penalty?: number;
  passed?: boolean;  // Only for quizzes
  score_percentage?: number;  // Only for quizzes
}

export interface GradingConfig {
  assignments_weight: number;
  quizzes_weight: number;
  participation_weight: number;
}

export interface StudentGradeDetailItem {
  id: number;
  type: 'assignment' | 'quiz';
  title: string;
  unit_title: string;
  max_points: number;
  points_earned: number | null;
  status: 'graded' | 'submitted' | 'missing' | 'not_started';
  is_late: boolean;
  due_date: string | null;
  passed?: boolean;  // Only for quizzes
}

export interface GradeSummary {
  course?: {
    code: string;
    title: string;
  };
  assignments: {
    earned: number;
    possible: number;
    percentage: number | null;
    weight: number | null;
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

export interface UpcomingDeadline {
  id: number;
  type: 'assignment' | 'quiz';
  title: string;
  course_code: string;
  course_title: string;
  due_date: string;
  max_points: number;
  has_draft?: boolean;
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
  assignments: {
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

export interface RecentSubmission {
  id: number;
  assignment_id: number;
  student_name: string;
  student_email: string;
  assignment_title: string;
  course_code: string;
  course_title: string;
  submitted_at: string | null;
  is_late: boolean;
}

export interface InstructorCourseProgress {
  course_code: string;
  course_title: string;
  student_count: number;
  pending_submissions: number;
}

export interface EnhancedDashboardStudent {
  continue_learning: ContinueLearning | null;
  upcoming_deadlines: UpcomingDeadline[];
  course_progress_overview: CourseProgressItem[];
  is_instructor: false;
}

export interface EnhancedDashboardInstructor {
  recent_submissions: RecentSubmission[];
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
  type: 'assignment' | 'quiz' | 'reminder';
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

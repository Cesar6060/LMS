import api from './api';

// ---- Response types (Phase 31 instructor analytics) ----

export interface AnalyticsOverview {
  course: {
    code: string;
    title: string;
  };
  student_count: number;
  avg_progress_percentage: number | null;
  avg_grade_percentage: number | null;
  active_last_7_days: number;
}

export interface UnitQuizRow {
  id: number;
  title: string;
  unit_title: string;
  passing_score: number;
  avg_score: number | null;
  pass_rate: number | null;
  completion_rate: number | null;
}

export interface LessonCheckRow {
  id: number;
  title: string;
  unit_title: string;
  attempted_count: number;
  passed_count: number;
  stuck_count: number;
  avg_attempts_to_pass: number | null;
}

export interface AnalyticsQuizzes {
  unit_quizzes: UnitQuizRow[];
  lesson_checks: LessonCheckRow[];
}

export interface AnalyticsStudentRow {
  student: {
    id: number;
    name: string;
    email: string;
  };
  progress_percentage: number;
  quiz_average: number | null;
  weighted_grade: number | null;
  last_activity_at: string | null;
  current_streak: number;
  at_risk: boolean;
}

export interface AnalyticsStudents {
  students: AnalyticsStudentRow[];
}

export interface ActivityDay {
  date: string;
  lessons_completed: number;
  quiz_attempts: number;
  lesson_check_attempts: number;
}

export interface AnalyticsActivity {
  days: ActivityDay[];
}

export const analyticsService = {
  async getOverview(courseCode: string): Promise<AnalyticsOverview> {
    const response = await api.get<AnalyticsOverview>(`/courses/courses/${courseCode}/analytics/overview/`);
    return response.data;
  },

  async getQuizzes(courseCode: string): Promise<AnalyticsQuizzes> {
    const response = await api.get<AnalyticsQuizzes>(`/courses/courses/${courseCode}/analytics/quizzes/`);
    return response.data;
  },

  async getStudents(courseCode: string): Promise<AnalyticsStudents> {
    const response = await api.get<AnalyticsStudents>(`/courses/courses/${courseCode}/analytics/students/`);
    return response.data;
  },

  async getActivity(courseCode: string): Promise<AnalyticsActivity> {
    const response = await api.get<AnalyticsActivity>(`/courses/courses/${courseCode}/analytics/activity/`);
    return response.data;
  },
};

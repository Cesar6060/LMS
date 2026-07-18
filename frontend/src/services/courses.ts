import api from './api';
import type { Course, Unit, Lesson, Enrollment, LessonProgress, GradingConfig, GradeSummary, EnhancedDashboard, LessonQuestion, LessonQuestionsStatus, AnswerQuestionResult, QuizSubmissionResult, LessonAttachment, LessonSection, InstructorReminder, CalendarResponse } from '../types';

// Re-export types for convenience
export type { Unit, Lesson } from '../types';

export interface CourseListItem {
  id: number;
  code: string;
  title: string;
  description: string;
  instructor_name: string;
  is_active: boolean;
  student_count: number;
  unit_count: number;
  created_at: string;
}

export interface LessonListItem {
  id: number;
  title: string;
  order: number;
  video_type: 'none' | 'youtube' | 'vimeo';
  content?: string;
  video_id: string | null;
  required_quiz?: number | null;
  required_quiz_info?: {
    id: number;
    title: string;
    passing_score: number;
  } | null;
  question_count?: number;
  attachment_count?: number;
  section_count?: number;
}

export interface UnitWithLessons {
  id: number;
  course: number;
  title: string;
  order: number;
  lessons: LessonListItem[];
}

export interface CourseDetail extends Course {
  units: UnitWithLessons[];
  student_count: number;
  is_enrolled: boolean;
}

export interface InstructorCourse extends Course {
  units: UnitWithLessons[];
  student_count: number;
  enrollment_code: string;
}

export interface AnnouncementListItem {
  id: number;
  course_code: string;
  author_name: string;
  title: string;
  is_pinned: boolean;
  created_at: string;
}

export interface Announcement {
  id: number;
  course: number;
  course_code: string;
  author: {
    id: number;
    email: string;
    first_name: string;
    last_name: string;
  };
  title: string;
  content: string;
  is_pinned: boolean;
  send_email: boolean;
  created_at: string;
  updated_at: string;
}

export interface GradebookItem {
  id: number;
  title: string;
  unit_title: string;
  max_points: number;
  type: 'quiz';
}

export interface StudentGrade {
  item_id: number;
  item_type: 'quiz';
  points_earned: number | null;
  status: 'graded' | 'not_started';
  passed?: boolean | null;
  score_percentage?: number;
}

export interface GradebookStudent {
  id: number;
  name: string;
  email: string;
  grades: StudentGrade[];
  total_earned: number;
  total_possible: number;
  percentage: number | null;
  letter_grade: string | null;
  quizzes_percentage: number | null;
  participation_percentage: number | null;
}

export interface Gradebook {
  course: {
    code: string;
    title: string;
  };
  gradebook_items: GradebookItem[];
  students: GradebookStudent[];
  total_possible: number;
  has_quizzes: boolean;
  grading_config: GradingConfig | null;
}

export interface RosterStudent {
  id: number;
  student_id: number;
  email: string;
  first_name: string;
  last_name: string;
  enrolled_at: string;
  last_activity_at: string | null;
  is_active: boolean;
  progress_percentage: number;
  is_inactive: boolean;
}

export interface InviteResult {
  message: string;
  email: string;
}

export const courseService = {
  // Courses
  async listCourses(): Promise<CourseListItem[]> {
    const response = await api.get<CourseListItem[]>('/courses/courses/');
    return response.data;
  },

  async getCourse(code: string): Promise<CourseDetail> {
    const response = await api.get<CourseDetail>(`/courses/courses/${code}/`);
    return response.data;
  },

  async createCourse(data: { code: string; title: string; description?: string }): Promise<Course> {
    const response = await api.post<Course>('/courses/courses/', data);
    return response.data;
  },

  async updateCourse(code: string, data: Partial<Course>): Promise<Course> {
    const response = await api.patch<Course>(`/courses/courses/${code}/`, data);
    return response.data;
  },

  async deleteCourse(code: string): Promise<void> {
    await api.delete(`/courses/courses/${code}/`);
  },

  // Instructor courses (with enrollment codes)
  async getInstructorCourses(): Promise<InstructorCourse[]> {
    const response = await api.get<InstructorCourse[]>('/courses/instructor/courses/');
    return response.data;
  },

  async regenerateEnrollmentCode(code: string): Promise<{ enrollment_code: string }> {
    const response = await api.post<{ enrollment_code: string }>(`/courses/courses/${code}/regenerate_code/`);
    return response.data;
  },

  // Enrollment
  async enroll(courseCode: string, enrollmentCode: string): Promise<Enrollment> {
    const response = await api.post<Enrollment>(`/courses/courses/${courseCode}/enroll/`, {
      enrollment_code: enrollmentCode
    });
    return response.data;
  },

  async enrollWithCode(enrollmentCode: string): Promise<Enrollment> {
    const response = await api.post<Enrollment>('/courses/enrollments/', {
      enrollment_code: enrollmentCode
    });
    return response.data;
  },

  async getMyEnrollments(): Promise<Enrollment[]> {
    const response = await api.get<Enrollment[]>('/courses/enrollments/');
    return response.data;
  },

  async unenroll(enrollmentId: number): Promise<void> {
    await api.delete(`/courses/enrollments/${enrollmentId}/`);
  },

  // Units
  async getUnits(courseCode: string): Promise<UnitWithLessons[]> {
    const response = await api.get<UnitWithLessons[]>(`/courses/courses/${courseCode}/units/`);
    return response.data;
  },

  async createUnit(courseCode: string, data: { title: string; order?: number }): Promise<Unit> {
    const response = await api.post<Unit>(`/courses/courses/${courseCode}/units/`, data);
    return response.data;
  },

  async updateUnit(unitId: number, data: Partial<Unit>): Promise<Unit> {
    const response = await api.patch<Unit>(`/courses/units/${unitId}/`, data);
    return response.data;
  },

  async deleteUnit(unitId: number): Promise<void> {
    await api.delete(`/courses/units/${unitId}/`);
  },

  async reorderUnit(unitId: number, order: number): Promise<Unit> {
    const response = await api.patch<Unit>(`/courses/units/${unitId}/reorder/`, { order });
    return response.data;
  },

  // Lessons
  async getLessons(unitId: number): Promise<Lesson[]> {
    const response = await api.get<Lesson[]>(`/courses/units/${unitId}/lessons/`);
    return response.data;
  },

  async getLesson(lessonId: number): Promise<Lesson> {
    const response = await api.get<Lesson>(`/courses/lessons/${lessonId}/`);
    return response.data;
  },

  async createLesson(unitId: number, data: { title: string; content?: string; video_type?: string; video_id?: string; order?: number }): Promise<Lesson> {
    const response = await api.post<Lesson>(`/courses/units/${unitId}/lessons/`, data);
    return response.data;
  },

  async updateLesson(lessonId: number, data: Partial<Lesson>): Promise<Lesson> {
    const response = await api.patch<Lesson>(`/courses/lessons/${lessonId}/`, data);
    return response.data;
  },

  async deleteLesson(lessonId: number): Promise<void> {
    await api.delete(`/courses/lessons/${lessonId}/`);
  },

  async reorderLesson(lessonId: number, order: number, unitId?: number): Promise<Lesson> {
    const payload: { order: number; unit?: number } = { order };
    if (unitId !== undefined) {
      payload.unit = unitId;
    }
    const response = await api.patch<Lesson>(`/courses/lessons/${lessonId}/reorder/`, payload);
    return response.data;
  },

  // Progress
  async getLessonProgress(lessonId: number): Promise<LessonProgress> {
    const response = await api.get<LessonProgress>(`/courses/lessons/${lessonId}/progress/`);
    return response.data;
  },

  async updateLessonProgress(lessonId: number, data: { completed?: boolean; video_position?: number; current_section?: number }): Promise<LessonProgress> {
    const response = await api.patch<LessonProgress>(`/courses/lessons/${lessonId}/progress/`, data);
    return response.data;
  },

  async resetLessonProgress(lessonId: number): Promise<void> {
    await api.post(`/courses/lessons/${lessonId}/progress/reset/`);
  },

  // Course progress
  async getCourseProgress(courseCode: string): Promise<{
    total_lessons: number;
    completed_lessons: number;
    progress_percentage: number;
  }> {
    const response = await api.get(`/courses/courses/${courseCode}/progress/`);
    return response.data;
  },

  // Dashboard stats
  async getDashboardStats(): Promise<{
    // Instructor stats
    total_students?: number;
    // Student stats
    lessons_completed?: number;
    // Common
    course_count: number;
  }> {
    const response = await api.get('/courses/dashboard/stats/');
    return response.data;
  },

  // Enhanced Dashboard (Phase 13)
  async getEnhancedDashboard(): Promise<EnhancedDashboard> {
    const response = await api.get<EnhancedDashboard>('/courses/dashboard/enhanced/');
    return response.data;
  },

  // Announcements
  async getCourseAnnouncements(courseCode: string): Promise<AnnouncementListItem[]> {
    const response = await api.get<AnnouncementListItem[]>(`/courses/courses/${courseCode}/announcements/`);
    return response.data;
  },

  async getAnnouncement(announcementId: number): Promise<Announcement> {
    const response = await api.get<Announcement>(`/courses/announcements/${announcementId}/`);
    return response.data;
  },

  async createAnnouncement(courseCode: string, data: {
    title: string;
    content: string;
    is_pinned?: boolean;
    send_email?: boolean;
  }): Promise<Announcement> {
    const response = await api.post<Announcement>(`/courses/courses/${courseCode}/announcements/`, data);
    return response.data;
  },

  async updateAnnouncement(announcementId: number, data: Partial<{
    title: string;
    content: string;
    is_pinned: boolean;
  }>): Promise<Announcement> {
    const response = await api.patch<Announcement>(`/courses/announcements/${announcementId}/`, data);
    return response.data;
  },

  async deleteAnnouncement(announcementId: number): Promise<void> {
    await api.delete(`/courses/announcements/${announcementId}/`);
  },

  async pinAnnouncement(announcementId: number): Promise<Announcement> {
    const response = await api.post<Announcement>(`/courses/announcements/${announcementId}/pin/`);
    return response.data;
  },

  async unpinAnnouncement(announcementId: number): Promise<Announcement> {
    const response = await api.post<Announcement>(`/courses/announcements/${announcementId}/unpin/`);
    return response.data;
  },

  // Gradebook
  async getGradebook(courseCode: string): Promise<Gradebook> {
    const response = await api.get<Gradebook>(`/courses/courses/${courseCode}/gradebook/`);
    return response.data;
  },

  getGradebookExportUrl(courseCode: string): string {
    const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';
    return `${baseUrl}/courses/courses/${courseCode}/gradebook/export/`;
  },

  // Student Roster
  async getStudentRoster(courseCode: string): Promise<RosterStudent[]> {
    const response = await api.get<RosterStudent[]>(`/courses/courses/${courseCode}/students/`);
    return response.data;
  },

  async removeStudent(courseCode: string, enrollmentId: number): Promise<void> {
    await api.delete(`/courses/courses/${courseCode}/students/${enrollmentId}/`);
  },

  async sendCourseInvite(courseCode: string, email: string): Promise<InviteResult> {
    const response = await api.post<InviteResult>(
      `/courses/courses/${courseCode}/students/invite/`,
      { email }
    );
    return response.data;
  },

  async updateCourseActivity(courseCode: string): Promise<void> {
    await api.post(`/courses/courses/${courseCode}/activity/`);
  },

  // Grading config
  async getGradingConfig(courseCode: string): Promise<GradingConfig> {
    const response = await api.get<GradingConfig>(`/courses/courses/${courseCode}/grading-config/`);
    return response.data;
  },

  async updateGradingConfig(courseCode: string, data: GradingConfig): Promise<GradingConfig> {
    const response = await api.put<GradingConfig>(`/courses/courses/${courseCode}/grading-config/`, data);
    return response.data;
  },

  // Student grade summary
  async getMyGradeSummary(courseCode: string): Promise<GradeSummary> {
    const response = await api.get<GradeSummary>(`/courses/courses/${courseCode}/my-grades/`);
    return response.data;
  },

  // Course with progress (for course player)
  async getCourseWithProgress(courseCode: string): Promise<CourseDetail & {
    units: Array<UnitWithLessons & {
      lessons: Array<LessonListItem & { is_completed?: boolean }>;
    }>;
  }> {
    // Get course details
    const courseData = await this.getCourse(courseCode);

    // Get all lesson progress for this course (in parallel for performance)
    const lessonProgressMap = new Map<number, boolean>();
    const allLessons = courseData.units.flatMap(unit => unit.lessons);

    const progressResults = await Promise.all(
      allLessons.map(lesson =>
        this.getLessonProgress(lesson.id)
          .then(progress => ({ id: lesson.id, completed: progress.completed }))
          .catch(() => ({ id: lesson.id, completed: false }))
      )
    );

    for (const { id, completed } of progressResults) {
      lessonProgressMap.set(id, completed);
    }

    // Merge progress into course data
    return {
      ...courseData,
      units: courseData.units.map(unit => ({
        ...unit,
        lessons: unit.lessons.map(lesson => ({
          ...lesson,
          is_completed: lessonProgressMap.get(lesson.id) || false
        }))
      }))
    };
  },

  // Lesson Questions (Mini Comprehension Quizzes)
  async getLessonQuestions(lessonId: number): Promise<LessonQuestion[]> {
    const response = await api.get<LessonQuestion[]>(`/courses/lessons/${lessonId}/questions/`);
    return response.data;
  },

  async createLessonQuestion(lessonId: number, data: {
    text: string;
    order?: number;
    choices: Array<{ text: string; is_correct: boolean; order?: number }>;
  }): Promise<LessonQuestion> {
    const response = await api.post<LessonQuestion>(`/courses/lessons/${lessonId}/questions/`, data);
    return response.data;
  },

  async updateLessonQuestion(lessonId: number, questionId: number, data: {
    text: string;
    order?: number;
    choices: Array<{ text: string; is_correct: boolean; order?: number }>;
  }): Promise<LessonQuestion> {
    const response = await api.put<LessonQuestion>(`/courses/lessons/${lessonId}/questions/${questionId}/`, data);
    return response.data;
  },

  async deleteLessonQuestion(lessonId: number, questionId: number): Promise<void> {
    await api.delete(`/courses/lessons/${lessonId}/questions/${questionId}/`);
  },

  async answerLessonQuestion(lessonId: number, questionId: number, choiceId: number): Promise<AnswerQuestionResult> {
    const response = await api.post<AnswerQuestionResult>(`/courses/lessons/${lessonId}/answer-question/`, {
      question_id: questionId,
      choice_id: choiceId,
    });
    return response.data;
  },

  async getLessonQuestionsStatus(lessonId: number): Promise<LessonQuestionsStatus> {
    const response = await api.get<LessonQuestionsStatus>(`/courses/lessons/${lessonId}/questions-status/`);
    return response.data;
  },

  async submitLessonQuiz(lessonId: number, answers: Record<string, number>): Promise<QuizSubmissionResult> {
    const response = await api.post<QuizSubmissionResult>(`/courses/lessons/${lessonId}/submit-quiz/`, {
      answers,
    });
    return response.data;
  },
  // Lesson Attachments (Phase 16)
  async getLessonAttachments(lessonId: number): Promise<LessonAttachment[]> {
    const response = await api.get<LessonAttachment[]>(`/courses/lessons/${lessonId}/attachments/`);
    return response.data;
  },

  async uploadLessonAttachments(lessonId: number, files: File[]): Promise<LessonAttachment[]> {
    const formData = new FormData();
    files.forEach(file => {
      formData.append('files', file);
    });

    const response = await api.post<LessonAttachment[]>(
      `/courses/lessons/${lessonId}/attachments/`,
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      }
    );
    return response.data;
  },

  async deleteLessonAttachment(lessonId: number, attachmentId: number): Promise<void> {
    await api.delete(`/courses/lessons/${lessonId}/attachments/${attachmentId}/`);
  },

  // Lesson Sections (Phase 17: Lesson Pagination)
  async getLessonSections(lessonId: number): Promise<LessonSection[]> {
    const response = await api.get<LessonSection[]>(`/courses/lessons/${lessonId}/sections/`);
    return response.data;
  },

  async createLessonSection(lessonId: number, data: {
    title?: string;
    content?: string;
    video_type?: 'none' | 'youtube' | 'vimeo';
    video_id?: string;
    order?: number;
  }): Promise<LessonSection> {
    const response = await api.post<LessonSection>(`/courses/lessons/${lessonId}/sections/`, data);
    return response.data;
  },

  async updateLessonSection(lessonId: number, sectionId: number, data: {
    title?: string;
    content?: string;
    video_type?: 'none' | 'youtube' | 'vimeo';
    video_id?: string;
    order?: number;
  }): Promise<LessonSection> {
    const response = await api.put<LessonSection>(`/courses/lessons/${lessonId}/sections/${sectionId}/`, data);
    return response.data;
  },

  async deleteLessonSection(lessonId: number, sectionId: number): Promise<void> {
    await api.delete(`/courses/lessons/${lessonId}/sections/${sectionId}/`);
  },

  async reorderLessonSections(lessonId: number, sectionIds: number[]): Promise<LessonSection[]> {
    const response = await api.post<LessonSection[]>(`/courses/lessons/${lessonId}/sections/reorder/`, {
      section_ids: sectionIds,
    });
    return response.data;
  },

  // Instructor Calendar & Reminders
  async getInstructorCalendar(startDate?: string, endDate?: string): Promise<CalendarResponse> {
    const params = new URLSearchParams();
    if (startDate) params.append('start_date', startDate);
    if (endDate) params.append('end_date', endDate);
    const query = params.toString() ? `?${params.toString()}` : '';
    const response = await api.get<CalendarResponse>(`/courses/instructor/calendar/${query}`);
    return response.data;
  },

  async getReminders(): Promise<InstructorReminder[]> {
    const response = await api.get<InstructorReminder[]>('/courses/instructor/reminders/');
    return response.data;
  },

  async getReminder(id: number): Promise<InstructorReminder> {
    const response = await api.get<InstructorReminder>(`/courses/instructor/reminders/${id}/`);
    return response.data;
  },

  async createReminder(data: {
    title: string;
    description?: string;
    date: string;
    time?: string;
    end_time?: string;
    color?: string;
    course?: number;
  }): Promise<InstructorReminder> {
    const response = await api.post<InstructorReminder>('/courses/instructor/reminders/', data);
    return response.data;
  },

  async updateReminder(id: number, data: {
    title?: string;
    description?: string;
    date?: string;
    time?: string;
    end_time?: string;
    color?: string;
    course?: number;
  }): Promise<InstructorReminder> {
    const response = await api.patch<InstructorReminder>(`/courses/instructor/reminders/${id}/`, data);
    return response.data;
  },

  async deleteReminder(id: number): Promise<void> {
    await api.delete(`/courses/instructor/reminders/${id}/`);
  },
};

export default courseService;

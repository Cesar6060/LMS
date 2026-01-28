import api from './api';
import type { Course, Unit, Lesson, Enrollment, LessonProgress, GradingConfig, GradeSummary } from '../types';

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

export interface GradebookAssignment {
  id: number;
  title: string;
  unit_title: string;
  max_points: number;
  due_date: string | null;
}

export interface GradebookItem {
  id: number;
  title: string;
  unit_title: string;
  max_points: number;
  due_date: string | null;
  type: 'assignment' | 'quiz';
}

export interface StudentGrade {
  assignment_id?: number;
  item_id: number;
  item_type: 'assignment' | 'quiz';
  points_earned: number | null;
  status: 'graded' | 'submitted' | 'missing' | 'not_started';
  is_late: boolean;
  passed?: boolean | null;
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
}

export interface Gradebook {
  course: {
    code: string;
    title: string;
  };
  assignments: GradebookAssignment[];
  gradebook_items: GradebookItem[];
  students: GradebookStudent[];
  total_possible: number;
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

  async reorderLesson(lessonId: number, order: number): Promise<Lesson> {
    const response = await api.patch<Lesson>(`/courses/lessons/${lessonId}/reorder/`, { order });
    return response.data;
  },

  // Progress
  async getLessonProgress(lessonId: number): Promise<LessonProgress> {
    const response = await api.get<LessonProgress>(`/courses/lessons/${lessonId}/progress/`);
    return response.data;
  },

  async updateLessonProgress(lessonId: number, data: { completed?: boolean; video_position?: number }): Promise<LessonProgress> {
    const response = await api.patch<LessonProgress>(`/courses/lessons/${lessonId}/progress/`, data);
    return response.data;
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
    pending_grades?: number;
    total_students?: number;
    // Student stats
    lessons_completed?: number;
    assignments_due?: number;
    // Common
    course_count: number;
  }> {
    const response = await api.get('/courses/dashboard/stats/');
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

    // Get all lesson progress for this course
    const lessonProgressMap = new Map<number, boolean>();

    // Fetch progress for each lesson
    for (const unit of courseData.units) {
      for (const lesson of unit.lessons) {
        try {
          const progress = await this.getLessonProgress(lesson.id);
          lessonProgressMap.set(lesson.id, progress.completed);
        } catch {
          lessonProgressMap.set(lesson.id, false);
        }
      }
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
};

export default courseService;

import api from './api';
import type { Assignment, AssignmentListItem, Submission } from '../types';

export const assignmentService = {
  // List assignments for a course
  async getCourseAssignments(courseCode: string): Promise<AssignmentListItem[]> {
    const response = await api.get<AssignmentListItem[]>(
      `/assignments/courses/${courseCode}/assignments/`
    );
    return response.data;
  },

  // List assignments for a unit
  async getUnitAssignments(unitId: number): Promise<AssignmentListItem[]> {
    const response = await api.get<AssignmentListItem[]>(
      `/assignments/units/${unitId}/assignments/`
    );
    return response.data;
  },

  // Get assignment details
  async getAssignment(assignmentId: number): Promise<Assignment> {
    const response = await api.get<Assignment>(
      `/assignments/assignments/${assignmentId}/`
    );
    return response.data;
  },

  // Create assignment (instructor)
  async createAssignment(
    unitId: number,
    data: {
      title: string;
      description?: string;
      max_points?: number;
      due_date?: string | null;
      allow_late?: boolean;
      available_from?: string | null;
      available_until?: string | null;
      late_penalty_percent?: number | null;
      late_penalty_interval?: 'day' | 'hour';
      max_late_penalty?: number | null;
    }
  ): Promise<Assignment> {
    const response = await api.post<Assignment>(
      `/assignments/units/${unitId}/assignments/`,
      data
    );
    return response.data;
  },

  // Update assignment (instructor)
  async updateAssignment(
    assignmentId: number,
    data: Partial<{
      title: string;
      description: string;
      max_points: number;
      due_date: string | null;
      allow_late: boolean;
      available_from: string | null;
      available_until: string | null;
      late_penalty_percent: number | null;
      late_penalty_interval: 'day' | 'hour';
      max_late_penalty: number | null;
    }>
  ): Promise<Assignment> {
    const response = await api.patch<Assignment>(
      `/assignments/assignments/${assignmentId}/`,
      data
    );
    return response.data;
  },

  // Delete assignment (instructor)
  async deleteAssignment(assignmentId: number): Promise<void> {
    await api.delete(`/assignments/assignments/${assignmentId}/`);
  },

  // Get my submission for an assignment
  async getMySubmission(assignmentId: number): Promise<Submission> {
    const response = await api.get<Submission>(
      `/assignments/assignments/${assignmentId}/my-submission/`
    );
    return response.data;
  },

  // Update my submission (save draft)
  async updateSubmission(
    assignmentId: number,
    data: { content?: string; files?: File[]; deleteFileIds?: number[] }
  ): Promise<Submission> {
    const formData = new FormData();
    if (data.content !== undefined) {
      formData.append('content', data.content);
    }
    if (data.files && data.files.length > 0) {
      data.files.forEach(file => {
        formData.append('files', file);
      });
    }
    if (data.deleteFileIds && data.deleteFileIds.length > 0) {
      data.deleteFileIds.forEach(id => {
        formData.append('delete_files', id.toString());
      });
    }

    const response = await api.patch<Submission>(
      `/assignments/assignments/${assignmentId}/my-submission/`,
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      }
    );
    return response.data;
  },

  // Submit assignment
  async submitAssignment(assignmentId: number): Promise<Submission> {
    const response = await api.post<Submission>(
      `/assignments/assignments/${assignmentId}/submit/`
    );
    return response.data;
  },

  // List submissions for assignment (instructor)
  async getAssignmentSubmissions(assignmentId: number): Promise<Submission[]> {
    const response = await api.get<Submission[]>(
      `/assignments/assignments/${assignmentId}/submissions/`
    );
    return response.data;
  },

  // Grade a submission (instructor)
  async gradeSubmission(
    submissionId: number,
    data: { points: number; feedback?: string }
  ): Promise<Submission> {
    const response = await api.post<Submission>(
      `/assignments/submissions/${submissionId}/grade/`,
      data
    );
    return response.data;
  },

  // Update grade (instructor)
  async updateGrade(
    submissionId: number,
    data: { points?: number; feedback?: string }
  ): Promise<Submission> {
    const response = await api.put<Submission>(
      `/assignments/submissions/${submissionId}/grade/`,
      data
    );
    return response.data;
  },

  // Allow resubmission (instructor)
  async allowResubmission(submissionId: number): Promise<Submission> {
    const response = await api.post<Submission>(
      `/assignments/submissions/${submissionId}/allow-resubmit/`
    );
    return response.data;
  },

  // Quick grade from gradebook
  async quickGrade(assignmentId: number, studentId: number, points: number): Promise<{
    success: boolean;
    assignment_id: number;
    student_id: number;
    points: number;
    max_points: number;
  }> {
    const response = await api.post(`/assignments/assignments/${assignmentId}/quick-grade/${studentId}/`, { points });
    return response.data;
  },
};

export default assignmentService;

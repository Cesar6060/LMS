import api from './api';
import type { Quiz, Question, QuizAttempt } from '../types';

export const quizzesService = {
  // Get all quizzes in a course
  async getCourseQuizzes(courseCode: string): Promise<Quiz[]> {
    const response = await api.get<Quiz[]>(`/courses/${courseCode}/quizzes/`);
    return response.data;
  },

  // Get quizzes in a unit
  async getUnitQuizzes(unitId: number): Promise<Quiz[]> {
    const response = await api.get<Quiz[]>(`/units/${unitId}/quizzes/`);
    return response.data;
  },

  // Get quiz detail
  async getQuiz(quizId: number): Promise<Quiz> {
    const response = await api.get<Quiz>(`/quizzes/${quizId}/`);
    return response.data;
  },

  // Create a quiz
  async createQuiz(unitId: number, data: {
    title: string;
    description?: string;
    passing_score?: number;
    points?: number;
    max_attempts?: number;
  }): Promise<Quiz> {
    const response = await api.post<Quiz>(`/units/${unitId}/quizzes/`, data);
    return response.data;
  },

  // Update a quiz
  async updateQuiz(quizId: number, data: Partial<{
    title: string;
    description: string;
    passing_score: number;
    points: number;
    max_attempts: number;
    order: number;
  }>): Promise<Quiz> {
    const response = await api.put<Quiz>(`/quizzes/${quizId}/`, data);
    return response.data;
  },

  // Delete a quiz
  async deleteQuiz(quizId: number): Promise<void> {
    await api.delete(`/quizzes/${quizId}/`);
  },

  // Add a question to a quiz
  async addQuestion(quizId: number, data: {
    text: string;
    choices: { text: string; is_correct: boolean }[];
  }): Promise<Question> {
    const response = await api.post<Question>(`/quizzes/${quizId}/questions/`, data);
    return response.data;
  },

  // Update a question
  async updateQuestion(questionId: number, data: {
    text: string;
    choices: { text: string; is_correct: boolean }[];
  }): Promise<Question> {
    const response = await api.put<Question>(`/questions/${questionId}/`, data);
    return response.data;
  },

  // Delete a question
  async deleteQuestion(questionId: number): Promise<void> {
    await api.delete(`/questions/${questionId}/`);
  },

  // Submit quiz answers
  async submitQuiz(quizId: number, answers: Record<string, number>): Promise<QuizAttempt> {
    const response = await api.post<QuizAttempt>(`/quizzes/${quizId}/submit/`, { answers });
    return response.data;
  },

  // Get quiz attempts
  async getAttempts(quizId: number): Promise<QuizAttempt[]> {
    const response = await api.get<QuizAttempt[]>(`/quizzes/${quizId}/attempts/`);
    return response.data;
  },
};

export default quizzesService;

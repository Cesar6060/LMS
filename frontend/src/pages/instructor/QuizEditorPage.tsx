import { useState, useEffect, type FormEvent } from 'react';
import { useParams, useSearchParams } from 'react-router';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { courseService, type CourseDetail } from '@/services/courses';
import { quizzesService } from '@/services/quizzes';
import { isForbidden } from '@/services/api';
import { AccessDenied } from '@/components/AccessDenied';
import type { Quiz, Question } from '@/types';
import { PageContainer } from '@/components/layout/PageContainer';
import { BackLink } from '@/components/layout/BackLink';
import { CourseToolsNav } from '@/components/instructor/CourseToolsNav';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import {
  Loader2, Plus, Trash2, FileQuestion,
  Check, X, ChevronDown, ChevronRight, AlertCircle
} from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/Dialog';

type EditingQuiz = {
  id?: number;
  title: string;
  description: string;
  passing_score: number;
  points: number;
  max_attempts: number;
};

type EditingQuestion = {
  id?: number;
  text: string;
  choices: { text: string; is_correct: boolean }[];
};

export function QuizEditorPage() {
  const { code } = useParams<{ code: string }>();
  const [searchParams] = useSearchParams();

  const [course, setCourse] = useState<CourseDetail | null>(null);
  const [quizzes, setQuizzes] = useState<Quiz[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [forbidden, setForbidden] = useState(false);

  // Quiz modal
  const [showQuizModal, setShowQuizModal] = useState(false);
  const [editingQuiz, setEditingQuiz] = useState<EditingQuiz | null>(null);
  const [selectedUnitId, setSelectedUnitId] = useState<number | null>(null);
  const [quizLoading, setQuizLoading] = useState(false);

  // Question modal
  const [showQuestionModal, setShowQuestionModal] = useState(false);
  const [editingQuestion, setEditingQuestion] = useState<EditingQuestion | null>(null);
  const [selectedQuizId, setSelectedQuizId] = useState<number | null>(null);
  const [questionLoading, setQuestionLoading] = useState(false);

  // Expanded quiz for viewing questions
  const [expandedQuizId, setExpandedQuizId] = useState<number | null>(null);
  const [expandedQuizData, setExpandedQuizData] = useState<Quiz | null>(null);

  // Delete confirmations
  const [deleteQuizId, setDeleteQuizId] = useState<number | null>(null);
  const [deleteQuestionId, setDeleteQuestionId] = useState<number | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  // Inline validation error for the question modal
  const [questionError, setQuestionError] = useState('');

  useEffect(() => {
    if (code) {
      loadData();
    }
  }, [code]);

  // Deep link from the course outline: /instructor/courses/:code/quizzes?quiz={id}
  useEffect(() => {
    const quizParam = searchParams.get('quiz');
    if (quizParam && !isLoading && quizzes.some(q => q.id === Number(quizParam))) {
      setExpandedQuizId(Number(quizParam));
      loadQuizDetail(Number(quizParam));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams, isLoading, quizzes.length]);

  const loadData = async () => {
    try {
      setIsLoading(true);
      const [courseData, quizzesData] = await Promise.all([
        courseService.getCourse(code!),
        quizzesService.getCourseQuizzes(code!),
      ]);
      setCourse(courseData);
      setQuizzes(quizzesData);
    } catch (err) {
      if (isForbidden(err)) {
        setForbidden(true);
      } else {
        setError('Failed to load course data');
        console.error(err);
      }
    } finally {
      setIsLoading(false);
    }
  };

  const loadQuizDetail = async (quizId: number) => {
    try {
      const data = await quizzesService.getQuiz(quizId);
      setExpandedQuizData(data);
    } catch (err) {
      console.error('Failed to load quiz:', err);
    }
  };

  const toggleExpandQuiz = async (quizId: number) => {
    if (expandedQuizId === quizId) {
      setExpandedQuizId(null);
      setExpandedQuizData(null);
    } else {
      setExpandedQuizId(quizId);
      await loadQuizDetail(quizId);
    }
  };

  // Quiz handlers
  const openAddQuizModal = (unitId: number) => {
    setSelectedUnitId(unitId);
    setEditingQuiz({
      title: '',
      description: '',
      passing_score: 70,
      points: 10,
      max_attempts: 0, // 0 = unlimited
    });
    setShowQuizModal(true);
  };

  const openEditQuizModal = (quiz: Quiz) => {
    setEditingQuiz({
      id: quiz.id,
      title: quiz.title,
      description: quiz.description,
      passing_score: quiz.passing_score,
      points: quiz.points,
      max_attempts: quiz.max_attempts,
    });
    setShowQuizModal(true);
  };

  const handleSaveQuiz = async (e: FormEvent) => {
    e.preventDefault();
    if (!editingQuiz) return;

    setQuizLoading(true);
    try {
      if (editingQuiz.id) {
        await quizzesService.updateQuiz(editingQuiz.id, editingQuiz);
      } else if (selectedUnitId) {
        await quizzesService.createQuiz(selectedUnitId, editingQuiz);
      }
      await loadData();
      setShowQuizModal(false);
      setEditingQuiz(null);
    } catch (err) {
      console.error('Failed to save quiz:', err);
    } finally {
      setQuizLoading(false);
    }
  };

  const confirmDeleteQuiz = async () => {
    if (deleteQuizId === null) return;
    setIsDeleting(true);
    try {
      await quizzesService.deleteQuiz(deleteQuizId);
      await loadData();
      if (expandedQuizId === deleteQuizId) {
        setExpandedQuizId(null);
        setExpandedQuizData(null);
      }
    } catch (err) {
      console.error('Failed to delete quiz:', err);
    } finally {
      setIsDeleting(false);
      setDeleteQuizId(null);
    }
  };

  // Question handlers
  const openAddQuestionModal = (quizId: number) => {
    setSelectedQuizId(quizId);
    setQuestionError('');
    setEditingQuestion({
      text: '',
      choices: [
        { text: '', is_correct: true },
        { text: '', is_correct: false },
        { text: '', is_correct: false },
        { text: '', is_correct: false },
      ],
    });
    setShowQuestionModal(true);
  };

  const openEditQuestionModal = (question: Question, quizId: number) => {
    setSelectedQuizId(quizId);
    setQuestionError('');
    setEditingQuestion({
      id: question.id,
      text: question.text,
      choices: question.choices.map(c => ({
        text: c.text,
        is_correct: c.is_correct || false,
      })),
    });
    setShowQuestionModal(true);
  };

  const handleSaveQuestion = async (e: FormEvent) => {
    e.preventDefault();
    if (!editingQuestion || !selectedQuizId) return;

    // Validate at least one correct answer
    if (!editingQuestion.choices.some(c => c.is_correct)) {
      setQuestionError('Please mark at least one choice as correct');
      return;
    }

    // Filter out empty choices
    const validChoices = editingQuestion.choices.filter(c => c.text.trim());
    if (validChoices.length < 2) {
      setQuestionError('Please provide at least 2 choices');
      return;
    }

    setQuestionError('');
    setQuestionLoading(true);
    try {
      if (editingQuestion.id) {
        await quizzesService.updateQuestion(editingQuestion.id, {
          text: editingQuestion.text,
          choices: validChoices,
        });
      } else {
        await quizzesService.addQuestion(selectedQuizId, {
          text: editingQuestion.text,
          choices: validChoices,
        });
      }
      await loadQuizDetail(selectedQuizId);
      await loadData();
      setShowQuestionModal(false);
      setEditingQuestion(null);
    } catch (err) {
      console.error('Failed to save question:', err);
    } finally {
      setQuestionLoading(false);
    }
  };

  const confirmDeleteQuestion = async () => {
    if (deleteQuestionId === null) return;
    setIsDeleting(true);
    try {
      await quizzesService.deleteQuestion(deleteQuestionId);
      if (expandedQuizId) {
        await loadQuizDetail(expandedQuizId);
      }
      await loadData();
    } catch (err) {
      console.error('Failed to delete question:', err);
    } finally {
      setIsDeleting(false);
      setDeleteQuestionId(null);
    }
  };

  const handleChoiceChange = (index: number, field: 'text' | 'is_correct', value: string | boolean) => {
    if (!editingQuestion) return;

    const newChoices = [...editingQuestion.choices];
    if (field === 'is_correct') {
      // Only one correct answer allowed
      newChoices.forEach((c, i) => {
        c.is_correct = i === index;
      });
    } else {
      newChoices[index] = { ...newChoices[index], text: value as string };
    }
    setEditingQuestion({ ...editingQuestion, choices: newChoices });
  };

  const addChoice = () => {
    if (!editingQuestion || editingQuestion.choices.length >= 6) return;
    setEditingQuestion({
      ...editingQuestion,
      choices: [...editingQuestion.choices, { text: '', is_correct: false }],
    });
  };

  const removeChoice = (index: number) => {
    if (!editingQuestion || editingQuestion.choices.length <= 2) return;
    const newChoices = editingQuestion.choices.filter((_, i) => i !== index);
    // Ensure at least one is correct
    if (!newChoices.some(c => c.is_correct)) {
      newChoices[0].is_correct = true;
    }
    setEditingQuestion({ ...editingQuestion, choices: newChoices });
  };

  if (isLoading) {
    return (
      <PageContainer maxWidth="max-w-6xl">
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      </PageContainer>
    );
  }

  if (forbidden) {
    return <AccessDenied />;
  }

  if (error || !course) {
    return (
      <PageContainer maxWidth="max-w-6xl">
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-destructive mb-4">{error || 'Course not found'}</p>
            <BackLink to={`/instructor/courses/${code}/manage`} label="Manage Course" />
          </CardContent>
        </Card>
      </PageContainer>
    );
  }

  // Group quizzes by unit
  const quizzesByUnit: Record<number, Quiz[]> = {};
  course.units.forEach(unit => {
    quizzesByUnit[unit.id] = quizzes.filter(q => q.unit_title === unit.title);
  });

  return (
    <PageContainer maxWidth="max-w-6xl">
      {/* Course tools sub-nav */}
      <CourseToolsNav courseCode={code!} className="mb-6" />

      {/* Header */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold flex items-center gap-3">
          <FileQuestion className="h-6 w-6" />
          Manage Quizzes
        </h1>
        <p className="text-muted-foreground mt-1">{course.title}</p>
      </div>

      {/* Units with Quizzes */}
      <div className="space-y-6">
        {course.units.map((unit) => (
          <Card key={unit.id}>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-lg">{unit.title}</CardTitle>
                <Button size="sm" variant="outline" onClick={() => openAddQuizModal(unit.id)}>
                  <Plus className="h-4 w-4 mr-1" />
                  Add Quiz
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {quizzesByUnit[unit.id]?.length > 0 ? (
                <div className="space-y-3">
                  {quizzesByUnit[unit.id].map((quiz) => (
                    <div key={quiz.id} className="border rounded-lg">
                      <div className="p-4 flex items-center justify-between gap-2 hover:bg-muted/50">
                        <button
                          type="button"
                          onClick={() => toggleExpandQuiz(quiz.id)}
                          aria-expanded={expandedQuizId === quiz.id}
                          className="flex flex-1 items-center gap-3 text-left min-w-0"
                        >
                          {expandedQuizId === quiz.id ? (
                            <ChevronDown className="h-4 w-4 flex-shrink-0 text-muted-foreground" />
                          ) : (
                            <ChevronRight className="h-4 w-4 flex-shrink-0 text-muted-foreground" />
                          )}
                          <span className="min-w-0">
                            <h4 className="font-medium">{quiz.title}</h4>
                            <p className="text-sm text-muted-foreground">
                              {quiz.question_count} questions • {quiz.points} pts • Pass: {quiz.passing_score}% • {quiz.max_attempts === 0 ? 'Unlimited attempts' : `${quiz.max_attempts} attempt${quiz.max_attempts === 1 ? '' : 's'}`}
                            </p>
                          </span>
                        </button>
                        <div className="flex items-center gap-2">
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => openEditQuizModal(quiz)}
                          >
                            Edit Details
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            className="text-destructive hover:text-destructive"
                            onClick={() => setDeleteQuizId(quiz.id)}
                            aria-label={`Delete quiz ${quiz.title}`}
                            title="Delete quiz"
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>

                      {/* Expanded quiz questions */}
                      {expandedQuizId === quiz.id && expandedQuizData && (
                        <div className="border-t p-4 bg-muted/30">
                          <div className="flex items-center justify-between mb-3">
                            <h5 className="font-medium text-sm">Questions</h5>
                            <Button size="sm" onClick={() => openAddQuestionModal(quiz.id)}>
                              <Plus className="h-4 w-4 mr-1" />
                              Add Question
                            </Button>
                          </div>

                          {expandedQuizData.questions && expandedQuizData.questions.length > 0 ? (
                            <div className="space-y-3">
                              {expandedQuizData.questions.map((question, qIndex) => (
                                <div key={question.id} className="bg-background p-3 rounded border">
                                  <div className="flex items-start justify-between">
                                    <div className="flex-1">
                                      <p className="font-medium text-sm mb-2">
                                        Q{qIndex + 1}: {question.text}
                                      </p>
                                      <div className="space-y-1">
                                        {question.choices.map((choice) => (
                                          <div
                                            key={choice.id}
                                            className={`text-sm flex items-center gap-2 ${
                                              choice.is_correct ? 'text-green-600 font-medium' : 'text-muted-foreground'
                                            }`}
                                          >
                                            {choice.is_correct ? (
                                              <Check className="h-3 w-3" />
                                            ) : (
                                              <X className="h-3 w-3" />
                                            )}
                                            {choice.text}
                                          </div>
                                        ))}
                                      </div>
                                    </div>
                                    <div className="flex items-center gap-1">
                                      <Button
                                        size="sm"
                                        variant="ghost"
                                        onClick={() => openEditQuestionModal(question, quiz.id)}
                                      >
                                        Edit
                                      </Button>
                                      <Button
                                        size="sm"
                                        variant="ghost"
                                        className="text-destructive hover:text-destructive"
                                        onClick={() => setDeleteQuestionId(question.id)}
                                        aria-label={`Delete question ${qIndex + 1}`}
                                        title="Delete question"
                                      >
                                        <Trash2 className="h-3 w-3" />
                                      </Button>
                                    </div>
                                  </div>
                                </div>
                              ))}
                            </div>
                          ) : (
                            <p className="text-sm text-muted-foreground text-center py-4">
                              No questions yet. Add your first question to this quiz.
                            </p>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground text-center py-4">
                  No quizzes in this unit yet.
                </p>
              )}
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Quiz Modal */}
      <Dialog open={showQuizModal} onOpenChange={setShowQuizModal}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editingQuiz?.id ? 'Edit Quiz' : 'Add Quiz'}</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSaveQuiz}>
            <div className="space-y-4 py-4">
              <div>
                <label className="block text-sm font-medium mb-1">Title *</label>
                <Input
                  value={editingQuiz?.title || ''}
                  onChange={(e) => setEditingQuiz(prev => prev ? { ...prev, title: e.target.value } : null)}
                  placeholder="Quiz title"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Description</label>
                <textarea
                  value={editingQuiz?.description || ''}
                  onChange={(e) => setEditingQuiz(prev => prev ? { ...prev, description: e.target.value } : null)}
                  placeholder="Optional description"
                  className="w-full px-3 py-2 border rounded-lg bg-background min-h-[80px]"
                />
              </div>
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-1">Passing Score (%)</label>
                  <Input
                    type="number"
                    min="0"
                    max="100"
                    value={editingQuiz?.passing_score || 70}
                    onChange={(e) => setEditingQuiz(prev => prev ? { ...prev, passing_score: parseInt(e.target.value) || 70 } : null)}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Points</label>
                  <Input
                    type="number"
                    min="1"
                    value={editingQuiz?.points || 10}
                    onChange={(e) => setEditingQuiz(prev => prev ? { ...prev, points: parseInt(e.target.value) || 10 } : null)}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Max Attempts</label>
                  <Input
                    type="number"
                    min="0"
                    value={editingQuiz?.max_attempts ?? 0}
                    onChange={(e) => setEditingQuiz(prev => prev ? { ...prev, max_attempts: parseInt(e.target.value) || 0 } : null)}
                  />
                  <p className="text-xs text-muted-foreground mt-1">0 = unlimited</p>
                </div>
              </div>
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setShowQuizModal(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={quizLoading}>
                {quizLoading && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                {editingQuiz?.id ? 'Save Changes' : 'Create Quiz'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Question Modal */}
      <Dialog open={showQuestionModal} onOpenChange={setShowQuestionModal}>
        <DialogContent className="max-w-xl">
          <DialogHeader>
            <DialogTitle>{editingQuestion?.id ? 'Edit Question' : 'Add Question'}</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSaveQuestion}>
            <div className="space-y-4 py-4">
              {questionError && (
                <div className="bg-destructive/10 border border-destructive/20 rounded-lg p-3 flex items-center gap-2">
                  <AlertCircle className="h-4 w-4 text-destructive flex-shrink-0" />
                  <p className="text-sm text-destructive">{questionError}</p>
                </div>
              )}
              <div>
                <label className="block text-sm font-medium mb-1">Question *</label>
                <textarea
                  value={editingQuestion?.text || ''}
                  onChange={(e) => setEditingQuestion(prev => prev ? { ...prev, text: e.target.value } : null)}
                  placeholder="Enter your question"
                  className="w-full px-3 py-2 border rounded-lg bg-background min-h-[80px]"
                  required
                />
              </div>

              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="block text-sm font-medium">Choices (select correct answer)</label>
                  {editingQuestion && editingQuestion.choices.length < 6 && (
                    <Button type="button" size="sm" variant="ghost" onClick={addChoice}>
                      <Plus className="h-4 w-4 mr-1" />
                      Add Choice
                    </Button>
                  )}
                </div>
                <div className="space-y-2">
                  {editingQuestion?.choices.map((choice, index) => (
                    <div key={index} className="flex items-center gap-2">
                      <input
                        type="radio"
                        name="correct_choice"
                        checked={choice.is_correct}
                        onChange={() => handleChoiceChange(index, 'is_correct', true)}
                        className="h-4 w-4"
                      />
                      <Input
                        value={choice.text}
                        onChange={(e) => handleChoiceChange(index, 'text', e.target.value)}
                        placeholder={`Choice ${index + 1}`}
                        className="flex-1"
                      />
                      {editingQuestion.choices.length > 2 && (
                        <Button
                          type="button"
                          size="sm"
                          variant="ghost"
                          onClick={() => removeChoice(index)}
                          className="text-destructive hover:text-destructive"
                          aria-label={`Remove choice ${index + 1}`}
                          title="Remove choice"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      )}
                    </div>
                  ))}
                </div>
                <p className="text-xs text-muted-foreground mt-2">
                  Select the radio button next to the correct answer
                </p>
              </div>
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setShowQuestionModal(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={questionLoading}>
                {questionLoading && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                {editingQuestion?.id ? 'Save Changes' : 'Add Question'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Delete quiz confirmation */}
      <ConfirmDialog
        open={deleteQuizId !== null}
        onOpenChange={(open) => {
          if (!open) setDeleteQuizId(null);
        }}
        title="Delete Quiz"
        confirmLabel="Delete Quiz"
        loadingLabel="Deleting..."
        onConfirm={confirmDeleteQuiz}
        isLoading={isDeleting}
      >
        Are you sure you want to delete this quiz? All questions and attempts
        will be deleted.
      </ConfirmDialog>

      {/* Delete question confirmation */}
      <ConfirmDialog
        open={deleteQuestionId !== null}
        onOpenChange={(open) => {
          if (!open) setDeleteQuestionId(null);
        }}
        title="Delete Question"
        confirmLabel="Delete Question"
        loadingLabel="Deleting..."
        onConfirm={confirmDeleteQuestion}
        isLoading={isDeleting}
      >
        Are you sure you want to delete this question?
      </ConfirmDialog>
    </PageContainer>
  );
}

import { useState, useEffect, type FormEvent } from 'react';
import { useParams, Link } from 'react-router';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { courseService, type CourseDetail } from '@/services/courses';
import { quizzesService } from '@/services/quizzes';
import type { Quiz, Question } from '@/types';
import {
  Loader2, ChevronLeft, Plus, Trash2, FileQuestion,
  Check, X
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

  const [course, setCourse] = useState<CourseDetail | null>(null);
  const [quizzes, setQuizzes] = useState<Quiz[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

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

  useEffect(() => {
    if (code) {
      loadData();
    }
  }, [code]);

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
      console.error('Failed to load data:', err);
      setError('Failed to load course data');
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

  const handleDeleteQuiz = async (quizId: number) => {
    if (!confirm('Are you sure you want to delete this quiz? All questions and attempts will be deleted.')) {
      return;
    }

    try {
      await quizzesService.deleteQuiz(quizId);
      await loadData();
      if (expandedQuizId === quizId) {
        setExpandedQuizId(null);
        setExpandedQuizData(null);
      }
    } catch (err) {
      console.error('Failed to delete quiz:', err);
    }
  };

  // Question handlers
  const openAddQuestionModal = (quizId: number) => {
    setSelectedQuizId(quizId);
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
      alert('Please mark at least one choice as correct');
      return;
    }

    // Filter out empty choices
    const validChoices = editingQuestion.choices.filter(c => c.text.trim());
    if (validChoices.length < 2) {
      alert('Please provide at least 2 choices');
      return;
    }

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

  const handleDeleteQuestion = async (questionId: number) => {
    if (!confirm('Are you sure you want to delete this question?')) {
      return;
    }

    try {
      await quizzesService.deleteQuestion(questionId);
      if (expandedQuizId) {
        await loadQuizDetail(expandedQuizId);
      }
      await loadData();
    } catch (err) {
      console.error('Failed to delete question:', err);
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
      <div className="container mx-auto px-4 py-8 max-w-4xl">
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      </div>
    );
  }

  if (error || !course) {
    return (
      <div className="container mx-auto px-4 py-8 max-w-4xl">
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-destructive">{error || 'Course not found'}</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Group quizzes by unit
  const quizzesByUnit: Record<number, Quiz[]> = {};
  course.units.forEach(unit => {
    quizzesByUnit[unit.id] = quizzes.filter(q => q.unit_title === unit.title);
  });

  return (
    <div className="container mx-auto px-4 py-8 max-w-4xl">
      {/* Header */}
      <div className="mb-6">
        <Link
          to={`/instructor/courses/${code}/manage`}
          className="inline-flex items-center gap-2 text-muted-foreground hover:text-foreground mb-4"
        >
          <ChevronLeft className="h-4 w-4" />
          Back to Manage Course
        </Link>
        <h1 className="text-2xl font-bold flex items-center gap-3">
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
                      <div
                        className="p-4 flex items-center justify-between cursor-pointer hover:bg-muted/50"
                        onClick={() => toggleExpandQuiz(quiz.id)}
                      >
                        <div>
                          <h4 className="font-medium">{quiz.title}</h4>
                          <p className="text-sm text-muted-foreground">
                            {quiz.question_count} questions • {quiz.points} pts • Pass: {quiz.passing_score}% • {quiz.max_attempts === 0 ? 'Unlimited attempts' : `${quiz.max_attempts} attempt${quiz.max_attempts === 1 ? '' : 's'}`}
                          </p>
                        </div>
                        <div className="flex items-center gap-2">
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={(e) => {
                              e.stopPropagation();
                              openEditQuizModal(quiz);
                            }}
                          >
                            Edit
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            className="text-destructive hover:text-destructive"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleDeleteQuiz(quiz.id);
                            }}
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
                                        onClick={() => handleDeleteQuestion(question.id)}
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
    </div>
  );
}

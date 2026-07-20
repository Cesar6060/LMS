import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Card, CardContent } from '@/components/ui/Card';
import { courseService } from '@/services/courses';
import type { LessonQuestion } from '@/types';
import { Plus, Trash2, Edit2, Loader2, CheckCircle, HelpCircle } from 'lucide-react';
import { cn } from '@/lib/utils';

interface LessonQuestionsManagerProps {
  lessonId: number;
  lessonTitle: string;
}

interface EditingQuestion {
  id?: number;
  text: string;
  choices: Array<{
    id?: number;
    text: string;
    is_correct: boolean;
    order: number;
  }>;
}

const emptyQuestion: EditingQuestion = {
  text: '',
  choices: [
    { text: '', is_correct: true, order: 0 },
    { text: '', is_correct: false, order: 1 },
  ],
};

export function LessonQuestionsManager({ lessonId, lessonTitle }: LessonQuestionsManagerProps) {
  const [questions, setQuestions] = useState<LessonQuestion[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState('');

  // Editing state
  const [showQuestionEditor, setShowQuestionEditor] = useState(false);
  const [editingQuestion, setEditingQuestion] = useState<EditingQuestion | null>(null);

  useEffect(() => {
    loadData();
  }, [lessonId]);

  const loadData = async () => {
    setIsLoading(true);
    setError('');
    try {
      const questionsData = await courseService.getLessonQuestions(lessonId);
      setQuestions(questionsData);
    } catch (err) {
      console.error('Failed to load data:', err);
      setError('Failed to load questions');
    } finally {
      setIsLoading(false);
    }
  };

  const loadQuestions = async () => {
    try {
      const data = await courseService.getLessonQuestions(lessonId);
      setQuestions(data);
    } catch (err) {
      console.error('Failed to load questions:', err);
    }
  };

  const handleAddQuestion = () => {
    setEditingQuestion({ ...emptyQuestion });
    setShowQuestionEditor(true);
  };

  const handleEditQuestion = (question: LessonQuestion) => {
    setEditingQuestion({
      id: question.id,
      text: question.text,
      choices: question.choices.map(c => ({
        id: c.id,
        text: c.text,
        is_correct: c.is_correct || false,
        order: c.order,
      })),
    });
    setShowQuestionEditor(true);
  };

  const handleDeleteQuestion = async (questionId: number) => {
    if (!confirm('Are you sure you want to delete this question?')) return;

    try {
      await courseService.deleteLessonQuestion(lessonId, questionId);
      await loadQuestions();
    } catch (err) {
      console.error('Failed to delete question:', err);
      setError('Failed to delete question');
    }
  };

  const handleSaveQuestion = async () => {
    if (!editingQuestion) return;

    // Validation
    if (!editingQuestion.text.trim()) {
      setError('Question text is required');
      return;
    }

    const validChoices = editingQuestion.choices.filter(c => c.text.trim());
    if (validChoices.length < 2) {
      setError('At least 2 choices are required');
      return;
    }

    if (!validChoices.some(c => c.is_correct)) {
      setError('At least one choice must be marked as correct');
      return;
    }

    setIsSaving(true);
    setError('');

    try {
      const data = {
        text: editingQuestion.text.trim(),
        choices: validChoices.map((c, i) => ({
          text: c.text.trim(),
          is_correct: c.is_correct,
          order: i,
        })),
      };

      if (editingQuestion.id) {
        await courseService.updateLessonQuestion(lessonId, editingQuestion.id, data);
      } else {
        await courseService.createLessonQuestion(lessonId, data);
      }

      await loadQuestions();
      setShowQuestionEditor(false);
      setEditingQuestion(null);
    } catch (err) {
      console.error('Failed to save question:', err);
      setError('Failed to save question');
    } finally {
      setIsSaving(false);
    }
  };

  const handleAddChoice = () => {
    if (!editingQuestion || editingQuestion.choices.length >= 6) return;

    setEditingQuestion({
      ...editingQuestion,
      choices: [
        ...editingQuestion.choices,
        { text: '', is_correct: false, order: editingQuestion.choices.length },
      ],
    });
  };

  const handleRemoveChoice = (index: number) => {
    if (!editingQuestion || editingQuestion.choices.length <= 2) return;

    setEditingQuestion({
      ...editingQuestion,
      choices: editingQuestion.choices.filter((_, i) => i !== index),
    });
  };

  const handleChoiceChange = (index: number, field: 'text' | 'is_correct', value: string | boolean) => {
    if (!editingQuestion) return;

    const newChoices = [...editingQuestion.choices];
    if (field === 'is_correct' && value === true) {
      // Only one correct answer allowed
      newChoices.forEach((c, i) => {
        c.is_correct = i === index;
      });
    } else {
      newChoices[index] = { ...newChoices[index], [field]: value };
    }

    setEditingQuestion({ ...editingQuestion, choices: newChoices });
  };

  return (
    <div className="space-y-4">
        <p className="text-sm text-muted-foreground">
          Manage questions for "{lessonTitle}". Students must answer all questions correctly to complete the lesson.
        </p>

        {error && (
          <div className="bg-destructive/10 border border-destructive/20 text-destructive rounded-md px-4 py-3 text-sm">
            {error}
          </div>
        )}

        <div className="space-y-4">
          {isLoading ? (
            <div className="flex justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : showQuestionEditor && editingQuestion ? (
            // Question Editor
            <div className="space-y-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">Question</label>
                <Input
                  value={editingQuestion.text}
                  onChange={(e) => setEditingQuestion({ ...editingQuestion, text: e.target.value })}
                  placeholder="Enter your question..."
                />
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium">Answer Choices</label>
                <p className="text-xs text-muted-foreground mb-2">
                  Click the circle to mark the correct answer.
                </p>
                <div className="space-y-2">
                  {editingQuestion.choices.map((choice, index) => (
                    <div key={index} className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => handleChoiceChange(index, 'is_correct', true)}
                        className={cn(
                          "flex-shrink-0 w-6 h-6 rounded-full border-2 flex items-center justify-center transition-colors",
                          choice.is_correct
                            ? "border-green-500 bg-green-500 text-white"
                            : "border-muted-foreground hover:border-green-500"
                        )}
                      >
                        {choice.is_correct && <CheckCircle className="h-4 w-4" />}
                      </button>
                      <Input
                        value={choice.text}
                        onChange={(e) => handleChoiceChange(index, 'text', e.target.value)}
                        placeholder={`Choice ${index + 1}`}
                        className="flex-1"
                      />
                      {editingQuestion.choices.length > 2 && (
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => handleRemoveChoice(index)}
                        >
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      )}
                    </div>
                  ))}
                </div>
                {editingQuestion.choices.length < 6 && (
                  <Button type="button" variant="outline" size="sm" onClick={handleAddChoice}>
                    <Plus className="h-4 w-4 mr-1" />
                    Add Choice
                  </Button>
                )}
              </div>

              <div className="flex justify-end gap-2 pt-4 border-t">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => {
                    setShowQuestionEditor(false);
                    setEditingQuestion(null);
                    setError('');
                  }}
                  disabled={isSaving}
                >
                  Cancel
                </Button>
                <Button onClick={handleSaveQuestion} disabled={isSaving}>
                  {isSaving && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                  {editingQuestion.id ? 'Save Changes' : 'Add Question'}
                </Button>
              </div>
            </div>
          ) : (
            // Questions List
            <>
              {questions.length === 0 ? (
                <Card>
                  <CardContent className="py-8 text-center text-muted-foreground">
                    <HelpCircle className="h-8 w-8 mx-auto mb-3 opacity-50" />
                    <p>No comprehension questions yet.</p>
                    <p className="text-sm mt-1">Add questions to require students to demonstrate understanding.</p>
                  </CardContent>
                </Card>
              ) : (
                <div className="space-y-3">
                  {questions.map((question, index) => (
                    <Card key={question.id}>
                      <CardContent className="py-4">
                        <div className="flex items-start gap-3">
                          <div className="flex-shrink-0 w-6 h-6 rounded-full bg-primary/10 text-primary flex items-center justify-center text-sm font-medium">
                            {index + 1}
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className="font-medium mb-2">{question.text}</p>
                            <div className="space-y-1">
                              {question.choices.map((choice) => (
                                <div
                                  key={choice.id}
                                  className={cn(
                                    "text-sm px-2 py-1 rounded flex items-center gap-2",
                                    choice.is_correct && "bg-green-50 text-green-800 dark:bg-green-900/20 dark:text-green-400"
                                  )}
                                >
                                  {choice.is_correct && <CheckCircle className="h-3 w-3" />}
                                  {choice.text}
                                </div>
                              ))}
                            </div>
                          </div>
                          <div className="flex items-center gap-1">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleEditQuestion(question)}
                            >
                              <Edit2 className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleDeleteQuestion(question.id)}
                            >
                              <Trash2 className="h-4 w-4 text-destructive" />
                            </Button>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              )}

              <Button onClick={handleAddQuestion} className="w-full">
                <Plus className="h-4 w-4 mr-2" />
                Add Question
              </Button>
            </>
          )}
        </div>
    </div>
  );
}

import { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router';
import { useAuth } from '@/contexts/useAuth';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Card, CardContent } from '@/components/ui/Card';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/Tabs';
import { AccessDenied } from '@/components/AccessDenied';
import { SectionEditor, type SaveStatus } from '@/components/lesson/SectionEditor';
import { AttachmentUploader } from '@/components/lesson/AttachmentUploader';
import { LessonQuestionsManager } from '@/components/lesson/LessonQuestionsManager';
import { courseService } from '@/services/courses';
import { quizzesService } from '@/services/quizzes';
import { isForbidden } from '@/services/api';
import type { Lesson, Quiz } from '@/types';
import { PageContainer } from '@/components/layout/PageContainer';
import { BackLink } from '@/components/layout/BackLink';
import {
  Loader2, ChevronLeft, FileText, Layers, HelpCircle, Paperclip, BookOpen,
  Check, AlertCircle,
} from 'lucide-react';

// Phase 53: lesson body lives in sections. The editor page only owns lesson
// "details" (title, quiz gating). Everything auto-saves.
interface LessonDetailsForm {
  title: string;
  required_quiz: number | null;
}

function detailsFromLesson(lesson: Lesson): LessonDetailsForm {
  return {
    title: lesson.title,
    required_quiz: lesson.required_quiz ?? null,
  };
}

export function LessonEditorPage() {
  const { code, lessonId } = useParams<{ code: string; lessonId: string }>();
  const { user } = useAuth();
  const navigate = useNavigate();

  const [lesson, setLesson] = useState<Lesson | null>(null);
  const [quizzes, setQuizzes] = useState<Quiz[]>([]);
  const [form, setForm] = useState<LessonDetailsForm | null>(null);
  const [savedForm, setSavedForm] = useState<LessonDetailsForm | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [forbidden, setForbidden] = useState(false);
  const [notFound, setNotFound] = useState(false);

  // Unified save status across Details auto-save and the section editor.
  const [saveStatus, setSaveStatus] = useState<SaveStatus>('idle');
  const [saveMessage, setSaveMessage] = useState('');

  const detailsDirty =
    form !== null && savedForm !== null && JSON.stringify(form) !== JSON.stringify(savedForm);

  useEffect(() => {
    const load = async () => {
      if (!code || !lessonId) return;
      try {
        setIsLoading(true);
        const [courseData, lessonData, quizzesData] = await Promise.all([
          courseService.getCourse(code),
          courseService.getLesson(Number(lessonId)),
          quizzesService.getCourseQuizzes(code),
        ]);

        if (user && courseData.instructor.id !== user.id) {
          setForbidden(true);
          return;
        }
        // Guard against a lesson URL that doesn't belong to this course
        if (!courseData.units.some(u => u.id === lessonData.unit)) {
          setNotFound(true);
          return;
        }

        setLesson(lessonData);
        setQuizzes(quizzesData);
        const initial = detailsFromLesson(lessonData);
        setForm(initial);
        setSavedForm(initial);
      } catch (err) {
        if (isForbidden(err)) {
          setForbidden(true);
        } else {
          console.error('Failed to load lesson:', err);
          setNotFound(true);
        }
      } finally {
        setIsLoading(false);
      }
    };
    load();
  }, [code, lessonId, user]);

  const updateForm = (patch: Partial<LessonDetailsForm>) => {
    setForm(prev => (prev ? { ...prev, ...patch } : prev));
  };

  // Auto-save lesson details (title / quiz) with a debounce.
  const saveDetails = useCallback(async () => {
    if (!form || !lesson) return;
    const snapshot = form;
    setSaveStatus('saving');
    setSaveMessage('');
    try {
      const updated = await courseService.updateLesson(lesson.id, {
        title: snapshot.title,
        required_quiz: snapshot.required_quiz,
      });
      setLesson(updated);
      setSavedForm(snapshot);
      setSaveStatus('saved');
    } catch (err: unknown) {
      console.error('Failed to save lesson details:', err);
      const apiError = err as {
        response?: { data?: { detail?: string; title?: string[] } };
        message?: string;
      };
      const message =
        apiError.response?.data?.detail ||
        apiError.response?.data?.title?.[0] ||
        apiError.message ||
        'Failed to save lesson details';
      setSaveMessage(message);
      setSaveStatus('error');
    }
  }, [form, lesson]);

  const saveTimer = useRef<number | null>(null);
  useEffect(() => {
    if (!detailsDirty) return;
    if (saveTimer.current) window.clearTimeout(saveTimer.current);
    saveTimer.current = window.setTimeout(() => { void saveDetails(); }, 800);
    return () => {
      if (saveTimer.current) window.clearTimeout(saveTimer.current);
    };
  }, [detailsDirty, saveDetails]);

  // Section editor reports its own save activity into the shared indicator.
  const handleSectionStatus = useCallback((status: SaveStatus, message?: string) => {
    setSaveStatus(status);
    setSaveMessage(status === 'error' ? (message || "Couldn't save") : '');
  }, []);

  const hasPendingWork = detailsDirty || saveStatus === 'saving' || saveStatus === 'error';

  // Warn on reload/close while a save is pending or failed.
  useEffect(() => {
    if (!hasPendingWork) return;
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = '';
    };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [hasPendingWork]);

  const handleBack = () => {
    if (!hasPendingWork || confirm('Some changes may not be saved yet. Leave anyway?')) {
      navigate(`/instructor/courses/${code}/manage`);
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (forbidden) {
    return <AccessDenied />;
  }

  if (notFound || !lesson || !form) {
    return (
      <PageContainer maxWidth="max-w-6xl">
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <BookOpen className="h-12 w-12 text-muted-foreground mb-4" />
            <h3 className="text-lg font-semibold mb-2">Lesson not found</h3>
            <BackLink to={`/instructor/courses/${code}/manage`} label="Manage Course" />
          </CardContent>
        </Card>
      </PageContainer>
    );
  }

  return (
    <PageContainer maxWidth="max-w-6xl">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
        <div className="flex items-center gap-2 min-w-0">
          <Button variant="ghost" size="sm" onClick={handleBack}>
            <ChevronLeft className="h-4 w-4 mr-1" />
            Back to Manage Course
          </Button>
          <span className="text-muted-foreground">/</span>
          <h1 className="text-2xl font-bold truncate">{lesson.title}</h1>
        </div>
        {/* Auto-save status */}
        <div className="min-w-[11rem] flex justify-end">
          {saveStatus === 'saving' && (
            <span className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Saving…
            </span>
          )}
          {saveStatus === 'saved' && (
            <span className="flex items-center gap-2 text-sm text-green-600 dark:text-green-500">
              <Check className="h-4 w-4" />
              All changes saved
            </span>
          )}
          {saveStatus === 'error' && (
            <span className="flex items-center gap-2 text-sm text-destructive">
              <AlertCircle className="h-4 w-4" />
              {saveMessage || "Couldn't save"}
            </span>
          )}
          {saveStatus === 'idle' && (
            <span className="text-sm text-muted-foreground">Changes save automatically</span>
          )}
        </div>
      </div>

      <Tabs defaultValue="content">
        <TabsList>
          <TabsTrigger value="content">
            <Layers className="h-4 w-4" />
            Content
          </TabsTrigger>
          <TabsTrigger value="details">
            <FileText className="h-4 w-4" />
            Details
          </TabsTrigger>
          <TabsTrigger value="questions">
            <HelpCircle className="h-4 w-4" />
            Questions
          </TabsTrigger>
          <TabsTrigger value="attachments">
            <Paperclip className="h-4 w-4" />
            Attachments
          </TabsTrigger>
        </TabsList>

        <TabsContent value="content">
          <SectionEditor
            lessonId={lesson.id}
            lessonTitle={lesson.title}
            onSaveStatus={handleSectionStatus}
          />
        </TabsContent>

        <TabsContent value="details" className="space-y-6">
          {/* Title */}
          <div className="space-y-2 max-w-2xl">
            <label htmlFor="lesson-title" className="text-sm font-medium">
              Lesson Title
            </label>
            <Input
              id="lesson-title"
              type="text"
              value={form.title}
              onChange={(e) => updateForm({ title: e.target.value })}
              required
            />
          </div>

          {/* Quiz gating */}
          <div className="grid gap-4 max-w-2xl">
            <div className="space-y-2">
              <label htmlFor="required-quiz" className="text-sm font-medium">
                Required Quiz
              </label>
              <select
                id="required-quiz"
                value={form.required_quiz ?? ''}
                onChange={(e) =>
                  updateForm({ required_quiz: e.target.value ? Number(e.target.value) : null })
                }
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              >
                <option value="">None</option>
                {quizzes.map(quiz => (
                  <option key={quiz.id} value={quiz.id}>
                    {quiz.title} ({quiz.unit_title})
                  </option>
                ))}
              </select>
              <p className="text-xs text-muted-foreground">
                Students must pass this quiz to complete the lesson.
              </p>
            </div>
          </div>
        </TabsContent>

        <TabsContent value="questions">
          <LessonQuestionsManager lessonId={lesson.id} lessonTitle={lesson.title} />
        </TabsContent>

        <TabsContent value="attachments">
          <AttachmentUploader lessonId={lesson.id} lessonTitle={lesson.title} />
        </TabsContent>
      </Tabs>
    </PageContainer>
  );
}

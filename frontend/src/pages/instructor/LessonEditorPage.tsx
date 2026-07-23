import { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router';
import { useAuth } from '@/contexts/useAuth';
import { Button } from '@/components/ui/Button';
import { Card, CardContent } from '@/components/ui/Card';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/Tabs';
import { AccessDenied } from '@/components/AccessDenied';
import { SectionEditor, type SaveStatus } from '@/components/lesson/SectionEditor';
import { AttachmentUploader } from '@/components/lesson/AttachmentUploader';
import { LessonQuestionsManager } from '@/components/lesson/LessonQuestionsManager';
import { courseService } from '@/services/courses';
import { isForbidden } from '@/services/api';
import type { Lesson } from '@/types';
import { PageContainer } from '@/components/layout/PageContainer';
import { BackLink } from '@/components/layout/BackLink';
import {
  Loader2, ChevronLeft, Layers, HelpCircle, Paperclip, BookOpen,
  Check, AlertCircle,
} from 'lucide-react';

// Phase 54: the Details tab is gone. The lesson body lives in sections
// ("Content"); the only remaining lesson-level field is the title, edited inline
// in the header. Quiz gating now lives in the Questions tab. Everything auto-saves.
interface LessonDetailsForm {
  title: string;
}

function detailsFromLesson(lesson: Lesson): LessonDetailsForm {
  return {
    title: lesson.title,
  };
}

export function LessonEditorPage() {
  const { code, lessonId } = useParams<{ code: string; lessonId: string }>();
  const { user } = useAuth();
  const navigate = useNavigate();

  const [lesson, setLesson] = useState<Lesson | null>(null);
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
        const [courseData, lessonData] = await Promise.all([
          courseService.getCourse(code),
          courseService.getLesson(Number(lessonId)),
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

  // Phase 54: the "require this lesson's quiz" toggle (Questions tab) saves
  // immediately and reports into the same status indicator.
  const handleRequiresQuizChange = useCallback(async (value: boolean) => {
    if (!lesson) return;
    setSaveStatus('saving');
    setSaveMessage('');
    setLesson(prev => (prev ? { ...prev, requires_quiz: value } : prev)); // optimistic
    try {
      const updated = await courseService.updateLesson(lesson.id, { requires_quiz: value });
      setLesson(updated);
      setSaveStatus('saved');
    } catch (err) {
      console.error('Failed to update quiz requirement:', err);
      setLesson(prev => (prev ? { ...prev, requires_quiz: !value } : prev)); // revert
      setSaveStatus('error');
      setSaveMessage("Couldn't save quiz requirement");
    }
  }, [lesson]);

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
        <div className="flex items-center gap-2 min-w-0 flex-1">
          <Button variant="ghost" size="sm" onClick={handleBack}>
            <ChevronLeft className="h-4 w-4 mr-1" />
            Back to Manage Course
          </Button>
          <span className="text-muted-foreground">/</span>
          {/* Phase 54: lesson title is edited inline here (the Details tab is gone). */}
          <input
            aria-label="Lesson title"
            value={form.title}
            onChange={(e) => updateForm({ title: e.target.value })}
            placeholder="Untitled lesson"
            className="min-w-0 flex-1 bg-transparent text-2xl font-bold truncate rounded-md px-2 py-1 -mx-1 border border-transparent hover:border-input focus:border-input focus:bg-background focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
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

        <TabsContent value="questions">
          <LessonQuestionsManager
            lessonId={lesson.id}
            lessonTitle={lesson.title}
            requiresQuiz={!!lesson.requires_quiz}
            onRequiresQuizChange={handleRequiresQuizChange}
          />
        </TabsContent>

        <TabsContent value="attachments">
          <AttachmentUploader lessonId={lesson.id} lessonTitle={lesson.title} />
        </TabsContent>
      </Tabs>
    </PageContainer>
  );
}

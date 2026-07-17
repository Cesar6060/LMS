import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useAuth } from '@/contexts/AuthContext';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Card, CardContent } from '@/components/ui/Card';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/Tabs';
import { AccessDenied } from '@/components/AccessDenied';
import { SectionEditor } from '@/components/lesson/SectionEditor';
import { AttachmentUploader } from '@/components/lesson/AttachmentUploader';
import { LessonQuestionsManager } from '@/components/lesson/LessonQuestionsManager';
import { courseService } from '@/services/courses';
import { quizzesService } from '@/services/quizzes';
import { isForbidden } from '@/services/api';
import { extractYouTubeVideoId, extractVimeoVideoId } from '@/lib/video';
import type { Lesson, Quiz } from '@/types';
import {
  Loader2, ChevronLeft, Save, FileText, Layers, HelpCircle, Paperclip, BookOpen,
} from 'lucide-react';

interface LessonForm {
  title: string;
  content: string;
  video_type: 'none' | 'youtube' | 'vimeo';
  video_id: string;
  required_quiz: number | null;
  max_quiz_attempts: number;
}

function formFromLesson(lesson: Lesson): LessonForm {
  return {
    title: lesson.title,
    content: lesson.content || '',
    video_type: lesson.video_type,
    video_id: lesson.video_id || '',
    required_quiz: lesson.required_quiz ?? null,
    max_quiz_attempts: lesson.max_quiz_attempts ?? 0,
  };
}

export function LessonEditorPage() {
  const { code, lessonId } = useParams<{ code: string; lessonId: string }>();
  const { user } = useAuth();
  const navigate = useNavigate();

  const [lesson, setLesson] = useState<Lesson | null>(null);
  const [quizzes, setQuizzes] = useState<Quiz[]>([]);
  const [form, setForm] = useState<LessonForm | null>(null);
  const [savedForm, setSavedForm] = useState<LessonForm | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [forbidden, setForbidden] = useState(false);
  const [notFound, setNotFound] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState('');

  const isDirty =
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
        const initial = formFromLesson(lessonData);
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

  // Warn on reload/close with unsaved changes
  useEffect(() => {
    if (!isDirty) return;
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = '';
    };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [isDirty]);

  const confirmLeave = useCallback(() => {
    return !isDirty || confirm('You have unsaved changes. Leave without saving?');
  }, [isDirty]);

  const handleBack = () => {
    if (confirmLeave()) {
      navigate(`/instructor/courses/${code}/manage`);
    }
  };

  const updateForm = (patch: Partial<LessonForm>) => {
    setForm(prev => (prev ? { ...prev, ...patch } : prev));
  };

  const handleSave = async () => {
    if (!form || !lesson) return;
    setIsSaving(true);
    setSaveError('');
    try {
      let videoId = '';
      if (form.video_type === 'youtube') {
        videoId = extractYouTubeVideoId(form.video_id);
      } else if (form.video_type === 'vimeo') {
        videoId = extractVimeoVideoId(form.video_id);
      }

      const updated = await courseService.updateLesson(lesson.id, {
        title: form.title,
        content: form.content,
        video_type: form.video_type,
        video_id: videoId,
        required_quiz: form.required_quiz,
        max_quiz_attempts: form.max_quiz_attempts,
      });
      setLesson(updated);
      const next = formFromLesson(updated);
      setForm(next);
      setSavedForm(next);
    } catch (err: unknown) {
      console.error('Failed to save lesson:', err);
      const apiError = err as { response?: { data?: { detail?: string } }; message?: string };
      setSaveError(apiError.response?.data?.detail || apiError.message || 'Failed to save lesson');
    } finally {
      setIsSaving(false);
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
      <div className="container mx-auto px-4 py-8">
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <BookOpen className="h-12 w-12 text-muted-foreground mb-4" />
            <h3 className="text-lg font-semibold mb-2">Lesson not found</h3>
            <Button onClick={() => navigate(`/instructor/courses/${code}/manage`)}>
              Back to Course
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8 max-w-6xl">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
        <div className="flex items-center gap-2 min-w-0">
          <Button variant="ghost" size="sm" onClick={handleBack}>
            <ChevronLeft className="h-4 w-4 mr-1" />
            Course Outline
          </Button>
          <span className="text-muted-foreground">/</span>
          <h1 className="text-xl font-semibold truncate">{lesson.title}</h1>
        </div>
        <div className="flex items-center gap-3">
          {isDirty && (
            <span className="text-sm text-muted-foreground">Unsaved changes</span>
          )}
          <Button onClick={handleSave} disabled={isSaving || !isDirty}>
            {isSaving ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Save className="mr-2 h-4 w-4" />
            )}
            Save
          </Button>
        </div>
      </div>

      {saveError && (
        <div className="bg-destructive/10 border border-destructive/20 text-destructive rounded-md px-4 py-3 text-sm mb-4">
          {saveError}
        </div>
      )}

      <Tabs defaultValue="content">
        <TabsList>
          <TabsTrigger value="content">
            <FileText className="h-4 w-4" />
            Content
          </TabsTrigger>
          <TabsTrigger value="sections">
            <Layers className="h-4 w-4" />
            Sections
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

        <TabsContent value="content" className="space-y-6">
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

          {/* Video settings */}
          <div className="grid gap-4 md:grid-cols-2 max-w-2xl">
            <div className="space-y-2">
              <label htmlFor="video-type" className="text-sm font-medium">
                Video Type
              </label>
              <select
                id="video-type"
                value={form.video_type}
                onChange={(e) =>
                  updateForm({
                    video_type: e.target.value as 'none' | 'youtube' | 'vimeo',
                    video_id: '',
                  })
                }
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              >
                <option value="none">No Video</option>
                <option value="youtube">YouTube</option>
                <option value="vimeo">Vimeo</option>
              </select>
            </div>
            {form.video_type !== 'none' && (
              <div className="space-y-2">
                <label htmlFor="video-id" className="text-sm font-medium">
                  {form.video_type === 'youtube' ? 'YouTube' : 'Vimeo'} URL or Video ID
                </label>
                <Input
                  id="video-id"
                  type="text"
                  placeholder={
                    form.video_type === 'youtube'
                      ? 'e.g., https://www.youtube.com/watch?v=dQw4w9WgXcQ'
                      : 'e.g., https://vimeo.com/123456789'
                  }
                  value={form.video_id}
                  onChange={(e) => updateForm({ video_id: e.target.value })}
                />
                <p className="text-xs text-muted-foreground">
                  Paste the full URL or just the video ID.
                </p>
              </div>
            )}
          </div>

          {/* Quiz gating */}
          <div className="grid gap-4 md:grid-cols-2 max-w-2xl">
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
            <div className="space-y-2">
              <label htmlFor="max-quiz-attempts" className="text-sm font-medium">
                Max Comprehension Quiz Attempts
              </label>
              <Input
                id="max-quiz-attempts"
                type="number"
                min="0"
                value={form.max_quiz_attempts}
                onChange={(e) =>
                  updateForm({ max_quiz_attempts: parseInt(e.target.value) || 0 })
                }
              />
              <p className="text-xs text-muted-foreground">Set to 0 for unlimited attempts.</p>
            </div>
          </div>

          {/* Markdown editor with live preview */}
          <div className="space-y-2">
            <label htmlFor="lesson-content" className="text-sm font-medium">
              Content (Markdown)
            </label>
            <div className="grid gap-4 lg:grid-cols-2">
              <textarea
                id="lesson-content"
                placeholder="Write your lesson content using Markdown..."
                value={form.content}
                onChange={(e) => updateForm({ content: e.target.value })}
                rows={24}
                className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm font-mono ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 resize-y"
              />
              <Card className="overflow-y-auto max-h-[600px]">
                <CardContent className="prose prose-neutral dark:prose-invert max-w-none py-4">
                  {form.content ? (
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{form.content}</ReactMarkdown>
                  ) : (
                    <p className="text-muted-foreground not-prose text-sm">
                      Preview appears here as you type.
                    </p>
                  )}
                </CardContent>
              </Card>
            </div>
            <p className="text-xs text-muted-foreground">
              Supports GitHub Flavored Markdown (headers, lists, code blocks, links, etc.)
            </p>
          </div>
        </TabsContent>

        <TabsContent value="sections">
          <SectionEditor lessonId={lesson.id} lessonTitle={lesson.title} />
        </TabsContent>

        <TabsContent value="questions">
          <LessonQuestionsManager lessonId={lesson.id} lessonTitle={lesson.title} />
        </TabsContent>

        <TabsContent value="attachments">
          <AttachmentUploader lessonId={lesson.id} lessonTitle={lesson.title} />
        </TabsContent>
      </Tabs>
    </div>
  );
}

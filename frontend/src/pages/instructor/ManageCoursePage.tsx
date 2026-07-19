import { useState, useEffect, useRef, useCallback, type KeyboardEvent } from 'react';
import { useParams } from 'react-router';
import {
  DndContext,
  closestCorners,
  PointerSensor,
  KeyboardSensor,
  useSensor,
  useSensors,
  type DragOverEvent,
  type DragEndEvent,
} from '@dnd-kit/core';
import {
  SortableContext,
  verticalListSortingStrategy,
  sortableKeyboardCoordinates,
  arrayMove,
} from '@dnd-kit/sortable';
import { useAuth } from '@/contexts/AuthContext';
import { Card, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { courseService, type CourseDetail } from '@/services/courses';
import { quizzesService } from '@/services/quizzes';
import { isForbidden } from '@/services/api';
import { AccessDenied } from '@/components/AccessDenied';
import { OutlineUnitCard, type OutlineUnit } from '@/components/manage/OutlineUnitCard';
import { CourseSettingsDialog } from '@/components/manage/CourseSettingsDialog';
import { CourseToolsNav } from '@/components/instructor/CourseToolsNav';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { BackLink } from '@/components/layout/BackLink';
import type { Quiz } from '@/types';
import { PageContainer } from '@/components/layout/PageContainer';
import {
  Loader2, Plus, Copy, CheckCircle, Settings, BookOpen,
  ChevronsDownUp, ChevronsUpDown,
} from 'lucide-react';

function AddUnitRow({
  onAdd,
  autoFocus,
}: {
  onAdd: (title: string) => Promise<void>;
  autoFocus: boolean;
}) {
  const [active, setActive] = useState(autoFocus);
  const [title, setTitle] = useState('');
  const [isCreating, setIsCreating] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (active) {
      inputRef.current?.focus();
    }
  }, [active]);

  const handleKeyDown = async (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Escape') {
      setActive(false);
      setTitle('');
      return;
    }
    if (e.key === 'Enter' && title.trim()) {
      e.preventDefault();
      setIsCreating(true);
      try {
        await onAdd(title.trim());
        setTitle('');
        inputRef.current?.focus();
      } finally {
        setIsCreating(false);
      }
    }
  };

  if (!active) {
    return (
      <button
        type="button"
        className="w-full rounded-lg border border-dashed px-4 py-3.5 text-base font-medium text-muted-foreground hover:text-foreground hover:border-foreground/30 flex items-center justify-center gap-2"
        onClick={() => setActive(true)}
      >
        <Plus className="h-5 w-5" />
        Add unit
      </button>
    );
  }

  return (
    <div className="rounded-lg border border-dashed px-4 py-3">
      <Input
        ref={inputRef}
        type="text"
        placeholder="Unit title — Enter to create, Esc to cancel"
        value={title}
        disabled={isCreating}
        onChange={(e) => setTitle(e.target.value)}
        onKeyDown={handleKeyDown}
        onBlur={() => {
          if (!title.trim()) setActive(false);
        }}
      />
    </div>
  );
}

export function ManageCoursePage() {
  const { code } = useParams<{ code: string }>();
  const { user } = useAuth();

  const [course, setCourse] = useState<CourseDetail | null>(null);
  const [units, setUnits] = useState<OutlineUnit[]>([]);
  const [quizzes, setQuizzes] = useState<Quiz[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [forbidden, setForbidden] = useState(false);
  const [copied, setCopied] = useState(false);

  // Collapse state, persisted per course
  const [collapsed, setCollapsed] = useState<Record<number, boolean>>({});

  // Settings dialog
  const [showSettings, setShowSettings] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<
    { type: 'unit' | 'lesson' | 'quiz'; id: number } | null
  >(null);
  const [isDeleting, setIsDeleting] = useState(false);

  // Snapshot for drag rollback
  const dragSnapshot = useRef<OutlineUnit[] | null>(null);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  );

  const storageKey = `outline-collapsed:${code}`;

  useEffect(() => {
    try {
      const stored = localStorage.getItem(storageKey);
      if (stored) {
        const ids = JSON.parse(stored) as number[];
        setCollapsed(Object.fromEntries(ids.map(id => [id, true])));
      } else {
        setCollapsed({});
      }
    } catch {
      setCollapsed({});
    }
  }, [storageKey]);

  const persistCollapsed = (next: Record<number, boolean>) => {
    setCollapsed(next);
    const ids = Object.entries(next)
      .filter(([, v]) => v)
      .map(([k]) => Number(k));
    localStorage.setItem(storageKey, JSON.stringify(ids));
  };

  const loadCourse = useCallback(async (showSpinner = false) => {
    if (!code) return;
    try {
      if (showSpinner) setIsLoading(true);
      const [data, quizzesData] = await Promise.all([
        courseService.getCourse(code),
        quizzesService.getCourseQuizzes(code),
      ]);
      setCourse(data);
      setUnits(data.units.map(u => ({ id: u.id, title: u.title, lessons: u.lessons })));
      setQuizzes(quizzesData);
    } catch (err) {
      if (isForbidden(err)) {
        setForbidden(true);
      } else {
        setError('Failed to load course');
        console.error(err);
      }
    } finally {
      if (showSpinner) setIsLoading(false);
    }
  }, [code]);

  useEffect(() => {
    loadCourse(true);
  }, [loadCourse]);

  // Ownership check (course detail is visible to enrolled students too)
  useEffect(() => {
    if (course && user && course.instructor.id !== user.id) {
      setForbidden(true);
    }
  }, [course, user]);

  const handleCopyEnrollmentCode = async () => {
    if (course?.enrollment_code) {
      await navigator.clipboard.writeText(course.enrollment_code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  // ---------- Structure operations (commit immediately) ----------

  const handleAddUnit = async (title: string) => {
    if (!course) return;
    try {
      await courseService.createUnit(course.code, { title });
      await loadCourse();
    } catch (err) {
      console.error('Failed to add unit:', err);
      setError('Failed to add unit');
    }
  };

  const handleRenameUnit = async (unitId: number, title: string) => {
    setUnits(prev => prev.map(u => (u.id === unitId ? { ...u, title } : u)));
    try {
      await courseService.updateUnit(unitId, { title });
    } catch (err) {
      console.error('Failed to rename unit:', err);
      await loadCourse();
    }
  };

  const handleDeleteUnit = (unitId: number) => {
    setDeleteTarget({ type: 'unit', id: unitId });
  };

  const handleAddLesson = async (unitId: number, title: string) => {
    try {
      await courseService.createLesson(unitId, { title, content: '' });
      await loadCourse();
    } catch (err) {
      console.error('Failed to add lesson:', err);
      setError('Failed to add lesson');
    }
  };

  const handleRenameLesson = async (lessonId: number, title: string) => {
    setUnits(prev =>
      prev.map(u => ({
        ...u,
        lessons: u.lessons.map(l => (l.id === lessonId ? { ...l, title } : l)),
      }))
    );
    try {
      await courseService.updateLesson(lessonId, { title });
    } catch (err) {
      console.error('Failed to rename lesson:', err);
      await loadCourse();
    }
  };

  const handleDeleteLesson = (lessonId: number) => {
    setDeleteTarget({ type: 'lesson', id: lessonId });
  };

  const handleAddQuiz = async (unitId: number, title: string) => {
    try {
      await quizzesService.createQuiz(unitId, { title });
      await loadCourse();
    } catch (err) {
      console.error('Failed to add quiz:', err);
      setError('Failed to add quiz');
    }
  };

  const handleDeleteQuiz = (quizId: number) => {
    setDeleteTarget({ type: 'quiz', id: quizId });
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    setIsDeleting(true);
    try {
      if (deleteTarget.type === 'unit') {
        await courseService.deleteUnit(deleteTarget.id);
      } else if (deleteTarget.type === 'lesson') {
        await courseService.deleteLesson(deleteTarget.id);
      } else {
        await quizzesService.deleteQuiz(deleteTarget.id);
      }
      setDeleteTarget(null);
      await loadCourse();
    } catch (err) {
      console.error(`Failed to delete ${deleteTarget.type}:`, err);
      setDeleteTarget(null);
    } finally {
      setIsDeleting(false);
    }
  };

  // ---------- Drag & drop ----------

  const findLessonContainer = (id: string): number | null => {
    if (id.startsWith('unitdrop-')) return Number(id.slice('unitdrop-'.length));
    if (id.startsWith('unit-')) return Number(id.slice('unit-'.length));
    if (id.startsWith('lesson-')) {
      const lessonId = Number(id.slice('lesson-'.length));
      const container = units.find(u => u.lessons.some(l => l.id === lessonId));
      return container?.id ?? null;
    }
    return null;
  };

  const handleDragStart = () => {
    dragSnapshot.current = units.map(u => ({ ...u, lessons: [...u.lessons] }));
  };

  const handleDragOver = (event: DragOverEvent) => {
    const { active, over } = event;
    const activeId = String(active.id);
    if (!over || !activeId.startsWith('lesson-')) return;

    const overId = String(over.id);
    const activeContainer = findLessonContainer(activeId);
    const overContainer = findLessonContainer(overId);
    if (activeContainer === null || overContainer === null) return;
    if (activeContainer === overContainer) return;

    const lessonId = Number(activeId.slice('lesson-'.length));
    setUnits(prev => {
      const source = prev.find(u => u.id === activeContainer);
      const target = prev.find(u => u.id === overContainer);
      if (!source || !target) return prev;
      const lesson = source.lessons.find(l => l.id === lessonId);
      if (!lesson) return prev;

      let insertIndex = target.lessons.length;
      if (overId.startsWith('lesson-')) {
        const overLessonId = Number(overId.slice('lesson-'.length));
        const overIndex = target.lessons.findIndex(l => l.id === overLessonId);
        if (overIndex >= 0) insertIndex = overIndex;
      }

      return prev.map(u => {
        if (u.id === source.id) {
          return { ...u, lessons: u.lessons.filter(l => l.id !== lessonId) };
        }
        if (u.id === target.id) {
          const lessons = [...u.lessons];
          lessons.splice(insertIndex, 0, lesson);
          return { ...u, lessons };
        }
        return u;
      });
    });
  };

  const rollbackDrag = () => {
    if (dragSnapshot.current) {
      setUnits(dragSnapshot.current);
    }
    dragSnapshot.current = null;
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    const activeId = String(active.id);
    const snapshot = dragSnapshot.current;

    if (!over) {
      rollbackDrag();
      return;
    }
    const overId = String(over.id);

    // --- Unit reorder ---
    if (activeId.startsWith('unit-')) {
      const unitId = Number(activeId.slice('unit-'.length));
      // The drop target may resolve to a lesson row inside another unit card;
      // findLessonContainer maps any droppable id back to its unit.
      const overUnitId = findLessonContainer(overId);
      if (overUnitId === null) {
        dragSnapshot.current = null;
        return;
      }
      const oldIndex = units.findIndex(u => u.id === unitId);
      const newIndex = units.findIndex(u => u.id === overUnitId);
      dragSnapshot.current = null;
      if (oldIndex < 0 || newIndex < 0 || oldIndex === newIndex) return;

      setUnits(prev => arrayMove(prev, oldIndex, newIndex));
      courseService.reorderUnit(unitId, newIndex + 1).catch(err => {
        console.error('Failed to reorder unit:', err);
        if (snapshot) setUnits(snapshot);
      });
      return;
    }

    // --- Lesson reorder / cross-unit move ---
    if (activeId.startsWith('lesson-')) {
      const lessonId = Number(activeId.slice('lesson-'.length));
      const container = units.find(u => u.lessons.some(l => l.id === lessonId));
      dragSnapshot.current = null;
      if (!container || !snapshot) return;

      let workingUnits = units;
      let finalIndex = container.lessons.findIndex(l => l.id === lessonId);

      if (overId.startsWith('lesson-')) {
        const overLessonId = Number(overId.slice('lesson-'.length));
        if (overLessonId !== lessonId) {
          const overContainer = units.find(u => u.lessons.some(l => l.id === overLessonId));
          if (overContainer && overContainer.id === container.id) {
            const overIndex = container.lessons.findIndex(l => l.id === overLessonId);
            workingUnits = units.map(u =>
              u.id === container.id
                ? { ...u, lessons: arrayMove(u.lessons, finalIndex, overIndex) }
                : u
            );
            finalIndex = overIndex;
            setUnits(workingUnits);
          }
        }
      }

      const originalContainer = snapshot.find(u => u.lessons.some(l => l.id === lessonId));
      const unitChanged = originalContainer ? originalContainer.id !== container.id : false;
      const originalIndex = originalContainer
        ? originalContainer.lessons.findIndex(l => l.id === lessonId)
        : -1;

      if (!unitChanged && finalIndex === originalIndex) return;

      courseService
        .reorderLesson(lessonId, finalIndex + 1, unitChanged ? container.id : undefined)
        .catch(err => {
          console.error('Failed to reorder lesson:', err);
          setUnits(snapshot);
        });
    }
  };

  // ---------- Render ----------

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

  if (error && !course) {
    return (
      <PageContainer maxWidth="max-w-6xl">
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <BookOpen className="h-12 w-12 text-muted-foreground mb-4" />
            <h3 className="text-lg font-semibold mb-2">Course not found</h3>
            <p className="text-muted-foreground mb-4">{error}</p>
            <BackLink to="/dashboard" label="Dashboard" />
          </CardContent>
        </Card>
      </PageContainer>
    );
  }

  if (!course) return null;

  const unitQuizzes = (unitId: number) => quizzes.filter(q => q.unit === unitId);

  return (
    <PageContainer maxWidth="max-w-6xl">
      {/* Course tools sub-nav */}
      <CourseToolsNav courseCode={course.code} className="mb-6" />

      {/* Header */}
      <div className="mb-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <h1 className="text-3xl font-bold mb-1 truncate">{course.title}</h1>
            <div className="flex flex-wrap items-center gap-3 text-base text-muted-foreground">
              <span className="font-mono">{course.code}</span>
              {!course.is_active && (
                <span className="rounded bg-muted px-2 py-0.5 text-sm font-medium">Inactive</span>
              )}
            </div>
          </div>

          {/* Enrollment code — the thing instructors share with students */}
          <div className="flex items-center gap-3 rounded-xl border border-neon-green/30 bg-neon-green/5 pl-4 pr-2 py-2.5">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Enrollment Code
              </p>
              <p className="font-mono text-2xl font-bold tracking-[0.2em] text-neon-green leading-tight">
                {course.enrollment_code}
              </p>
            </div>
            <Button
              variant="ghost"
              size="icon"
              onClick={handleCopyEnrollmentCode}
              aria-label="Copy enrollment code"
              title="Copy enrollment code"
            >
              {copied ? (
                <CheckCircle className="h-5 w-5 text-green-500" />
              ) : (
                <Copy className="h-5 w-5" />
              )}
            </Button>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2 mt-4">
          <Button
            variant="outline"
            size="sm"
            onClick={() => persistCollapsed(Object.fromEntries(units.map(u => [u.id, true])))}
            title="Collapse all units"
          >
            <ChevronsDownUp className="h-4 w-4 mr-1" />
            Collapse all
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => persistCollapsed({})}
            title="Expand all units"
          >
            <ChevronsUpDown className="h-4 w-4 mr-1" />
            Expand all
          </Button>
          <Button variant="outline" size="sm" onClick={() => setShowSettings(true)}>
            <Settings className="h-4 w-4 mr-1" />
            Settings
          </Button>
        </div>
      </div>

      {error && (
        <div className="bg-destructive/10 border border-destructive/20 text-destructive rounded-md px-4 py-3 text-sm mb-4">
          {error}
        </div>
      )}

      {/* Outline */}
      {units.length === 0 ? (
        <Card className="mb-4">
          <CardContent className="py-12 text-center">
            <BookOpen className="h-12 w-12 mx-auto mb-4 text-muted-foreground opacity-50" />
            <h3 className="text-lg font-semibold mb-1">Create your first unit</h3>
            <p className="text-sm text-muted-foreground">
              Units organize your lessons and quizzes.
            </p>
          </CardContent>
        </Card>
      ) : (
        <DndContext
          sensors={sensors}
          collisionDetection={closestCorners}
          onDragStart={handleDragStart}
          onDragOver={handleDragOver}
          onDragEnd={handleDragEnd}
          onDragCancel={rollbackDrag}
        >
          <SortableContext
            items={units.map(u => `unit-${u.id}`)}
            strategy={verticalListSortingStrategy}
          >
            <div className="space-y-3 mb-4">
              {units.map(unit => (
                <OutlineUnitCard
                  key={unit.id}
                  unit={unit}
                  courseCode={course.code}
                  collapsed={!!collapsed[unit.id]}
                  quizzes={unitQuizzes(unit.id)}
                  onToggleCollapse={(unitId) =>
                    persistCollapsed({ ...collapsed, [unitId]: !collapsed[unitId] })
                  }
                  onRenameUnit={handleRenameUnit}
                  onDeleteUnit={handleDeleteUnit}
                  onRenameLesson={handleRenameLesson}
                  onDeleteLesson={handleDeleteLesson}
                  onDeleteQuiz={handleDeleteQuiz}
                  onAddLesson={handleAddLesson}
                  onAddQuiz={handleAddQuiz}
                />
              ))}
            </div>
          </SortableContext>
        </DndContext>
      )}

      <AddUnitRow onAdd={handleAddUnit} autoFocus={units.length === 0} />

      {/* Course settings */}
      <CourseSettingsDialog
        open={showSettings}
        onOpenChange={setShowSettings}
        course={course}
        onSaved={() => loadCourse()}
      />

      {/* Delete confirmation */}
      <ConfirmDialog
        open={!!deleteTarget}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null);
        }}
        title={
          deleteTarget?.type === 'unit'
            ? 'Delete Unit'
            : deleteTarget?.type === 'lesson'
              ? 'Delete Lesson'
              : 'Delete Quiz'
        }
        confirmLabel={
          deleteTarget?.type === 'unit'
            ? 'Delete Unit'
            : deleteTarget?.type === 'lesson'
              ? 'Delete Lesson'
              : 'Delete Quiz'
        }
        loadingLabel="Deleting..."
        onConfirm={confirmDelete}
        isLoading={isDeleting}
      >
        {deleteTarget?.type === 'unit'
          ? 'Delete this unit? All lessons and quizzes in it will also be deleted.'
          : deleteTarget?.type === 'lesson'
            ? 'Are you sure you want to delete this lesson?'
            : 'Are you sure you want to delete this quiz?'}
      </ConfirmDialog>
    </PageContainer>
  );
}

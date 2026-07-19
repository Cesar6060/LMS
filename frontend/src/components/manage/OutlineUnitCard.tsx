import { useState, useRef, useEffect, type KeyboardEvent } from 'react';
import { Link } from 'react-router';
import { useSortable, SortableContext, verticalListSortingStrategy } from '@dnd-kit/sortable';
import { useDroppable } from '@dnd-kit/core';
import { CSS } from '@dnd-kit/utilities';
import { Card, CardContent, CardHeader } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import type { LessonListItem } from '@/services/courses';
import type { Quiz } from '@/types';
import { cn } from '@/lib/utils';
import {
  GripVertical, ChevronDown, ChevronRight, Trash2,
  Pencil, Play, FileText, FileQuestion, Plus,
} from 'lucide-react';

export interface OutlineUnit {
  id: number;
  title: string;
  lessons: LessonListItem[];
}

interface InlineAddRowProps {
  onAddLesson: (title: string) => Promise<void>;
  onAddQuiz: (title: string) => Promise<void>;
}

function InlineAddRow({ onAddLesson, onAddQuiz }: InlineAddRowProps) {
  const [mode, setMode] = useState<'lesson' | 'quiz' | null>(null);
  const [title, setTitle] = useState('');
  const [isCreating, setIsCreating] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (mode) {
      inputRef.current?.focus();
    }
  }, [mode]);

  const reset = () => {
    setMode(null);
    setTitle('');
  };

  const handleKeyDown = async (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Escape') {
      reset();
      return;
    }
    if (e.key === 'Enter' && title.trim() && mode) {
      e.preventDefault();
      setIsCreating(true);
      try {
        if (mode === 'lesson') {
          await onAddLesson(title.trim());
        } else {
          await onAddQuiz(title.trim());
        }
        reset();
      } finally {
        setIsCreating(false);
      }
    }
  };

  const modeLabel = mode === 'quiz' ? 'unit quiz' : 'lesson';

  if (mode) {
    return (
      <div className="mt-3 flex items-center gap-2 rounded-lg border border-dashed border-border px-3 py-2.5">
        {mode === 'lesson' ? (
          <FileText className="h-4 w-4 text-muted-foreground flex-shrink-0" />
        ) : (
          <FileQuestion className="h-4 w-4 text-muted-foreground flex-shrink-0" />
        )}
        <Input
          ref={inputRef}
          type="text"
          className="h-8"
          placeholder={`New ${modeLabel} title — Enter to create, Esc to cancel`}
          value={title}
          disabled={isCreating}
          onChange={(e) => setTitle(e.target.value)}
          onKeyDown={handleKeyDown}
          onBlur={() => {
            if (!title.trim()) reset();
          }}
        />
      </div>
    );
  }

  return (
    <div className="mt-3 flex items-center gap-2 rounded-lg border border-dashed border-border px-3 py-2.5">
      <Button type="button" variant="outline" onClick={() => setMode('lesson')}>
        <Plus className="h-4 w-4 mr-1.5" />
        Add Lesson
      </Button>
      <Button type="button" variant="outline" onClick={() => setMode('quiz')}>
        <Plus className="h-4 w-4 mr-1.5" />
        Add Unit Quiz
      </Button>
    </div>
  );
}

interface InlineTitleProps {
  value: string;
  className?: string;
  editing: boolean;
  onStartEdit: () => void;
  onSave: (title: string) => void;
  onCancel: () => void;
}

function InlineTitle({ value, className, editing, onStartEdit, onSave, onCancel }: InlineTitleProps) {
  const [draft, setDraft] = useState(value);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editing) {
      setDraft(value);
      inputRef.current?.focus();
      inputRef.current?.select();
    }
  }, [editing, value]);

  if (!editing) {
    return (
      <button
        type="button"
        className={cn('text-left hover:underline decoration-dotted underline-offset-4', className)}
        onClick={onStartEdit}
        title="Click to rename"
      >
        {value}
      </button>
    );
  }

  return (
    <Input
      ref={inputRef}
      type="text"
      className="h-8"
      value={draft}
      onChange={(e) => setDraft(e.target.value)}
      onKeyDown={(e) => {
        if (e.key === 'Enter') {
          e.preventDefault();
          if (draft.trim()) onSave(draft.trim());
        } else if (e.key === 'Escape') {
          onCancel();
        }
      }}
      onBlur={() => {
        if (draft.trim() && draft.trim() !== value) {
          onSave(draft.trim());
        } else {
          onCancel();
        }
      }}
    />
  );
}

interface SortableLessonRowProps {
  lesson: LessonListItem;
  courseCode: string;
  onRename: (lessonId: number, title: string) => void;
  onDelete: (lessonId: number) => void;
}

function SortableLessonRow({ lesson, courseCode, onRename, onDelete }: SortableLessonRowProps) {
  const [editing, setEditing] = useState(false);
  const {
    attributes, listeners, setNodeRef, transform, transition, isDragging,
  } = useSortable({ id: `lesson-${lesson.id}` });

  return (
    <li
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      className={cn(
        'group flex items-center gap-2 rounded-lg border border-border px-3 py-2.5',
        isDragging && 'opacity-50'
      )}
    >
      <button
        type="button"
        className="cursor-grab touch-none opacity-60 hover:opacity-100 focus-visible:opacity-100 text-muted-foreground"
        aria-label={`Reorder lesson ${lesson.title}`}
        {...attributes}
        {...listeners}
      >
        <GripVertical className="h-4 w-4" />
      </button>
      {lesson.video_type !== 'none' ? (
        <Play className="h-4 w-4 text-muted-foreground flex-shrink-0" />
      ) : (
        <FileText className="h-4 w-4 text-muted-foreground flex-shrink-0" />
      )}
      <div className="flex-1 min-w-0">
        <InlineTitle
          value={lesson.title}
          className="text-base"
          editing={editing}
          onStartEdit={() => setEditing(true)}
          onSave={(title) => {
            setEditing(false);
            onRename(lesson.id, title);
          }}
          onCancel={() => setEditing(false)}
        />
      </div>
      <div className="flex items-center gap-1 opacity-60 hover:opacity-100 focus-within:opacity-100">
        <Link to={`/instructor/courses/${courseCode}/lessons/${lesson.id}/edit`}>
          <Button
            variant="ghost"
            size="sm"
            className="h-8 w-8 p-0"
            aria-label={`Edit lesson ${lesson.title}`}
            title="Edit lesson"
          >
            <Pencil className="h-4 w-4" />
          </Button>
        </Link>
        <Button
          variant="ghost"
          size="sm"
          className="h-8 w-8 p-0 text-destructive hover:text-destructive"
          onClick={() => onDelete(lesson.id)}
          aria-label={`Delete lesson ${lesson.title}`}
          title="Delete lesson"
        >
          <Trash2 className="h-4 w-4" />
        </Button>
      </div>
    </li>
  );
}

interface OutlineUnitCardProps {
  unit: OutlineUnit;
  courseCode: string;
  collapsed: boolean;
  quizzes: Quiz[];
  onToggleCollapse: (unitId: number) => void;
  onRenameUnit: (unitId: number, title: string) => void;
  onDeleteUnit: (unitId: number) => void;
  onRenameLesson: (lessonId: number, title: string) => void;
  onDeleteLesson: (lessonId: number) => void;
  onDeleteQuiz: (quizId: number) => void;
  onAddLesson: (unitId: number, title: string) => Promise<void>;
  onAddQuiz: (unitId: number, title: string) => Promise<void>;
}

export function OutlineUnitCard({
  unit,
  courseCode,
  collapsed,
  quizzes,
  onToggleCollapse,
  onRenameUnit,
  onDeleteUnit,
  onRenameLesson,
  onDeleteLesson,
  onDeleteQuiz,
  onAddLesson,
  onAddQuiz,
}: OutlineUnitCardProps) {
  const [editingTitle, setEditingTitle] = useState(false);
  const {
    attributes, listeners, setNodeRef, transform, transition, isDragging,
  } = useSortable({ id: `unit-${unit.id}` });

  const { setNodeRef: setDropRef } = useDroppable({ id: `unitdrop-${unit.id}` });

  const itemCount = unit.lessons.length + quizzes.length;

  return (
    <Card
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      className={cn('group/unit', isDragging && 'opacity-50 shadow-lg')}
      data-testid={`unit-card-${unit.id}`}
    >
      <CardHeader className="py-3">
        <div className="flex items-center gap-2">
          <button
            type="button"
            className="cursor-grab touch-none opacity-60 hover:opacity-100 focus-visible:opacity-100 text-muted-foreground"
            aria-label={`Reorder unit ${unit.title}`}
            {...attributes}
            {...listeners}
          >
            <GripVertical className="h-5 w-5" />
          </button>
          <Button
            variant="ghost"
            size="sm"
            className="h-8 w-8 p-0"
            onClick={() => onToggleCollapse(unit.id)}
            aria-label={collapsed ? `Expand unit ${unit.title}` : `Collapse unit ${unit.title}`}
            title={collapsed ? 'Expand unit' : 'Collapse unit'}
          >
            {collapsed ? (
              <ChevronRight className="h-4 w-4" />
            ) : (
              <ChevronDown className="h-4 w-4" />
            )}
          </Button>
          <div className="flex-1 min-w-0">
            <InlineTitle
              value={unit.title}
              className="text-lg font-semibold"
              editing={editingTitle}
              onStartEdit={() => setEditingTitle(true)}
              onSave={(title) => {
                setEditingTitle(false);
                onRenameUnit(unit.id, title);
              }}
              onCancel={() => setEditingTitle(false)}
            />
          </div>
          <span className="text-base text-muted-foreground whitespace-nowrap">
            {itemCount} {itemCount === 1 ? 'item' : 'items'}
          </span>
          <Button
            variant="ghost"
            size="sm"
            className="h-8 w-8 p-0 text-destructive hover:text-destructive"
            onClick={() => onDeleteUnit(unit.id)}
            aria-label={`Delete unit ${unit.title}`}
            title="Delete unit"
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      </CardHeader>
      {!collapsed && (
        <CardContent className="pt-0 pb-3" ref={setDropRef}>
          {itemCount === 0 && (
            <p className="text-sm text-muted-foreground px-2 py-2">
              No lessons yet — add a lesson or quiz.
            </p>
          )}
          <SortableContext
            items={unit.lessons.map(l => `lesson-${l.id}`)}
            strategy={verticalListSortingStrategy}
          >
            <ul className="space-y-2">
              {unit.lessons.map(lesson => (
                <SortableLessonRow
                  key={lesson.id}
                  lesson={lesson}
                  courseCode={courseCode}
                  onRename={onRenameLesson}
                  onDelete={onDeleteLesson}
                />
              ))}
            </ul>
          </SortableContext>

          {quizzes.length > 0 && (
            <ul className="mt-2 space-y-2">
              {quizzes.map(quiz => (
                <li
                  key={quiz.id}
                  className="group flex items-center gap-2 rounded-lg border border-border px-3 py-2.5"
                >
                  <span className="w-4" />
                  <FileQuestion className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                  <Link
                    to={`/instructor/courses/${courseCode}/quizzes?quiz=${quiz.id}`}
                    className="min-w-0 text-base hover:underline truncate"
                  >
                    {quiz.title}
                  </Link>
                  <span className="flex-shrink-0 text-xs text-muted-foreground border border-border rounded px-1.5 py-0.5">
                    Unit Quiz
                  </span>
                  <span className="flex-1 text-base text-muted-foreground whitespace-nowrap text-right">
                    {quiz.question_count} {quiz.question_count === 1 ? 'question' : 'questions'} · {quiz.points} pts
                  </span>
                  <div className="flex items-center gap-1 opacity-60 hover:opacity-100 focus-within:opacity-100">
                    <Link to={`/instructor/courses/${courseCode}/quizzes?quiz=${quiz.id}`}>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-8 w-8 p-0"
                        aria-label={`Edit quiz ${quiz.title}`}
                        title="Edit quiz"
                      >
                        <Pencil className="h-4 w-4" />
                      </Button>
                    </Link>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-8 w-8 p-0 text-destructive hover:text-destructive"
                      onClick={() => onDeleteQuiz(quiz.id)}
                      aria-label={`Delete quiz ${quiz.title}`}
                      title="Delete quiz"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          )}

          <InlineAddRow
            onAddLesson={(title) => onAddLesson(unit.id, title)}
            onAddQuiz={(title) => onAddQuiz(unit.id, title)}
          />
        </CardContent>
      )}
    </Card>
  );
}

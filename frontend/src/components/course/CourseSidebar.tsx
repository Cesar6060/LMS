import { useState, useEffect } from 'react';
import { ChevronDown, ChevronRight, CheckCircle, Circle, PlayCircle, FileText, FileQuestion } from 'lucide-react';
import { cn } from '@/lib/utils';

interface Lesson {
  id: number;
  title: string;
  video_type: 'none' | 'youtube';
  video_id: string | null;
  order: number;
  /** Phase 54 — true when the lesson gates completion on its own quiz. */
  requires_quiz?: boolean;
  /** Phase 53 — true if any section has a playable YouTube video. */
  has_video?: boolean;
}

interface LessonWithProgress extends Lesson {
  is_completed?: boolean;
}

interface Unit {
  id: number;
  title: string;
  order: number;
  lessons: LessonWithProgress[];
}

/** Unit-wide quiz (quizzes.Quiz), a graded sibling of lessons. */
interface SidebarQuiz {
  id: number;
  title: string;
  unit?: number;
  question_count: number;
  points: number;
  best_score?: { score: number; passed: boolean } | null;
}

interface CourseSidebarProps {
  units: Unit[];
  quizzes?: SidebarQuiz[];
  currentLessonId: number | null;
  currentQuizId?: number | null;
  onLessonSelect: (lessonId: number) => void;
  onQuizSelect?: (quizId: number) => void;
  isCollapsed: boolean;
  onToggleCollapse: () => void;
  progressPercentage: number;
  completedCount: number;
  totalCount: number;
}

export function CourseSidebar({
  units,
  quizzes = [],
  currentLessonId,
  currentQuizId = null,
  onLessonSelect,
  onQuizSelect,
  isCollapsed,
  onToggleCollapse,
  progressPercentage,
  completedCount,
  totalCount,
}: CourseSidebarProps) {
  const [expandedUnits, setExpandedUnits] = useState<number[]>([]);

  // Auto-expand the unit containing the current lesson or unit quiz
  useEffect(() => {
    setExpandedUnits(prev => {
      const next = new Set(prev);
      if (currentLessonId) {
        const unitWithLesson = units.find(unit =>
          unit.lessons.some(lesson => lesson.id === currentLessonId)
        );
        if (unitWithLesson) next.add(unitWithLesson.id);
      }
      if (currentQuizId) {
        const quiz = quizzes.find(q => q.id === currentQuizId);
        if (quiz?.unit != null) next.add(quiz.unit);
      }
      return next.size === prev.length ? prev : Array.from(next);
    });
  }, [currentLessonId, currentQuizId, units, quizzes]);

  const toggleUnit = (unitId: number) => {
    setExpandedUnits(prev =>
      prev.includes(unitId)
        ? prev.filter(id => id !== unitId)
        : [...prev, unitId]
    );
  };

  const getUnitProgress = (unit: Unit) => {
    const completed = unit.lessons.filter(l => l.is_completed).length;
    return { completed, total: unit.lessons.length };
  };

  if (isCollapsed) {
    return (
      <div className="w-14 bg-card border-r flex flex-col items-center py-4">
        <button
          onClick={onToggleCollapse}
          className="p-2 hover:bg-accent rounded-md mb-4"
          title="Expand sidebar"
        >
          <ChevronRight className="h-5 w-5" />
        </button>
        <div className="flex-1 flex flex-col items-center">
          <div className="w-2 bg-muted rounded-full h-32 relative">
            <div
              className="absolute bottom-0 w-full bg-primary rounded-full transition-all"
              style={{ height: `${progressPercentage}%` }}
            />
          </div>
          <span className="text-xs text-muted-foreground mt-2 -rotate-90 whitespace-nowrap origin-center">
            {Math.round(progressPercentage)}%
          </span>
        </div>
      </div>
    );
  }

  return (
    <div className="w-[420px] bg-card border-r flex flex-col h-full">
      {/* Header */}
      <div className="p-5 border-b">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-semibold text-base">Course Content</h2>
          <button
            onClick={onToggleCollapse}
            className="p-1 hover:bg-accent rounded"
            title="Collapse sidebar"
          >
            <ChevronRight className="h-5 w-5 rotate-180" />
          </button>
        </div>

        {/* Progress bar */}
        <div className="space-y-1.5">
          <div className="h-2.5 bg-muted rounded-full overflow-hidden">
            <div
              className="h-full bg-primary transition-all duration-300"
              style={{ width: `${progressPercentage}%` }}
            />
          </div>
          <p className="text-sm text-muted-foreground">
            {completedCount} of {totalCount} complete ({Math.round(progressPercentage)}%)
          </p>
        </div>
      </div>

      {/* Units list */}
      <div className="flex-1 overflow-y-auto">
        {units.map((unit) => {
          const isExpanded = expandedUnits.includes(unit.id);
          const { completed, total } = getUnitProgress(unit);

          return (
            <div key={unit.id} className="border-b">
              {/* Unit header */}
              <button
                onClick={() => toggleUnit(unit.id)}
                className="w-full px-5 py-4 flex items-center justify-between hover:bg-accent/50 transition-colors"
              >
                <div className="flex items-center gap-2.5 text-left">
                  {isExpanded ? (
                    <ChevronDown className="h-5 w-5 flex-shrink-0" />
                  ) : (
                    <ChevronRight className="h-5 w-5 flex-shrink-0" />
                  )}
                  <div>
                    <p className="font-medium text-base">{unit.title}</p>
                    <p className="text-sm text-muted-foreground">
                      {completed}/{total} lessons
                    </p>
                  </div>
                </div>
                {completed === total && total > 0 && (
                  <CheckCircle className="h-5 w-5 text-green-500 flex-shrink-0" />
                )}
              </button>

              {/* Lessons list */}
              {isExpanded && (
                <div className="bg-muted/30">
                  {unit.lessons.map((lesson) => {
                    const isActive = lesson.id === currentLessonId;
                    // Phase 53: video lives in sections; the API exposes has_video.
                    const hasVideo = lesson.has_video ?? false;

                    return (
                      <button
                        key={lesson.id}
                        onClick={() => onLessonSelect(lesson.id)}
                        className={cn(
                          "w-full px-5 py-3 flex items-center gap-3 text-left transition-colors",
                          isActive
                            ? "bg-primary/10 border-l-[3px] border-primary"
                            : "hover:bg-accent/50 border-l-[3px] border-transparent"
                        )}
                      >
                        {/* Completion icon */}
                        <div className="flex-shrink-0">
                          {lesson.is_completed ? (
                            <CheckCircle className="h-5 w-5 text-green-500" />
                          ) : (
                            <Circle className="h-5 w-5 text-muted-foreground" />
                          )}
                        </div>

                        {/* Content type icon */}
                        <div className="flex-shrink-0">
                          {hasVideo ? (
                            <PlayCircle className="h-5 w-5 text-muted-foreground" />
                          ) : (
                            <FileText className="h-5 w-5 text-muted-foreground" />
                          )}
                        </div>

                        {/* Lesson title */}
                        <span
                          className={cn(
                            "text-sm flex-1 truncate",
                            isActive ? "font-medium" : "",
                            lesson.is_completed ? "text-muted-foreground" : ""
                          )}
                        >
                          {lesson.title}
                        </span>

                        {/* Quiz requirement indicator */}
                        {lesson.requires_quiz && !lesson.is_completed && (
                          <span title="Quiz required to complete this lesson">
                            <FileQuestion className="h-5 w-5 text-amber-500 flex-shrink-0" />
                          </span>
                        )}
                      </button>
                    );
                  })}

                  {/* Unit-wide quizzes (graded siblings of lessons) */}
                  {quizzes
                    .filter(quiz => quiz.unit === unit.id)
                    .map(quiz => {
                      const isActive = quiz.id === currentQuizId;
                      const passed = quiz.best_score?.passed;

                      return (
                        <button
                          key={`quiz-${quiz.id}`}
                          onClick={() => onQuizSelect?.(quiz.id)}
                          className={cn(
                            "w-full px-5 py-3 flex items-center gap-3 text-left transition-colors",
                            isActive
                              ? "bg-primary/10 border-l-[3px] border-primary"
                              : "hover:bg-accent/50 border-l-[3px] border-transparent"
                          )}
                        >
                          {/* Completion icon */}
                          <div className="flex-shrink-0">
                            {passed ? (
                              <CheckCircle className="h-5 w-5 text-green-500" />
                            ) : (
                              <Circle className="h-5 w-5 text-muted-foreground" />
                            )}
                          </div>

                          {/* Quiz icon */}
                          <div className="flex-shrink-0">
                            <FileQuestion className="h-5 w-5 text-amber-500" />
                          </div>

                          {/* Quiz title + label */}
                          <span className="flex-1 min-w-0">
                            <span
                              className={cn(
                                "text-sm block truncate",
                                isActive ? "font-medium" : "",
                                passed ? "text-muted-foreground" : ""
                              )}
                            >
                              {quiz.title}
                            </span>
                            <span className="text-xs text-muted-foreground">
                              Unit Quiz · {quiz.points} pts
                            </span>
                          </span>
                        </button>
                      );
                    })}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

import { useState, useEffect } from 'react';
import { ChevronDown, ChevronRight, CheckCircle, Circle, PlayCircle, FileText } from 'lucide-react';
import { cn } from '@/lib/utils';

interface Lesson {
  id: number;
  title: string;
  video_type: 'none' | 'youtube' | 'vimeo';
  video_id: string | null;
  order: number;
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

interface CourseSidebarProps {
  units: Unit[];
  currentLessonId: number | null;
  onLessonSelect: (lessonId: number) => void;
  isCollapsed: boolean;
  onToggleCollapse: () => void;
  progressPercentage: number;
  completedCount: number;
  totalCount: number;
}

export function CourseSidebar({
  units,
  currentLessonId,
  onLessonSelect,
  isCollapsed,
  onToggleCollapse,
  progressPercentage,
  completedCount,
  totalCount,
}: CourseSidebarProps) {
  const [expandedUnits, setExpandedUnits] = useState<number[]>([]);

  // Auto-expand unit containing current lesson
  useEffect(() => {
    if (currentLessonId) {
      const unitWithLesson = units.find(unit =>
        unit.lessons.some(lesson => lesson.id === currentLessonId)
      );
      if (unitWithLesson && !expandedUnits.includes(unitWithLesson.id)) {
        setExpandedUnits(prev => [...prev, unitWithLesson.id]);
      }
    }
  }, [currentLessonId, units]);

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
      <div className="w-12 bg-card border-r flex flex-col items-center py-4">
        <button
          onClick={onToggleCollapse}
          className="p-2 hover:bg-accent rounded-md mb-4"
          title="Expand sidebar"
        >
          <ChevronRight className="h-4 w-4" />
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
    <div className="w-[380px] bg-card border-r flex flex-col h-full">
      {/* Header */}
      <div className="p-4 border-b">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-semibold text-sm">Course Content</h2>
          <button
            onClick={onToggleCollapse}
            className="p-1 hover:bg-accent rounded"
            title="Collapse sidebar"
          >
            <ChevronRight className="h-4 w-4 rotate-180" />
          </button>
        </div>

        {/* Progress bar */}
        <div className="space-y-1">
          <div className="h-2 bg-muted rounded-full overflow-hidden">
            <div
              className="h-full bg-primary transition-all duration-300"
              style={{ width: `${progressPercentage}%` }}
            />
          </div>
          <p className="text-xs text-muted-foreground">
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
                className="w-full px-4 py-3 flex items-center justify-between hover:bg-accent/50 transition-colors"
              >
                <div className="flex items-center gap-2 text-left">
                  {isExpanded ? (
                    <ChevronDown className="h-4 w-4 flex-shrink-0" />
                  ) : (
                    <ChevronRight className="h-4 w-4 flex-shrink-0" />
                  )}
                  <div>
                    <p className="font-medium text-sm">{unit.title}</p>
                    <p className="text-xs text-muted-foreground">
                      {completed}/{total} lessons
                    </p>
                  </div>
                </div>
                {completed === total && total > 0 && (
                  <CheckCircle className="h-4 w-4 text-green-500 flex-shrink-0" />
                )}
              </button>

              {/* Lessons list */}
              {isExpanded && (
                <div className="bg-muted/30">
                  {unit.lessons.map((lesson) => {
                    const isActive = lesson.id === currentLessonId;
                    const hasVideo = lesson.video_type !== 'none' && lesson.video_id;

                    return (
                      <button
                        key={lesson.id}
                        onClick={() => onLessonSelect(lesson.id)}
                        className={cn(
                          "w-full px-4 py-2 flex items-center gap-3 text-left transition-colors",
                          isActive
                            ? "bg-primary/10 border-l-2 border-primary"
                            : "hover:bg-accent/50 border-l-2 border-transparent"
                        )}
                      >
                        {/* Completion icon */}
                        <div className="flex-shrink-0">
                          {lesson.is_completed ? (
                            <CheckCircle className="h-4 w-4 text-green-500" />
                          ) : (
                            <Circle className="h-4 w-4 text-muted-foreground" />
                          )}
                        </div>

                        {/* Content type icon */}
                        <div className="flex-shrink-0">
                          {hasVideo ? (
                            <PlayCircle className="h-4 w-4 text-muted-foreground" />
                          ) : (
                            <FileText className="h-4 w-4 text-muted-foreground" />
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

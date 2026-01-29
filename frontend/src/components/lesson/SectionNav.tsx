import { ChevronLeft, ChevronRight } from 'lucide-react';
import { Button } from '@/components/ui/Button';

interface SectionNavProps {
  currentSection: number;
  totalSections: number;
  onNavigate: (index: number) => void;
  onComplete?: () => void;
  canComplete?: boolean;
  isLastSection?: boolean;
}

export function SectionNav({
  currentSection,
  totalSections,
  onNavigate,
  onComplete,
  canComplete = false,
  isLastSection = false,
}: SectionNavProps) {
  const hasPrevious = currentSection > 0;
  const hasNext = currentSection < totalSections - 1;

  return (
    <div className="flex items-center justify-between mt-6 pt-4 border-t">
      {/* Previous button */}
      <Button
        variant="outline"
        size="sm"
        onClick={() => onNavigate(currentSection - 1)}
        disabled={!hasPrevious}
        className="gap-2"
      >
        <ChevronLeft className="h-4 w-4" />
        <span className="hidden sm:inline">Previous</span>
      </Button>

      {/* Section indicators */}
      <div className="flex items-center gap-3">
        {/* Dot indicators */}
        <div className="flex items-center gap-1.5">
          {Array.from({ length: totalSections }, (_, i) => (
            <button
              key={i}
              onClick={() => onNavigate(i)}
              className={`w-2 h-2 rounded-full transition-all ${
                i === currentSection
                  ? 'bg-primary w-4'
                  : i < currentSection
                    ? 'bg-primary/50'
                    : 'bg-muted-foreground/30 hover:bg-muted-foreground/50'
              }`}
              title={`Section ${i + 1}`}
            />
          ))}
        </div>

        {/* Text indicator */}
        <span className="text-sm text-muted-foreground">
          {currentSection + 1} / {totalSections}
        </span>
      </div>

      {/* Next / Complete button */}
      {isLastSection && canComplete && onComplete ? (
        <Button size="sm" onClick={onComplete} className="gap-2">
          Complete
          <ChevronRight className="h-4 w-4" />
        </Button>
      ) : (
        <Button
          variant={hasNext ? 'default' : 'outline'}
          size="sm"
          onClick={() => onNavigate(currentSection + 1)}
          disabled={!hasNext}
          className="gap-2"
        >
          <span className="hidden sm:inline">Next</span>
          <ChevronRight className="h-4 w-4" />
        </Button>
      )}
    </div>
  );
}

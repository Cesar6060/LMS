import type { ReactNode } from 'react';
import { Button } from '@/components/ui/Button';
import { LessonMarkdown } from './LessonMarkdown';
import { Maximize, Minimize } from 'lucide-react';

interface SlideStageProps {
  /** Changes per page so the entry animation replays on navigation. */
  slideKey: number | string;
  title: string;
  content: string;
  /** Rendered above the content, inside the stage (the page's video block). */
  video?: ReactNode;
  /** Which way the deck moved — picks the slide-in direction. */
  direction: 'forward' | 'backward';
  isPresenting: boolean;
  onTogglePresent: () => void;
}

/**
 * Phase 60 — the slide-layout page renderer: a centered 16:9-ish stage with
 * scaled-up typography. Long content scrolls inside the stage body (decided in
 * scoping: no auto-fit/shrink). The width cap ties the stage to viewport
 * height so it keeps slide proportions beside the collapsible sidebar.
 */
export function SlideStage({
  slideKey,
  title,
  content,
  video,
  direction,
  isPresenting,
  onTogglePresent,
}: SlideStageProps) {
  return (
    <div className="h-full w-full flex items-center justify-center px-4 py-2 sm:px-6 sm:py-4">
      <div
        key={slideKey}
        className={`relative flex h-full w-full mx-auto max-w-[calc((100vh-10rem)*1.7778)] flex-col overflow-hidden rounded-xl border bg-card shadow-lg animate-in fade-in duration-300 ${
          direction === 'forward' ? 'slide-in-from-right-8' : 'slide-in-from-left-8'
        }`}
      >
        {/* No button where the Fullscreen API is unavailable (e.g. iPhone
            Safari) — presenting can't work there. */}
        {document.fullscreenEnabled && (
          <Button
            variant="outline"
            size="sm"
            onClick={onTogglePresent}
            className="absolute top-4 right-4 z-10 gap-2"
            aria-label={isPresenting ? 'Exit fullscreen (Esc)' : 'Present fullscreen (F)'}
            title={isPresenting ? 'Exit fullscreen (Esc)' : 'Present fullscreen (F)'}
          >
            {isPresenting ? <Minimize className="h-4 w-4" /> : <Maximize className="h-4 w-4" />}
            <span className="hidden md:inline">{isPresenting ? 'Exit' : 'Present'}</span>
          </Button>
        )}

        {/* Long content scrolls here, inside the stage. */}
        <div className="flex-1 overflow-y-auto px-8 py-8 sm:px-14 sm:py-12">
          {title && (
            <h3 className="text-3xl sm:text-4xl font-bold tracking-tight mb-8 pr-24">
              {title}
            </h3>
          )}

          {video && (
            <div className="mb-8 mx-auto w-full max-w-3xl">{video}</div>
          )}

          {content ? (
            <LessonMarkdown content={content} className="prose-lg sm:prose-xl" />
          ) : (
            !video && (
              <p className="text-muted-foreground text-lg">
                No content available for this page.
              </p>
            )
          )}
        </div>
      </div>
    </div>
  );
}

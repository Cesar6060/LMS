import type { ReactNode } from 'react';
import { LessonMarkdown } from './LessonMarkdown';

interface SlideStageProps {
  /** Changes per page so the entry animation replays on navigation. */
  slideKey: number | string;
  title: string;
  content: string;
  /** Rendered above the content, inside the stage (the page's video block). */
  video?: ReactNode;
  /**
   * Phase 61 — imported slide image. When set, the image fills the stage and
   * the title is suppressed (it's baked into the image).
   */
  image?: { url: string; alt: string };
  /** Which way the deck moved — picks the slide-in direction. */
  direction: 'forward' | 'backward';
}

/**
 * Phase 60 — the slide-layout page renderer: a centered 16:9 stage with
 * scaled-up typography. Long content scrolls inside the stage body (decided in
 * scoping: no auto-fit/shrink).
 *
 * Phase 62 — the 16:9 constraint is now relative to the stage's own box, not
 * the viewport. The old cap derived width from viewport height minus a fixed
 * chrome allowance, so anything that shrank the parent (a tall attachments
 * card) shortened the stage while it kept the viewport-derived width, and the
 * ratio broke. Now the card sets `aspect-video` with `height: auto`, so height
 * always follows from width; the only extra constraint is a width cap taken
 * from the wrapper's own height (`cqh`, hence `container-type: size`), which
 * binds when the box is wider than 16:9. Deliberately only ONE cross-axis
 * container-query cap: constraining both axes that way left Chrome resolving
 * one of them against a stale container size after a relayout. `max-h-full`
 * doesn't preserve the ratio — where container queries are unsupported it just
 * stops the card overflowing its box.
 *
 * Below `md` the ratio is dropped (`max-md:aspect-auto max-md:h-full`): a phone
 * in portrait is far taller than 16:9, so enforcing it would leave a ~220px
 * stage with `prose-lg` text scrolling inside. Presenting happens on laptops
 * and projectors, which is where true 16:9 earns its keep; phones keep the
 * fill-height reading view they had before. The Present button lives in the
 * player content area now (see PresentButton).
 */
export function SlideStage({
  slideKey,
  title,
  content,
  video,
  image,
  direction,
}: SlideStageProps) {
  return (
    <div className="h-full w-full flex items-center justify-center px-4 py-2 sm:px-6 sm:py-4 [container-type:size]">
      <div
        key={slideKey}
        className={`relative flex aspect-video h-auto max-h-full max-md:aspect-auto max-md:h-full w-full mx-auto max-w-[calc(100cqh*1.7778)] flex-col overflow-hidden rounded-xl border bg-card shadow-lg animate-in fade-in duration-300 ${
          direction === 'forward' ? 'slide-in-from-right-8' : 'slide-in-from-left-8'
        }`}
      >
        {image ? (
          /* Imported slide: the image IS the page (title baked in). A video
             on the same page still renders above it. */
          <div className="flex-1 min-h-0 flex flex-col items-center justify-center gap-4 p-4">
            {video && <div className="w-full max-w-3xl shrink-0">{video}</div>}
            <img
              src={image.url}
              alt={image.alt}
              className="min-h-0 w-full flex-1 object-contain"
            />
          </div>
        ) : (
          /* Long content scrolls here, inside the stage. */
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
        )}
      </div>
    </div>
  );
}

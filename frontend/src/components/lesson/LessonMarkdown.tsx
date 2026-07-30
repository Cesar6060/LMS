import { memo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';
import './lessonMarkdown.css';

interface LessonMarkdownProps {
  content: string;
  /** Extra classes on the prose wrapper, e.g. `prose-xl` for the slide stage. */
  className?: string;
}

// Phase 62 — hoisted to module scope on purpose: inline `[remarkGfm]` /
// `[rehypeHighlight]` literals are new arrays on every render, so ReactMarkdown
// would re-run its whole pipeline (including highlight.js) each time and the
// `memo` below would be a no-op.
const REMARK_PLUGINS = [remarkGfm];
const REHYPE_PLUGINS = [rehypeHighlight];

/**
 * Phase 60 — the one markdown renderer for lesson content: GFM plus
 * syntax-highlighted code fences (rehype-highlight's common-language bundle).
 * Used by the player (doc and slide layouts) and the SectionEditor previews so
 * instructors preview exactly what students see. Token colors live in
 * lessonMarkdown.css, scoped under `.lesson-markdown` (light/dark via the
 * `dark` class) so they never leak into other prose surfaces. Regenerate the
 * theme after a highlight.js bump with `npm run gen:hljs-theme`.
 *
 * Phase 62 — memoized: highlighting is the most expensive render in the editor,
 * and the previews now feed it a debounced value (see `hooks/useDebounce.ts`).
 */
export const LessonMarkdown = memo(function LessonMarkdown({
  content,
  className,
}: LessonMarkdownProps) {
  return (
    <div
      className={`lesson-markdown prose prose-neutral dark:prose-invert max-w-none ${className ?? ''}`}
    >
      <ReactMarkdown remarkPlugins={REMARK_PLUGINS} rehypePlugins={REHYPE_PLUGINS}>
        {content}
      </ReactMarkdown>
    </div>
  );
});

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';
import './lessonMarkdown.css';

interface LessonMarkdownProps {
  content: string;
  /** Extra classes on the prose wrapper, e.g. `prose-xl` for the slide stage. */
  className?: string;
}

/**
 * Phase 60 — the one markdown renderer for lesson content: GFM plus
 * syntax-highlighted code fences (rehype-highlight's common-language bundle).
 * Used by the player (doc and slide layouts) and the SectionEditor previews so
 * instructors preview exactly what students see. Token colors live in
 * lessonMarkdown.css, scoped under `.lesson-markdown` (light/dark via the
 * `dark` class) so they never leak into other prose surfaces. Regenerate the
 * theme after a highlight.js bump with `npm run gen:hljs-theme`.
 */
export function LessonMarkdown({ content, className }: LessonMarkdownProps) {
  return (
    <div
      className={`lesson-markdown prose prose-neutral dark:prose-invert max-w-none ${className ?? ''}`}
    >
      <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>
        {content}
      </ReactMarkdown>
    </div>
  );
}

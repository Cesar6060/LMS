/**
 * Paste-to-split parser (Phase 29).
 *
 * Splits a pasted markdown document into ordered lesson-section chunks on
 * `---` thematic-break lines. The parser is *code-fence aware*: a `---` line
 * inside a ``` or ~~~ fenced block does NOT split (important for code-heavy
 * courses). Each chunk is auto-titled from its first heading line.
 *
 * Pure and side-effect free so it can be unit-tested / previewed client-side
 * before anything is saved. See docs/specs/phase-29-authoring-efficiency.md.
 */

export interface SplitSection {
  title: string;
  content: string;
}

const FENCE_RE = /^\s*(```|~~~)/;
const DELIMITER_RE = /^\s*---\s*$/;
const HEADING_RE = /^\s*#{1,6}\s+(.+?)\s*$/;

/** Remove leading and trailing blank lines from a list of lines. */
function trimBlankLines(lines: string[]): string[] {
  let start = 0;
  let end = lines.length;
  while (start < end && lines[start].trim() === '') start++;
  while (end > start && lines[end - 1].trim() === '') end--;
  return lines.slice(start, end);
}

/**
 * Turn a block of raw lines into a {title, content} section, applying
 * auto-title extraction: if the first non-blank line is a heading, its text
 * becomes the title and that heading line is stripped from the body (so the
 * title does not render twice).
 */
function toSection(rawLines: string[]): SplitSection {
  const lines = trimBlankLines(rawLines);
  if (lines.length === 0) {
    return { title: '', content: '' };
  }

  const headingMatch = lines[0].match(HEADING_RE);
  if (headingMatch) {
    const body = trimBlankLines(lines.slice(1));
    return { title: headingMatch[1].trim(), content: body.join('\n') };
  }

  return { title: '', content: lines.join('\n') };
}

/**
 * Split a pasted markdown string into ordered sections.
 *
 * - `---` on its own line (outside a code fence) ends a chunk and starts the next.
 * - Delimiter lines are discarded.
 * - Empty / whitespace-only chunks are dropped (handles leading/trailing/
 *   consecutive delimiters).
 * - No delimiter → a single chunk. Empty input → empty list.
 */
export function splitSections(input: string): SplitSection[] {
  if (!input || input.trim() === '') {
    return [];
  }

  const lines = input.split('\n');
  const chunks: string[][] = [];
  let current: string[] = [];
  let inFence = false;

  for (const line of lines) {
    if (FENCE_RE.test(line)) {
      inFence = !inFence;
      current.push(line);
      continue;
    }

    if (!inFence && DELIMITER_RE.test(line)) {
      chunks.push(current);
      current = [];
      continue;
    }

    current.push(line);
  }
  chunks.push(current);

  return chunks
    .map(toSection)
    // Drop chunks with neither a title nor body (empty from stray delimiters).
    .filter((section) => section.title !== '' || section.content.trim() !== '');
}

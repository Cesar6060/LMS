// Generates a scoped light+dark highlight.js theme for LessonMarkdown.
// Light rules come from github.css scoped under .lesson-markdown;
// dark rules from github-dark.css scoped under .dark .lesson-markdown.
import { readFileSync, writeFileSync } from 'node:fs';

const strip = (css) => css.replace(/\/\*[\s\S]*?\*\//g, '');

function prefix(css, pre) {
  const out = [];
  const re = /([^{}]+)\{([^}]*)\}/g;
  let m;
  while ((m = re.exec(strip(css))) !== null) {
    const sels = m[1]
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);
    // Skip the base `pre code.hljs` layout rules — written once by hand.
    if (sels.some((s) => s === 'pre code.hljs' || s === 'code.hljs')) continue;
    out.push(`${sels.map((s) => `${pre} ${s}`).join(',\n')} {${m[2]}}`);
  }
  return out.join('\n');
}

const light = readFileSync('node_modules/highlight.js/styles/github.css', 'utf8');
const dark = readFileSync('node_modules/highlight.js/styles/github-dark.css', 'utf8');
const version = JSON.parse(
  readFileSync('node_modules/highlight.js/package.json', 'utf8')
).version;

const header = `/*
 * GENERATED — do not edit by hand.
 * Built from highlight.js@${version} github.css / github-dark.css, scoped under
 * .lesson-markdown so hljs token colors apply only inside LessonMarkdown and
 * never fight prose/prose-invert elsewhere. Regenerate with
 * scripts/gen-hljs-theme.mjs (see LessonMarkdown.tsx).
 */

/* Code-block surface: typography's :where() selectors lose to these, so the
 * pre background always matches the hljs theme in both modes. */
.lesson-markdown pre {
  background: #f6f8fa;
  color: #24292e;
}
.dark .lesson-markdown pre {
  background: #161b22;
  color: #c9d1d9;
}
.lesson-markdown pre code.hljs,
.dark .lesson-markdown pre code.hljs {
  display: block;
  overflow-x: auto;
  padding: 0;
  background: transparent;
}
`;

writeFileSync(
  'src/components/lesson/lessonMarkdown.css',
  `${header}\n${prefix(light, '.lesson-markdown')}\n\n${prefix(dark, '.dark .lesson-markdown')}\n`
);
console.log('written src/components/lesson/lessonMarkdown.css');

import { describe, expect, it } from 'vitest';
import { splitSections } from './splitSections';

/**
 * The paste-to-split parser (phase 29). The interesting behaviour is the
 * code-fence awareness — a `---` inside a fenced block must not split, which
 * matters a lot for a Java course full of code samples.
 */
describe('splitSections', () => {
  it('returns nothing for empty or whitespace-only input', () => {
    expect(splitSections('')).toEqual([]);
    expect(splitSections('   \n\n  ')).toEqual([]);
  });

  it('returns a single untitled section when there is no delimiter or heading', () => {
    expect(splitSections('just some prose')).toEqual([
      { title: '', content: 'just some prose' },
    ]);
  });

  it('splits on a --- line and drops the delimiter', () => {
    expect(splitSections('one\n---\ntwo')).toEqual([
      { title: '', content: 'one' },
      { title: '', content: 'two' },
    ]);
  });

  it('auto-titles from a leading heading and strips it from the body', () => {
    expect(splitSections('# Hello World\n\nSome body text')).toEqual([
      { title: 'Hello World', content: 'Some body text' },
    ]);
  });

  it('accepts any heading level', () => {
    expect(splitSections('###### Deep\nbody')[0].title).toBe('Deep');
  });

  it('only auto-titles from the first line, not a later heading', () => {
    const [section] = splitSections('intro text\n# Not A Title\nmore');
    expect(section.title).toBe('');
    expect(section.content).toBe('intro text\n# Not A Title\nmore');
  });

  it('does not split on a --- inside a ``` code fence', () => {
    const input = [
      '# Code sample',
      '```java',
      'int a = 1;',
      '---',
      'int b = 2;',
      '```',
      'trailing prose',
    ].join('\n');

    const sections = splitSections(input);
    expect(sections).toHaveLength(1);
    expect(sections[0].title).toBe('Code sample');
    expect(sections[0].content).toContain('---');
  });

  it('does not split on a --- inside a ~~~ code fence', () => {
    const input = ['~~~', 'a', '---', 'b', '~~~'].join('\n');
    expect(splitSections(input)).toHaveLength(1);
  });

  it('splits again once the fence has closed', () => {
    const input = [
      '# One',
      '```',
      '---',
      '```',
      '---',
      '# Two',
      'body',
    ].join('\n');

    const sections = splitSections(input);
    expect(sections.map(s => s.title)).toEqual(['One', 'Two']);
  });

  it('drops empty chunks from leading, trailing and consecutive delimiters', () => {
    expect(splitSections('---\n---\none\n---\n---\ntwo\n---')).toEqual([
      { title: '', content: 'one' },
      { title: '', content: 'two' },
    ]);
  });

  it('trims blank lines around each chunk', () => {
    const [section] = splitSections('\n\n\nbody\n\n\n');
    expect(section.content).toBe('body');
  });

  it('keeps a heading-only section with an empty body', () => {
    expect(splitSections('# Just A Title')).toEqual([
      { title: 'Just A Title', content: '' },
    ]);
  });

  it('preserves order across many sections', () => {
    const input = ['# A', '---', '# B', '---', '# C'].join('\n');
    expect(splitSections(input).map(s => s.title)).toEqual(['A', 'B', 'C']);
  });

  it('tolerates leading whitespace on the delimiter', () => {
    expect(splitSections('one\n  ---  \ntwo')).toHaveLength(2);
  });
});

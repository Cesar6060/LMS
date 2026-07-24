import { describe, expect, it } from 'vitest';
import { extractYouTubeVideoId } from './video';

/**
 * The phase 52 bug lived here: a valid share URL was stored raw instead of
 * being reduced to its 11-char ID. These pin the accepted shapes and, just as
 * importantly, that anything unparseable returns null so the caller blocks the
 * save rather than storing junk.
 *
 * Mirrors backend/courses/video.py — the two must agree.
 */
const ID = 'dQw4w9WgXcQ';

describe('extractYouTubeVideoId', () => {
  it('passes a bare 11-char id straight through', () => {
    expect(extractYouTubeVideoId(ID)).toBe(ID);
  });

  it('trims surrounding whitespace', () => {
    expect(extractYouTubeVideoId(`  ${ID}  `)).toBe(ID);
  });

  it.each([
    ['watch URL', `https://www.youtube.com/watch?v=${ID}`],
    ['watch URL without www', `https://youtube.com/watch?v=${ID}`],
    ['mobile watch URL', `https://m.youtube.com/watch?v=${ID}`],
    ['watch URL with v not first', `https://www.youtube.com/watch?t=42&v=${ID}`],
    ['watch URL with tracking suffix', `https://www.youtube.com/watch?v=${ID}&si=aB3dEfGhIjKl`],
    ['youtu.be short link', `https://youtu.be/${ID}`],
    ['youtu.be with tracking', `https://youtu.be/${ID}?si=TrAcKiNg42`],
    ['shorts URL', `https://www.youtube.com/shorts/${ID}`],
    ['live URL', `https://www.youtube.com/live/${ID}`],
    ['embed URL', `https://www.youtube.com/embed/${ID}`],
    ['scheme-less host', `youtube.com/watch?v=${ID}`],
  ])('extracts the id from a %s', (_label, input) => {
    expect(extractYouTubeVideoId(input)).toBe(ID);
  });

  it.each([
    ['empty string', ''],
    ['a non-YouTube host', 'https://example.com/watch?v=dQw4w9WgXcQ'],
    ['vimeo', 'https://vimeo.com/123456789'],
    ['a watch URL with no v param', 'https://www.youtube.com/watch?t=42'],
    ['a too-short id', 'https://www.youtube.com/watch?v=abc'],
    ['a too-long id', 'https://www.youtube.com/watch?v=dQw4w9WgXcQextra'],
    ['an id with invalid characters', 'https://www.youtube.com/watch?v=dQw4w9WgX!Q'],
    ['a bare channel URL', 'https://www.youtube.com/@somechannel'],
    ['unparseable junk', 'not a url at all'],
  ])('returns null for %s', (_label, input) => {
    expect(extractYouTubeVideoId(input)).toBeNull();
  });

  it('does not treat a 11-char path segment on a foreign host as an id', () => {
    expect(extractYouTubeVideoId(`https://evil.example/${ID}`)).toBeNull();
  });
});

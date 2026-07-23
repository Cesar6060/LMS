/**
 * Extract the 11-char YouTube video ID from a URL or bare ID.
 * Mirrors backend/courses/video.py; keep the two in sync.
 *
 * Accepts watch?v= (v anywhere in the query), youtu.be, shorts/, live/,
 * embed/ URLs (www./m./bare hosts), and a bare 11-char ID.
 * Returns null when no ID can be extracted — callers must block the save
 * and surface an error instead of storing the raw input.
 */
const VIDEO_ID_RE = /^[A-Za-z0-9_-]{11}$/;
const PATH_RE = /^\/(?:shorts|live|embed)\/([A-Za-z0-9_-]{11})(?:\/|$)/;
const YOUTUBE_HOSTS = ['youtube.com', 'm.youtube.com'];

export function extractYouTubeVideoId(input: string): string | null {
  if (!input) return null;
  const trimmed = input.trim();

  if (VIDEO_ID_RE.test(trimmed)) return trimmed;

  let url: URL;
  try {
    url = new URL(trimmed.includes('//') ? trimmed : `https://${trimmed}`);
  } catch {
    return null;
  }
  const host = url.hostname.toLowerCase().replace(/^www\./, '');

  if (host === 'youtu.be') {
    const candidate = url.pathname.split('/')[1] ?? '';
    return VIDEO_ID_RE.test(candidate) ? candidate : null;
  }

  if (!YOUTUBE_HOSTS.includes(host)) return null;

  if (url.pathname === '/watch') {
    const candidate = url.searchParams.get('v') ?? '';
    return VIDEO_ID_RE.test(candidate) ? candidate : null;
  }

  const match = url.pathname.match(PATH_RE);
  return match ? match[1] : null;
}

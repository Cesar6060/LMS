"""YouTube video-ID extraction — server-side source of truth.

Mirrors frontend/src/lib/video.ts; keep the two in sync.
"""
import re
from urllib.parse import parse_qs, urlparse

VIDEO_ID_RE = re.compile(r'^[A-Za-z0-9_-]{11}$')
_PATH_RE = re.compile(r'^/(?:shorts|live|embed)/([A-Za-z0-9_-]{11})(?:[/?]|$)')
_YOUTUBE_HOSTS = {'youtube.com', 'm.youtube.com'}


def extract_youtube_video_id(value) -> str | None:
    """Return the 11-char YouTube video ID from a URL or bare ID, else None.

    Accepts watch?v= (v anywhere in the query), youtu.be, shorts/, live/,
    embed/ URLs (www./m./bare hosts), and a bare 11-char ID.
    """
    if not value or not isinstance(value, str):
        return None
    value = value.strip()

    if VIDEO_ID_RE.match(value):
        return value

    parsed = urlparse(value if '//' in value else f'https://{value}')
    host = parsed.netloc.lower().removeprefix('www.')

    if host == 'youtu.be':
        candidate = parsed.path.lstrip('/').split('/')[0]
        return candidate if VIDEO_ID_RE.match(candidate) else None

    if host not in _YOUTUBE_HOSTS:
        return None

    if parsed.path == '/watch':
        candidate = parse_qs(parsed.query).get('v', [''])[0]
        return candidate if VIDEO_ID_RE.match(candidate) else None

    match = _PATH_RE.match(parsed.path)
    return match.group(1) if match else None

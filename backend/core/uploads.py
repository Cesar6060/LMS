"""Content verification for uploaded files, and download-safe URLs.

Phase 73. The avatar and slide-import endpoints already confirmed that an
upload's *bytes* match its claimed extension; lesson attachments checked only
the extension and the size, both of which are client-supplied strings. This
module holds the shared checks so the three paths cannot drift apart again.

The threat here is not "a .py file executes on our server" — attachments live
in a private R2 bucket on a different origin and are handed out as presigned
URLs, so nothing uploaded is reachable as same-origin script. It is that a
file's *name* is the only thing a student sees before opening it. An executable
or an HTML page named `homework.pdf` is a phishing primitive aimed at the
class, and the extension allowlist alone cannot tell the difference.

Code and plain-text types stay allowed on purpose: this platform teaches Python
and game development, so .py/.js/.json/.zip are ordinary course material.
"""

import logging
import re

logger = logging.getLogger(__name__)


# Formats Pillow should be able to open, keyed by the extension claimed. The
# detected format is pinned against the extension rather than merely "is an
# image", so untrusted bytes only ever reach the handful of decoders below —
# the less-common codecs are where most image-library CVEs live.
IMAGE_EXTENSION_FORMATS = {
    'png': {'PNG'},
    'jpg': {'JPEG'},
    'jpeg': {'JPEG'},
    'gif': {'GIF'},
    'webp': {'WEBP'},
}

# Leading byte signatures for the non-image formats that have one. A tuple means
# any of the alternatives is acceptable. Formats whose magic is not at offset 0
# are handled separately below.
MAGIC_SIGNATURES = {
    'pdf': (b'%PDF-',),
    # OOXML is a zip container, so docx/pptx/xlsx share the zip signature.
    'zip': (b'PK\x03\x04', b'PK\x05\x06', b'PK\x07\x08'),
    'docx': (b'PK\x03\x04',),
    'pptx': (b'PK\x03\x04',),
    'xlsx': (b'PK\x03\x04',),
    # Legacy Office is OLE2 compound storage.
    'doc': (b'\xd0\xcf\x11\xe0',),
    'ppt': (b'\xd0\xcf\x11\xe0',),
    'xls': (b'\xd0\xcf\x11\xe0',),
    'rar': (b'Rar!\x1a\x07',),
    '7z': (b'7z\xbc\xaf\x27\x1c',),
    'webm': (b'\x1a\x45\xdf\xa3',),
    'wav': (b'RIFF',),
    'mp3': (b'ID3', b'\xff\xfb', b'\xff\xf3', b'\xff\xf2'),
}

# ISO base-media containers put 'ftyp' at offset 4, not 0.
FTYP_EXTENSIONS = {'mp4', 'mov'}

# Extensions whose contents are text by definition. There is no signature to
# check, so the test is the inverse: they must NOT be a binary wearing a text
# extension. Course material lives here — .py and .js especially.
TEXT_EXTENSIONS = {'txt', 'md', 'csv', 'py', 'js', 'css', 'json'}

# Signatures that are never acceptable whatever the extension says. These are
# the payloads worth disguising: native executables, and HTML (which would be a
# stored-XSS vector anywhere the bucket is served same-origin).
EXECUTABLE_SIGNATURES = (
    b'MZ',                 # DOS/PE — .exe, .dll
    b'\x7fELF',            # ELF — Linux binaries
    b'\xca\xfe\xba\xbe',   # Mach-O fat / Java class
    b'\xcf\xfa\xed\xfe',   # Mach-O 64-bit
    b'\xfe\xed\xfa\xce',   # Mach-O 32-bit
    b'#!',                 # shebang script
)

HTML_MARKERS = (b'<!doctype html', b'<html', b'<script', b'<svg')

_HEADER_BYTES = 512


def _read_header(upload):
    """Read the leading bytes without disturbing the caller's file position."""
    upload.seek(0)
    header = upload.read(_HEADER_BYTES)
    upload.seek(0)
    return header


def verify_image(upload, ext):
    """Confirm the bytes decode as the image format the extension claims.

    Returns an error string, or None when the file is acceptable.
    """
    from PIL import Image

    # Pillow raises a broad, undocumented set of exceptions on malformed input
    # (OSError, SyntaxError, DecompressionBomb, struct errors from plugins), so
    # catch Exception rather than try to enumerate them. `.format` must be read
    # BEFORE verify(), which leaves the Image unusable.
    try:
        upload.seek(0)
        image = Image.open(upload)
        detected = image.format
        image.verify()
    except Exception:
        return f'"{upload.name}" is not a valid image file.'
    finally:
        upload.seek(0)

    if detected not in IMAGE_EXTENSION_FORMATS[ext]:
        return (
            f'"{upload.name}" contains {detected or "an unknown format"}, '
            f'which does not match its ".{ext}" extension.'
        )
    return None


def verify_upload(upload, ext):
    """Check an upload's contents against its claimed extension.

    Returns an error string, or None when the file is acceptable. Extensions
    with no known signature (the text and code types) are accepted as long as
    they are not a disguised executable or HTML document.
    """
    header = _read_header(upload)
    if not header:
        return f'"{upload.name}" is empty.'

    lowered = header.lstrip().lower()
    if any(lowered.startswith(marker) for marker in HTML_MARKERS):
        return (
            f'"{upload.name}" contains HTML. Upload it as a .txt or .zip so it '
            f'cannot be opened as a web page.'
        )

    if ext in IMAGE_EXTENSION_FORMATS:
        return verify_image(upload, ext)

    if ext in FTYP_EXTENSIONS:
        if header[4:8] != b'ftyp':
            return _mismatch(upload, ext)
        return None

    if ext in MAGIC_SIGNATURES:
        if not header.startswith(MAGIC_SIGNATURES[ext]):
            return _mismatch(upload, ext)
        return None

    if ext in TEXT_EXTENSIONS:
        if header.startswith(EXECUTABLE_SIGNATURES):
            return _mismatch(upload, ext)
        # A NUL byte in the first block means this is not the text file it
        # claims to be. Real source and prose never contain one.
        if b'\x00' in header:
            return _mismatch(upload, ext)
        return None

    # An extension in the allowlist but absent from every table above: fail
    # closed rather than let a new allowlist entry silently skip verification.
    logger.warning('No content check defined for uploaded extension %r', ext)
    return _mismatch(upload, ext)


def _mismatch(upload, ext):
    return (
        f'"{upload.name}" does not look like a ".{ext}" file. Its contents do '
        f'not match its extension.'
    )


# Strip anything that could break out of the quoted filename in a
# Content-Disposition header, or smuggle a second header in.
_UNSAFE_FILENAME = re.compile(r'[^A-Za-z0-9 ._()\[\]-]')


def download_url(filefield, filename=None):
    """URL that downloads the file rather than rendering it in the browser.

    On S3/R2 the disposition rides on the presigned URL, so it cannot be
    stripped by re-requesting the object without a fresh signature. Storages
    whose url() takes no parameters (FileSystemStorage in local dev) fall back
    to the plain URL.
    """
    if not filefield:
        return None

    safe = _UNSAFE_FILENAME.sub('_', filename or '').strip() or 'download'
    disposition = f'attachment; filename="{safe}"'
    try:
        return filefield.storage.url(
            filefield.name,
            parameters={'ResponseContentDisposition': disposition},
        )
    except TypeError:
        return filefield.url

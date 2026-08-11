"""Content verification for uploads (phase 73, task D).

The HTML cases came out of the phase's adversarial pass, which got an
`<iframe src="javascript:...">` stored as a .txt attachment through the first
implementation: it matched four tag names and `<iframe` was not one of them.

The list is now wider but still not the full browser sniffing set, and both
halves are pinned here on purpose. Widening it to every sniffable tag was tried
and rejected in review: `<div`, `<p`, `<br`, `<table` are how ordinary markdown
begins, and refusing a lesson handout to defend a path already closed by the
download disposition is a bad trade. So the accepted-cases tests below are as
load-bearing as the rejected ones — they are what stops the next person
"hardening" this back into a false positive.
"""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from core.uploads import download_url, verify_upload


def upload(name, content, content_type='application/octet-stream'):
    return SimpleUploadedFile(name, content, content_type=content_type)


# --- HTML sniffing -------------------------------------------------------


@pytest.mark.parametrize('payload', [
    b'<iframe src="javascript:alert(document.cookie)"></iframe>',
    b'<body onload="alert(1)">',
    b'<meta http-equiv="refresh" content="0;url=http://evil.example">',
    b'<script>alert(1)</script>',
    b'<html><head></head></html>',
    b'<!doctype html><p>hi',
    b'<svg onload="alert(1)">',
    b'<style>@import url(http://evil.example)</style>',
    b'<title>x</title>',
    b'<object data="evil.swf">',
    b'<embed src="evil.swf">',
    b'<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg">',
])
def test_html_payloads_are_rejected_whatever_the_tag(payload):
    assert verify_upload(upload('notes.txt', payload), 'txt') is not None


@pytest.mark.parametrize('prefix', [
    b'',
    b'   ',
    b'\n\r\t',
    b'\xef\xbb\xbf',          # UTF-8 BOM — browsers strip it before sniffing
    b'\xef\xbb\xbf   ',
])
def test_leading_bytes_do_not_smuggle_html_past_the_check(prefix):
    payload = prefix + b'<iframe src="javascript:alert(1)"></iframe>'

    assert verify_upload(upload('notes.txt', payload), 'txt') is not None


@pytest.mark.parametrize('ext', ['txt', 'py', 'js', 'md', 'csv', 'json'])
def test_html_is_rejected_for_every_text_extension(ext):
    payload = b'<body onload="alert(1)">'

    assert verify_upload(upload(f'file.{ext}', payload), ext) is not None


# --- and the inverse: ordinary course material still uploads -------------


@pytest.mark.parametrize('name,payload,ext', [
    ('starter.py', b'import pygame\n\n\ndef main():\n    pass\n', 'py'),
    ('main.js', b'export function run() {\n  return 1;\n}\n', 'js'),
    ('data.json', b'{"level": 1, "items": []}', 'json'),
    ('notes.md', b'# Lesson 1\n\nOpen the editor and press Run.\n', 'md'),
    ('scores.csv', b'name,score\nada,10\n', 'csv'),
    ('readme.txt', b'Remember to save your work.\n', 'txt'),
])
def test_ordinary_course_material_is_accepted(name, payload, ext):
    assert verify_upload(upload(name, payload), ext) is None


def test_tag_names_are_not_matched_as_prefixes_of_longer_words():
    """A marker must not swallow prose that merely starts with '<'."""
    assert verify_upload(upload('notes.txt', b'<answer> goes here'), 'txt') is None
    assert verify_upload(upload('notes.txt', b'<metadata> notes'), 'txt') is None


# Markdown routinely opens with raw HTML — a centred heading, a badge block.
# Refusing those broke real course material to defend a path already closed by
# the download disposition, so the marker list stops at tags that carry or load
# something.
@pytest.mark.parametrize('payload', [
    b'<div align="center">\n\n# Lesson 1\n',
    b'<p>Intro paragraph</p>\n',
    b'<br>\n\nNotes follow\n',
    b'<!-- lesson notes -->\n# Heading\n',
    b'<table><tr><td>data</td></tr></table>',
    b'<a href="https://docs.python.org">docs</a>',
])
def test_markdown_opening_with_ordinary_html_is_accepted(payload):
    assert verify_upload(upload('lesson.md', payload), 'md') is None


# --- the shebang regression ---------------------------------------------


@pytest.mark.parametrize('name,payload,ext', [
    ('starter.py', b'#!/usr/bin/env python3\nimport pygame\n', 'py'),
    ('run.js', b'#!/usr/bin/env node\nconsole.log(1)\n', 'js'),
    ('build.sh', b'#!/bin/sh\necho hi\n', 'txt'),
])
def test_shebang_scripts_are_accepted(name, payload, ext):
    """`#!` was in EXECUTABLE_SIGNATURES and rejected every runnable starter
    script — the exact material task D decided to keep uploadable."""
    assert verify_upload(upload(name, payload), ext) is None


def test_utf16_text_is_accepted():
    """Notepad's "Unicode" save interleaves NUL bytes; the BOM says why."""
    payload = b'\xff\xfe' + 'hello world'.encode('utf-16-le')

    assert verify_upload(upload('notes.txt', payload), 'txt') is None


# --- disguised binaries --------------------------------------------------


@pytest.mark.parametrize('payload', [
    b'MZ\x90\x00' + b'\x00' * 100,          # PE executable
    b'\x7fELF\x02\x01\x01' + b'\x00' * 100,  # ELF
    b'\xcf\xfa\xed\xfe' + b'\x00' * 100,     # Mach-O
])
def test_executables_renamed_as_text_are_rejected(payload):
    assert verify_upload(upload('solution.py', payload), 'py') is not None


def test_signature_mismatch_is_rejected():
    assert verify_upload(upload('doc.pdf', b'not a pdf at all'), 'pdf') is not None


def test_real_pdf_header_is_accepted():
    assert verify_upload(upload('doc.pdf', b'%PDF-1.7\n%\xe2\xe3\xcf\xd3\n'), 'pdf') is None


def test_empty_file_is_rejected():
    assert verify_upload(upload('empty.txt', b''), 'txt') is not None


def test_unknown_extension_fails_closed():
    """A new allowlist entry must not skip verification by omission."""
    assert verify_upload(upload('thing.xyz', b'anything'), 'xyz') is not None


# --- download disposition ------------------------------------------------


def test_download_url_falls_back_when_storage_takes_no_parameters():
    """FileSystemStorage.url() has no `parameters` kwarg; local dev must not
    500 because production storage does."""
    class DummyStorage:
        def url(self, name):
            return f'/media/{name}'

    class DummyFile:
        name = 'lesson_attachments/notes.txt'
        storage = DummyStorage()
        url = '/media/lesson_attachments/notes.txt'

        def __bool__(self):
            return True

    assert download_url(DummyFile(), 'notes.txt') == '/media/lesson_attachments/notes.txt'


# Unsafe characters are replaced rather than dropped, so two different uploads
# cannot collapse into the same displayed name.
@pytest.mark.parametrize('filename,expected', [
    ('notes.txt', 'attachment; filename="notes.txt"'),
    ('a"; rm -rf /; x="', 'attachment; filename="a__ rm -rf __ x__"'),
    ('has\r\nnewlines.txt', 'attachment; filename="has__newlines.txt"'),
    ('', 'attachment; filename="download"'),
])
def test_download_disposition_filename_cannot_break_the_header(filename, expected):
    captured = {}

    class DummyStorage:
        def url(self, name, parameters=None):
            captured.update(parameters or {})
            return 'https://r2.example/signed'

    class DummyFile:
        name = 'lesson_attachments/x'
        storage = DummyStorage()

        def __bool__(self):
            return True

    download_url(DummyFile(), filename)

    assert captured['ResponseContentDisposition'] == expected
    # The disposition and the type together are the control that actually keeps
    # an upload from rendering; the content checks on the way in are the second
    # layer, not this one.
    assert captured['ResponseContentType'] == 'application/octet-stream'

"""One-shot rewrite of the two seed blueprints onto author-chosen content keys.

Lesson keys are derived from the lesson title (lowercase, hyphenated,
course-prefixed) with no unit or lesson number in them, so a lesson can move
between units without becoming new content. Quiz keys follow
`<course>-quiz-<unit topic>` and are hand-authored below.

Once written, a key is permanent: changing one re-awards its XP.
"""
import re
import pathlib

QUIZ_KEYS = {
    # ROB101 — one unit quiz per unit, keyed by the unit's topic.
    'Unit 1 Quiz: Robots, Careers & Teamwork': 'rob101-quiz-robots-careers-teamwork',
    'Safety, Tools & Project Management Quiz': 'rob101-quiz-safety-tools-project-management',
    'Mechanisms & Physics of Motion Quiz': 'rob101-quiz-mechanisms-physics-of-motion',
    'Sensors, Systems & Feedback Quiz': 'rob101-quiz-sensors-systems-feedback',
    'Programming Robots Quiz': 'rob101-quiz-programming-robots',
    'Engineering Design Capstone Quiz': 'rob101-quiz-engineering-design-capstone',
    # JAVA101
    'Program Structure Quiz': 'java101-quiz-program-structure',
    'Variables & Operators Quiz': 'java101-quiz-variables-operators',
    'Working with Text Quiz': 'java101-quiz-working-with-text',
    'Control Flow Quiz': 'java101-quiz-control-flow',
    'Methods Quiz': 'java101-quiz-methods',
}

TARGETS = [
    ('courses/management/commands/populate_robotics_course.py', 'rob101'),
    ('courses/management/commands/populate_java_course.py', 'java101'),
]

# title='...' or title="..." — both appear in the blueprints.
TITLE = r"""(?:'([^']*)'|"([^"]*)")"""


def lesson_slug(title, prefix):
    t = title.lower().replace('&', ' and ').replace("'", '')
    t = re.sub(r'[^a-z0-9]+', '-', t).strip('-')
    return f'{prefix}-{t}'


def quote(value):
    """Re-emit a Python string literal preserving the original quote style."""
    return f'"{value}"' if "'" in value else f"'{value}'"


def convert(path, prefix):
    source = pathlib.Path(path)
    text = source.read_text()
    stats = {'units': 0, 'lessons': 0, 'quizzes': 0}
    seen_keys = set()

    # --- Units: Unit.objects.create(course=course, title=..., order=N) ------
    def unit_repl(m):
        stats['units'] += 1
        title = m.group(1) if m.group(1) is not None else m.group(2)
        return f'self._unit(course, {m.group(3)}, {quote(title)})'

    text = re.sub(
        rf'Unit\.objects\.create\(course=course, title={TITLE}, order=(\d+)\)',
        unit_repl, text,
    )

    # --- Lessons, single line ----------------------------------------------
    def lesson_one_line(m):
        stats['lessons'] += 1
        title = m.group(1) if m.group(1) is not None else m.group(2)
        key = lesson_slug(title, prefix)
        assert key not in seen_keys, f'duplicate lesson key {key}'
        seen_keys.add(key)
        return (
            f"self._lesson(\n"
            f"            unit, '{key}', {m.group(3)}, title={quote(title)},\n"
            f"        )"
        )

    text = re.sub(
        rf'Lesson\.objects\.create\(unit=unit, title={TITLE}, order=(\d+)\)',
        lesson_one_line, text,
    )

    # --- Lessons, wrapped over three lines ---------------------------------
    def lesson_wrapped(m):
        stats['lessons'] += 1
        title = m.group(1) if m.group(1) is not None else m.group(2)
        key = lesson_slug(title, prefix)
        assert key not in seen_keys, f'duplicate lesson key {key}'
        seen_keys.add(key)
        return (
            f"self._lesson(\n"
            f"            unit, '{key}', {m.group(3)}, title={quote(title)},\n"
            f"        )"
        )

    text = re.sub(
        rf'Lesson\.objects\.create\(\s*\n\s*unit=unit, title={TITLE}, order=(\d+)\s*\n\s*\)',
        lesson_wrapped, text,
    )

    # --- Quizzes: multi-line kwargs block -----------------------------------
    def quiz_repl(m):
        stats['quizzes'] += 1
        title = m.group(1) if m.group(1) is not None else m.group(2)
        key = QUIZ_KEYS[title]
        assert key not in seen_keys, f'duplicate quiz key {key}'
        seen_keys.add(key)
        body = m.group(3)
        # Pull `order=N` out of the kwargs; it becomes a positional argument.
        order_match = re.search(r'\n\s*order=(\d+),?', body)
        order = order_match.group(1)
        body = body[:order_match.start()] + body[order_match.end():]
        body = body.rstrip().rstrip(',')
        return (
            f"self._quiz(\n"
            f"            unit, '{key}', {order},\n"
            f"            title={quote(title)},{body},\n"
            f"        )"
        )

    text = re.sub(
        rf'Quiz\.objects\.create\(\s*\n\s*unit=unit,\s*\n\s*title={TITLE},((?:\n\s*\w+=[^\n]*)+)\s*\n\s*\)',
        quiz_repl, text,
    )

    source.write_text(text)
    return stats


for path, prefix in TARGETS:
    print(prefix, convert(path, prefix))

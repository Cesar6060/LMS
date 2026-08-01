"""
Read-only report on the state of the XP ledger.

Phase 65 stopped content rebuilds from re-awarding XP, but it deliberately did
NOT repair the damage already done — deciding what to do about inflated totals
needs numbers first, and taking XP back from a student is not a decision a
migration should make quietly. This command produces those numbers.

It NEVER writes, never prompts, and always exits 0, so it is safe to point at
production. Four reports:

* orphans      — XPEvents whose lesson/quiz no longer exists
* ledger drift — sum(XPEvent.amount) vs the denormalized GameProfile.total_xp
* amount drift — rows whose amount no longer matches the XP constant
* duplicates   — keys held by more than one live row, and ROB101/JAVA101
                 content still on an auto: key (adoption did not take)

Usage:
    python manage.py audit_xp
    python manage.py audit_xp --user student@example.com
    python manage.py audit_xp --verbose
"""
from collections import defaultdict

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db.models import Count, Sum

from courses.models import Lesson
from quizzes.models import Quiz

from gamification.leveling import level_for_xp
from gamification.models import GameProfile, XPEvent
from gamification.services import XP_LESSON, XP_QUIZ, XP_LESSON_QUIZ

User = get_user_model()

SEEDED_COURSE_CODES = ['ROB101', 'JAVA101']

EXPECTED_AMOUNT = {
    XPEvent.SOURCE_LESSON: XP_LESSON,
    XPEvent.SOURCE_QUIZ: XP_QUIZ,
    XPEvent.SOURCE_LESSON_QUIZ: XP_LESSON_QUIZ,
}


class Command(BaseCommand):
    help = (
        'Read-only audit of the XP ledger: orphaned events, ledger drift, '
        'amount drift and duplicate/unadopted content keys. Writes nothing.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--user', dest='user_email', default=None,
            help='Scope the per-student reports to one email address.',
        )
        parser.add_argument(
            '--verbose', action='store_true',
            help='Print per-row detail instead of just the summary table.',
        )

    def handle(self, *args, **options):
        self.verbose = options['verbose']
        email = options['user_email']

        events = XPEvent.objects.all()
        profiles = GameProfile.objects.select_related('user')
        if email:
            user = User.objects.filter(email=email).first()
            if user is None:
                self.stdout.write(self.style.WARNING(
                    f'No user with email {email}; per-student reports are empty.'
                ))
                events = events.none()
                profiles = profiles.none()
            else:
                events = events.filter(user=user)
                profiles = profiles.filter(user=user)
            self.stdout.write(f'Scoped to {email}\n')

        self._header('XP LEDGER AUDIT (read-only)')
        self._orphan_report(events)
        self._ledger_drift_report(profiles)
        self._amount_drift_report(events)
        self._content_key_report()

        self.stdout.write('\nNothing was modified.')

    # -- helpers ------------------------------------------------------------

    def _header(self, text):
        self.stdout.write('')
        self.stdout.write('=' * 68)
        self.stdout.write(text)
        self.stdout.write('=' * 68)

    def _section(self, text):
        self.stdout.write('')
        self.stdout.write(f'-- {text} ' + '-' * max(0, 64 - len(text)))

    def _live_keys_and_ids(self):
        """Content keys and primary keys of every live lesson and quiz."""
        lesson_keys = set(
            Lesson.objects.exclude(content_key=None)
            .values_list('content_key', flat=True)
        )
        quiz_keys = set(
            Quiz.objects.exclude(content_key=None)
            .values_list('content_key', flat=True)
        )
        lesson_ids = set(Lesson.objects.values_list('id', flat=True))
        quiz_ids = set(Quiz.objects.values_list('id', flat=True))
        return lesson_keys, quiz_keys, lesson_ids, quiz_ids

    # -- reports ------------------------------------------------------------

    def _orphan_report(self, events):
        """
        XPEvents whose source is gone.

        Existence is decided by looking the source up, NOT by the ``orphan:``
        prefix, so this is correct whether or not the backfill has run — and it
        still catches content deleted after the backfill.
        """
        self._section('ORPHANED XP EVENTS (source lesson/quiz no longer exists)')
        lesson_keys, quiz_keys, lesson_ids, quiz_ids = self._live_keys_and_ids()

        per_user = defaultdict(lambda: {'count': 0, 'xp': 0})
        total_count = 0
        total_xp = 0

        rows = events.select_related('user').order_by('user__email', 'id')
        for event in rows:
            if event.source_type == XPEvent.SOURCE_QUIZ:
                keys, ids = quiz_keys, quiz_ids
            else:
                keys, ids = lesson_keys, lesson_ids

            alive = (event.source_key in keys) or (event.source_id in ids)
            if alive:
                continue

            per_user[event.user.email]['count'] += 1
            per_user[event.user.email]['xp'] += event.amount
            total_count += 1
            total_xp += event.amount
            if self.verbose:
                self.stdout.write(
                    f'    {event.user.email}: {event.source_type} '
                    f'key={event.source_key!r} id={event.source_id} '
                    f'+{event.amount} XP ({event.created_at:%Y-%m-%d})'
                )

        if not total_count:
            self.stdout.write('  None.')
            return

        self.stdout.write(f'  {"student":<40} {"events":>8} {"XP":>8}')
        for email in sorted(per_user):
            data = per_user[email]
            self.stdout.write(
                f'  {email:<40} {data["count"]:>8} {data["xp"]:>8}'
            )
        self.stdout.write(
            f'  {"TOTAL":<40} {total_count:>8} {total_xp:>8}'
        )
        self.stdout.write(
            '  These rows keep their XP by design (XP never decreases). This '
            'is the\n  measure of what earlier destructive reseeds cost.'
        )

    def _ledger_drift_report(self, profiles):
        """
        ``sum(XPEvent.amount)`` vs the denormalized ``GameProfile.total_xp``.

        This is the number that says how inflated a total actually is. A
        positive delta means the profile holds more XP than the ledger can
        account for.
        """
        self._section('LEDGER DRIFT (GameProfile.total_xp vs sum of XPEvents)')
        ledger = dict(
            XPEvent.objects.values_list('user_id').annotate(
                total=Sum('amount')
            ).values_list('user_id', 'total')
        )

        drifted = []
        for profile in profiles.order_by('user__email'):
            summed = ledger.get(profile.user_id, 0) or 0
            if summed != profile.total_xp:
                drifted.append((profile, summed))

        if not drifted:
            self.stdout.write('  None — every profile matches its ledger.')
            return

        self.stdout.write(
            f'  {"student":<34} {"profile":>9} {"ledger":>9} '
            f'{"delta":>8} {"Lv":>4} {"Lv*":>4}'
        )
        for profile, summed in drifted:
            delta = profile.total_xp - summed
            self.stdout.write(
                f'  {profile.user.email:<34} {profile.total_xp:>9} '
                f'{summed:>9} {delta:>+8} '
                f'{level_for_xp(profile.total_xp):>4} {level_for_xp(summed):>4}'
            )
        self.stdout.write(
            '  Lv is the level at the stored total; Lv* the level the ledger '
            'alone\n  would give. Repairing these is a separate decision — '
            'this command never writes.'
        )

    def _amount_drift_report(self, events):
        """
        Rows whose ``amount`` no longer matches the constant for their type.

        ``_award_xp`` passes ``amount`` in ``get_or_create(defaults=...)``, so
        an existing row keeps whatever it was first written with, forever, and
        nothing reconciles it if the constants change.
        """
        self._section('AMOUNT DRIFT (row amount vs the current XP constant)')
        clauses = []
        for source_type, expected in EXPECTED_AMOUNT.items():
            clauses.append((source_type, expected))

        found = 0
        for source_type, expected in clauses:
            drifted = events.filter(source_type=source_type).exclude(amount=expected)
            count = drifted.count()
            if not count:
                continue
            found += count
            total = drifted.aggregate(total=Sum('amount'))['total'] or 0
            self.stdout.write(
                f'  {source_type:<14} expected {expected:>4} XP — '
                f'{count} row(s) differ, holding {total} XP'
            )
            if self.verbose:
                for event in drifted.select_related('user').order_by('id'):
                    self.stdout.write(
                        f'    {event.user.email}: key={event.source_key!r} '
                        f'amount={event.amount}'
                    )

        if not found:
            self.stdout.write('  None.')
        else:
            self.stdout.write(
                '  Not rewritten: changing a stored amount silently moves '
                'student totals.'
            )

    def _content_key_report(self):
        """Keys held by more than one live row, and unadopted seeded content."""
        self._section('CONTENT KEYS')

        duplicates = []
        for model, label in ((Lesson, 'lesson'), (Quiz, 'quiz')):
            dupes = (
                model.objects.exclude(content_key=None)
                .values('content_key')
                .annotate(n=Count('id'))
                .filter(n__gt=1)
            )
            for row in dupes:
                duplicates.append((label, row['content_key'], row['n']))

        # A key is globally unique per table, but the namespace is meant to be
        # flat — the same key on a lesson AND a quiz is still a collision.
        lesson_keys = set(
            Lesson.objects.exclude(content_key=None)
            .values_list('content_key', flat=True)
        )
        quiz_keys = set(
            Quiz.objects.exclude(content_key=None)
            .values_list('content_key', flat=True)
        )
        cross = sorted(lesson_keys & quiz_keys)

        if duplicates:
            for label, key, n in duplicates:
                self.stdout.write(self.style.WARNING(
                    f'  Duplicate {label} key {key!r} held by {n} rows'
                ))
        if cross:
            for key in cross:
                self.stdout.write(self.style.WARNING(
                    f'  Key {key!r} is held by both a lesson and a quiz'
                ))
        if not duplicates and not cross:
            self.stdout.write('  No duplicate keys.')

        # Unadopted seeded content: adoption should have stamped every ROB101
        # and JAVA101 lesson/quiz with its blueprint key.
        self.stdout.write('')
        for code in SEEDED_COURSE_CODES:
            stray_lessons = Lesson.objects.filter(
                unit__course__code=code
            ).filter(content_key__startswith='auto:')
            stray_quizzes = Quiz.objects.filter(
                unit__course__code=code
            ).filter(content_key__startswith='auto:')
            unkeyed_lessons = Lesson.objects.filter(
                unit__course__code=code, content_key=None
            )
            unkeyed_quizzes = Quiz.objects.filter(
                unit__course__code=code, content_key=None
            )
            total = (
                stray_lessons.count() + stray_quizzes.count()
                + unkeyed_lessons.count() + unkeyed_quizzes.count()
            )
            if not total:
                self.stdout.write(f'  {code}: all content carries a blueprint key.')
                continue
            self.stdout.write(self.style.WARNING(
                f'  {code}: {total} row(s) still unadopted '
                f'({stray_lessons.count()} auto: lessons, '
                f'{stray_quizzes.count()} auto: quizzes, '
                f'{unkeyed_lessons.count()} unkeyed lessons, '
                f'{unkeyed_quizzes.count()} unkeyed quizzes)'
            ))
            if self.verbose:
                for lesson in stray_lessons.union(unkeyed_lessons):
                    self.stdout.write(
                        f'    lesson #{lesson.id} "{lesson.title}" '
                        f'key={lesson.content_key!r}'
                    )

"""
Management command to create/refresh the ROB201 course ("Robotics 2") with a
complete TEKS-aligned curriculum (Texas TEKS Robotics II, 19 TAC §127.750, one
credit, recommended grades 10-12, Robotics I as the stated prerequisite, STEM
CTE cluster).

Content is platform-agnostic: no hardware kit is assumed, and hands-on work
uses free simulators (VEXcode VR, Tinkercad Circuits). Six thematic units group
the 12 TEKS knowledge-and-skills strands (c)(1)-(c)(12); every lesson cites the
strand(s) it covers. Where Robotics 1 taught pseudocode and block logic,
Robotics 2 teaches **Python**, and artificial intelligence gets a unit of its
own — matching the TEKS course overview, which centers on "artificial
intelligence and programming in the robotic and automation industry".

The prerequisite is stated in the content only. The platform does NOT enforce
it: there is no prerequisite field and no enrollment gate (phase-69 decision).

This command is NON-DESTRUCTIVE:
1. Does NOT delete or create any users
2. Does NOT touch any other course
3. Creates (or idempotently refreshes) only the ROB201 course and its content
   (units -> lessons -> paginated sections + comprehension quizzes, plus a unit
   quiz per unit)

It upserts on each lesson's and quiz's author-chosen ``content_key`` (see
``_content_upsert``), so a refresh touches content only and student work
survives it. Content in the database that the blueprint no longer lists is
reported, and deleted only under ``--prune``.
"""
import hashlib

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.db import transaction
from courses.models import Course

from ._content_upsert import (
    prune_stale, upsert_lesson, upsert_lesson_questions, upsert_quiz,
    upsert_quiz_questions, upsert_sections, upsert_unit,
)

User = get_user_model()


class Command(BaseCommand):
    help = (
        'Create or refresh the ROB201 Robotics 2 course (non-destructive: no '
        'user, other-course or student-progress changes). --prune also deletes '
        'ROB201 content the blueprint no longer lists.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--prune',
            action='store_true',
            help=(
                'Delete ROB201 lessons/quizzes/units that are not in this '
                'blueprint. This CASCADES student progress for the removed '
                'content, which is why it is opt-in. Without it the command '
                'only warns about them.'
            ),
        )

    def handle(self, *args, **options):
        self.stdout.write('Populating ROB201 course...\n')

        # Every content key this run touched. `prune_stale` treats anything in
        # the course that is not in these sets as blueprint-absent.
        self.seen_lesson_keys = set()
        self.seen_quiz_keys = set()

        # Find the instructor (never modifies users)
        instructor = self._get_instructor()

        # Atomic so a mid-rebuild failure can't leave students looking at a
        # half-built course — either the refresh lands whole or not at all.
        with transaction.atomic():
            # Get or create ROB201 (touches no other course)
            course = self._get_or_update_course(instructor)

            self._create_course_content(course)
            self._report_stale(course, prune=options['prune'])

        self.stdout.write(self.style.SUCCESS('\nROB201 population complete (non-destructive).'))

    # ---------------- Upsert wrappers (record what the run touched) ---------

    def _unit(self, course, order, title):
        return upsert_unit(course, order, title)

    def _lesson(self, unit, key, order, **fields):
        """Upsert a lesson by its permanent content key. See ``_content_upsert``.

        A key reused within one run is a copy-pasted slug, not an update: the
        second call would upsert the FIRST lesson's row in place, so the
        blueprint's two lessons collapse into one and the first one's identity
        and content vanish without an error. Caught loudly instead.
        """
        if key in self.seen_lesson_keys:
            raise ValueError(
                f'lesson content key {key!r} was used twice in one seed run. '
                f'Each lesson needs its own permanent slug; reusing one '
                f'silently merges the two lessons into a single row.'
            )
        self.seen_lesson_keys.add(key)
        return upsert_lesson(unit, key, order, **fields)

    def _quiz(self, unit, key, order, **fields):
        """Upsert a unit quiz by its permanent content key. See ``_lesson``."""
        if key in self.seen_quiz_keys:
            raise ValueError(
                f'quiz content key {key!r} was used twice in one seed run. '
                f'Each quiz needs its own permanent slug; reusing one silently '
                f'merges the two quizzes into a single row.'
            )
        self.seen_quiz_keys.add(key)
        return upsert_quiz(unit, key, order, **fields)

    def _report_stale(self, course, *, prune):
        report = prune_stale(
            course, self.seen_lesson_keys, self.seen_quiz_keys, dry_run=not prune,
        )
        if not (report.lessons or report.quizzes or report.units):
            return
        verb = 'Deleted' if report.deleted else 'Found'
        for lesson in report.lessons:
            self.stdout.write(self.style.WARNING(
                f'  {verb} blueprint-absent lesson #{lesson.pk} "{lesson.title}"'
            ))
        for quiz in report.quizzes:
            self.stdout.write(self.style.WARNING(
                f'  {verb} blueprint-absent quiz #{quiz.pk} "{quiz.title}"'
            ))
        for unit in report.units:
            self.stdout.write(self.style.WARNING(
                f'  {verb} blueprint-absent unit #{unit.pk} "{unit.title}"'
            ))
        if not report.deleted:
            self.stdout.write(self.style.WARNING(
                '  Nothing was deleted. Re-run with --prune to remove the above '
                '(this CASCADES student progress for that content).'
            ))

    def _get_instructor(self):
        """Find the instructor Cesar Villarreal.

        Filters on is_instructor so a student namesake can never be assigned
        course ownership, and fails loudly (non-zero exit) so an automated
        seeding step can't silently no-op.
        """
        instructor = User.objects.filter(
            first_name='Cesar', last_name='Villarreal', is_instructor=True,
        ).first()
        if instructor is None:
            raise CommandError('Instructor "Cesar Villarreal" (is_instructor=True) not found!')
        self.stdout.write(f'Found instructor: {instructor.email}')
        return instructor

    def _get_or_update_course(self, instructor):
        """Get or create the ROB201 course (non-destructive; no other course touched).

        Writes only title/description/instructor. Never touches is_active,
        enrollment_code or join_code (a reseed must not rotate a live class
        code), and never creates a CourseGradingConfig — the gradebook falls
        back to 50/50, same as ROB101 and JAVA101.
        """
        title = 'Robotics 2'
        description = (
            'Build on Robotics 1 and design robots that think. Aligned to the '
            'Texas TEKS for Robotics II, this course covers industrial safety '
            'and teamwork, the math and physics of torque, gear ratios and '
            'payload, robot arms and end effectors, programming robots in '
            'Python, artificial intelligence and autonomous systems, and a '
            'full engineering design capstone - with hands-on work in free '
            'simulators like VEXcode VR and Tinkercad Circuits. Robotics 1 is '
            'assumed. No robot kit required.'
        )
        course, created = Course.objects.get_or_create(
            code='ROB201',
            defaults={
                'title': title,
                'description': description,
                'instructor': instructor,
            }
        )
        if not created:
            course.title = title
            course.description = description
            course.instructor = instructor
            course.save()
        self.stdout.write(
            f'Course: {course.code} - {course.title} '
            f'({"created" if created else "refreshed"})'
        )
        return course

    def _create_course_content(self, course):
        """Create all units, lessons, sections, and quizzes."""
        self._create_unit1(course)
        self._create_unit2(course)
        self._create_unit3(course)
        self._create_unit4(course)
        self._create_unit5(course)
        self._create_unit6(course)
        self.stdout.write('Created 6 units with lessons and quizzes')

    # ================== UNIT 1: Advanced Systems, Safety & Teams ==================
    def _create_unit1(self, course):
        unit = self._unit(course, 0, 'Advanced Systems, Safety & Teams')

        # Lesson 1: From Robotics 1 to Robotics 2: Systems at Scale
        lesson = self._lesson(
            unit, 'rob201-from-robotics-1-to-robotics-2', 0,
            title='From Robotics 1 to Robotics 2: Systems at Scale',
        )
        self._create_sections(lesson, [
            {
                'title': 'Overview',
                'content': '''# From Robotics 1 to Robotics 2: Systems at Scale

In Robotics 1 the unit of work was a robot. In Robotics 2 it is a **system**: a robot plus the conveyor that feeds it, the sensors that tell it a part arrived, the controller that sequences the whole cell, and the technician who keeps it running at 2 a.m. Almost nothing in a modern factory is a lone robot, and the engineering problems that matter most live in the spaces *between* components.

## Learning Objectives

By the end of this lesson, you will be able to:
- Explain how an integrated automated system differs from a single stand-alone robot
- Compare open and closed system architectures and justify choosing one for a given project
- Describe the integration tasks that connect robots, sensors, controllers, and human operators into one working cell
- Explain how technological systems are maintained over their service life and why maintenance drives the cost of automation

> **TEKS alignment:** §127.750(c)(6) — the student understands, evaluates, and maintains technological systems.'''
            },
            {
                'title': 'From One Robot to an Automated System',
                'content': '''# From One Robot to an Automated System

A Robotics 1 project succeeded when the robot completed a task. A Robotics 2 project succeeds when a **system** meets a throughput and reliability target, hour after hour, with no one watching.

## The Work Cell

The basic unit of industrial automation is the **work cell**: one or more robots surrounded by everything they need to do useful work.

- **Infeed** — a conveyor, tray, or bin that presents raw parts
- **Fixturing** — clamps and jigs that hold a part in a known position so the robot does not have to search for it
- **Process equipment** — the welder, dispenser, press, or screwdriver the robot actually operates
- **Inspection** — a camera or gauge that decides whether the part passed
- **Outfeed and reject** — where good parts go, and where bad parts go instead
- **Cell controller** — the logic that sequences all of the above and stops everything if one piece misbehaves

## New Questions You Have to Answer

| Robotics 1 question | Robotics 2 question |
|---------------------|---------------------|
| Did the robot pick up the block? | What is the cycle time, and can we hold it for 8 hours? |
| Did my program run? | What happens when a part is missing, jammed, or upside down? |
| Is the robot fast enough? | Which station is the bottleneck of the whole line? |
| Did it work today? | What is the uptime this month, and what caused the downtime? |

## Cycle Time and Bottlenecks

If a cell has three stations that take 8, 14, and 9 seconds, the cell produces one part every **14 seconds** — not 8. The slowest station sets the pace, so every other improvement is wasted until the bottleneck moves. A line running at 14 seconds per part for two 8-hour shifts produces about 4,100 parts a day. Shaving two seconds off that station adds roughly 700 parts a day; shaving two seconds off the 8-second station adds zero.

## Try It Without Hardware

In **VEXcode VR**, build a program where the robot completes a repeatable task, then time ten consecutive cycles. Record the fastest, slowest, and average. The spread between fastest and slowest is your **variability** — and in real automation, variability is what turns a working demo into an unreliable line.'''
            },
            {
                'title': 'Open and Closed System Architecture',
                'content': '''# Open and Closed System Architecture

Every automated system is built on an **architecture**: the set of decisions about what parts can talk to what, using which interfaces, and who is allowed to change them. Architectures fall on a spectrum between open and closed.

## Closed (Proprietary) Architecture

A **closed architecture** uses a single vendor's controllers, cables, programming language, and service network. The vendor guarantees the pieces work together; in exchange, you cannot easily substitute a competitor's part.

- Predictable performance — the vendor tested this exact combination
- One phone number when something breaks
- Training and certification are well defined
- But: parts, software licenses, and service are priced by a supplier with no competition
- And: an obsolete controller can strand an otherwise healthy machine

## Open Architecture

An **open architecture** uses published standards and interfaces so components from different manufacturers interoperate — standard fieldbus protocols, standard file formats, general-purpose programming languages.

- You can mix vendors and shop for price
- Longer service life: replace one obsolete piece, not the whole cell
- A larger pool of people already know the tools
- But: integration is now *your* problem, and so is the finger-pointing when two vendors blame each other
- And: nobody has tested your specific combination before you do

## Choosing

| Situation | Better fit | Why |
|-----------|-----------|-----|
| A school lab with one teacher and no integrator | Closed | Support and predictability outweigh flexibility |
| A plant standardizing 40 cells over 15 years | Open | Vendor lock-in compounds badly at that scale |
| A safety-rated welding cell | Closed | Certified, pre-validated safety chain matters more than price |
| A research testbed that changes monthly | Open | Swapping components is the entire point |

## Why It Shows Up on Every Project

Architecture decisions are hard to reverse. Choosing a closed controller in year one quietly decides what your spare-parts budget looks like in year eight. Professionals write the trade-off down at decision time — in the engineering notebook, with the reasons — so the next person understands why the system is shaped the way it is.'''
            },
            {
                'title': 'System Integration: Making the Pieces Talk',
                'content': '''# System Integration: Making the Pieces Talk

**System integration** is the engineering work of connecting independently built components so they behave as one machine. It is its own profession: a *systems integrator* is the company a factory hires to turn a pile of robots, sensors, and conveyors into a working line.

## Three Kinds of Connection

1. **Mechanical** — mounting, alignment, and reach. Can the robot physically get to every point it needs, at every orientation, without hitting the fixture?
2. **Electrical** — power, grounding, and signal wiring. Are the voltages compatible? Is the sensor sourcing or sinking current? Is the signal wire routed away from the motor cable that will induce noise into it?
3. **Logical** — the sequence and the data. Who tells the robot the part has arrived? What does the robot say back when it is done? What happens if the answer never comes?

## Handshaking

The heart of logical integration is the **handshake**: a short exchange of signals that keeps two machines in step.

| Step | Conveyor | Robot |
|------|----------|-------|
| 1 | Part in place, raises PART_READY | Waiting |
| 2 | Holds still | Sees PART_READY, raises ROBOT_BUSY |
| 3 | Waits for ROBOT_BUSY to clear | Picks the part |
| 4 | Waits | Clears ROBOT_BUSY, lowers itself out of the way |
| 5 | Sees ROBOT_BUSY clear, indexes the next part | Waiting |

Without the handshake the conveyor might index while the robot's gripper is still inside it. Notice that every step also needs a **timeout**: if PART_READY never arrives within, say, 30 seconds, the cell should raise a fault rather than wait forever.

## The Controllers in the Middle

- **PLC (programmable logic controller)** — the rugged industrial computer that usually sequences the whole cell and owns the safety interlocks
- **Robot controller** — runs the motion program for one robot and exchanges I/O with the PLC
- **HMI (human-machine interface)** — the touchscreen where an operator starts the cycle, sees a fault code, and clears it
- **Fieldbus / industrial network** — the wiring standard (EtherNet/IP, PROFINET, and similar) that carries those signals reliably in an electrically noisy building

## Integration Failures Are Interface Failures

When a cell fails during commissioning, the individual components are usually fine. The fault is almost always at an interface: a mismatched signal polarity, a missing timeout, an assumption one team made that the other team never heard. That is why integration work is documented obsessively — the interface list *is* the design.'''
            },
            {
                'title': 'Maintaining Technological Systems',
                'content': '''# Maintaining Technological Systems

A robot is bought once and maintained for a decade. Over the life of an automated system, **maintenance and downtime usually cost more than the hardware did** — which is why maintaining technological systems, not just building them, is a TEKS-level skill and a career in its own right.

## Three Maintenance Strategies

- **Reactive (run to failure)** — fix it when it breaks. Cheapest to plan, most expensive to live with, because failures happen at the worst possible moment and take the whole line with them.
- **Preventive** — service on a fixed schedule: grease at 500 hours, replace the belt at 2,000 hours, recalibrate quarterly. Predictable and easy to staff. Sometimes replaces parts that had life left.
- **Predictive** — instrument the machine and service it when the data says to: vibration trending up, motor current climbing, cycle time drifting. Highest payoff, highest setup cost.

## The Vocabulary of Reliability

| Term | Meaning | Why it matters |
|------|---------|----------------|
| Uptime | Percent of scheduled time the system is available | The number plant managers are judged on |
| MTBF | Mean time between failures | How often to expect trouble |
| MTTR | Mean time to repair | How long trouble lasts; spares and documentation shrink it |
| PM | Preventive maintenance task | The scheduled work that raises MTBF |
| Downtime cost | Money lost per hour of stoppage | Justifies the entire maintenance budget |

Uptime is unforgiving arithmetic. A cell running 99% uptime across a 20-hour day is down 12 minutes a day — about 73 hours a year. If stopping the line costs the plant $1,500 an hour, that is roughly $110,000 annually, which easily pays for a maintenance technician and a shelf of spare parts.

## What Maintenance Actually Involves

- **Inspection** — looking and listening on a schedule: frayed cables, weeping air lines, loose fasteners, unusual noise
- **Lubrication and wear parts** — greases, belts, filters, and gripper pads have published intervals; follow them
- **Calibration** — restoring the robot's idea of where it is after a crash or a component swap
- **Backups** — a current copy of every program and configuration file, stored off the machine. A controller that dies without a backup can idle a line for days
- **Records** — a maintenance log with dates, symptoms, actions, and parts used. The log is what turns a hunch into a trend

## Obsolescence

Systems also age out. Controllers stop being manufactured, operating systems stop getting security patches, and the last technician who knew the old programming language retires. Planning for **end of life** — spare controllers, current documentation, a migration budget — is part of maintaining a technological system, not a separate problem.'''
            }
        ])
        self._create_lesson_questions(lesson, [
            {
                'text': 'A work cell has three stations with cycle times of 8, 14, and 9 seconds. What is the cell producing a part every how many seconds, and which station should be improved first?',
                'choices': [
                    ('Every 14 seconds — improve the 14-second station, because the slowest station sets the pace', True),
                    ('Every 8 seconds — improve the 8-second station, because it runs most often', False),
                    ('Every 31 seconds — improve all three equally', False),
                    ('Every 10.3 seconds — improve whichever station is easiest to change', False),
                ]
            },
            {
                'text': 'A plant plans to standardize 40 robot cells over the next 15 years and wants to shop competitively for spare parts. Which architecture choice best fits, and why?',
                'choices': [
                    ('Open architecture, because published standard interfaces let components from different vendors be substituted over a long service life', True),
                    ('Closed architecture, because a single vendor always costs less over 15 years', False),
                    ('Closed architecture, because open systems cannot be used in factories', False),
                    ('Either one, because architecture has no effect on spare-parts cost', False),
                ]
            },
            {
                'text': 'During commissioning, a conveyor indexes forward while the robot gripper is still inside the pick zone. Which part of the integration was most likely missing?',
                'choices': [
                    ('The handshake signals that keep the two machines in step, such as a ROBOT_BUSY signal the conveyor waits on', True),
                    ('The robot motor was undersized for the payload', False),
                    ('The conveyor belt needed lubrication', False),
                    ('The HMI touchscreen was mounted at the wrong height', False),
                ]
            },
            {
                'text': 'A maintenance team monitors motor current and vibration on a robot and schedules service when the trend rises, rather than at a fixed hour count. Which maintenance strategy is this?',
                'choices': [
                    ('Predictive maintenance', True),
                    ('Reactive (run-to-failure) maintenance', False),
                    ('Preventive maintenance on a fixed schedule', False),
                    ('Corrective calibration', False),
                ]
            }
        ])

        # Lesson 2: Industrial Safety, Lockout/Tagout & Risk Assessment
        lesson = self._lesson(
            unit, 'rob201-industrial-safety-and-lockout-tagout', 1,
            title='Industrial Safety, Lockout/Tagout & Risk Assessment',
        )
        self._create_sections(lesson, [
            {
                'title': 'Overview',
                'content': '''# Industrial Safety, Lockout/Tagout & Risk Assessment

Robotics 1 safety was about you and a hand tool. Industrial safety is about a machine that weighs 900 kilograms, moves faster than you can react, and has no idea you are standing in its work envelope. The rules that follow were written after people were hurt, and every one of them is enforceable law in a real workplace.

## Learning Objectives

By the end of this lesson, you will be able to:
- Describe OSHA's role and the employer and employee duties it creates in an automated workplace
- Perform a hazard identification and score a risk using a severity-by-likelihood matrix
- List the steps of a lockout/tagout procedure and explain why each one exists
- Compare machine guarding, light curtains, emergency stops, and collaborative-robot safety methods, and choose the right control for a hazard

> **TEKS alignment:** §127.750(c)(5) — the student implements personal and workplace safety rules, regulations, and procedures.'''
            },
            {
                'title': 'OSHA and the Rules of an Industrial Workplace',
                'content': '''# OSHA and the Rules of an Industrial Workplace

**OSHA** — the Occupational Safety and Health Administration — is the federal agency created by the Occupational Safety and Health Act of 1970 to set and enforce workplace safety standards in the United States. Its rules are not suggestions; OSHA inspectors issue citations and fines, and serious violations can carry criminal penalties.

## The General Duty Clause

The most important sentence in the Act is short: employers must provide a workplace **free from recognized hazards** that are likely to cause death or serious physical harm. Even when no specific standard covers a new machine, that clause still applies. It is why "there is no rule about this robot yet" is never a defense.

## Standards You Will Meet in Automation

| Standard | Subject | Where it bites |
|----------|---------|----------------|
| 29 CFR 1910.147 | The control of hazardous energy (lockout/tagout) | Any service or maintenance on powered equipment |
| 29 CFR 1910.212 | General machine guarding | Points of operation, nip points, rotating parts |
| 29 CFR 1910.132 | Personal protective equipment | Eye, hand, foot, and hearing protection |
| 29 CFR 1910.1200 | Hazard communication | Safety data sheets for solvents, adhesives, coolants |
| ANSI/RIA R15.06 | Industrial robot safety (consensus standard) | Robot cell design, safeguarding, risk assessment |

The first four are federal regulations. **ANSI/RIA R15.06** is a voluntary consensus standard for industrial robots and robot systems — but OSHA routinely cites it as the definition of accepted practice, so in effect the industry treats it as required.

## Employee Rights and Duties

You have the right to training in a language you understand, to see the safety data sheet for anything you handle, to report a hazard without retaliation, and to refuse work you reasonably believe is imminently dangerous. In exchange you are expected to follow procedures, wear required protection, and report near misses.

## Near Misses Are Data

A **near miss** is an event that could have caused injury but did not. Mature safety programs chase near misses hard, because the conditions that produce a near miss and an injury are identical — only luck differs. Reporting one is not admitting failure; it is the cheapest possible way to find out where the system is weak.'''
            },
            {
                'title': 'Hazard Identification and Risk Assessment',
                'content': '''# Hazard Identification and Risk Assessment

Safety engineering starts with an honest inventory. A **hazard** is anything with the potential to cause harm. **Risk** is the combination of how badly it could hurt someone and how likely that is to happen.

## Hazards in a Robot Cell

- **Mechanical** — crushing between the arm and a fixture, shearing at a nip point, impact from a whipping cable, being struck by a dropped part
- **Electrical** — shock and arc flash from control cabinets, often at 480 V
- **Stored energy** — a raised axis that falls when power is removed, charged capacitors, pressurized air, a compressed spring
- **Process** — weld flash and fume, laser light, hot surfaces, chemicals
- **Ergonomic** — repetitive loading of the infeed, awkward reaches during changeover

## Scoring the Risk

A **risk assessment matrix** multiplies severity by likelihood so a team can compare unlike hazards with one number.

| Severity \\ Likelihood | Unlikely (1) | Possible (2) | Likely (3) | Frequent (4) |
|------------------------|--------------|--------------|------------|--------------|
| Minor — first aid (1) | 1 Low | 2 Low | 3 Low | 4 Medium |
| Moderate — lost time (2) | 2 Low | 4 Medium | 6 Medium | 8 High |
| Serious — permanent injury (3) | 3 Low | 6 Medium | 9 High | 12 Critical |
| Catastrophic — fatality (4) | 4 Medium | 8 High | 12 Critical | 16 Critical |

**Worked example.** A technician reaches into a cell to clear jammed parts about six times per shift, and the arm can move on a restart. Severity is catastrophic (4) because a crushing injury from a 900 kg arm can kill; likelihood is frequent (4) because the reach happens every shift. Score 16 — Critical. That score means the cell may not run in that condition; the risk must be reduced before production continues.

## The Hierarchy of Controls

Reduce risk in this order, most effective first:

1. **Elimination** — redesign the fixture so parts stop jamming and nobody reaches in
2. **Substitution** — use a lighter, slower robot that cannot generate a lethal force
3. **Engineering controls** — fence, interlocked gate, light curtain, safety-rated speed limit
4. **Administrative controls** — procedures, training, warning signs, restricted access
5. **PPE** — safety glasses, gloves, steel-toe boots

PPE is *last* because it protects one person, only when worn correctly, and does nothing to reduce the hazard itself. Reassess after every change: a new gripper, a faster cycle, or a new part number can move a score from Medium back to Critical.'''
            },
            {
                'title': 'Lockout/Tagout: Controlling Hazardous Energy',
                'content': '''# Lockout/Tagout: Controlling Hazardous Energy

**Lockout/tagout (LOTO)** is the procedure that makes a machine provably unable to start while someone is working on it. OSHA 29 CFR 1910.147 requires it for service and maintenance, and it is one of the most frequently cited standards in American industry — because skipping it is fast, and it kills people.

## The Terms

- **Lockout** — physically applying a lock to an energy-isolating device, such as a disconnect switch or a valve, so it cannot be moved
- **Tagout** — attaching a durable warning tag naming who applied it and why. A tag alone is only a warning; a lock is a barrier
- **Authorized employee** — the person performing the service, who applies their own personal lock
- **Affected employee** — anyone who operates the machine or works nearby and must be told it is down
- **Group lockout** — a lock box where every worker on the job hangs a personal lock, so the machine cannot restart until the last person removes theirs

## The Six Steps

1. **Prepare.** Identify every energy source: electrical, pneumatic, hydraulic, gravity, springs, thermal, and stored charge. A robot arm often has three or more.
2. **Notify.** Tell affected employees the machine is going down and why.
3. **Shut down.** Stop the machine using its normal controls, in the normal sequence.
4. **Isolate.** Operate each energy-isolating device — open the disconnect, close and bleed the air valve, block or lower the raised axis.
5. **Lock and tag.** Apply a personal lock and tag to each isolating device. One person, one lock, one key, and that person keeps the key.
6. **Verify zero energy.** Try to start the machine with its normal controls, then test with a meter and confirm the arm cannot move. **Verification is the step people skip, and it is the step that saves lives.**

Removing locks reverses the order: clear tools, confirm everyone is out of the danger zone, notify, then each person removes their own lock. Never remove someone else's lock — every plant has a documented, supervisor-led exception process for the one case where a worker has gone home with the key.

## Why an E-Stop Is Not Lockout

Pressing the emergency stop removes motion power, but it is a **control-circuit** device: it can be reset by anyone, it can fail, and it does not remove stored pneumatic or gravitational energy. An e-stop is for emergencies. Lockout is for maintenance. Treating one as the other is the classic fatal shortcut.

## The Habit to Build Now

Practice the mindset in the lab: before adjusting a mechanism, disconnect the battery or power supply, set it where you can see it, and tell your partner what you are doing. The scale is smaller; the discipline is identical.'''
            },
            {
                'title': 'Guarding, Presence Sensing, and Collaborative Robots',
                'content': '''# Guarding, Presence Sensing, and Collaborative Robots

Engineering controls sit third in the hierarchy but do most of the day-to-day work. Their job is simple: keep people and moving machinery out of the same space at the same time.

## Fixed and Interlocked Guarding

**Fixed guards** are fences, panels, and covers that require a tool to remove. **Interlocked guards** are gates wired so that opening them removes motion power: a safety-rated switch on the gate feeds a safety relay or safety PLC that drops the robot's drive power. Good interlocks are **tamper resistant** — a switch you can defeat by taping a magnet to it is a hazard pretending to be a control.

## Presence-Sensing Devices

- **Light curtains** — a wall of infrared beams across an opening. Break a beam and the machine stops. They allow parts to pass through where a gate cannot.
- **Safety laser scanners** — sweep a horizontal plane and define zones on the floor: a *warning* zone that slows the machine and a *stop* zone that halts it.
- **Safety mats and edges** — pressure-sensitive floor mats and bumpers on moving equipment.

Every one of these needs correct **safety distance**. The device must be far enough from the hazard that the machine stops before a hand traveling at the standard approach speed of roughly 1.6 metres per second can reach the danger point. The calculation adds the machine's own stopping time to the safety system's response time — and the machine's stopping time gets *worse* as brakes wear, which is why stop-time measurement is a periodic check, not a one-time number.

## Muting and Bypassing

Some processes legitimately **mute** a light curtain so a pallet can pass without stopping the line. Muting is a designed, safety-rated function with its own sensors and indicator lamp. **Bypassing** — taping over an emitter, jumpering a gate switch, propping a door — is not a technique. It is the leading cause of robot fatalities, and in a real plant it ends employment.

## Collaborative Robots

Cobots are designed to share space with people. ISO/TS 15066 describes four collaborative methods:

| Method | How it protects people |
|--------|------------------------|
| Safety-rated monitored stop | The robot halts while a person is in the shared space and resumes when they leave |
| Hand guiding | An operator moves the robot directly using a safety-rated device |
| Speed and separation monitoring | Sensors track the person; the robot slows as separation shrinks and stops before contact |
| Power and force limiting | The robot is built and limited so any contact stays below documented pain and injury thresholds |

Two cautions. First, **there is no such thing as a safe robot, only a safe application** — a power-and-force-limited arm holding a knife or a hot part is not collaborative. Second, the safety case belongs to the whole cell, gripper and workpiece included, and that is established by a risk assessment, not by the label on the robot.'''
            }
        ])
        self._create_lesson_questions(lesson, [
            {
                'text': 'A technician reaches into a robot cell about six times per shift to clear jams, and the arm can move on restart. Rating severity as catastrophic (4) and likelihood as frequent (4), what does the risk matrix indicate?',
                'choices': [
                    ('A critical score of 16 — the cell must not run in that condition until the risk is reduced', True),
                    ('A low score of 8 — annual retraining is sufficient', False),
                    ('A medium score that can be accepted if the technician wears gloves', False),
                    ('No score is needed because the technician is experienced', False),
                ]
            },
            {
                'text': 'A maintenance worker presses the emergency stop, then reaches into the cell to replace a gripper. Which required procedure was skipped?',
                'choices': [
                    ('Lockout/tagout — the e-stop is a control-circuit device that can be reset and does not release stored pneumatic or gravitational energy', True),
                    ('Nothing was skipped; an e-stop satisfies the lockout requirement', False),
                    ('Hazard communication — a safety data sheet was needed for the gripper', False),
                    ('The worker only needed to notify affected employees afterward', False),
                ]
            },
            {
                'text': 'Which step of the lockout/tagout procedure is most often skipped, and why does it matter most?',
                'choices': [
                    ('Verifying zero energy by attempting a normal start and testing with a meter, because it is the only step that proves the isolation actually worked', True),
                    ('Notifying affected employees, because they cannot enter the cell anyway', False),
                    ('Attaching the tag, because the lock already blocks the switch', False),
                    ('Shutting down with the normal controls, because the disconnect does the same job', False),
                ]
            },
            {
                'text': 'A cell uses sensors that track an operator and progressively slow the robot as the person gets closer, stopping it before contact. Which collaborative method is in use?',
                'choices': [
                    ('Speed and separation monitoring', True),
                    ('Power and force limiting', False),
                    ('Hand guiding', False),
                    ('Safety-rated monitored stop', False),
                ]
            }
        ])

        # Lesson 3: Professional Standards & Industry Certifications
        lesson = self._lesson(
            unit, 'rob201-professional-standards-and-certifications', 2,
            title='Professional Standards & Industry Certifications',
        )
        self._create_sections(lesson, [
            {
                'title': 'Overview',
                'content': '''# Professional Standards & Industry Certifications

Automation employers hire on evidence. A transcript says you attended; a certification says you were tested by someone with no reason to be nice to you; a portfolio says you have actually built something. This lesson is about assembling that evidence deliberately, starting now, and about the professional conduct that keeps the job once you have it.

## Learning Objectives

By the end of this lesson, you will be able to:
- Describe the professional standards employers in automation expect and how they differ from classroom expectations
- Build a resume and technical portfolio that document verifiable skills
- Compare industry certifications relevant to robotics and automation and plan a realistic sequence to earn them
- Explain professional ethics, conduct, and continuing education as ongoing obligations of a technical career

> **TEKS alignment:** §127.750(c)(1) — the student demonstrates professional standards and employability skills as required by business and industry.'''
            },
            {
                'title': 'Employability at a Professional Level',
                'content': '''# Employability at a Professional Level

Robotics 1 asked for initiative, adaptability, and quality work. Those still count. What changes at the professional level is that these behaviors become **measurable obligations** attached to money, safety, and other people's schedules.

## What Raises the Bar

| Habit | Classroom version | Workplace version |
|-------|-------------------|-------------------|
| Punctuality | Arrive before the bell | The line starts at shift change; being late stops production for everyone |
| Following procedure | Read the assignment sheet | Follow the documented work instruction exactly; deviations require sign-off |
| Asking for help | Raise your hand | Escalate within a defined time so the problem does not eat the schedule |
| Quality | Turn in something that works | Meet a written spec, with inspection records that prove it |
| Communication | Tell the teacher | Write it where the next shift will find it |

## Reliability Is the Whole Reputation

In a plant, work is handed between shifts and between trades. Everything depends on whether your word is worth planning around. Three habits carry most of it:

- **Give honest estimates.** "Two hours" that turns into six is worse than saying six.
- **Report bad news early.** Problems are cheapest at the moment you first suspect them.
- **Close the loop.** Say when you started, say when you finished, say what you found.

## Judgment Under Pressure

Automation work happens in the hard hours — during shutdowns, at night, at the end of a quarter. Under pressure, the temptation is always the same: bypass the interlock, skip the verification, sign off on a test you did not finish. Professional standards exist precisely for those moments. The person who stops the line and says "I need thirty minutes to do this correctly" is more employable than the one who saves thirty minutes and cannot prove the machine is safe.

## Presenting Yourself

Personal appearance, workplace language, phone use, and how you treat the newest person in the room are all evaluated continuously and informally. So is your response to correction. Reacting to a supervisor's critique with "got it, I will change it" rather than a defense is one of the most visible markers of professional maturity there is.'''
            },
            {
                'title': 'Resumes, Portfolios, and Evidence',
                'content': '''# Resumes, Portfolios, and Evidence

A resume gets you the interview. A portfolio gets you the job. Both are exercises in the same skill: turning what you did into something a stranger can verify in under a minute.

## Resume Rules That Actually Matter

- **One page** until you have roughly ten years of experience
- **Reverse chronological** order within each section
- **Quantify everything you can.** "Reduced cycle time from 22 s to 17 s" beats "improved efficiency"
- **Lead with verbs**: built, wired, programmed, tested, documented, trained
- **Plain formatting.** Many employers run resumes through applicant tracking software that mangles columns, tables, and graphics
- **List certifications with dates**, because most of them expire
- **Zero typos.** In a field where a transposed digit crashes a robot, a careless resume is treated as evidence

## Weak Line Versus Strong Line

| Weak | Strong |
|------|--------|
| Worked on the robotics team | Programmed autonomous routines in VEXcode VR; cut average run time 22 s to 17 s across 10 timed trials |
| Good with tools | Wired and troubleshot 24 VDC sensor circuits; read and corrected ladder-logic I/O assignments |
| Team player | Led a 5-person build subteam; ran weekly stand-ups and maintained the task board |

## The Technical Portfolio

A portfolio is the proof behind the resume claims. For each project, include:

1. **The problem** in one or two sentences
2. **Your specific role** — say what *you* did, not what the team did
3. **Evidence** — annotated photos, a wiring or flow diagram, a short code excerpt, before-and-after data
4. **The result**, with numbers
5. **What you would do differently**, which is the section experienced interviewers read first

Keep it in a simple, shareable form — a PDF or a plain personal site. Never put an employer's or a competition partner's confidential material in it, and never include anything you cannot legally share.

## Build It Continuously

The hardest part of a portfolio is reconstructing work months later from memory. Photograph the wiring before you close the panel. Save the timing data. Write two sentences in the notebook while the fix is fresh. Ten minutes at the end of each project makes the portfolio nearly free.'''
            },
            {
                'title': 'Industry Certifications',
                'content': '''# Industry Certifications

A **certification** is a credential issued by an organization independent of your school, based on an exam or a performance assessment. Employers value them because the standard is uniform: a certificate from one testing body means the same thing in Texas as it does in Ohio.

## Certifications and Certificates Are Different

A course **certificate** says you completed training. A **certification** says you passed an assessment against a published standard, and it usually expires and must be renewed. Both belong on a resume; only the second answers "can this person do the work?"

## Families of Credentials in Automation

| Family | Typical example | What it signals |
|--------|-----------------|-----------------|
| Safety | OSHA 10-hour (entry) or OSHA 30-hour (supervisory) general industry training | You know the regulatory basics before you set foot on a floor |
| Automation skills | SACA-style modular certifications in electrical systems, mechanical systems, and industrial networking | Verified, stackable competencies in specific automation subjects |
| Robot manufacturer | Vendor operation and programming credentials, such as FANUC-style handling or CERT-track courses offered through schools | You can operate and program that vendor's controller |
| Controls | Programmable-controller and industrial-network credentials from control vendors | You can build and troubleshoot the logic layer |
| Design tools | CAD and CAM certifications | You can produce manufacturable drawings and models |

## What They Cost You

Exams generally run from tens to a few hundred dollars, and many Texas high school CTE programs pay for approved industry-based certifications outright. Ask your teacher which ones your district funds — students routinely leave free credentials on the table simply by not asking.

## A Realistic Sequence

1. **Now, in high school:** OSHA 10 general industry, plus whichever entry-level automation or CAD certification your program supports
2. **Late high school or first job:** the first vendor or modular automation credential in the area you like best
3. **On the job:** additional modules and the manufacturer credentials your employer uses, usually paid for by them
4. **Later:** advanced controls or safety credentials, and for a degree path, an ABET-accredited program leading toward professional licensure

## Do Not Overclaim

List only credentials you hold, with the issuing organization and the date. Padding a resume with a certification you started but never passed is discovered easily and treated as dishonesty — which ends the application immediately and, in a small industry, follows you.'''
            },
            {
                'title': 'Ethics, Conduct, and Continuing Education',
                'content': '''# Ethics, Conduct, and Continuing Education

Technical skill gets audited by machines; professional conduct gets audited by people. Both determine how far a career goes.

## The Core Obligations

Engineering and technology codes of ethics differ in wording but agree on the essentials:

- **Hold public safety paramount.** When safety conflicts with schedule or cost, safety wins. This is the first canon in essentially every engineering code, and it is not negotiable.
- **Practice only within your competence.** Say so when a job is beyond your current training, and get help rather than guessing on a live machine.
- **Be truthful in reports and claims.** Test data is not a rough draft. Reporting an untested check as passed is falsification.
- **Avoid conflicts of interest.** Disclose a personal stake in a vendor decision before, not after.
- **Protect confidential information.** Designs, pricing, and processes you learn at work stay at work, including after you leave.
- **Credit others honestly.** Cite sources, respect open-source licenses, and never present a teammate's work as your own.

## Raising a Concern

Ethics is mostly ordinary, not dramatic. The everyday version is a technician who notices a guard interlock has been jumpered and says something. Do it in order: raise it with the person, then the supervisor, then safety or quality. Put it in writing with dates and facts, keep it factual rather than accusatory, and understand that retaliation for reporting a safety hazard is illegal under the OSH Act.

## Professional Conduct Online

Your public posts are part of your professional record. Do not post photographs of an employer's production floor, customer names, or internal drawings. Assume anything posted is permanent and will be read by a hiring manager, because it usually is.

## Continuing Education Is the Job

Automation technology turns over quickly. Controllers, vision systems, industrial networks, and safety standards all revise on a cycle of a few years, and standards such as R15.06 are periodically updated. Professionals keep current by:

- Taking employer-paid vendor training when it is offered, which it usually is
- Renewing certifications before they lapse rather than re-testing from scratch
- Reading the standard, not a summary of it, when the standard governs your work
- Joining a professional association or user group and attending trade shows
- Teaching what they know, because explaining a system is the fastest way to find the gaps in your own understanding

The graduates who advance are not the ones who knew the most on their first day. They are the ones who were still learning in year five.'''
            }
        ])
        self._create_lesson_questions(lesson, [
            {
                'text': 'A supervisor tells a new technician their wiring labels are inconsistent and must be redone. Which response best demonstrates professional maturity?',
                'choices': [
                    ('Accepting the correction, asking what standard to follow, and redoing the labels', True),
                    ('Explaining that the labels are readable enough and moving on to the next task', False),
                    ('Pointing out that another technician labels theirs the same way', False),
                    ('Redoing them silently but telling teammates the supervisor is being unreasonable', False),
                ]
            },
            {
                'text': 'Which resume line gives an employer the most usable evidence of skill?',
                'choices': [
                    ('Programmed autonomous routines in VEXcode VR; cut average run time from 22 s to 17 s across 10 timed trials', True),
                    ('Worked on the robotics team for two years and enjoyed it', False),
                    ('Good with tools and a fast learner', False),
                    ('Team player with strong passion for technology', False),
                ]
            },
            {
                'text': 'What is the key difference between a course certificate and an industry certification?',
                'choices': [
                    ('A certification is earned by passing an independent assessment against a published standard and usually must be renewed, while a certificate records completion of training', True),
                    ('A certificate is issued by the government and a certification is issued by a school', False),
                    ('A certification is permanent and a certificate expires every year', False),
                    ('There is no difference; the words are interchangeable on a resume', False),
                ]
            },
            {
                'text': 'A technician is asked to sign off that a safety interlock was tested, but the shift ended before the test was run. What does professional ethics require?',
                'choices': [
                    ('Refuse to sign, report that the test was not completed, and have it run before the machine returns to production', True),
                    ('Sign it, since the interlock worked the last time it was checked', False),
                    ('Sign it and quietly run the test during the next shift', False),
                    ('Ask a coworker to sign instead so no one is personally responsible', False),
                ]
            }
        ])

        # Lesson 4: Leading a Robotics Project Team
        lesson = self._lesson(
            unit, 'rob201-leading-a-robotics-project-team', 3,
            title='Leading a Robotics Project Team',
        )
        self._create_sections(lesson, [
            {
                'title': 'Overview',
                'content': '''# Leading a Robotics Project Team

An automation project fails for people reasons far more often than for physics reasons. Two subteams solve the same problem twice, a decision made in a hallway never reaches the programmer, the documentation is written the night before the deadline by someone who was not there. Leading a project is the work of making sure none of that happens.

## Learning Objectives

By the end of this lesson, you will be able to:
- Assign and describe the roles on an automation project team and explain how they depend on each other
- Delegate work with clear ownership, acceptance criteria, and deadlines
- Run a meeting that produces decisions and assigned actions instead of consuming time
- Give and receive technical critique and resolve conflict using evidence, and treat documentation as a shared team responsibility

> **TEKS alignment:** §127.750(c)(3) — the student works productively in teams, applying leadership, delegation, and conflict-resolution skills.'''
            },
            {
                'title': 'Roles on an Automation Project',
                'content': '''# Roles on an Automation Project

A Robotics 1 team split into builder, programmer, documenter, and driver. An automation project needs the same functions but organized around a **system** rather than a robot, and it adds roles that exist only because multiple people must agree.

## The Roles

| Role | Owns | Fails visibly when |
|------|------|--------------------|
| Project lead | Scope, schedule, decisions, and outside communication | The team is busy but nobody can say what "done" means |
| Mechanical lead | Frame, fixtures, tooling, and end effectors | Parts do not locate repeatably and the robot misses |
| Controls / electrical lead | Wiring, I/O, controller configuration, and power | Signals are unlabeled and nobody can trace a fault |
| Software lead | Motion programs, sequence logic, and error handling | The cell works only when nothing goes wrong |
| Safety lead | Risk assessment, guarding, and the LOTO procedure | A hazard reaches the build with no assessment behind it |
| Documentation lead | Notebook, interface list, drawings, and test records | The team argues about what was decided last week |
| Test / quality lead | Test plan, acceptance criteria, and defect tracking | Bugs are found by the customer instead of the team |

## Interfaces Between Roles

The dangerous work is at the seams. Mechanical decides where the sensor mounts; controls decides what voltage it needs; software decides what the signal means. If those three never meet, the sensor gets installed in a spot the arm collides with, wired at the wrong logic level, and read by code that expects the opposite polarity.

Strong teams therefore maintain an explicit **interface list**: for each connection between subteams, who provides what, in what form, and by when. It is a one-page table, and it prevents most integration surprises.

## Sizing and Cross-Training

On a five-person team one person holds two or three roles — that is normal. What is not negotiable is that every role has exactly **one named owner**. Two owners means no owner. Rotate roles between projects so people build range, and cross-train enough that one absence does not stop the team.

## Leading Without Authority

Most robotics leads have no power to hire, fire, or grade anyone. Influence comes from being the person who is prepared, who removes obstacles for teammates, who shares credit, and who takes responsibility for the team's misses in public. That is exactly how technical leadership works in industry too.'''
            },
            {
                'title': 'Delegation That Actually Works',
                'content': '''# Delegation That Actually Works

New leads fail in one of two directions: they do everything themselves and become the bottleneck, or they announce "someone should handle the sensors" and nobody does. Both are delegation failures.

## What a Delegated Task Must Contain

1. **A single named owner.** Not a subteam; a person.
2. **A clear outcome.** What must be true when this is finished.
3. **Acceptance criteria.** How the team will verify it — the test, the measurement, the reviewer.
4. **A deadline** with a real date and time.
5. **The boundaries.** What the owner may decide alone, and what needs a team decision.
6. **The resources.** Budget, parts, access, and who can help when they get stuck.

**Weak:** "Can someone look at the gripper?"
**Strong:** "Maya owns the gripper mount. Done means it holds the part within 1 mm across 20 pick cycles in the VR sim, demonstrated at Thursday's 3:30 stand-up. Choose the bracket geometry yourself; check with me before changing the mounting pattern."

## Match the Task to the Person

| Owner is | Delegate this way |
|----------|-------------------|
| Skilled and confident | Give the outcome and get out of the way; check in at the milestone |
| Skilled but unsure | Give the outcome, then check in early to build confidence |
| Learning | Pair them with someone experienced and break the task into visible steps |
| Overloaded | Do not delegate; rebalance first, or the task silently dies |

## Follow-Up Is Not Micromanagement

Micromanaging is telling someone *how* to do a job you already assigned. Following up is asking whether the *outcome* is on track. Agree on check-in points when you delegate, so the follow-up is expected rather than a surprise inspection.

## Track It Where Everyone Can See

Use one shared task board with columns for To Do, In Progress, Blocked, and Done, and put the owner's name and the due date on every card. The **Blocked** column matters most: it is the lead's daily job to unblock people, and a task that has been blocked for three days is the lead's failure, not the owner's.

## Escalation Rules

Set the rule in advance: if you are stuck for more than a defined time — 30 minutes on a small task, a day on a large one — you must escalate. Teams that skip this rule lose entire afternoons to one person quietly fighting a problem someone else already solved.'''
            },
            {
                'title': 'Meetings That Produce Decisions',
                'content': '''# Meetings That Produce Decisions

A meeting is the most expensive thing a team does. Six people for thirty minutes costs three person-hours, and that is only worth spending if the meeting produces something the team could not produce over messages.

## Three Meetings, Three Jobs

- **Stand-up (10-15 minutes, frequent).** Each person answers three questions: what I finished, what I am doing next, what is blocking me. No problem-solving in the room — blockers are noted and taken offline with the two people who care.
- **Working session (60-120 minutes, as needed).** A small group actually solves one problem: a design review, a debugging session, a risk assessment. Only the people needed attend.
- **Milestone review (30-60 minutes, scheduled).** Demonstrate against acceptance criteria, decide go or no-go, and re-plan the next block of work.

## The Rules That Make Them Work

- **Publish an agenda** with the decisions to be made, not just the topics. "Choose gripper design A or B" is an agenda item; "gripper" is not.
- **Start on time**, even with people missing. Waiting punishes the punctual.
- **One conversation at a time.** Side discussions split the room and repeat the meeting.
- **Timebox each item.** When time runs out, either decide with what you have or assign someone to gather the missing data by a date.
- **End every item with an action:** who, what, by when.
- **Send notes within the day**, listing decisions and actions only. Nobody reads a transcript.

## Deciding When the Team Cannot Agree

Say the decision rule at the start of the discussion, not after it stalls: consensus, majority, or lead decides after hearing input. When the team deadlocks on a technical question, prefer running the test over continuing the argument — an hour of data usually settles what an hour of opinions cannot. When no test is possible in time, the lead decides, states the reasoning, and records it. Everyone then supports the decision publicly, including whoever argued the other way.

## The Meeting You Should Cancel

If the agenda is only status, replace the meeting with a written update. Status is broadcast; meetings are for the things that need dialogue.'''
            },
            {
                'title': 'Critique, Conflict, and Shared Documentation',
                'content': '''# Critique, Conflict, and Shared Documentation

The last skills of a project lead are the uncomfortable ones: telling a teammate their design will not work, hearing the same about yours, and making sure the team writes things down when nobody wants to.

## Giving Critique

- **Aim at the artifact, not the author.** "This bracket will flex under a 3 kg load" — never "you always over-engineer things."
- **Bring specific, testable evidence.** A measurement, a spec, a failed test, a standard. Vague praise and vague criticism are equally useless.
- **Offer a path forward.** Suggest a fix or an experiment; naming a problem with no next step just stalls the work.
- **Private for the person, public for the work.** Design gets reviewed in front of the team; performance conversations happen one-on-one.

## Receiving Critique

Listen to the whole comment before responding. Restate it — "so the concern is deflection under load, not the mounting pattern" — to make sure you are arguing about the same thing. Thank the reviewer, decide, and if you disagree, disagree with data rather than with volume. Defensiveness costs a team more than any single bad design does, because it teaches everyone to stop reviewing.

## When Conflict Escalates

1. **Separate the technical disagreement from the interpersonal one.** They usually get tangled and must be untangled to be solved.
2. **Restate both positions** until each side agrees the summary is fair.
3. **Find the shared criterion** — cycle time, cost, reliability, safety — and agree on it before comparing options.
4. **Test if you can.** Data ends more arguments than authority does.
5. **Decide, record the reasoning, and move.** Revisit only if new evidence appears.

Behavior that is never acceptable, in class or in industry: personal attacks, going silent and withdrawing effort, agreeing in the room and undermining the decision outside it, or bypassing a safety objection because it is inconvenient. A safety concern always stops the work until it is resolved.

## Documentation Is Everyone's Job

The documentation lead maintains the system; they cannot author it alone. What the whole team owes the record:

| Item | Who writes it | When |
|------|---------------|------|
| Design decision and the reason rejected options lost | Whoever made the decision | Same day |
| Wiring and I/O assignments | Controls owner | As built, not later |
| Test results, including failures | Whoever ran the test | Immediately, with the raw numbers |
| Interface agreements between subteams | Both sides | Before the work starts |
| Known issues and workarounds | Anyone who finds one | On discovery |

Write for the person who joins the team in six weeks, or for yourself after a long break, because that is who actually reads it. A team that documents as it goes never has to reconstruct a decision from memory — and reconstructing from memory is how the same mistake gets made twice.'''
            }
        ])
        self._create_lesson_questions(lesson, [
            {
                'text': 'A project lead assigns a task by saying "the controls subteam should handle the sensor wiring this week." What is the main weakness of this delegation?',
                'choices': [
                    ('There is no single named owner or acceptance criteria, so no one is accountable and no one can tell when it is done', True),
                    ('A week is too long a deadline for a wiring task', False),
                    ('Wiring should never be delegated by a project lead', False),
                    ('The lead should have wired it personally to guarantee quality', False),
                ]
            },
            {
                'text': 'During a stand-up, a teammate reports being blocked by a sensor that reads the wrong polarity. What should the team do?',
                'choices': [
                    ('Note the blocker and take the problem offline with the people who can solve it, keeping the stand-up short', True),
                    ('Debug the sensor immediately with all six people in the room', False),
                    ('Skip it, since a blocker is the responsibility of its owner alone', False),
                    ('Schedule a full milestone review to discuss it next week', False),
                ]
            },
            {
                'text': 'Two subteams deadlock over which gripper design to use and both have arguments but no data. What is the best next step?',
                'choices': [
                    ('Agree on a shared criterion, run a test to produce data, and decide from the result', True),
                    ('Let the more senior teammate decide because they have more experience', False),
                    ('Build both designs so neither subteam feels dismissed', False),
                    ('Postpone the decision until the deadline forces one option', False),
                ]
            },
            {
                'text': 'A reviewer tells a teammate, "You always over-engineer everything." How should this critique be reframed?',
                'choices': [
                    ('Aim it at the artifact with evidence: "This bracket adds 200 g and the load case only needs 3 kg of stiffness — can we test a lighter version?"', True),
                    ('Say the same thing privately so the rest of the team does not hear it', False),
                    ('Drop the concern entirely to keep the team getting along', False),
                    ('Redesign the bracket without telling the teammate', False),
                ]
            }
        ])

        self._create_unit1_quiz(unit)

    def _create_unit1_quiz(self, unit):
        quiz = self._quiz(
            unit, 'rob201-quiz-advanced-systems-safety-teams', 0,
            title='Advanced Systems, Safety & Teams Quiz',
            description='Test your understanding of integrated automated systems, industrial safety and lockout/tagout, professional standards, and leading a project team.',
            passing_score=70,
            points=20,
            max_attempts=3,
        )
        self._create_quiz_questions(quiz, [
            {
                'text': 'An automated line has stations with cycle times of 11, 19, and 13 seconds. An engineer speeds up the 11-second station to 9 seconds. What happens to the line output?',
                'choices': [
                    ('Nothing changes — the 19-second station is still the bottleneck that sets the line pace', True),
                    ('Output rises by about 18 percent because one station got faster', False),
                    ('Output falls because the stations are now less balanced', False),
                    ('The line now produces a part every 9 seconds', False),
                ]
            },
            {
                'text': 'A research lab replaces components in its test cell almost every month and wants to mix parts from several manufacturers. Which architecture fits best?',
                'choices': [
                    ('Open architecture, because published standard interfaces make substituting components straightforward', True),
                    ('Closed architecture, because a single vendor guarantees the combination works', False),
                    ('Closed architecture, because open systems cannot use industrial networks', False),
                    ('Neither — architecture only applies to production factories', False),
                ]
            },
            {
                'text': 'During a shutdown, a technician opens the electrical disconnect, applies a personal lock and tag, and immediately begins removing a robot axis motor. Which required step was skipped, and what is the risk?',
                'choices': [
                    ('Verifying zero energy — a raised axis and pressurized air can still release stored energy even with electrical power isolated', True),
                    ('Notifying affected employees, which only matters for a shift change', False),
                    ('Applying a second lock, since every lockout requires two locks', False),
                    ('Nothing was skipped; locking the electrical disconnect isolates all energy sources', False),
                ]
            },
            {
                'text': 'A team scores a hazard as Serious (3) severity and Likely (3) likelihood, producing a High score of 9. Following the hierarchy of controls, which response should be preferred first?',
                'choices': [
                    ('Redesign the process so the hazard is eliminated or the operator never needs to enter the hazard zone', True),
                    ('Issue cut-resistant gloves and safety glasses to everyone entering the cell', False),
                    ('Post a warning sign and add the hazard to the annual training slides', False),
                    ('Accept the risk because a score of 9 is not the maximum on the matrix', False),
                ]
            },
            {
                'text': 'Which combination gives an employer the strongest verifiable evidence from a high school automation student?',
                'choices': [
                    ('An OSHA 10 card with its date, plus a portfolio entry showing the problem, the specific role the student held, wiring photos, and before-and-after cycle-time data', True),
                    ('A transcript with a high grade in the robotics course', False),
                    ('A resume describing the student as passionate, hardworking, and a fast learner', False),
                    ('A list of every robotics club meeting the student attended', False),
                ]
            },
            {
                'text': 'A project lead assigns a task as: "Devon owns the light-curtain mounting. Done means the safety distance calculation is documented and reviewed by the safety lead before Friday at 3 p.m." Which delegation elements does this demonstrate?',
                'choices': [
                    ('A single named owner, a clear outcome with acceptance criteria, and a real deadline', True),
                    ('Consensus decision-making with the whole team involved', False),
                    ('Micromanagement, because the lead specified how to mount the device', False),
                    ('Delegation to a subteam so the work can be shared flexibly', False),
                ]
            }
        ])

    # ================== UNIT 2: Math & Physics: Torque, Gear Ratio, Stability & Payload ==================
    def _create_unit2(self, course):
        unit = self._unit(course, 1, 'Math & Physics: Torque, Gear Ratio, Stability & Payload')

        # Lesson 1: Torque & Rotational Motion
        lesson = self._lesson(
            unit, 'rob201-torque-and-rotational-motion', 0,
            title='Torque & Rotational Motion',
        )
        self._create_sections(lesson, [
            {
                'title': 'Overview',
                'content': '''# Torque & Rotational Motion

Two robot arms use the exact same motor. One lifts a full water bottle without complaining; the other stalls, gets hot, and trips a breaker. The difference is almost never the motor - it is torque, and torque is a number you can calculate before you ever cut a piece of aluminum.

## Learning Objectives

By the end of this lesson, you will be able to:
- Calculate torque as force times perpendicular distance and convert between N·m, in·lb, ft·lb, and kg·cm
- Find the moment arm of a load, including when an arm is raised above horizontal
- Distinguish static (holding) torque from dynamic (accelerating) torque and estimate both
- Read a motor torque-speed curve and explain why torque falls as speed rises

> **TEKS alignment:** §127.750(c)(7) — applies advanced mathematics and physics concepts to the design, analysis, and operation of robotic and automated systems.'''
            },
            {
                'title': 'What Torque Is and How to Compute It',
                'content': '''# What Torque Is and How to Compute It

**Torque** is twisting effort - the rotational equivalent of force. A force pushes something in a straight line; a torque turns something about an axis. The definition is one line:

`torque = force x perpendicular distance from the axis`

That perpendicular distance has a name: the **moment arm**. Both halves matter equally. Double the force and you double the torque; move the load twice as far from the pivot and you also double the torque. This is why a long robot arm is so much harder on a motor than a short one carrying the same object.

## A Worked Example

A robot arm pivots at its shoulder and holds a 2 kg payload at the far end, 0.35 m from the pivot, with the arm horizontal.

1. Convert mass to weight (force): `weight = mass x g = 2 kg x 9.8 m/s^2 = 19.6 N`
2. Identify the moment arm: the arm is horizontal, so the perpendicular distance is the full `0.35 m`
3. Multiply: `torque = 19.6 N x 0.35 m = 6.86 N·m`

The single most common mistake in this calculation is skipping step 1 and multiplying kilograms by meters. That gives 0.7, which is not torque and is not anything.

## Units and Conversions

Motor and servo data sheets are a zoo of units. Learn to normalize everything to newton-meters before comparing parts.

| Unit | Value in N·m | Where you see it |
|------|--------------|------------------|
| 1 N·m | 1.000 | SI standard; most gearmotor data sheets |
| 1 in·lb | 0.113 | US industrial actuators, fastener specs |
| 1 ft·lb | 1.356 | Large motors, automotive |
| 1 kg·cm | 0.0981 | Hobby and competition servos |
| 1 oz·in | 0.00706 | Small stepper motors |

So a servo advertised at "20 kg·cm" delivers `20 x 0.0981 = 1.96 N·m`, and a 25 in·lb actuator delivers `25 x 0.113 = 2.83 N·m`. Written in the same units, the servo is weaker than the actuator - which you could not tell at a glance from the marketing numbers.'''
            },
            {
                'title': 'Moment Arms and Arm Angle',
                'content': '''# Moment Arms and Arm Angle

The word **perpendicular** in the torque formula does real work. The moment arm is not the length of the part - it is the perpendicular distance from the axis of rotation to the line along which the force acts.

## Three Cases Worth Memorizing

- **Force perpendicular to the arm:** moment arm equals the full arm length. Maximum torque.
- **Force pointing straight at the axis:** the line of action passes through the pivot, the perpendicular distance is zero, and the torque is zero no matter how hard you push. Pushing a door toward its hinges never opens it.
- **Force at an angle:** only the perpendicular component turns the joint. The rest just tries to stretch or crush the arm.

## Gravity and a Raised Arm

Gravity always pulls straight down. So for an arm carrying a load, the moment arm is the **horizontal** distance from the pivot to the load, not the arm length. If the arm has length L and is raised by an angle above horizontal:

`moment arm = L x cos(angle above horizontal)`

| Arm angle above horizontal | cos(angle) | Moment arm for a 0.35 m arm | Torque holding 2 kg |
|---------------------------|-----------|------------------------------|---------------------|
| 0 degrees (horizontal) | 1.00 | 0.350 m | 6.86 N·m |
| 30 degrees | 0.87 | 0.305 m | 5.97 N·m |
| 45 degrees | 0.71 | 0.249 m | 4.87 N·m |
| 60 degrees | 0.50 | 0.175 m | 3.43 N·m |
| 90 degrees (straight up) | 0.00 | 0.000 m | 0.00 N·m |

Read that table again, because it explains a behavior every robot builder eventually meets: **an arm is hardest to hold when it is horizontal**, and it gets easier as it rises. Teams routinely size a motor by testing the arm near vertical, then watch it collapse the first time it reaches straight out. Always size for the worst case, which is the horizontal position at full extension.

The same logic runs in reverse for a wrench: pulling perpendicular to the handle gives full torque, pulling at 45 degrees gives about 71 percent of it, and pulling along the handle gives none.'''
            },
            {
                'title': 'Static Torque vs Dynamic Torque',
                'content': '''# Static Torque vs Dynamic Torque

Engineers separate the torque a joint needs into two parts, because they scale with completely different things.

## Static Torque - Just Holding Still

**Static torque** is what the joint needs to hold a position against gravity and friction. Nothing is moving; nothing is accelerating. For the 2 kg arm from earlier, the static requirement at full horizontal extension is the `6.86 N·m` already calculated, plus whatever the arm structure itself weighs.

A joint that is only barely strong enough to hold still has no capacity left for anything else - and a motor stalled at maximum torque draws maximum current and heats fast. Holding position for a full match is a real thermal load.

## Dynamic Torque - Getting It Moving

**Dynamic torque** is the extra twist needed to *accelerate* the arm. Its rotational form of Newton's second law is:

`torque = moment of inertia x angular acceleration`

Treat the 2 kg payload as a point mass at 0.35 m to estimate the moment of inertia:

1. `I = m x r^2 = 2 kg x (0.35 m)^2 = 2 x 0.1225 = 0.245 kg·m^2`
2. Suppose the arm must reach 1.0 rad/s in 0.5 s, so `angular acceleration = 1.0 / 0.5 = 2.0 rad/s^2`
3. `dynamic torque = 0.245 x 2.0 = 0.49 N·m`

## Adding Them Up

The joint must supply both at the same time:

`total = static + dynamic = 6.86 + 0.49 = 7.35 N·m`

Two lessons fall out of those numbers. First, for a **slow** arm, gravity dominates and the dynamic term is almost a rounding error. Second, dynamic torque grows with the *square* of the distance and linearly with acceleration - so a longer, faster arm flips the balance quickly. Double the arm length and the moment of inertia quadruples.

Finally, add **friction and breakaway torque**. Gearboxes, bearings, and bent shafts all resist motion, and a mechanism that has been sitting still needs a bit more torque to break loose than to keep turning. Practicing engineers budget for it rather than discovering it at competition.'''
            },
            {
                'title': 'Motor Torque Curves, Stall Torque, and Free Speed',
                'content': '''# Motor Torque Curves, Stall Torque, and Free Speed

A motor does not have "a" torque. It has a **torque-speed curve**, and where it lands on that curve depends entirely on how hard the load is fighting it.

## The Two Endpoints

- **Stall torque** - the torque the motor produces at zero speed, when the output shaft is held completely still. This is the *maximum* torque the motor can ever make.
- **Free speed** (no-load speed) - the speed the motor spins with nothing attached. At free speed it produces essentially *zero* useful torque.

For a brushed DC motor, the line between those two points is close to straight:

`torque = stall torque x (1 - speed / free speed)`

## Why Torque Falls as Speed Rises

A spinning motor is also a generator. As the armature turns, it produces a voltage that opposes the supply voltage - **back-EMF** - and back-EMF grows with speed. The current through the windings is set by the *difference* between the supply voltage and the back-EMF, and motor torque is proportional to current. So:

- At **stall** there is no back-EMF, current is maximum, torque is maximum, and so is the heat
- At **free speed** back-EMF nearly cancels the supply, almost no current flows, and torque collapses to near zero

## Reading the Curve

A motor with a 2.10 N·m stall torque and 100 RPM free speed:

| Speed (RPM) | Fraction of free speed | Torque (N·m) | Mechanical power (W) |
|-------------|------------------------|--------------|----------------------|
| 0 | 0.00 | 2.10 | 0.0 |
| 25 | 0.25 | 1.58 | 4.1 |
| 50 | 0.50 | 1.05 | 5.5 |
| 75 | 0.75 | 0.53 | 4.1 |
| 100 | 1.00 | 0.00 | 0.0 |

Power is zero at both ends - all torque with no motion, then all motion with no torque - and **peaks at about half free speed**. That is the sweet spot a gear ratio is chosen to hit.

## The Practical Rules

1. **Never design to stall torque.** A stalled motor is a resistor: it converts the entire battery input into heat, cooks its windings, and trips breakers. Size a mechanism to run at 20 to 50 percent of stall torque.
2. **Batteries sag.** A drooping battery lowers both stall torque and free speed, so late-match performance is worse than data-sheet performance.
3. **A gearmotor curve is different from its bare motor curve.** Gearbox ratings publish output torque and output speed already reduced - and the gearbox has its own maximum it can survive.'''
            }
        ])
        self._create_lesson_questions(lesson, [
            {
                'text': 'A 3 kg payload sits at the end of a horizontal robot arm, 0.5 m from the pivot. Using g = 9.8 m/s^2, what torque does the payload create at the pivot?',
                'choices': [
                    ('14.7 N·m', True),
                    ('1.5 N·m - multiplying mass by distance without converting mass to weight', False),
                    ('29.4 N·m - the payload weight alone, with the moment arm ignored', False),
                    ('58.8 N·m - dividing the weight by the moment arm instead of multiplying', False),
                ]
            },
            {
                'text': 'Why does a brushed DC motor produce less torque as its speed increases?',
                'choices': [
                    ('Back-EMF grows with speed, which lowers the current through the windings, and torque is proportional to current', True),
                    ('The gearbox ratio automatically changes as the motor speeds up', False),
                    ('Friction inside the motor increases until it cancels all of the torque', False),
                    ('The battery voltage rises with speed and pushes back against the motor', False),
                ]
            },
            {
                'text': 'An arm of fixed length holds the same load. At which arm position does the joint have to supply the MOST torque?',
                'choices': [
                    ('Horizontal, because the moment arm equals the full arm length there', True),
                    ('Straight up, because the load is highest off the ground', False),
                    ('At 45 degrees, because the load is split between two directions', False),
                    ('The position does not matter - the torque is the same at every angle', False),
                ]
            },
            {
                'text': 'A slow-moving arm needs 8.0 N·m to hold its load still. What can you say about the torque needed to also accelerate that arm from rest?',
                'choices': [
                    ('It is more than 8.0 N·m, because dynamic torque adds on top of the static holding torque', True),
                    ('It is exactly 8.0 N·m, because static torque already includes acceleration', False),
                    ('It is less than 8.0 N·m, because a moving arm no longer fights gravity', False),
                    ('It cannot be more than 8.0 N·m unless the payload mass changes', False),
                ]
            }
        ])

        # Lesson 2: Gear Ratios, Speed & Mechanical Advantage
        lesson = self._lesson(
            unit, 'rob201-gear-ratios-and-mechanical-advantage', 1,
            title='Gear Ratios, Speed & Mechanical Advantage',
        )
        self._create_sections(lesson, [
            {
                'title': 'Overview',
                'content': '''# Gear Ratios, Speed & Mechanical Advantage

A motor hands you exactly one combination of speed and torque, and it is almost never the combination your mechanism needs. Gears are the exchange rate: they let you buy torque with speed, or speed with torque, in whatever proportion the job requires - and the whole transaction is arithmetic you can do before you build.

## Learning Objectives

By the end of this lesson, you will be able to:
- Compute a gear ratio from driver and driven tooth counts and identify reductions vs overdrives
- Calculate output RPM and output torque for single-stage and compound gear trains
- Explain mechanical advantage as a trade of distance and speed for force
- Account for efficiency losses when predicting the real output of a gear train

> **TEKS alignment:** §127.750(c)(2) — applies mathematical process standards to analyze relationships and solve problems in robotic and automated systems.
> **TEKS alignment:** §127.750(c)(7) — applies advanced mathematics and physics concepts to the design, analysis, and operation of robotic and automated systems.'''
            },
            {
                'title': 'Driver, Driven, and the Ratio',
                'content': '''# Driver, Driven, and the Ratio

Two meshing gears have names based on where the power comes from:

- The **driver** (input) gear is the one attached to the motor
- The **driven** (output) gear is the one attached to the mechanism

The **gear ratio** compares them by tooth count:

`gear ratio = driven teeth / driver teeth`

A 12-tooth driver turning a 60-tooth driven gear gives `60 / 12 = 5`, written **5:1**. Because gear teeth are the same size on both gears, tooth count is proportional to diameter - so you can equally use `driven diameter / driver diameter` and get the same answer.

## Reduction vs Overdrive

| Ratio | Name | Output speed | Output torque | Typical use |
|-------|------|--------------|---------------|-------------|
| Greater than 1 (5:1) | Reduction | Slower | Higher | Arms, lifts, climbers, heavy pushing |
| Exactly 1 (1:1) | Direct | Unchanged | Unchanged | Just changing shaft position |
| Less than 1 (1:3) | Overdrive | Faster | Lower | Fast flywheels, high top-speed drivetrains |

Most robot mechanisms use reductions, because electric motors naturally spin fast and weak while robot jobs are usually slow and strong.

## Direction and Idlers

Two externally meshing gears always spin in **opposite** directions. Slip a third gear between them - an **idler** - and the input and output turn the same way. Here is the part that surprises students: an idler changes direction but **does not change the ratio at all**. Its tooth count cancels out, because it is simultaneously the driven gear of the first mesh and the driver of the second. Use idlers to fix rotation direction or to span a distance, never to gain torque.

## Chain, Belt, and Sprockets

Chain-and-sprocket and toothed-belt drives obey exactly the same math with sprocket tooth counts in place of gear tooth counts, and they have one advantage: the two shafts can be far apart, and both shafts turn the **same** direction. That is why most drivetrains use chain or belt between the gearbox and the wheels.'''
            },
            {
                'title': 'The Speed-Torque Trade-off in Numbers',
                'content': '''# The Speed-Torque Trade-off in Numbers

Gears do not create energy. They redistribute it. Ideally, the power going in equals the power coming out, and since power is torque times rotational speed, whatever you multiply one by, you divide the other by.

`output RPM = input RPM / gear ratio`

`output torque = input torque x gear ratio`

The gear ratio *is* the ideal **mechanical advantage** of the gear train.

## A Worked Example

A motor is turning at 200 RPM and producing 0.50 N·m. Put a 12-tooth gear on the motor and mesh it with a 60-tooth gear on the mechanism.

1. `gear ratio = 60 / 12 = 5`, a 5:1 reduction
2. `output RPM = 200 / 5 = 40 RPM`
3. `output torque = 0.50 x 5 = 2.50 N·m`

Sanity check the power: input is roughly `0.50 N·m x 200 RPM`, output is roughly `2.50 N·m x 40 RPM`, and both products equal 100. Power balanced, exactly as expected.

## A Table of Ratios

Every row below starts from the same motor: **200 RPM, 0.50 N·m**.

| Driver teeth | Driven teeth | Ratio | Output RPM | Output torque (N·m) |
|--------------|--------------|-------|------------|---------------------|
| 36 | 12 | 1:3 (overdrive) | 600.0 | 0.17 |
| 12 | 12 | 1:1 | 200.0 | 0.50 |
| 12 | 36 | 3:1 | 66.7 | 1.50 |
| 12 | 60 | 5:1 | 40.0 | 2.50 |
| 12 | 84 | 7:1 | 28.6 | 3.50 |

Notice that no row escapes the trade: the RPM column and the torque column move in exactly opposite proportion. There is no ratio that gives you more of both.

## Reading It as Mechanical Advantage

Mechanical advantage always costs distance. In a 5:1 reduction, the motor shaft turns five full revolutions for every one revolution of the output. The motor moves five times as far to deliver five times the twist - the same bargain a lever or a pulley system offers, just packaged in metal teeth.'''
            },
            {
                'title': 'Compound Gear Trains',
                'content': '''# Compound Gear Trains

One pair of gears can only reduce so far before the big gear stops fitting on the robot. A 50:1 reduction from a 12-tooth driver would need a 600-tooth gear - a wheel roughly a meter across. The solution is to **stage** the reduction.

## Stages Multiply

A **compound gear train** puts two gears on a shared middle shaft so they turn together: the large driven gear of stage one is rigidly coupled to the small driver gear of stage two. Overall ratio is the **product** of the stage ratios:

`overall ratio = stage 1 ratio x stage 2 ratio x ...`

## A Worked Example

Motor: 300 RPM, 0.50 N·m.

- **Stage 1:** 12-tooth driver into a 36-tooth gear = `36 / 12 = 3`, so 3:1
- **Stage 2:** 15-tooth driver (on the same middle shaft) into a 60-tooth gear = `60 / 15 = 4`, so 4:1
- **Overall:** `3 x 4 = 12`, so 12:1

Now compute the output:

1. `output RPM = 300 / 12 = 25 RPM`
2. `ideal output torque = 0.50 x 12 = 6.00 N·m`

That 50:1 problem from before becomes two ordinary stages - `7 x 7 = 49` from two 12-to-84 meshes - with no gear larger than 84 teeth.

## Multiply, Do Not Add

The single most common error on this topic is adding stage ratios. A 3:1 followed by a 4:1 is **12:1**, not 7:1. If a student answer is 7:1, they added; if it is 1.33:1, they divided. Check your work by tracking speed through the train one shaft at a time: 300 RPM in, 100 RPM after stage one, 25 RPM after stage two.

## Planetary Gearboxes

Most commercial gearmotors hide a **planetary** gearbox inside: a central sun gear driving several planet gears inside a fixed ring gear. Planetary stages pack a large reduction into a short cylinder and share the load across several teeth at once, which is why they survive torque that would strip a single exposed spur pair. Their published ratios stage exactly the same way - a 5:1 cartridge plus a 7:1 cartridge is a 35:1 gearbox.'''
            },
            {
                'title': 'Efficiency, Losses, and Choosing a Ratio',
                'content': '''# Efficiency, Losses, and Choosing a Ratio

Every calculation so far assumed a perfect gear train. Real gears lose energy to sliding friction between teeth, bearing drag, oil churning, and misalignment. So the honest formula is:

`actual output torque = input torque x gear ratio x efficiency`

## Typical Efficiencies Per Stage

| Drive type | Efficiency per stage | Notes |
|------------|---------------------|-------|
| Spur gears, well aligned and lubricated | 95 to 98 percent | The workhorse of robot gearboxes |
| Chain and sprocket | 95 to 98 percent | Drops fast when the chain is loose or dry |
| Toothed belt | 95 to 98 percent | Quiet; needs correct tension |
| Bevel gears | 93 to 97 percent | For turning power through 90 degrees |
| Worm gear | 40 to 70 percent | Huge reduction in one stage, but very lossy |

## Losses Compound Too

Stack three spur stages at 95 percent each and the train keeps `0.95 x 0.95 x 0.95 = 0.857`, or about **86 percent**. So the 12:1 example from the previous section, built from two meshes at 95 percent, delivers:

`6.00 N·m x 0.95 x 0.95 = 6.00 x 0.9025 = 5.42 N·m`

Its effective mechanical advantage is `12 x 0.9025 = 10.8`, not 12. Predicting 12 and building for exactly 12 is how a mechanism ends up two percent short at the worst possible moment.

## The Worm Gear Trade

A worm drive is inefficient on purpose in one useful way: most worm gears are **self-locking**, meaning the output cannot back-drive the input. An arm on a worm drive holds its position with the motor completely off - no holding current, no heat, no drift. You pay for that with roughly half your power and a gearbox that cannot be moved by hand.

## Choosing a Ratio

1. Calculate the worst-case torque the mechanism actually needs (highest load, full extension)
2. Add a safety margin - do not plan to run near stall
3. Divide by the motor torque you intend to use at that operating point to get the required ratio
4. Round *up* to the nearest ratio you can build from available gears
5. Check the resulting speed: a lift that is strong enough but takes 30 seconds to raise has failed too

Torque and speed are both requirements. A ratio that satisfies only one of them is not a solution.'''
            }
        ])
        self._create_lesson_questions(lesson, [
            {
                'text': 'A 12-tooth gear on a motor drives a 60-tooth gear on a mechanism. The motor turns at 300 RPM and produces 0.6 N·m. Ignoring losses, what does the output shaft do?',
                'choices': [
                    ('60 RPM at 3.0 N·m', True),
                    ('1500 RPM at 0.12 N·m - the ratio applied upside down', False),
                    ('60 RPM at 0.12 N·m - speed reduced and torque reduced as well', False),
                    ('300 RPM at 3.0 N·m - torque multiplied with no change in speed', False),
                ]
            },
            {
                'text': 'A compound gear train has a 3:1 first stage followed by a 4:1 second stage. What is the overall reduction?',
                'choices': [
                    ('12:1', True),
                    ('7:1 - adding the two stage ratios', False),
                    ('1.33:1 - dividing the two stage ratios', False),
                    ('4:1 - only the last stage counts', False),
                ]
            },
            {
                'text': 'A team builds a 12:1 gearbox from two spur stages that are each about 95 percent efficient. Why is the measured output torque less than 12 times the input torque?',
                'choices': [
                    ('Friction in each mesh loses energy, and the losses multiply: 0.95 x 0.95 is about 0.90 of the ideal torque', True),
                    ('The gear ratio changes once the gears begin turning under load', False),
                    ('Torque multiplication only works for chain drives, not spur gears', False),
                    ('The second stage cancels part of the first stage ratio', False),
                ]
            },
            {
                'text': 'An idler gear is added between a driver gear and a driven gear. What does it change?',
                'choices': [
                    ('The direction the output turns, but not the gear ratio', True),
                    ('The gear ratio, multiplying it by the idler tooth count', False),
                    ('The output torque, increasing it without changing speed', False),
                    ('Nothing at all - an idler has no effect on the train', False),
                ]
            }
        ])

        # Lesson 3: Center of Mass, Stability & Tipping
        lesson = self._lesson(
            unit, 'rob201-center-of-mass-and-stability', 2,
            title='Center of Mass, Stability & Tipping',
        )
        self._create_sections(lesson, [
            {
                'title': 'Overview',
                'content': '''# Center of Mass, Stability & Tipping

A robot that tips over has lost the match, damaged itself, and possibly hurt someone - and it almost always tips for a reason you could have calculated on paper. Stability is not luck or driving skill. It is the geometry of where the mass sits relative to where the wheels touch the ground.

## Learning Objectives

By the end of this lesson, you will be able to:
- Calculate the center of mass of a multi-part robot as a mass-weighted average
- Define the support polygon and the static stability margin
- Apply the tipping condition to predict the critical incline angle and acceleration
- Evaluate design fixes such as lowering mass, widening the base, and adding counterweights

> **TEKS alignment:** §127.750(c)(7) — applies advanced mathematics and physics concepts to the design, analysis, and operation of robotic and automated systems.'''
            },
            {
                'title': 'Finding the Center of Mass',
                'content': '''# Finding the Center of Mass

The **center of mass** (CoM) is the single point where you could treat the robot's entire mass as being concentrated. Because gravity acts uniformly at robot scale, it is the same point as the **center of gravity**, and the whole weight of the robot behaves as one force acting straight down through it.

## The Formula

The CoM along any axis is a **mass-weighted average** of the part positions:

`CoM = (m1 x d1 + m2 x d2 + ... ) / (m1 + m2 + ... )`

Each part pulls the CoM toward itself in proportion to its mass. Heavy parts dominate; light parts barely matter.

## A Worked Example: CoM Height

A robot has three significant masses, measured as heights above the floor:

| Part | Mass (kg) | Height (m) | Mass x Height |
|------|-----------|------------|---------------|
| Chassis and drivetrain | 8.0 | 0.15 | 1.20 |
| Battery | 1.5 | 0.08 | 0.12 |
| Arm assembly (stowed) | 3.0 | 0.55 | 1.65 |
| **Total** | **12.5** | | **2.97** |

`CoM height = 2.97 / 12.5 = 0.238 m` - about 24 cm off the floor.

## Now Raise the Arm

Same robot, but the arm is lifted so its mass now sits at 1.00 m:

- New moment sum: `1.20 + 0.12 + (3.0 x 1.00) = 4.32`
- `CoM height = 4.32 / 12.5 = 0.346 m` - about 35 cm

Raising the arm moved the robot's center of mass up by **11 cm**, even though the chassis and battery never moved. That is the whole reason a robot that is rock-solid while driving becomes twitchy the moment the lift goes up, and it is why competition drivers are coached to lower the arm before crossing rough terrain.

## Measuring It Instead

You can also find CoM experimentally: balance the robot on a narrow edge (a length of pipe) and mark the balance line, then repeat in a second direction. Or set each side of the robot on a separate scale and use the weight split to solve for the CoM position. Estimate on paper during design, then measure the real machine - CAD models miss wire harnesses, tape, and the tools someone left inside the frame.'''
            },
            {
                'title': 'Support Polygon and Stability Margin',
                'content': '''# Support Polygon and Stability Margin

## The Support Polygon

Draw the points where the robot touches the ground, then draw the smallest convex shape that encloses them all. That shape is the **support polygon**. For a four-wheel robot it is a rectangle set by the **track width** (side to side) and the **wheelbase** (front to back). For a three-wheel robot it is a triangle - one which is often uncomfortably narrow at the single-wheel corner.

The fundamental rule of static stability:

> A robot is stable as long as the vertical line through its center of mass falls **inside** the support polygon. The instant that line crosses an edge, the robot tips.

## Static Stability Margin

The **static stability margin** is the horizontal distance from the CoM ground projection to the nearest edge of the support polygon. A robot with a 0.40 m track width, perfectly centered, has 0.20 m of margin on each side. Shift the CoM 0.05 m to the left and the left margin becomes 0.15 m - a 25 percent loss of protection on that side, with no change in total weight.

Margin is often reported as a percentage of the half-dimension so robots of different sizes can be compared.

## What Eats Your Margin

- **A raised load** does not move the CoM sideways, but it raises it - and, as the next section shows, height converts into lost margin the moment the robot tilts or accelerates
- **An extended arm** moves the CoM horizontally, straight toward one edge. A 3 kg arm swung 0.4 m forward on a 12.5 kg robot shifts the CoM forward by `(3.0 x 0.4) / 12.5 = 0.096 m` - nearly 10 cm of margin gone
- **Grabbing a heavy game piece** does both at once
- **A worn or flat wheel** silently shrinks the polygon

## Tracked and Legged Robots

Tracked robots enjoy an enormous support polygon: the full contact patch of both tracks. Legged robots have the opposite problem - their polygon changes shape at every step, and while a leg is in the air the polygon may collapse to a line. That is why walking robots need active balance control while a wheeled robot can rely on geometry alone.'''
            },
            {
                'title': 'The Tipping Condition',
                'content': '''# The Tipping Condition

Tipping is a contest between two moments about the edge the robot would roll over.

- The **restoring moment** is the robot weight times its horizontal distance to that edge: `W x d`
- The **overturning moment** is whatever sideways force acts at the CoM times the CoM height: `F x h`

The robot tips when the overturning moment wins: `F x h > W x d`.

## On an Incline

Park a robot on a ramp and gravity itself supplies the overturning force. The robot tips when:

`tan(critical angle) = d / h`

where `d` is the horizontal distance from the CoM to the downhill support edge and `h` is the CoM height. Take the robot from the previous section - 0.40 m track width, so `d = 0.20 m`:

| Condition | CoM height h | d / h | Critical angle |
|-----------|--------------|-------|----------------|
| Arm stowed | 0.238 m | 0.84 | about 40 degrees |
| Arm raised | 0.346 m | 0.58 | about 30 degrees |

Raising the arm cost that robot **10 degrees** of usable slope. Note what the formula does *not* contain: mass. A heavy robot and a light robot with the same geometry tip at the same angle, because weight appears on both sides of the inequality and cancels.

## Under Acceleration

Hard acceleration, braking, and turning all push the CoM the same way an incline does. The critical acceleration is:

`critical acceleration = g x d / h`

For the stowed robot with `d = 0.20 m` toward the front axle and `h = 0.238 m`:

`critical acceleration = 9.8 x 0.20 / 0.238 = 8.2 m/s^2`

With the arm raised, that drops to `9.8 x 0.20 / 0.346 = 5.7 m/s^2`. Turning counts too: a robot at 1.5 m/s carving a 0.8 m radius turn pulls `v^2 / r = 2.25 / 0.8 = 2.8 m/s^2` sideways - safe in both configurations here, but not with a heavier arm held higher.

## Design Fixes, Ranked

1. **Lower the CoM.** Height is in the denominator of every formula above. Mount the battery on the floor of the chassis, inside the wheelbase.
2. **Widen the base.** More track width or wheelbase means more `d`. Cheap, if the size rules allow it.
3. **Limit the payload height and speed.** Software can cap drive acceleration whenever the lift is above a set height - a very common and very effective fix.
4. **Add a counterweight** only as a last resort. Ballast behind the pivot does rebalance the CoM, but it adds mass the drivetrain must move and inertia every turn must fight. Relocating existing mass is nearly always better than adding new mass.'''
            },
            {
                'title': 'Stability in Practice',
                'content': '''# Stability in Practice

Formulas tell you where the cliff is. These habits keep robots away from the edge.

## Design-Time Checks

- **Compute the CoM in the worst configuration**, not the parked one: arm fully extended, at maximum height, holding the heaviest legal payload. That is the case that tips.
- **Check every axis.** Robots tip sideways *and* forward. A long, narrow robot is stable front-to-back and fragile side-to-side; run the numbers for both.
- **Keep heavy things low and centered.** Battery, gearboxes, and motors belong near the floor, inside the wheelbase. A drive motor mounted high to save space is a stability tax you pay every match.
- **Watch the arm reach limit.** Doubling reach doubles the horizontal CoM shift a payload causes.

## Test-Time Checks

- **The tilt-table test.** Drive the robot onto a board and slowly raise one end until two wheels lift. Measure the angle, and compare it to your prediction. If reality is 8 degrees worse than the calculation, something heavy is not where you think it is.
- **The push test.** Push the robot at CoM height until it starts to lift a wheel. Repeat in the worst configuration.
- **Log the failures.** Every tip during practice is data. Note the configuration, speed, and surface.

## Control-Time Fixes

Software is the fastest lever in a stability problem:

- **Slew-rate limiting** on the drive command prevents a driver from slamming full throttle and pitching the robot back
- **Height-based speed caps** slow the drivetrain automatically when the lift is up
- An **accelerometer or IMU** can detect a dangerous tilt angle and cut drive power or lower the arm automatically

## Why This Matters Beyond Competition

Industrial mobile robots and forklifts are governed by the same physics and by real safety standards. A forklift is rated for a load at a specified **load center** distance, and exceeding either the weight or the distance risks a tip-over that kills workers every year. Warehouse AMRs limit their own speed in turns based on payload height for exactly this reason. The classroom version of this calculation and the industrial version are the same calculation - only the consequences differ.'''
            }
        ])
        self._create_lesson_questions(lesson, [
            {
                'text': 'A 10 kg robot has its center of mass 0.20 m above the floor. It picks up a 2 kg payload and holds it 0.80 m above the floor. What is the new center of mass height?',
                'choices': [
                    ('0.30 m', True),
                    ('0.50 m - averaging the two heights without weighting them by mass', False),
                    ('0.36 m - dividing the moment sum by 10 kg instead of the 12 kg total', False),
                    ('1.00 m - adding the two heights together', False),
                ]
            },
            {
                'text': 'A robot has a 0.40 m track width and its center of mass is centered, 0.20 m above the floor. Using tan(critical angle) = d / h, at about what side-slope angle does it tip?',
                'choices': [
                    ('About 45 degrees, since d = 0.20 m and h = 0.20 m give a ratio of 1', True),
                    ('About 63 degrees, using the full 0.40 m track width in place of the half-track', False),
                    ('About 22 degrees, because the two downhill wheels each carry half the load', False),
                    ('It cannot tip on a ramp as long as all four wheels stay on the surface', False),
                ]
            },
            {
                'text': 'What is the support polygon of a wheeled robot?',
                'choices': [
                    ('The smallest convex shape enclosing all of its ground contact points; the robot is stable while the center of mass projects inside it', True),
                    ('The outline of the robot frame viewed from above, including any overhanging arm', False),
                    ('The area swept by the arm at full extension', False),
                    ('The rectangle formed by the robot height and its track width', False),
                ]
            },
            {
                'text': 'Two robots have identical geometry, but one weighs twice as much as the other. How do their critical tipping angles on an incline compare?',
                'choices': [
                    ('They are the same, because weight appears on both sides of the tipping condition and cancels out', True),
                    ('The heavier robot tips at a much smaller angle, because it has more weight to overturn', False),
                    ('The heavier robot tips at a much larger angle, because heavier robots are always more stable', False),
                    ('The angles cannot be compared unless the two robots use the same wheel material', False),
                ]
            }
        ])

        # Lesson 4: Payload, Load Calculations & Safety Factors
        lesson = self._lesson(
            unit, 'rob201-payload-and-load-calculations', 3,
            title='Payload, Load Calculations & Safety Factors',
        )
        self._create_sections(lesson, [
            {
                'title': 'Overview',
                'content': '''# Payload, Load Calculations & Safety Factors

"How much can it lift?" sounds like a simple question, and the honest answer is always "it depends - on how far out, how fast, how often, and how much margin you want left when the battery is low." This lesson turns that answer into arithmetic you can defend to a judge, a teacher, or a safety inspector.

## Learning Objectives

By the end of this lesson, you will be able to:
- Explain what a rated payload includes, and why the end effector counts against it
- Calculate the total joint moment produced by an arm, its gripper, and its payload at full extension
- Apply a factor of safety and select a component rating from a computed load
- Describe derating and the conditions that reduce usable payload below the rated value

> **TEKS alignment:** §127.750(c)(2) — applies mathematical process standards to analyze relationships and solve problems in robotic and automated systems.'''
            },
            {
                'title': 'What Rated Payload Actually Means',
                'content': '''# What Rated Payload Actually Means

Every industrial robot arm ships with a **rated payload** in its data sheet: 5 kg, 10 kg, 500 kg. That number is far more conditional than it looks.

## The End Effector Counts

The rated payload is the total mass hanging on the tool flange - and the **end effector is part of that mass**. A robot rated for 5 kg fitted with a 1.8 kg two-finger gripper can only pick up:

`5.0 - 1.8 = 3.2 kg` of actual part

Add a camera bracket and a hose fitting and you are down to 3.0 kg. Teams and integrators lose real money by ordering an arm sized to the part instead of to the part plus the tooling, and the fix afterwards is a bigger, more expensive robot.

## The Rating Assumes Conditions

A payload rating is quoted at a specific set of conditions, usually:

- The payload center of gravity within a stated distance of the tool flange
- Rated speed and acceleration
- A stated mounting orientation (floor mounted, not hanging from a ceiling)
- Continuous duty within a temperature range

Change any of those and the usable payload falls. Hang the mass 200 mm out from the flange instead of 50 mm and the wrist joint sees four times the moment even though the mass on the scale is identical.

## Reach and Payload Trade Against Each Other

This is why arm manufacturers publish payload-vs-reach charts rather than a single number, and why the same catalog will offer a 10 kg arm with 1.3 m reach next to a 20 kg arm with 1.0 m reach.

| Arm configuration | What the joint feels |
|-------------------|----------------------|
| Payload tucked close to the shoulder | Small moment - easy |
| Payload at mid-reach | Moderate moment |
| Payload at full horizontal extension | Maximum moment - the sizing case |

## Static vs Dynamic Payload

The rated payload is usually a *dynamic* rating: the mass the robot can move at rated speed and acceleration. Many arms can **hold** more than they can move. Some can hold considerably more with the brakes engaged and the motors off. Never mix the two numbers - lifting a mass the arm can only hold is how gearboxes get stripped.'''
            },
            {
                'title': 'Calculating the Load at Full Extension',
                'content': '''# Calculating the Load at Full Extension

Sizing a joint means adding up every moment acting on it in the worst configuration. Work in newton-meters and keep the parts separate so a mistake in one line does not hide.

## The Setup

A shoulder joint drives a horizontal arm:

- Arm structure: **1.5 kg**, center of mass at **0.30 m** from the pivot (its own midpoint)
- Gripper (end effector): **1.0 kg**, mounted at **0.60 m**
- Payload: unknown mass, carried at **0.60 m**
- Gearbox output rating: **40 N·m** continuous
- Required factor of safety: **2.0**

## Step 1: The Dead Load

The arm and gripper create a moment whether or not anything is being carried.

- Arm: `1.5 kg x 9.8 m/s^2 = 14.7 N`, at 0.30 m gives `14.7 x 0.30 = 4.41 N·m`
- Gripper: `1.0 kg x 9.8 m/s^2 = 9.8 N`, at 0.60 m gives `9.8 x 0.60 = 5.88 N·m`
- **Dead load total:** `4.41 + 5.88 = 10.29 N·m`

Over 10 N·m consumed before the robot picks up anything at all. This is why arm structures are made of thin-wall tube instead of solid bar.

## Step 2: The Torque Budget

Apply the factor of safety to the component rating:

`allowable torque = 40 N·m / 2.0 = 20 N·m`

`payload budget = 20 - 10.29 = 9.71 N·m`

## Step 3: Convert the Budget to a Mass

- `allowable payload weight = 9.71 N·m / 0.60 m = 16.2 N`
- `allowable payload mass = 16.2 N / 9.8 m/s^2 = 1.65 kg`

## Step 4: Check the Answer

Total moment at full extension with a 1.65 kg payload:

`10.29 + (1.65 x 9.8 x 0.60) = 10.29 + 9.70 = 19.99 N·m`

Actual factor of safety: `40 / 19.99 = 2.0`. The arithmetic closes.

## What Is Still Missing

This is a **static** result. Accelerating the arm adds dynamic torque on top, an off-center payload adds a twisting moment on the wrist, and a payload that swings adds a shock load far above its static weight. Each of those is a reason the factor of safety in the next section is not optional padding.'''
            },
            {
                'title': 'Factor of Safety',
                'content': '''# Factor of Safety

A **factor of safety** (FoS, sometimes called a design factor) is the ratio between what a component can withstand and what you actually ask of it:

`factor of safety = rated capacity / expected load`

An FoS of 2.0 means the part is twice as strong as the job requires. Rearranged for design work:

`required rating = expected load x desired factor of safety`

A joint that must supply 12 N·m worst case, designed to an FoS of 2.5, needs a component rated for `12 x 2.5 = 30 N·m`.

## Why Any Margin at All

Engineers do not add margin because they cannot do arithmetic. They add it because the world is not the spreadsheet:

- **Load uncertainty** - the payload turns out heavier, or someone grabs two at once
- **Material and manufacturing variation** - two parts from the same batch are not identical
- **Wear and fatigue** - a part that survives one cycle can fail after ten thousand
- **Shock loads** - a dropped or swinging payload spikes force far above its static weight
- **Modeling error** - your calculation left something out. It always did.

## Typical Values

| Application | Typical factor of safety |
|-------------|--------------------------|
| Static structure, well-characterized loads | 1.5 to 2 |
| Moving mechanisms, shock and impact loads | 2 to 3 |
| Loads carried over people, rigging and lifting slings | 4 to 5 or more |
| Aerospace, where every gram is fought over | 1.2 to 1.5, with extensive testing to justify it |

Notice the pattern: the factor rises with **uncertainty** and with **consequences**, and it falls when analysis and testing are rigorous enough to replace guesswork. Lifting slings carry roughly a 5:1 design factor precisely because a failure drops a load on someone.

## Too Much Is Also Wrong

An FoS of 10 is not "extra safe engineering" - it is usually a heavier, slower, more expensive machine than the job needed, and the extra mass can create new problems (a heavier arm has a bigger dead load and a higher center of mass). Pick the factor your application and standards call for, write down why you picked it, and design to it.'''
            },
            {
                'title': 'Derating and Real-World Checks',
                'content': '''# Derating and Real-World Checks

**Derating** means deliberately operating a component below its published rating because the real conditions are harsher than the test conditions that produced the rating.

## Common Reasons to Derate

- **Duty cycle.** A motor rated for a 25 percent duty cycle spends three-quarters of its time cooling. Run it continuously and it overheats at loads well under its rating.
- **Temperature.** Motors, batteries, and electronics all lose capacity when hot, and a robot arm working in a warm cell is running hot.
- **Battery sag.** As voltage drops through a match or a shift, motor torque and speed drop with it. Design to the sagging voltage, not the fresh-off-the-charger voltage.
- **Reach and orientation.** As shown earlier, payload ratings assume a payload center of gravity close to the flange.
- **Wear.** Chains stretch, belts slip, gear teeth round over. A drivetrain at end of life is not the drivetrain in the calculation.

## Dynamic and Shock Loads

Static arithmetic misses the two biggest surprises:

1. **Acceleration adds torque.** Starting and stopping a load quickly can easily add 20 to 50 percent to the joint torque a static analysis predicts.
2. **Shock multiplies force.** A payload that swings into its stop, or an arm that slams down when the power cuts, applies a peak force several times the static weight. Soft-start ramps, motion profiles, and mechanical stops with some compliance all reduce this.

## A Checklist Before You Trust a Payload Number

1. Did you compute the load at **full extension**, in the worst orientation?
2. Did you include the **end effector**, cables, and anything mounted on the arm?
3. Did you convert every mass to a **weight in newtons** before multiplying by a distance?
4. Did you apply an appropriate **factor of safety** to the component rating?
5. Did you check the **gearbox** rating separately from the motor rating? They are different components with different limits.
6. Did you check that the mechanism is fast enough at that load, not just strong enough?
7. Did you **measure** it? Compare the predicted stall point against a real test, at the end of a full run, with a used battery.

## Try It Yourself

You can practice this without any hardware. Build a long arm and a short arm in **VEXcode VR** and compare how the same drive command behaves as you move the load outward, or model a lever-and-motor circuit in **Tinkercad Circuits** and observe current climbing as the load moment grows. The numbers on the screen will match the numbers on your paper - and getting those two to agree is the entire skill.'''
            }
        ])
        self._create_lesson_questions(lesson, [
            {
                'text': 'A 2 kg payload is carried 0.75 m from a joint on a horizontal arm. Using g = 9.8 m/s^2, what moment does the payload alone create at that joint?',
                'choices': [
                    ('14.7 N·m', True),
                    ('1.5 N·m - multiplying mass by distance without converting to weight', False),
                    ('19.6 N·m - the payload weight with the moment arm left out', False),
                    ('26.1 N·m - dividing the weight by the moment arm instead of multiplying', False),
                ]
            },
            {
                'text': 'A joint must supply 12 N·m in its worst case, and the team is designing to a factor of safety of 2.5. What is the minimum rating the component needs?',
                'choices': [
                    ('30 N·m', True),
                    ('4.8 N·m - dividing the load by the factor instead of multiplying', False),
                    ('14.5 N·m - adding the factor to the load', False),
                    ('24 N·m - using a factor of 2.0 instead of the required 2.5', False),
                ]
            },
            {
                'text': 'A robot arm is rated for a 5 kg payload and is fitted with a 1.8 kg gripper. What is the heaviest part it can pick up?',
                'choices': [
                    ('3.2 kg, because the rated payload includes the end effector mass', True),
                    ('5.0 kg, because the gripper is part of the robot rather than the payload', False),
                    ('6.8 kg, because the gripper adds to the rated capacity', False),
                    ('1.8 kg, because the payload can never exceed the mass of the gripper', False),
                ]
            },
            {
                'text': 'Why do engineers derate a motor that will run continuously in a warm environment?',
                'choices': [
                    ('Published ratings assume a duty cycle and temperature; continuous hot operation makes the component overheat below its rated load', True),
                    ('Warm motors produce more torque than rated, so the rating must be reduced for accuracy', False),
                    ('Derating is a legal requirement that has no physical basis', False),
                    ('Continuous operation removes the need for any factor of safety', False),
                ]
            }
        ])

        self._create_unit2_quiz(unit)

    def _create_unit2_quiz(self, unit):
        quiz = self._quiz(
            unit, 'rob201-quiz-math-and-physics-of-motion', 0,
            title='Math & Physics of Motion Quiz',
            description='Test your ability to calculate torque, gear ratios, center of mass, and payload limits with a factor of safety.',
            passing_score=70,
            points=20,
            max_attempts=3,
        )
        self._create_quiz_questions(quiz, [
            {
                'text': 'A 4 kg load hangs at the end of a horizontal arm, 0.25 m from the pivot. Using g = 9.8 m/s^2, what torque does it create at the pivot?',
                'choices': [
                    ('9.8 N·m', True),
                    ('1.0 N·m - multiplying mass by distance without converting mass to weight', False),
                    ('39.2 N·m - the load weight with the moment arm left out', False),
                    ('156.8 N·m - dividing the weight by the moment arm instead of multiplying', False),
                ]
            },
            {
                'text': 'A 12-tooth driver gear meshes with a 48-tooth driven gear. The motor turns at 240 RPM producing 0.4 N·m. Ignoring losses, what is the output?',
                'choices': [
                    ('60 RPM at 1.6 N·m', True),
                    ('960 RPM at 0.1 N·m - the ratio applied upside down', False),
                    ('60 RPM at 0.1 N·m - both speed and torque reduced', False),
                    ('240 RPM at 1.6 N·m - torque multiplied with no change in speed', False),
                ]
            },
            {
                'text': 'A 12 kg robot has its center of mass 0.25 m above the floor. It lifts a 3 kg payload to 0.85 m. What is the new center of mass height?',
                'choices': [
                    ('0.37 m', True),
                    ('0.55 m - averaging the two heights without weighting them by mass', False),
                    ('0.46 m - dividing the moment sum by 12 kg instead of the 15 kg total', False),
                    ('1.10 m - adding the two heights together', False),
                ]
            },
            {
                'text': 'A gearbox is rated for 40 N·m and the worst-case load on it is calculated at 16 N·m. What factor of safety does that design have?',
                'choices': [
                    ('2.5', True),
                    ('0.4 - dividing the load by the rating instead of the rating by the load', False),
                    ('24 - subtracting the load from the rating', False),
                    ('56 - adding the load to the rating', False),
                ]
            },
            {
                'text': 'A motor data sheet lists a stall torque and a free speed. What do those two values describe?',
                'choices': [
                    ('The maximum torque at zero speed and the maximum speed at essentially zero torque - the two ends of the torque-speed curve', True),
                    ('The torque and speed the motor produces at the same time under normal load', False),
                    ('The torque before a gearbox and the speed after a gearbox', False),
                    ('The minimum torque needed to start the motor and the speed limit set by its controller', False),
                ]
            },
            {
                'text': 'A robot drives steadily across a level floor, then raises its loaded arm to full height without moving. What happened to its stability?',
                'choices': [
                    ('The center of mass rose, so the critical tipping angle and critical acceleration both dropped', True),
                    ('Nothing changed, because the wheels and the support polygon did not move', False),
                    ('Stability improved, because the raised load is farther from the ground', False),
                    ('Stability depends only on total mass, which did not change', False),
                ]
            }
        ])

    # ================== UNIT 3: Manipulators, End Effectors & Arm Construction ==================
    def _create_unit3(self, course):
        unit = self._unit(course, 2, 'Manipulators, End Effectors & Arm Construction')

        # Lesson 1: Robot Arm Anatomy & Degrees of Freedom
        lesson = self._lesson(
            unit, 'rob201-robot-arm-anatomy-and-degrees-of-freedom', 0,
            title='Robot Arm Anatomy & Degrees of Freedom',
        )
        self._create_sections(lesson, [
            {
                'title': 'Overview',
                'content': '''# Robot Arm Anatomy & Degrees of Freedom

A robot arm looks like a mechanical version of a human arm, and that resemblance is not an accident - engineers borrowed the vocabulary. But an arm is really just a chain of rigid **links** connected by movable **joints**, and once you can count the joints you can predict exactly what the arm can and cannot reach. In this lesson you will learn to read an arm the way an engineer does.

## Learning Objectives

By the end of this lesson, you will be able to:
- Identify the links, joints, base, wrist, and end effector of a manipulator
- Distinguish revolute from prismatic joints and count an arm's degrees of freedom
- Compare articulated, SCARA, cartesian, cylindrical, and delta configurations and match each to a task
- Explain forward and inverse kinematics conceptually and describe why singularities cause trouble

> **TEKS alignment:** §127.750(c)(9) — describes the characteristics and scope of manipulators, accumulators, and end effectors.'''
            },
            {
                'title': 'Links, Joints, and Degrees of Freedom',
                'content': '''# Links, Joints, and Degrees of Freedom

A **manipulator** is the arm itself: everything from the base up to (but not including) the tool at the tip. It is built from two kinds of parts.

- **Links** — the rigid structural members. They do not change shape; they just carry load and set distance. The link between the shoulder and the elbow is often called the upper arm, and the one between the elbow and the wrist the forearm.
- **Joints** — the movable connections between links. Every joint is powered by an actuator (a motor or a cylinder) and usually monitored by an encoder so the controller knows where it is.

## Two Joint Types

| Joint type | Motion | Everyday analogy | Typical drive |
|-----------|--------|------------------|---------------|
| **Revolute** (rotary, R) | Rotates about an axis, measured in degrees | Your elbow, a door hinge | Servo motor + gearbox |
| **Prismatic** (linear, P) | Slides along an axis, measured in millimeters | A drawer, a trombone slide | Lead screw, belt, or pneumatic cylinder |

Engineers describe an arm by listing its joints in order from the base outward. An **RRR** arm has three revolute joints (an articulated arm); a **PPP** arm has three linear axes (a gantry). Real machines mix them: a SCARA is **RRP** plus a final rotation, written RRPR.

## Counting Degrees of Freedom

A **degree of freedom (DOF)** is one independent way the arm can move. On a simple arm, DOF equals the number of powered joints - a joint you cannot command does not count, so a fixed brace or a passive idler adds zero.

Why the number matters: a rigid body floating in three-dimensional space has exactly **six** degrees of freedom - three position values (X, Y, Z) and three orientation values (roll, pitch, yaw). So:

- **Fewer than 6 DOF:** the arm can reach many points, but not in every orientation. A 4-DOF SCARA can put a screw anywhere over a table, but it can only drive it straight down.
- **Exactly 6 DOF:** the arm can theoretically place its tool at any reachable point in any orientation. This is why most industrial arms have six axes.
- **More than 6 DOF (redundant):** a 7-axis arm can reach the same pose in infinitely many ways, letting it reach around an obstacle or avoid a bad configuration. The cost is a harder control problem.

Count the joints on any arm you meet - a competition claw, a construction excavator, a phone tripod - and you can immediately state what it can and cannot do.'''
            },
            {
                'title': 'Arm Configurations',
                'content': '''# Five Arm Configurations

The order and type of the first three joints decide the *shape of the space* an arm can reach. Five arrangements dominate industry.

## Articulated (Jointed-Arm)

Three or more revolute joints, like a human shoulder-elbow-wrist. The most common industrial form. Its work envelope is a thick spherical shell with a dead zone near the base and a limit at full extension. Extremely flexible - it can reach over and around obstacles - but it is the hardest to program and the least stiff at full reach. Typical repeatability is around **±0.02 to ±0.1 mm**.

## SCARA (Selective Compliance Assembly Robot Arm)

Two revolute joints turning about **vertical** axes, then a vertical linear axis and a final tool rotation - four DOF. The name says it all: the arm is compliant (slightly springy) in the horizontal plane but very stiff vertically. That is perfect for pressing a component straight down into a circuit board, because small horizontal errors let the part self-align while the vertical push stays rigid. SCARAs are fast and precise, often **±0.01 mm**, but they cannot tilt their tool.

## Cartesian / Gantry

Three prismatic axes at right angles. The work envelope is a simple rectangular box, and the math is trivial - commanding X, Y, Z *is* commanding the joints. Gantries scale to enormous sizes (think of a 3D printer or a CNC router the size of a garage) and carry heavy loads because the structure, not a motor, resists gravity. The trade-off is a large footprint for the volume covered.

## Cylindrical and Polar

A rotating base plus linear extension gives a **cylindrical** envelope; a rotating base plus a tilting, extending arm gives a **polar (spherical)** envelope. Both are older designs, still found on machine-tending and die-casting machines where a simple reach-in, grab, reach-out motion is all that is needed.

## Delta (Parallel)

Three arms driven from a fixed overhead frame all connect to one small moving platform. Because the motors stay on the frame, the moving mass is tiny, and a delta can hit **150-300 picks per minute** - it is the machine that sorts candy and packs cookies. The price is a small, dome-shaped work envelope and a low payload, often under 3 kg.

## Choosing One

| Task | Best fit | Why |
|------|----------|-----|
| Welding a car frame from several angles | Articulated | Needs full 6-DOF orientation |
| Inserting connectors into a PCB | SCARA | Vertical stiffness, horizontal compliance |
| Cutting sheet goods on a 2.4 m table | Cartesian gantry | Big rectangular envelope, rigid |
| Sorting 200 chocolates a minute | Delta | Extreme speed, light payload |
| Loading blanks into one lathe | Cylindrical | Simple, cheap, repetitive path |'''
            },
            {
                'title': 'The Wrist: Roll, Pitch, and Yaw',
                'content': '''# The Wrist: Orienting the Tool

The first three joints of an arm are the **major axes** - they position the tool in space. The last joints form the **wrist**, and their only job is orientation. Aviation gave us the names.

- **Roll** — rotation about the axis the tool points along. A drill bit spinning about its own centerline rolls.
- **Pitch** — tilting the tool up or down, like nodding your head yes.
- **Yaw** — swinging the tool left or right, like shaking your head no.

## Wrist Architectures

A **three-roll wrist** (also called a spherical wrist) puts three revolute axes through a single common point. That single intersection point is called the **wrist center**, and it is a gift to programmers: it lets the control software split one hard problem into two easy ones - solve the first three joints for the position of the wrist center, then solve the last three for orientation. Almost every 6-axis industrial arm uses this design.

Cheaper or lighter arms may use a **pitch-yaw wrist** (two axes) or a **pitch-roll wrist**. These weigh less and cost less, but they give up orientations. A 5-axis arm with a two-axis wrist cannot always keep a paint gun perpendicular to a curved surface while following the path.

## Why the Wrist Is the Weak Point

The wrist sits at the end of the longest lever in the machine, so every gram there is punished:

- Wrist mass multiplies into shoulder torque. One extra kilogram of gripper at 1.2 m of reach adds about **11.8 N·m** of static torque at the shoulder before the arm even moves.
- The wrist is where cables, air lines, and signal wires must survive constant flexing, so it is the most common site of a wiring failure.
- Payload ratings on a datasheet always assume the load is at the tool flange. Mount a long tool that pushes the center of mass 150 mm past the flange and the safe payload drops sharply, because the rating is really about the **moment** the wrist can hold, not just the weight.

When you read a robot datasheet, look for three numbers together: payload in kilograms, reach in millimeters, and allowable wrist moment in newton-meters. Any one of them alone will mislead you.'''
            },
            {
                'title': 'Kinematics and Singularities',
                'content': '''# Kinematics: Turning Angles into Positions

**Kinematics** is the study of motion without worrying about the forces that cause it. For a robot arm it answers two mirror-image questions.

## Forward Kinematics: Angles In, Position Out

*Given every joint value, where is the tool?* You know the length of each link and the angle of each joint, so you can chain the geometry together and compute the tool position. Forward kinematics has exactly **one answer** - a given set of joint angles puts the tool in exactly one place. The controller runs it constantly to report where the arm is.

## Inverse Kinematics: Position In, Angles Out

*Given a target position and orientation, what should every joint be?* This is the question you actually need to answer, because you want to tell the robot "go to the corner of the pallet," not "set joint 3 to 47.2 degrees."

Inverse kinematics is much harder, for three reasons:

1. **Multiple solutions.** A 6-axis arm can typically reach the same pose eight different ways - elbow up or elbow down, wrist flipped or not, arm reaching forward or twisted around behind itself. The controller must pick one, and picking a different one mid-program makes the arm swing violently through a new path.
2. **No solutions.** Ask for a point outside the work envelope, or one blocked by a joint limit, and there is no valid answer at all. The controller throws a reach error.
3. **The math grows fast.** Even a modest arm produces long trigonometric expressions, which is why controllers use precomputed closed-form solutions or numerical solvers.

## Singularities

A **singularity** is an arm configuration in which two joint axes line up, so the arm momentarily loses a degree of freedom. Near a singularity, a small, slow motion of the tool demands enormous joint speeds - the controller either faults out or the arm lurches.

The three classic industrial singularities:

- **Wrist singularity:** joint 5 reaches 0 degrees, so axes 4 and 6 become collinear. Rolling either joint does the same thing, and one orientation direction is lost.
- **Shoulder singularity:** the wrist center passes directly over the base rotation axis. Joint 1 would have to spin instantly to follow.
- **Elbow singularity:** the arm stretches out nearly straight, at the edge of its reach. Vertical motion of the tool needs huge elbow speed.

Programmers avoid singularities by keeping paths a few degrees away from full extension, by never driving straight through the base, and by using joint-space moves rather than straight-line moves when passing through an awkward region. You can feel this yourself: hold your arm straight out and try to move your hand slowly toward your shoulder along a straight line - your elbow has to accelerate hard at the start, exactly as a robot elbow would.'''
            }
        ])
        self._create_lesson_questions(lesson, [
            {
                'text': 'A work cell must place a bolt at any point in a bin AND at any tilt angle so it can be threaded into angled holes. What is the minimum number of degrees of freedom the arm needs?',
                'choices': [
                    ('Six — three to set position and three to set orientation', True),
                    ('Three — one for each axis of space', False),
                    ('Four — three for position plus one for the gripper', False),
                    ('Twelve — two joints for every axis of motion', False),
                ]
            },
            {
                'text': 'An electronics line presses connectors straight down into circuit boards. Small horizontal misalignments should let the part self-seat, but the downward push must stay rigid. Which configuration fits best?',
                'choices': [
                    ('SCARA, because it is compliant horizontally but stiff vertically', True),
                    ('Delta, because it is the fastest configuration available', False),
                    ('Cartesian gantry, because its envelope is a rectangular box', False),
                    ('Cylindrical, because it rotates about a vertical base axis', False),
                ]
            },
            {
                'text': 'While running a straight-line move with the arm stretched out near full reach, the controller faults with an excessive joint-speed error. What is the most likely cause?',
                'choices': [
                    ('The path passed near an elbow singularity, where a slow tool motion demands very high joint speed', True),
                    ('The payload exceeded the rated mass of the end effector', False),
                    ('The encoder on joint 1 lost power and reported a random position', False),
                    ('Forward kinematics returned more than one valid solution for the pose', False),
                ]
            },
            {
                'text': 'A programmer types a target X, Y, Z and tool orientation, and the controller computes the joint angles that will get there. Which calculation did the controller perform?',
                'choices': [
                    ('Inverse kinematics', True),
                    ('Forward kinematics', False),
                    ('Static deflection analysis', False),
                    ('Encoder calibration', False),
                ]
            }
        ])

        # Lesson 2: End Effectors: Grippers, Suction & Tooling
        lesson = self._lesson(
            unit, 'rob201-end-effectors-grippers-and-tooling', 1,
            title='End Effectors: Grippers, Suction & Tooling',
        )
        self._create_sections(lesson, [
            {
                'title': 'Overview',
                'content': '''# End Effectors: Grippers, Suction & Tooling

An arm by itself does nothing useful. The **end effector** - the tool bolted to the wrist flange - is what actually touches the work, and choosing the wrong one is the single most common reason a well-built cell fails. A gripper that handles a steel block beautifully will crush an egg, tear a bag, and slide right off a pane of glass. In this lesson you will learn the major families and how professionals pick between them.

## Learning Objectives

By the end of this lesson, you will be able to:
- Describe mechanical, vacuum, magnetic, and soft end effectors and where each is used
- Explain what process tooling and automatic tool changers add to a work cell
- Calculate required grip force and vacuum-cup lifting force for a given part
- Select an end effector from a part's geometry, mass, surface, and required cycle time

> **TEKS alignment:** §127.750(c)(9) — describes the characteristics and scope of manipulators, accumulators, and end effectors.'''
            },
            {
                'title': 'Mechanical Grippers',
                'content': '''# Mechanical Grippers: Jaws That Close

A **mechanical gripper** holds a part by squeezing it between moving jaws (also called fingers). It is the workhorse of the field because it works on almost any rigid part, wet or dry, hot or cold.

## Parallel vs Angular

- **Parallel grippers** move their jaws toward each other along a straight line, staying parallel the whole way. The contact stays flat, the grip position is predictable, and the part center stays on the same spot as the jaws close. This is the default choice for precision work.
- **Angular grippers** swing their jaws open like a pair of scissors. They open much wider for the same body size and clear away from the part completely, which matters when a machine tool must move in right after the grab. The trade-off is that the contact angle changes with jaw position, so the grip is less repeatable.

## Two Jaws or Three?

Two-jaw grippers suit flat, square, or slab-shaped parts. **Three-jaw (concentric) grippers** close on a common center, so they self-center round parts - shafts, bottles, and machined discs - without careful positioning. If your part is a cylinder, a three-jaw gripper eliminates a whole class of alignment problems.

## Friction Grip vs Encapsulating Grip

This distinction saves more dropped parts than any other idea in the lesson.

- A **friction grip** relies on squeezing hard enough that friction alone holds the part. Oil, dust, or vibration reduces friction, and the part slips.
- An **encapsulating grip** shapes the jaws so the part is mechanically trapped - a V-groove around a shaft, a contoured pocket around a casting. Even if the squeeze weakens, the part cannot escape sideways. Custom jaws milled to match the part are cheap insurance.

## Sizing the Grip Force

Engineers size grip force with a version of this relationship:

**F ≥ ( m × (g + a) × S ) / ( µ × n )**

where *m* is part mass, *g* is 9.81 m/s², *a* is the peak acceleration the arm applies, *S* is a safety factor (2 is typical, 4 for overhead or high-speed moves), *µ* is the coefficient of friction between the jaw and the part, and *n* is the number of gripping surfaces.

**Worked example.** A 2 kg steel block, moved at a peak acceleration of 1 g, held by two smooth steel jaws (µ ≈ 0.15), with a safety factor of 2:

F ≥ (2 × (9.81 + 9.81) × 2) / (0.15 × 2) = 78.5 / 0.3 ≈ **262 N**

That is a surprisingly large number for a 2 kg part - about 60 pounds of squeeze. Now switch to urethane-faced jaws with µ ≈ 0.6 and the requirement drops to about 65 N. Better jaw material beats a bigger gripper almost every time.'''
            },
            {
                'title': 'Vacuum, Magnetic, and Soft Grippers',
                'content': '''# When Jaws Are the Wrong Answer

Squeezing is not always possible. Three other families cover the parts jaws cannot handle.

## Vacuum (Suction) Grippers

A vacuum generator - either a pump or a compressed-air **venturi ejector** - pulls air out from under a rubber cup. Atmospheric pressure outside then pushes the part against the cup. The theoretical holding force is simply pressure difference times area:

**F = ΔP × A**

**Worked example.** A 40 mm cup has an area of π × (0.020 m)² = 1.26 × 10⁻³ m². At a typical industrial vacuum level of -60 kPa, F = 60,000 × 1.26 × 10⁻³ ≈ **75 N**. Apply the usual safety factor of 2 for a vertical lift (4 if the part is held sideways or accelerated hard) and one cup safely carries about 37 N, or roughly 3.8 kg. Four cups on a spreader bar carry a 15 kg panel with margin.

Vacuum is ideal for **flat, smooth, non-porous, rigid** surfaces: glass, sheet metal, plastic panels, sealed film bags. It fails on porous surfaces - raw cardboard and open-cell foam leak so badly the cup never builds vacuum - and on parts too flimsy to resist being sucked into a dimple. Cycle time matters too: cups need time to seat and evacuate, and a **blow-off** pulse of positive air is usually needed to release cleanly at speed.

## Magnetic Grippers

Only ferrous parts need apply, but for steel plate a magnet beats everything. Two kinds:

- **Electromagnets** switch on and off electrically. Simple, fast, and adjustable - but a power failure drops the load, which is why they are avoided over people or in high-hazard cells.
- **Permanent-magnet grippers** hold with no power at all and use a small pneumatic **stripper pin** to push the part off. They fail safe: a power loss leaves the part attached.

Magnets tolerate oil, chips, and rough surfaces, and they can grab an unaligned part from a pile. They also leave residual magnetism in the part and will happily pick up two sheets at once, so a **fanner magnet** or double-blank detector is often required.

## Soft and Specialty Grippers

- **Soft robotic grippers** use flexible elastomer fingers inflated by air. They wrap around irregular, delicate items and are cleared for food handling - fruit, pastries, meat - where a rigid jaw would bruise the product.
- **Granular jamming grippers** press a bag of coffee-like granules onto a part, then apply vacuum so the bag locks into a rigid mold of the shape.
- **Needle grippers** poke tiny retractable needles into fabric, carbon-fiber cloth, or foam - materials with no rigid surface to grip.
- **Bernoulli grippers** blow a thin sheet of air that creates low pressure and lifts a wafer or a lens *without touching it*, which protects optical and semiconductor surfaces.'''
            },
            {
                'title': 'Process Tooling and Tool Changers',
                'content': '''# Tooling That Works, Not Just Holds

Not every end effector is a gripper. In many cells the tool *is* the process, and the arm exists only to aim it accurately for eight hours without getting tired.

## Common Process Tools

- **Spot-welding guns** — two copper electrodes squeeze sheet metal and pass thousands of amperes through it for a few cycles. The gun and its transformer can weigh 60-100 kg, which is why automotive body arms have huge payload ratings.
- **Arc-welding torches** — much lighter, but they demand precise, steady path speed and a constant tool angle, so path programming matters more than payload.
- **Dispensing nozzles** — lay a bead of adhesive, sealant, or solder paste. Bead width depends on the ratio of flow rate to travel speed, so the robot must hold speed constant even around corners.
- **Paint and coating atomizers** — spray guns on explosion-rated arms; the tool must stay perpendicular to a curved surface, which is a 6-DOF orientation problem.
- **Deburring and grinding spindles** — remove material; usually mounted on a compliant force-controlled holder so the tool follows a surface instead of digging into it.
- **Screwdriving and nutrunner spindles** — drive fasteners to a torque spec and report the actual torque achieved for traceability.
- **Inspection heads** — cameras, laser profilers, or probes that measure rather than modify.

## Tool Changers

One arm, several jobs. A **tool changer** is a two-part coupler: the **master** stays bolted to the robot wrist, and each tool carries a matching **tool-side** plate. The two lock together, usually with a pneumatically driven ball-lock mechanism, and pass utilities across the joint - compressed air, electrical power, signal wiring, and sometimes water or weld current.

- **Manual changers** cost little and swap in a minute by hand. Right for a training cell or a machine that changes jobs once a shift.
- **Automatic tool changers (ATC)** let the robot dock its own tool in a stand and pick up a different one in a few seconds, with no operator. Right for a cell that welds a seam, then swaps to a gripper to unload the part.

Whatever the design, the changer must **fail safe**: the ball lock is spring-held or self-locking so an air-pressure loss does not drop a 40 kg welding gun. Every tool change also costs payload, because the changer body itself weighs one to several kilograms and pushes the tool center of mass farther from the flange.'''
            },
            {
                'title': 'Selecting an End Effector',
                'content': '''# Selecting an End Effector: A Working Method

Engineers do not choose grippers by preference; they work through the part. Answer these five questions in order and the choice usually makes itself.

## 1. What Is the Part Made Of, and What Is Its Surface?

Ferrous and dirty points to magnetic. Flat, smooth, and sealed points to vacuum. Porous, soft, or irregular points to soft or mechanical. Fragile optical surfaces point to Bernoulli or a wide soft contact.

## 2. What Is the Geometry?

Round means a three-jaw or a V-jaw grip. Flat panel means vacuum with cups spread wide to resist bending. A part with a hole or a lip means an internal-expanding gripper or a hook, which is often the cheapest solution nobody thinks of.

## 3. What Is the Mass, and How Fast Will It Move?

Compute the required force with the equations from this lesson, then check the arm's payload budget. Remember that the payload rating includes the end effector: a 10 kg arm carrying a 3.5 kg gripper can only lift a 6.5 kg part, and less if the tool is long.

## 4. What Is the Cycle Time?

Vacuum needs milliseconds to build and release; add a blow-off valve if the beat is fast. Mechanical jaws take time to stroke - a long-stroke gripper opening 50 mm each cycle may not keep up with a 0.6 s beat. Magnets are nearly instant.

## 5. What Happens When Something Fails?

Ask what the part does when air pressure or electrical power is lost. If the answer is "it drops onto the conveyor from 1.5 m," redesign: use a check valve and vacuum reservoir, a spring-closed gripper, or a permanent magnet.

## Comparison Summary

| End effector | Best for | Avoid when | Failure mode on power loss |
|--------------|----------|-----------|---------------------------|
| Parallel mechanical | Rigid parts of known size | Very fragile or irregular parts | Depends on design; spring-closed can hold |
| Three-jaw concentric | Cylinders, discs, bottles | Flat slabs | Same as above |
| Vacuum cups | Flat, smooth, non-porous panels | Cardboard, foam, oily surfaces | Drops unless a reservoir and check valve exist |
| Electromagnet | Steel plate, scrap, hot parts | Aluminum, plastic, glass | Drops the part immediately |
| Permanent magnet + stripper | Steel where fail-safe matters | Non-ferrous parts | Holds the part |
| Soft elastomer fingers | Produce, baked goods, odd shapes | Heavy or high-force tasks | Usually relaxes and releases |

**A worked selection.** A cell must lift 1.2 m × 0.8 m glass panels off a flat stack and set them on a conveyor every 8 seconds. Glass is non-ferrous (no magnet), smooth and non-porous (vacuum works), heavy and floppy over its span (needs load spread), and cannot be squeezed on the edges without chipping. The answer is a spreader frame carrying six to eight 60 mm vacuum cups, plumbed through a vacuum reservoir and check valve so a compressor hiccup does not drop 20 kg of glass.'''
            }
        ])
        self._create_lesson_questions(lesson, [
            {
                'text': 'A cell must lift a smooth glass panel from the top of a flat stack without chipping its edges. Which end effector fits best?',
                'choices': [
                    ('An array of vacuum cups on a spreader frame', True),
                    ('A two-jaw parallel gripper closing on the panel edges', False),
                    ('An electromagnetic gripper sized for the panel area', False),
                    ('A needle gripper that penetrates the surface for grip', False),
                ]
            },
            {
                'text': 'Oily steel shafts keep slipping out of a two-jaw parallel gripper even at maximum squeeze. Which change most directly fixes the problem?',
                'choices': [
                    ('Switch to V-shaped jaws that encapsulate the shaft instead of relying on friction alone', True),
                    ('Increase the speed of the arm so the part has less time to slip', False),
                    ('Mount longer fingers so the jaws reach farther past the flange', False),
                    ('Reduce the safety factor used in the grip-force calculation', False),
                ]
            },
            {
                'text': 'Why do engineers avoid electromagnetic grippers for loads carried over walkways or operator stations?',
                'choices': [
                    ('A loss of electrical power releases the magnet and drops the load', True),
                    ('Electromagnets cannot generate enough force for steel parts', False),
                    ('Electromagnets require the part surface to be smooth and non-porous', False),
                    ('Electromagnets are much slower to engage than mechanical jaws', False),
                ]
            },
            {
                'text': 'One arm must run a bead of adhesive on a housing and then, in the same cycle, pick the finished housing off the fixture. What hardware makes this practical?',
                'choices': [
                    ('An automatic tool changer so the arm docks the dispenser and picks up a gripper', True),
                    ('A larger vacuum generator to increase available holding force', False),
                    ('A seventh axis added to the wrist for redundancy', False),
                    ('A three-jaw concentric gripper with custom contoured jaws', False),
                ]
            }
        ])

        # Lesson 3: Actuators & Accumulators: Pneumatics vs Hydraulics
        lesson = self._lesson(
            unit, 'rob201-actuators-and-accumulators', 2,
            title='Actuators & Accumulators: Pneumatics vs Hydraulics',
        )
        self._create_sections(lesson, [
            {
                'title': 'Overview',
                'content': '''# Actuators & Accumulators: Pneumatics vs Hydraulics

Every joint you counted in the last lessons needs something to move it. That something is an **actuator**, and industry uses three families: electric motors, compressed air, and pressurized oil. They are not interchangeable - each wins decisively at some tasks and fails badly at others. This lesson also covers the **accumulator**, a component that stores fluid energy and quietly makes fluid power systems both smoother and far more dangerous.

## Learning Objectives

By the end of this lesson, you will be able to:
- Compare electric, pneumatic, and hydraulic actuation on force, speed, precision, cost, and cleanliness
- Trace the components of a pneumatic circuit from compressor to cylinder
- Explain what an accumulator does, why it exists, and why it must be discharged before service
- Select an actuation technology for a stated application and justify the choice

> **TEKS alignment:** §127.750(c)(9) — describes the characteristics and scope of manipulators, accumulators, and end effectors.
> **TEKS alignment:** §127.750(c)(11) — demonstrates knowledge of the function and application of tools, equipment, and materials used in robotics.'''
            },
            {
                'title': 'Three Ways to Make Motion',
                'content': '''# Three Ways to Make Motion

## Electric

A motor turns electrical energy into rotation, and a gearbox, lead screw, or belt converts that into whatever motion the joint needs. Servo motors with encoders can be commanded to any position and held there, which is why nearly every modern industrial arm is electric.

- **Strengths:** precise multi-point positioning, programmable speed and torque curves, quiet, clean, energy-efficient, easy to instrument.
- **Weaknesses:** force density is modest - a motor big enough to press 20 kN is enormous - and gearboxes add backlash and cost.

## Pneumatic (Compressed Air)

Air compressed to roughly **6-8 bar (90-115 psi)** pushes a piston in a cylinder. Force is pressure times piston area:

**F = P × A**

**Worked example.** A 40 mm bore cylinder has a piston area of π × (0.020)² = 1.26 × 10⁻³ m². At 6 bar (600 kPa), the extend force is 600,000 × 1.26 × 10⁻³ ≈ **754 N**. Retracting is weaker, because the rod takes up part of the piston face: with a 16 mm rod the effective area drops to about 1.06 × 10⁻³ m² and the force to about **633 N**.

- **Strengths:** cheap, extremely fast, light, tolerant of stalling and overload, safe in wet or explosive areas, and the exhaust is just air.
- **Weaknesses:** air is compressible, so a pneumatic cylinder is springy and hard to stop accurately anywhere except its **hard end stops**. Compressed air is also expensive to produce - it is one of the least efficient utilities in a plant - and leaks waste money continuously.

## Hydraulic (Pressurized Oil)

Oil at **150-350 bar** drives the same kind of cylinder. Oil is essentially incompressible, so the motion is stiff and the position holds under load.

**Worked example.** That same 40 mm cylinder, fed at 210 bar instead of 6 bar, produces 21,000,000 × 1.26 × 10⁻³ ≈ **26,400 N** - about 35 times the pneumatic force from identical hardware. That ratio is the whole reason hydraulics exists.

- **Strengths:** enormous force in a small package, stiff holding under load, smooth control of heavy masses.
- **Weaknesses:** leaks make a mess and a fire hazard, the power unit is loud and hot, oil viscosity changes with temperature, and maintenance is demanding.

## Side-by-Side

| Criterion | Electric | Pneumatic | Hydraulic |
|-----------|----------|-----------|-----------|
| Typical operating pressure | n/a | 6-8 bar | 150-350 bar |
| Force density | Moderate | Low | Very high |
| Speed | Moderate, controllable | Very fast | Moderate |
| Position precision | Excellent, any point | Poor except at end stops | Good with servo valves |
| Stiffness under load | Good | Poor (air is springy) | Excellent |
| Cleanliness | Clean | Clean (exhaust is air) | Oil leaks and mist |
| Initial cost per axis | High | Low | High |
| Best classroom analogy | 3D printer axis | Competition robot claw | Excavator arm |'''
            },
            {
                'title': 'Inside a Pneumatic Circuit',
                'content': '''# Inside a Pneumatic Circuit

Follow the air from the wall to the work and you meet every component in order.

## 1. Compressor and Receiver

A **compressor** squeezes atmospheric air into a **receiver tank**, which stores a volume of compressed air so the compressor motor does not have to run continuously and so short bursts of high demand do not collapse system pressure. The receiver is the pneumatic cousin of the hydraulic accumulator you will meet in the next section.

## 2. Air Preparation: the FRL

Air arrives wet and dirty. An **FRL unit** fixes that:

- **Filter** — removes water droplets and particulates that would score cylinder bores
- **Regulator** — steps plant pressure down to what this machine actually needs, with a gauge to read it
- **Lubricator** — adds a fine oil mist for older equipment (many modern cylinders are pre-lubricated and must *not* get oil)

## 3. Valves

A **directional control valve** decides where air goes. Valves are named by ports and positions: a **5/2 valve** has five ports and two positions and is the standard for driving a double-acting cylinder; a **3/2 valve** runs a single-acting cylinder. Most are shifted by an electric **solenoid** on command from the controller. **Flow control valves** with a needle restriction and a bypass check valve set the extend and retract speeds independently - this is how you slow a cylinder without weakening it.

## 4. Cylinders

- **Single-acting:** air extends the rod; an internal spring returns it. Simple, uses half the air, and it **fails to a known position**, which makes it the right choice for a safety-critical clamp.
- **Double-acting:** air drives both directions, so the cylinder has full force each way and can stop wherever the valve leaves it. This is the general-purpose choice.

Other useful forms are **rodless cylinders** (long stroke in a short footprint), **rotary actuators** (a cylinder driving a rack and pinion for a 90 or 180 degree turn), and **air motors** for continuous rotation.

## 5. Safety Devices Every Circuit Needs

- A lockable **shutoff and bleed valve** so the machine can be depressurized and locked out for service
- A **soft-start valve** that re-pressurizes gradually, so a machine does not slam to its start position when air is restored
- **Speed controls** to keep a heavy tool from slamming into its end stops

You can model electrical control logic for these valves in **Tinkercad Circuits** without any hardware: wire a microcontroller output to a relay or transistor driving a "solenoid" load, and prove the timing and interlocks before anyone touches real air.'''
            },
            {
                'title': 'Accumulators: Storing and Smoothing Energy',
                'content': '''# Accumulators: Storing and Smoothing Energy

An **accumulator** is a pressure vessel that stores fluid under pressure so the system can give it back later. In a hydraulic system it holds oil compressed against a charge of nitrogen gas; the gas acts like a spring. In a pneumatic system a receiver tank or a small reservoir plays the same role.

## The Three Common Designs

| Type | How it works | Typical use |
|------|--------------|-------------|
| **Bladder** | A rubber bladder full of nitrogen sits inside a steel shell; oil enters around it and squeezes it | Most common; fast response, good for shock absorption |
| **Piston** | A free-floating piston separates nitrogen above from oil below | Large volumes, high flow, tolerant of pressure cycling |
| **Diaphragm** | A flexible diaphragm divides the two sides in a small welded shell | Compact, low volume, pulsation damping |

Accumulators are pre-charged with nitrogen - never oxygen or shop air, which can ignite in contact with oil - typically to about **90 percent of the minimum working pressure** of the circuit for a bladder unit. Set the pre-charge too high and the bladder slams the poppet every cycle; too low and the accumulator does almost nothing.

## Why Accumulators Exist: Four Jobs

1. **Peak-demand energy storage.** A press cycle may need 60 L/min for two seconds every minute. Sizing the pump for 60 L/min is expensive and wasteful. Instead a small pump slowly fills an accumulator between cycles, and the accumulator dumps the flow when the press fires. The same idea applies to a robot cell where four cylinders fire simultaneously and would otherwise cause a pressure sag.
2. **Shock and pulsation damping.** Every piston pump produces pressure ripple, and every fast-closing valve causes a **water-hammer** spike that can burst hoses and crack fittings. An accumulator absorbs those spikes the way a shock absorber absorbs a pothole.
3. **Leakage compensation and pressure holding.** A clamp that must stay closed for an hour would otherwise need the pump running the whole time. An accumulator makes up for slow seal leakage while the pump idles.
4. **Emergency and fail-safe actuation.** If power fails, the stored energy is still there. It can retract a tool clear of the work, close a safety brake, or steer a machine to a stop. This is the reason many mobile machines carry accumulators.

## The Safety Rule That Matters Most

**An accumulator stays dangerous after the machine is switched off.** The pump can be locked out, the motor cold, and the machine apparently dead, while the accumulator still holds hundreds of bar of stored energy - enough to move a heavy actuator without warning or to inject fluid through skin.

Correct procedure before servicing any accumulator circuit:

1. Stop the machine and lock out or tag out the power source
2. Open the manual **dump valve** to discharge stored fluid back to the reservoir
3. Verify **zero pressure on the gauge** before loosening a single fitting
4. Never weld, drill, or machine an accumulator shell, and never disassemble one before releasing the nitrogen pre-charge through the proper valve

Stored energy is invisible. Treating a quiet machine as a safe machine is one of the most common causes of serious fluid-power injuries.'''
            },
            {
                'title': 'Choosing an Actuation Technology',
                'content': '''# Choosing an Actuation Technology

Real designers pick actuation by working through requirements, not habit. Here is the decision path with worked cases.

## Ask These Five Questions

1. **How much force, and over what stroke?** Above roughly 10 kN in a compact package, hydraulics is usually the only practical answer.
2. **How many positions must the actuator hit?** Two positions means pneumatics is fine. Any position, repeatably, means electric servo.
3. **How stiff must it hold?** If an external load must not push the actuator back, avoid pneumatics - compressed air behaves like a spring.
4. **What does the environment allow?** Food, pharmaceutical, and cleanroom work rejects oil. Explosive atmospheres favor pneumatics. Outdoor mobile machines often already have a hydraulic power unit, so hydraulics is nearly free.
5. **What is the duty cycle and the energy cost?** Compressed air costs roughly seven to eight times more per unit of delivered work than electricity. A cylinder cycling once a minute is fine; one cycling twice a second all shift may justify an electric axis.

## Worked Cases

| Application | Choice | Reasoning |
|-------------|--------|-----------|
| Gripper jaws that only open or close | Pneumatic | Two positions, fast, cheap, tolerant of being stalled shut |
| Six-axis arm positioning a weld torch along a path | Electric servo | Continuous path control and repeatability are the whole job |
| Press that must apply 25 kN in a 300 mm frame | Hydraulic | Force density no other technology can match in that space |
| Conveyor lift gate in a bakery | Electric or pneumatic | Oil is unacceptable near food; both are clean |
| Excavator boom lifting 2 tonnes | Hydraulic | Huge force, stiff holding, power unit already on board |
| Clamp that must stay closed if power fails | Pneumatic single-acting spring-return, or accumulator-backed hydraulic | Fail-safe behavior is a design requirement, not an accident |

## Hybrids Are Normal

Plenty of machines mix technologies: an electric six-axis arm with a pneumatic gripper and a hydraulic press in the same cell is completely ordinary. Choose per axis, based on what that axis has to do, and document the reasoning in your engineering notebook so the next person understands why the machine looks the way it does.'''
            }
        ])
        self._create_lesson_questions(lesson, [
            {
                'text': 'A design requires 25 kN of clamping force from an actuator that must fit inside a 300 mm frame. Which actuation technology is the practical choice?',
                'choices': [
                    ('Hydraulic, because oil at 150-350 bar gives very high force from a small cylinder', True),
                    ('Pneumatic, because shop air at 6 bar is fast and inexpensive', False),
                    ('Electric servo, because it offers the best position precision', False),
                    ('Any of them, because actuation type does not affect available force', False),
                ]
            },
            {
                'text': 'A hydraulic cell fires four cylinders at the same moment and system pressure sags each time. Which component is designed to solve this?',
                'choices': [
                    ('An accumulator, which stores fluid between cycles and releases it during the peak demand', True),
                    ('A larger FRL filter to remove more contamination from the fluid', False),
                    ('A flow control valve to slow each cylinder down individually', False),
                    ('A rodless cylinder to reduce the volume of oil required', False),
                ]
            },
            {
                'text': 'A technician locks out the pump, confirms the motor is cold, and starts to loosen a fitting on an accumulator circuit. What is wrong with this procedure?',
                'choices': [
                    ('The accumulator still holds stored energy; the dump valve must be opened and the gauge must read zero first', True),
                    ('The pump should be running so the fluid stays warm and thin enough to drain', False),
                    ('The nitrogen pre-charge should be increased before any fitting is loosened', False),
                    ('Nothing is wrong; locking out the pump removes all stored energy in the circuit', False),
                ]
            },
            {
                'text': 'An axis must stop repeatably at eight different positions along its stroke and hold each one against a varying load. Which actuator suits it best?',
                'choices': [
                    ('An electric servo, because it can be commanded to any position and hold it', True),
                    ('A double-acting pneumatic cylinder, because it has full force in both directions', False),
                    ('A single-acting pneumatic cylinder, because the spring return is repeatable', False),
                    ('An air motor, because continuous rotation covers every position', False),
                ]
            }
        ])

        # Lesson 4: Building an Arm: Workspace, Reach & Materials
        lesson = self._lesson(
            unit, 'rob201-arm-construction-workspace-and-reach', 3,
            title='Building an Arm: Workspace, Reach & Materials',
        )
        self._create_sections(lesson, [
            {
                'title': 'Overview',
                'content': '''# Building an Arm: Workspace, Reach & Materials

Designing an arm on paper is one thing; building one that still points where you told it to after a thousand cycles is another. Real arms sag, vibrate, wear at the joints, and eventually break a wire that has been flexing for months. In this lesson you will learn to lay out a work envelope, predict deflection before you cut metal, choose materials on evidence, and use the shop tools that turn a drawing into a machine.

## Learning Objectives

By the end of this lesson, you will be able to:
- Lay out a work envelope from task requirements and check reach and clearance
- Explain how reach, payload, and cross-section affect deflection under load
- Compare aluminum, steel, engineering polymers, and carbon fiber on strength, stiffness, weight, and cost
- Select and use the fasteners, bearings, cable management, and measuring tools an arm build requires

> **TEKS alignment:** §127.750(c)(11) — demonstrates knowledge of the function and application of tools, equipment, and materials used in robotics.'''
            },
            {
                'title': 'Workspace Envelope and Reach',
                'content': '''# Laying Out the Work Envelope

The **work envelope** (or workspace) is the complete set of points the tool can reach. Getting it right is the first design decision, because everything else - link lengths, motor sizes, cell layout - follows from it.

## Reachable vs Dexterous Workspace

- The **reachable workspace** is every point the tool center can touch in *at least one* orientation.
- The **dexterous workspace** is the smaller region the tool can reach in *every* orientation.

A pick-and-place task may only need reachable workspace. A task that must approach a hole at a fixed angle needs that point inside the dexterous workspace, and beginners routinely design a cell that "reaches" a fixture only to discover the tool cannot get there pointing the right way.

## Envelope Shapes by Configuration

| Configuration | Envelope shape | Notable dead zones |
|---------------|----------------|--------------------|
| Cartesian gantry | Rectangular box | None inside the box |
| Cylindrical | Hollow cylinder | Column around the base |
| Articulated | Thick spherical shell | Sphere near the base; edge at full extension |
| SCARA | Annular disc with vertical travel | Inner circle the arms cannot fold into |
| Delta | Shallow dome under the frame | Everything outside the dome |

## A Layout Procedure

1. **Plot every point the tool must reach** - pick position, place position, tool-change stand, home position, service position.
2. **Add the approach and retreat clearance.** A gripper that grabs a part from above needs 100-150 mm above the pick point to clear before it moves.
3. **Draw the envelope over that point set**, then verify the farthest point is inside the reach with margin. Never design to 100 percent of reach: near full extension the arm is at its weakest, slowest to correct, and closest to an elbow singularity. Aim to use **80-90 percent** of rated reach.
4. **Check self-collision and cell collision.** Sweep the arm through its path in the simulator and look for the tool striking the arm's own link, the fixture, or a fence.
5. **Include the human.** Where does an operator stand? Where does the maintenance technician need access? An envelope that overlaps a walkway needs guarding or a rated safety-monitored stop.

Free simulators make this cheap to test. **VEXcode VR** lets you rehearse reach and path logic on a virtual robot with no hardware, so you can find the "it cannot quite get there" problem before it costs anything but time.'''
            },
            {
                'title': 'Deflection, Payload, and Moment',
                'content': '''# Why Arms Sag: Deflection and Moment

A link is not perfectly rigid. Load it and it bends, and the tool ends up somewhere below where the math said it would be. Two ideas explain almost everything you will see.

## Moment: Load Times Distance

The torque a joint must supply is the load force times the perpendicular distance to the joint:

**M = F × d**

A 2 kg payload held 0.6 m from the shoulder creates 2 × 9.81 × 0.6 ≈ **11.8 N·m** of static moment - and that is before adding the weight of the links themselves, the gripper, or any acceleration. Double the reach and the required torque doubles. This is why long-reach arms have dramatically lower payload ratings than short ones from the same family: it is the *moment* that limits them, not the mass.

## Deflection: Load Times Distance Cubed

For a cantilever - a beam supported at one end and loaded at the other, which is exactly what a robot link is - tip deflection follows:

**δ = F L³ / (3 E I)**

- **F** is the load at the tip
- **L** is the length
- **E** is the material stiffness (Young's modulus)
- **I** is the area moment of inertia of the cross-section

Three lessons hide in that equation:

1. **Length dominates.** Deflection scales with L **cubed**. Double the reach with the same tube and the same load, and the arm sags about **eight times** as much. Long arms need much heavier sections, not slightly heavier ones.
2. **Cross-section shape beats material.** *I* for a solid round bar scales with the fourth power of diameter, so going from a 20 mm bar to a 25 mm bar more than doubles stiffness for a 56 percent weight increase. Better still, a **hollow tube** puts material far from the neutral axis where it does the most good: a 25 mm tube with a 2 mm wall is far stiffer per gram than a 15 mm solid rod. This is why robot links are tubes, box sections, and extrusions rather than solid bars.
3. **Stiffness is not strength.** *E* controls how much it bends; yield strength controls when it stays bent. An arm can be strong enough never to break and still be useless because it flexes 3 mm under load.

## Vibration and Settling Time

A flexible arm does not just sag - it rings. After a fast move it oscillates for a fraction of a second before the tool settles, and that settling time is dead time in every cycle. Stiffer links and lower moving mass both shorten it. This is the hidden reason delta robots are so fast: their motors are on the frame, so the moving structure is featherweight.

## Design Moves That Help

- Shorten the reach if the task allows
- Use tube or box sections instead of solid bar or flat plate
- Add a triangulated gusset at the joint, where bending moment is highest
- Move mass toward the base - a motor at the shoulder driving the elbow through a belt beats a motor bolted at the elbow
- Lighten the end effector; every gram there is the most expensive gram in the machine'''
            },
            {
                'title': 'Selecting Materials',
                'content': '''# Selecting Materials for an Arm

Material choice is a trade among stiffness, weight, cost, and how easy the stuff is to work with in a school shop.

| Material | Density (g/cm³) | Young's modulus E (GPa) | Approx. yield / tensile strength | Notes |
|----------|-----------------|-------------------------|-------------------------------|-------|
| **Aluminum 6061-T6** | 2.70 | 69 | ~276 MPa yield | Easy to cut, drill, and tap; corrosion resistant; the default |
| **Aluminum extrusion (T-slot)** | 2.70 | 69 | Varies by profile | Bolts together with no machining; instantly reconfigurable |
| **Mild steel (1018)** | 7.85 | 200 | ~370 MPa yield (cold rolled) | Nearly three times the stiffness of aluminum but also three times the weight |
| **3D-printed PLA** | 1.24 | ~3.5 | ~50 MPa tensile | Fast, free-form geometry; creeps under sustained load; softens near 60 °C |
| **3D-printed PETG or ABS** | 1.27 / 1.04 | ~2 | ~45 MPa | Tougher and more heat tolerant than PLA; still far too soft for main links |
| **Carbon fiber composite tube** | ~1.6 | 70-150 along the fibers | Very high | Outstanding stiffness per gram; expensive, and the dust is a respiratory hazard |

## Reading the Table

- **Steel vs aluminum is a wash for stiffness per weight.** Steel's E is about 2.9 times aluminum's, but it is also about 2.9 times denser. Choose steel for wear surfaces, shafts, high loads, and weldability; choose aluminum when you must move the part, because for the same *mass* you can make an aluminum section much thicker and therefore stiffer in bending.
- **Printed polymers belong on brackets, guards, spacers, jaw pads, and custom gripper fingers**, not on the main structural links of a loaded arm. Their modulus is roughly **twenty times lower** than aluminum, so a printed link that looks fine will visibly droop.
- **Carbon fiber wins on paper and loses on budget.** It is the right call when moving mass is the binding constraint - a long reach at high speed - and the wrong call for a first prototype that will be redesigned three times.

## Practical Selection Rules

1. **Prototype in what you can change.** T-slot extrusion and printed brackets let you move a joint 20 mm on a Tuesday. Committing to welded steel on day one guarantees you build the wrong thing precisely.
2. **Match the material to the job of the part.** Structural link: aluminum tube or extrusion. Rotating shaft: steel. Bushing or wear pad: acetal or bronze. Cosmetic cover: printed polymer. Never make a bearing surface out of the same metal as its mate - like metals gall and seize.
3. **Cost the whole part, not the stock.** Carbon fiber tube is cheap compared with the labor of machining a complex aluminum weldment - but it needs bonded or clamped joints, which is a whole new skill.
4. **Think about repairs.** Aluminum extrusion is bolted, so it is field-serviceable. A one-piece printed link means reprinting the whole thing when one boss cracks.'''
            },
            {
                'title': 'Fasteners, Bearings, Cables, and Tools',
                'content': '''# Putting It Together: Hardware and Tools

## Fasteners

Metric **socket head cap screws** (M3, M4, M5, M6) are the standard in robot builds - a hex driver reaches into tight spots that a screwdriver cannot. A few rules keep joints tight:

- **Thread engagement** in aluminum should be at least **1.5 to 2 times the screw diameter** - an M4 screw wants 6-8 mm of thread. Less will strip.
- Vibration loosens screws. Use a **nylon-insert lock nut**, a **split or wedge lock washer**, or **thread-locking compound**: blue (medium strength, removable with hand tools) for almost everything, red (high strength, needs heat to remove) only where you truly never want it back out.
- Use a **shoulder bolt** at any pivot. The smooth, precisely sized shoulder is the actual bearing surface, and the threads stay out of the joint where they would wear an oval hole.
- **Do not overtighten.** Aluminum threads strip long before steel ones. Typical torque for an M4 screw in aluminum is on the order of **2-3 N·m** - light by hand-strength standards.

## Bearings

- **Plain bearings (bushings)** of bronze or acetal are cheap, quiet, tolerant of dirt, and fine for slow pivots.
- **Ball bearings** give far lower friction and higher precision for continuously rotating shafts. Watch the load direction: **radial** bearings take load perpendicular to the shaft, **thrust** bearings take it along the shaft, and loading a radial bearing axially destroys it.
- Support a rotating shaft at **two points**. A single bearing lets the shaft cock over and bind.

## Cable Management

Wiring is where prototypes die weeks after they work.

- Leave a **service loop** so a joint can move through its full range without pulling anything tight.
- At a moving joint use **continuous-flex cable** in a **drag chain**. Standard hookup wire work-hardens and breaks after a few thousand flexes.
- Respect the **minimum bend radius**, typically about **10 times the cable diameter** in a flexing application.
- Add **strain relief** at every connector so the pull lands on a clamp, not on a solder joint.
- Route **power and signal separately**; motor current induces noise that scrambles encoder signals sharing a bundle.

## The Tools of the Build

| Tool | What it is for | Typical spec |
|------|----------------|-------------|
| Digital calipers | Measuring stock, bores, and shaft diameters | 0.01 mm resolution |
| Machinist square and steel rule | Layout and checking squareness | 0.5 mm |
| Torque wrench or torque driver | Tightening fasteners to spec, repeatably | 1-10 N·m for small builds |
| Drill press | Holes perpendicular to the surface | Clamp the work, never hand-hold |
| Tap set with tapping fluid | Cutting threads into aluminum plate | M3-M8 covers most builds |
| Dial indicator | Measuring runout, backlash, and deflection | 0.01 mm |
| Multimeter | Verifying continuity and voltage before power-up | Continuity beep saves motors |

Two habits matter as much as the tools: **clamp the work** before drilling, and **measure before and after** - a hole drilled 2 mm off is a new part, not a repair.'''
            }
        ])
        self._create_lesson_questions(lesson, [
            {
                'text': 'A team doubles the length of an arm link while keeping the same tube cross-section and the same tip load. Roughly what happens to the tip deflection?',
                'choices': [
                    ('It increases about eight times, because deflection scales with length cubed', True),
                    ('It doubles, because deflection scales directly with length', False),
                    ('It stays the same, because the material and cross-section did not change', False),
                    ('It is cut in half, because the load is spread over a longer beam', False),
                ]
            },
            {
                'text': 'A class needs structural links that are stiff, light, cheap enough for a school budget, easy to drill and tap, and simple to reconfigure between design revisions. Which material fits best?',
                'choices': [
                    ('Aluminum tube or T-slot extrusion', True),
                    ('Carbon fiber composite tube', False),
                    ('3D-printed PLA', False),
                    ('Solid mild steel bar', False),
                ]
            },
            {
                'text': 'A wire running across a rotating joint works fine at first, then fails intermittently after a few weeks of operation. What is the best fix?',
                'choices': [
                    ('Replace it with continuous-flex cable in a drag chain, with a service loop and the minimum bend radius respected', True),
                    ('Tighten the wire against the link so it cannot move at all during operation', False),
                    ('Bundle it together with the motor power leads so both are supported', False),
                    ('Increase the wire gauge so it can carry more current without heating', False),
                ]
            },
            {
                'text': 'The assembly drawing specifies that a shoulder bolt at a pivot be tightened to 3 N·m. Which tool confirms you actually hit that value?',
                'choices': [
                    ('A torque wrench or torque driver', True),
                    ('Digital calipers', False),
                    ('A dial indicator', False),
                    ('A machinist square', False),
                ]
            }
        ])

        self._create_unit3_quiz(unit)

    def _create_unit3_quiz(self, unit):
        quiz = self._quiz(
            unit, 'rob201-quiz-manipulators-and-end-effectors', 0,
            title='Manipulators & End Effectors Quiz',
            description='Test your understanding of arm anatomy, end effector selection, fluid power and accumulators, and arm construction.',
            passing_score=70,
            points=20,
            max_attempts=3,
        )
        self._create_quiz_questions(quiz, [
            {
                'text': 'A packaging line must move small candies from a moving belt into trays at 200 picks per minute. The parts weigh a few grams each and all lie flat. Which arm configuration is designed for this job?',
                'choices': [
                    ('A delta robot, because its motors stay on the frame and the moving mass is tiny', True),
                    ('A six-axis articulated arm, because it has the most degrees of freedom', False),
                    ('A cartesian gantry, because its envelope is a rectangular box', False),
                    ('A cylindrical arm, because it rotates quickly about its base', False),
                ]
            },
            {
                'text': 'A recycling cell must pull steel cans out of a moving stream of mixed plastic, aluminum, and steel scrap. Which end effector is the right starting point?',
                'choices': [
                    ('A magnetic gripper, because it attracts only ferrous parts and tolerates a rough, unaligned pile', True),
                    ('A vacuum cup array, because it lifts quickly from flat surfaces', False),
                    ('A three-jaw concentric gripper, because it self-centers round parts', False),
                    ('A soft elastomer gripper, because it wraps around irregular shapes', False),
                ]
            },
            {
                'text': 'What is the primary function of an accumulator in a fluid power system?',
                'choices': [
                    ('It stores pressurized fluid so the system can cover peak demand, absorb pressure spikes, and act during a power loss', True),
                    ('It filters particulates and water out of the fluid before it reaches the cylinders', False),
                    ('It converts rotary motion from the pump into linear motion at the cylinder', False),
                    ('It measures flow rate so the controller can calculate actuator position', False),
                ]
            },
            {
                'text': 'Identical 40 mm bore cylinders are fed at 6 bar of air in one machine and 210 bar of oil in another. What does this mean for the designer?',
                'choices': [
                    ('The hydraulic version produces roughly 35 times the force from the same hardware, so high-force jobs go hydraulic', True),
                    ('The pneumatic version produces more force because air moves faster than oil', False),
                    ('Both produce the same force, because bore size alone determines cylinder force', False),
                    ('The hydraulic version produces less force because oil is denser and harder to move', False),
                ]
            },
            {
                'text': 'A student proposes 3D-printed PLA for the main structural links of a loaded arm to save money. What is the strongest technical objection?',
                'choices': [
                    ('PLA has a modulus roughly twenty times lower than aluminum, so the links will visibly deflect and it also creeps under sustained load', True),
                    ('PLA cannot be manufactured in the tube or box shapes that links require', False),
                    ('PLA is heavier than aluminum, so it would exceed the payload budget', False),
                    ('PLA cannot be fastened with screws, so the arm could not be assembled', False),
                ]
            },
            {
                'text': 'A cell layout places the farthest pick point at 99 percent of the arm rated reach. Why do experienced designers reject this?',
                'choices': [
                    ('Near full extension the arm is weakest, least accurate, and close to an elbow singularity, so 80-90 percent of reach is the target', True),
                    ('Manufacturers void the warranty on any arm operated past 90 percent of its reach', False),
                    ('Inverse kinematics cannot be computed at all beyond 90 percent of reach', False),
                    ('The work envelope of an articulated arm is a perfect sphere, so the edges are unusable', False),
                ]
            }
        ])

    # ================== UNIT 4: Programming Robots in Python ==================
    def _create_unit4(self, course):
        unit = self._unit(course, 3, 'Programming Robots in Python')

        # Lesson 1: Python Fundamentals for Robots
        lesson = self._lesson(
            unit, 'rob201-python-fundamentals-for-robots', 0, title='Python Fundamentals for Robots',
        )
        self._create_sections(lesson, [
            {
                'title': 'Overview',
                'content': '''# Python Fundamentals for Robots

In Robotics 1 you planned robot behavior with pseudocode and snapped together blocks. Now you write the real thing. Python is the language professional roboticists reach for first, and by the end of this lesson you will be storing sensor readings in variables, doing the arithmetic that turns centimeters into wheel turns, and reading your own program back to find out why the robot did something strange.

## Learning Objectives

By the end of this lesson, you will be able to:
- Create variables and identify the four core Python types used in robot code: int, float, bool, and str
- Use arithmetic and comparison operators to convert units and test sensor readings
- Explain how indentation defines a block in Python and why a misplaced space changes behavior
- Use comments and print statements to document and debug a robot program

> **TEKS alignment:** §127.750(c)(8) — the student creates a program to control a robotic or automated system.'''
            },
            {
                'title': 'Variables and Types',
                'content': '''# Variables: Named Boxes for Robot Data

A **variable** is a name attached to a value. Your program uses variables to remember things the robot needs: how fast a motor is turning, how far away the wall is, whether the gripper is holding something. You create one with an **assignment statement** — a name, an equals sign, and a value.

```python
motor_speed = 50            # int   - percent of full power
wheel_diameter_cm = 10.16   # float - centimeters
line_detected = False       # bool  - True or False
robot_name = "Rover-7"      # str   - text

print(motor_speed, wheel_diameter_cm, line_detected, robot_name)
```

Python figures out the type for you from the value you wrote. You never declare it.

## The Four Types You Will Use Constantly

| Type | What it holds | Robot example |
|------|---------------|---------------|
| int | Whole numbers | power = 75, loop_count = 4 |
| float | Numbers with a decimal point | battery_volts = 11.8, seconds = 0.02 |
| bool | Exactly True or False | bumper_pressed = True |
| str | Text, in quotes | mode = "autonomous" |

You can ask Python what it decided:

```python
speed = 50
battery_volts = 11.8
is_running = True

print(type(speed))          # <class 'int'>
print(type(battery_volts))  # <class 'float'>
print(type(is_running))     # <class 'bool'>
```

## Reassignment

A variable is a box, not a label carved in stone. Assigning again replaces what is inside, and the right side is evaluated **before** the assignment happens.

```python
speed = 30
speed = speed + 20   # Python computes 30 + 20, then stores 50
speed += 10          # shorthand for speed = speed + 10
print("speed is", speed)
```

That prints `speed is 60`.

## Naming Rules and Habits

Names may contain letters, digits, and underscores, but may not start with a digit and may not contain spaces. Python is case sensitive: `Speed` and `speed` are two different variables — a very common source of "but I set it!" bugs.

Good robot code puts the **unit in the name**. `distance` tells a teammate nothing; `distance_mm` tells them everything. Half of all robot math bugs are unit mix-ups, and naming is the cheapest defense against them.

The exact function names used to read a sensor or drive a motor differ from platform to platform — VEXcode VR, a Raspberry Pi library, and a simulator each spell them differently. Variables, types, and operators are identical everywhere.'''
            },
            {
                'title': 'Arithmetic and Comparison Operators',
                'content': '''# Doing the Math a Robot Needs

Robot programs are full of arithmetic: converting a distance into wheel turns, splitting a millisecond count into seconds, scaling a sensor reading into a motor power.

## Arithmetic Operators

| Operator | Meaning | Example | Result |
|----------|---------|---------|--------|
| + - | Add, subtract | 50 - 12 | 38 |
| * | Multiply | 4 * 90 | 360 |
| / | Divide (always gives a float) | 7 / 2 | 3.5 |
| // | Floor divide (drops the remainder) | 7 // 2 | 3 |
| % | Modulo (the remainder) | 7 % 2 | 1 |
| ** | Power | 2 ** 3 | 8 |

Python follows the same order of operations you use in math class: parentheses, then `**`, then `*` `/` `//` `%`, then `+` `-`. When in doubt, add parentheses — they cost nothing and they make your intent obvious.

Here is a real conversion every drivetrain program needs. How many wheel rotations does it take to drive 120 cm?

```python
import math

wheel_diameter_cm = 10.0
circumference_cm = math.pi * wheel_diameter_cm
target_cm = 120.0
turns_needed = target_cm / circumference_cm

print(round(turns_needed, 2))   # 3.82
```

And here is `//` and `%` splitting a duration:

```python
total_ms = 4500
seconds = total_ms // 1000      # 4
remainder_ms = total_ms % 1000  # 500
print(seconds, "s and", remainder_ms, "ms")
```

## Comparison Operators

Comparisons ask a question and answer with a `bool`. They are how a robot decides anything.

```python
distance_mm = 240

print(distance_mm < 300)    # True
print(distance_mm >= 240)   # True
print(distance_mm == 240)   # True
print(distance_mm != 240)   # False
```

## The Single Most Common Beginner Error

`=` and `==` are different operators and mixing them up breaks programs:

- `distance_mm = 240` **stores** 240 in the variable
- `distance_mm == 240` **asks** whether the variable already equals 240, and produces `True` or `False`

Writing `if distance_mm = 240:` is a syntax error, and writing `distance_mm == 0` when you meant to reset a counter silently does nothing at all. Read every line and ask yourself: am I storing, or am I asking?

One more caution: `float` math is approximate. `0.1 + 0.2` prints `0.30000000000000004`. Never test a float with `==`; compare with `<` or `>`, or check that the difference is small.'''
            },
            {
                'title': 'Indentation Is Syntax',
                'content': '''# Indentation Is Not Decoration

In most languages, indenting your code is a style choice. In Python it is **grammar**. The leading spaces on a line tell Python which block that line belongs to, and changing them changes what your robot does.

A block is introduced by a line ending in a colon, and every line indented under it belongs to that block:

```python
distance_mm = 150

if distance_mm < 200:
    print("Obstacle ahead")
    print("Stopping")
print("Program finished")
```

Because `distance_mm` is 150, all three lines print. Now watch what the indentation controls. `Obstacle ahead` and `Stopping` are indented, so they run **only** when the condition is true. `Program finished` sits back at the left margin, so it runs either way. If the reading had been 400, you would see only the last line.

## The Rules

- Use **four spaces** per level. That is the standard the whole Python world follows.
- Be consistent. Mixing tabs and spaces in one file produces a `TabError` even though the code looks perfectly aligned on your screen.
- Every line in a block must be indented the same amount, or you get an `IndentationError`.
- A block may never be empty. If you truly want a placeholder, write `pass`.

## Two Errors You Will Meet This Week

```python
distance_mm = 150

if distance_mm < 200:
    print("stopping")
    print("logging the stop")
```

Delete the indentation on that last `print` and it becomes an ordinary statement that runs every pass through the program — no error message, just a robot that logs a stop it never made. This is the dangerous kind of mistake: the program runs, so nothing tells you it is wrong except the behavior.

Forget the colon at the end of the `if` line and Python refuses to run the file at all, reporting a `SyntaxError`. That is the friendly kind of mistake — the computer catches it for you.

## Why Python Chose This

The indentation you would have written anyway to make code readable *is* the structure. There are no curly braces to forget or mismatch, and a Python program that looks right almost always is right. The price is that whitespace matters, so keep your editor set to insert four spaces when you press Tab and let it indent for you.'''
            },
            {
                'title': 'Comments and Printing to Debug',
                'content': '''# Comments and print(): Your Two Debugging Tools

A robot cannot tell you what it was thinking. Comments record what *you* were thinking, and `print()` shows you what the program actually saw.

## Comments

Everything after a `#` on a line is ignored by Python.

```python
# Threshold chosen after testing on the practice field.
STOP_DISTANCE_MM = 180   # any closer and the robot cannot brake in time
```

Write comments that explain **why**, not **what**. `speed = 50  # set speed to 50` is noise; `speed = 50  # higher values slip on the mat` is worth keeping. Comments are also how you temporarily disable a line while hunting a bug — put a `#` in front of it instead of deleting it.

By convention, values that never change get ALL_CAPS names like `STOP_DISTANCE_MM`. Python will not stop you from reassigning them, but every reader takes the name as a promise that you will not.

## print() Is a Window Into a Running Robot

When a robot misbehaves, you have exactly one question: what did the program believe at that moment? Print it.

```python
def read_front_distance():
    # Stand-in for the platform sensor call; returns millimeters.
    return 185

distance_mm = read_front_distance()
print("distance_mm =", distance_mm)

if distance_mm < 200:
    print("branch: obstacle")
else:
    print("branch: clear")
```

Running that prints:

```text
distance_mm = 185
branch: obstacle
```

Two lines of output answer both debugging questions at once: what the sensor reported, and which path the program took. Guessing at either one wastes an afternoon.

## Formatting Output

`print()` separates its arguments with a space. An **f-string** — a string with `f` in front — lets you drop variables directly inside:

```python
left_power = 45
right_power = 38
print(f"left={left_power} right={right_power}")
```

That prints `left=45 right=38`, which is far easier to scan in a scrolling log than four separate numbers.

## A Debugging Habit Worth Building

Print at the **decision points**: right after you read a sensor, right before you command a motor, and inside each branch of an `if`. When output stops matching what you expect, the bug is between the last good print and the first bad one. That habit turns "the robot is broken" into a two-line search, and it works on every platform, in every simulator, with no special tools.'''
            }
        ])
        self._create_lesson_questions(lesson, [
            {
                'text': 'Which line of Python actually stores a new value in the variable speed?',
                'choices': [
                    ('speed = speed + 10', True),
                    ('speed == speed + 10', False),
                    ('speed + 10', False),
                    ('10 = speed + 10', False),
                ]
            },
            {
                'text': 'What type does Python give the variable in the line wheel_diameter_cm = 10.16?',
                'choices': [
                    ('float, because the value has a decimal point', True),
                    ('int, because it is a number', False),
                    ('str, because it contains a period', False),
                    ('bool, because it is either true or false', False),
                ]
            },
            {
                'text': 'Consider this program: distance_mm = 150, then a line "if distance_mm < 200:" with an indented print("A") beneath it, followed by print("B") at the left margin. What is printed?',
                'choices': [
                    ('A and then B', True),
                    ('Only A', False),
                    ('Only B', False),
                    ('Nothing, because the condition is false', False),
                ]
            },
            {
                'text': 'Your robot stops earlier than expected. Which debugging step gives you the most useful information first?',
                'choices': [
                    ('Print the sensor value and the branch taken right before the stop', True),
                    ('Rewrite the whole program from scratch', False),
                    ('Delete the comments so the code is shorter', False),
                    ('Change the motor speed and run it again', False),
                ]
            }
        ])

        # Lesson 2: Loops, Conditionals & Functions in Robot Code
        lesson = self._lesson(
            unit, 'rob201-loops-conditionals-and-functions', 1,
            title='Loops, Conditionals & Functions in Robot Code',
        )
        self._create_sections(lesson, [
            {
                'title': 'Overview',
                'content': '''# Loops, Conditionals & Functions in Robot Code

Sequence, selection, and repetition are the three building blocks of every program ever written — and Python spells them `if`, `while`, and `for`. Add functions, and you stop copying and pasting the same four lines of turning code and start building a vocabulary of robot behaviors you can call by name.

## Learning Objectives

By the end of this lesson, you will be able to:
- Write if / elif / else statements that let a robot choose between actions
- Choose between a for loop and a while loop, and use range() without off-by-one errors
- Combine conditions with the boolean operators and, or, and not
- Define functions with parameters and return values to package reusable robot behaviors

> **TEKS alignment:** §127.750(c)(8) — the student creates a program to control a robotic or automated system.'''
            },
            {
                'title': 'Making Decisions with if, elif and else',
                'content': '''# Decisions: if, elif, else

An `if` statement runs a block only when a condition is `True`. This is *selection*, and it is what makes a robot look intelligent instead of merely programmed.

```python
distance_mm = 320

if distance_mm < 150:
    print("stop")
elif distance_mm < 400:
    print("slow")
else:
    print("full speed")
```

That prints `slow`.

## How the Chain Is Evaluated

Python checks the conditions **top to bottom and stops at the first one that is true**. Everything below it is skipped, even if it would also be true. In the example, 320 is less than 400, but Python never even reaches the `else`.

That ordering rule is a trap when you write the chain in the wrong order:

```python
distance_mm = 100

if distance_mm < 400:
    print("slow")       # this one wins
elif distance_mm < 150:
    print("stop")       # unreachable
```

The robot at 100 mm should stop, but it prints `slow`, because the looser condition was tested first and the tighter one can never be reached. **Order your conditions from the most specific to the most general.**

## The Parts

- `if` — required, tested first
- `elif` — optional, and you may chain as many as you need
- `else` — optional, runs when every condition above it was false

Only one branch of the whole chain ever runs. If you write several separate `if` statements instead of one `if`/`elif` chain, every one of them is tested and more than one block can run — sometimes that is what you want, usually it is a bug.

## Nesting

A block can contain another `if`. Indent one more level:

```python
front_mm = 900
battery_volts = 10.9

if front_mm > 500:
    if battery_volts < 11.0:
        print("path clear but battery low - returning to base")
    else:
        print("driving forward")
```

That prints the low-battery message. Nesting more than two or three levels deep gets hard to read fast; the next section shows how boolean operators often let you flatten it back to one level.'''
            },
            {
                'title': 'Repeating Work: while and for Loops',
                'content': '''# Repetition: for and while

Robot code repeats constantly — four sides of a square, fifty sensor checks a second, "keep going until something happens." Python gives you two loops, and picking the right one is most of the battle.

## for: repeat a known number of times

Use `for` with `range()` when you know the count up front.

```python
def drive_forward(distance_cm):
    print("driving", distance_cm, "cm")

def turn_degrees(angle_deg):
    print("turning", angle_deg, "degrees")

for side in range(4):
    print("side number", side + 1)
    drive_forward(50)
    turn_degrees(90)
```

`range(4)` produces `0, 1, 2, 3` — **four values, starting at zero, stopping before four**. That is the single most misread thing in Python. If you want the sides numbered 1 through 4 for a human reader, print `side + 1`, as above. `range(1, 5)` also gives four passes, numbered 1 through 4.

If you do not need the counter at all, the convention is to name it `_`:

```python
for _ in range(3):
    print("beep")
```

## while: repeat until a condition changes

Use `while` when you cannot know the count in advance — "drive until the wall is close."

```python
readings = [900, 700, 500, 300, 150]
index = 0
distance_mm = readings[index]

while distance_mm > 200:
    print("clear at", distance_mm, "mm")
    index = index + 1
    distance_mm = readings[index]   # re-read the sensor every pass

print("obstacle at", distance_mm, "mm - stopping")
```

The list stands in for a real sensor that returns a smaller number as the robot approaches. The loop prints four "clear" lines and then stops at 150.

## The Infinite Loop Trap

Look closely at the line marked *re-read the sensor*. Delete it and the loop tests the same stale value forever, the robot never stops, and nothing in the output tells you why. **Every `while` loop needs something inside its body that can change the condition.** In real robot code that something is almost always a fresh sensor reading.

Two escape hatches exist: `break` leaves the loop immediately, and `continue` skips to the next pass. Use them sparingly — a loop whose exit condition is honest in the `while` line is easier to reason about than one riddled with `break` statements. A common safety pattern is a loop counter that gives up after a maximum number of passes, so a stuck sensor can never freeze the whole program.'''
            },
            {
                'title': 'Boolean Logic: and, or, not',
                'content': '''# Combining Conditions

Real robot decisions rarely depend on one number. "Drive forward only if the path ahead is clear **and** the battery is healthy" needs two conditions in one `if`. Python provides three boolean operators.

| Operator | True when | Robot example |
|----------|-----------|---------------|
| and | **Both** sides are true | Path clear AND battery good |
| or | **At least one** side is true | Front bumper OR side bumper hit |
| not | The value is false | NOT holding a game piece |

```python
front_mm = 250
left_mm = 90
line_seen = False

if front_mm > 200 and left_mm > 120:
    print("path is fully clear")

if front_mm < 200 or left_mm < 120:
    print("something is close")

if not line_seen:
    print("no line under the sensor")
```

Trace it. The first condition needs both halves true; `left_mm > 120` is false because 90 is not greater than 120, so `and` gives `False` and nothing prints. The second condition needs only one half; `left_mm < 120` is true, so it prints. The third prints because `line_seen` is `False` and `not False` is `True`. Output: two lines.

## Truth Tables Worth Memorizing

| A | B | A and B | A or B |
|---|---|-----------|----------|
| True | True | True | True |
| True | False | False | True |
| False | True | False | True |
| False | False | False | False |

## Flattening Nested Ifs

Boolean operators frequently replace nesting and read better:

```python
front_mm = 900
battery_volts = 11.6

if front_mm > 500 and battery_volts >= 11.0:
    print("driving forward")
else:
    print("holding position")
```

That prints `driving forward`, and it says exactly what the pilot would say out loud.

## Two Beginner Traps

`if front_mm > 200 and left_mm:` does not mean what it looks like — `left_mm` on its own is a number, and any nonzero number counts as true, so that half of the test is always true. Write the full comparison on both sides of `and`.

Also, `not` binds tighter than `and` and `or`, so `not a and b` means `(not a) and b`. When you are unsure, use parentheses. They are free, and a teammate reading your code at a competition should never have to look up operator precedence.'''
            },
            {
                'title': 'Functions: Reusable Robot Behaviors',
                'content': '''# Functions: Naming a Behavior

A **function** is a named block of code you can run whenever you want. You define it once with `def`, then **call** it by name as many times as you like.

```python
def beep():
    print("beep!")

beep()
beep()
```

## Parameters Make Functions General

A **parameter** is an input the caller supplies, which turns one rigid behavior into a family of them.

```python
def turn_degrees(angle_deg, turn_speed=30):
    """Turn in place. A positive angle turns right, a negative angle left."""
    direction = "right"
    if angle_deg < 0:
        direction = "left"
    print(f"turning {abs(angle_deg)} degrees {direction} at {turn_speed}%")
    return abs(angle_deg) / 90.0   # rough estimate of seconds required

seconds = turn_degrees(-90)
print(round(seconds, 2))
```

That prints `turning 90 degrees left at 30%` and then `1.0`. Notice `turn_speed=30`: a **default value**, used when the caller does not supply one. `turn_degrees(180, 50)` overrides it.

## Return Values

`return` hands a value back to whoever called the function and ends the function immediately. A function with no `return` gives back `None`, which is Python for "nothing." Calling `print()` inside a function is not the same as returning — printing shows a human; returning gives the *program* something to use.

## Why This Matters on a Robot

```python
def drive_forward(distance_cm):
    print("driving", distance_cm, "cm")

def turn_degrees(angle_deg):
    print("turning", angle_deg, "degrees")

def drive_square(side_cm):
    for _ in range(4):
        drive_forward(side_cm)
        turn_degrees(90)

drive_square(50)
```

Three benefits, all of them practical:

- **Fix it once.** When you discover the robot actually needs 93 degrees to turn a true 90 on the competition mat, you change one line inside `turn_degrees` and every call in the program is corrected.
- **Read it later.** `drive_square(50)` says what the robot does. Eight lines of motor commands say how, which is not what you want to read at 2 a.m. before a match.
- **Test it alone.** You can call `turn_degrees(90)` by itself in a simulator to check the calibration, without running the whole autonomous routine.

## Scope, Briefly

Variables created inside a function exist only inside it. That is a feature: a helper cannot accidentally clobber `distance_mm` in your main loop. To get information in, use parameters; to get information out, use `return`. Reaching for globals instead is how two teammates end up overwriting each other in the same variable.'''
            }
        ])
        self._create_lesson_questions(lesson, [
            {
                'text': 'How many times does the body of "for side in range(4):" run, and what values does side take?',
                'choices': [
                    ('Four times, with side taking the values 0, 1, 2, 3', True),
                    ('Four times, with side taking the values 1, 2, 3, 4', False),
                    ('Five times, with side taking the values 0 through 4', False),
                    ('Three times, with side taking the values 1, 2, 3', False),
                ]
            },
            {
                'text': 'A while loop reads the distance sensor once BEFORE the loop and never again inside it. What happens?',
                'choices': [
                    ('The condition is tested against a stale value, so the loop can run forever', True),
                    ('Python automatically re-reads the sensor each pass', False),
                    ('The loop runs exactly once and then exits', False),
                    ('Python reports a syntax error before the program starts', False),
                ]
            },
            {
                'text': 'Given front_mm = 250 and left_mm = 90, what is the value of "front_mm > 200 and left_mm > 120"?',
                'choices': [
                    ('False, because and requires both comparisons to be true', True),
                    ('True, because the first comparison is true', False),
                    ('True, because at least one comparison is true', False),
                    ('False, because and is only used with numbers', False),
                ]
            },
            {
                'text': 'Your autonomous routine turns 90 degrees in six different places, and testing shows the robot needs 93 degrees for a true quarter turn. Why does having a turn_degrees() function help here?',
                'choices': [
                    ('The calibration is fixed in one place and every call is corrected at once', True),
                    ('Functions make the robot turn faster', False),
                    ('Functions remove the need to test the routine', False),
                    ('Functions let you skip the indentation rules', False),
                ]
            }
        ])

        # Lesson 3: Reading Sensors in Python
        lesson = self._lesson(
            unit, 'rob201-reading-sensors-in-python', 2, title='Reading Sensors in Python',
        )
        self._create_sections(lesson, [
            {
                'title': 'Overview',
                'content': '''# Reading Sensors in Python

A sensor does not hand your program a fact — it hands you a number, and that number is noisy, occasionally wrong, and measured in whatever units the manufacturer chose. This lesson is about the code that sits between a raw reading and a decision you are willing to bet a match on: polling, thresholds, debouncing, filtering, and refusing to trust a value that cannot be real.

## Learning Objectives

By the end of this lesson, you will be able to:
- Poll a sensor inside a loop and act on each reading
- Apply a threshold with hysteresis and debounce a noisy signal
- Convert units and smooth a signal by averaging or filtering
- Combine two sensors and reject readings that are out of a sensor valid range

> **TEKS alignment:** §127.750(c)(8) — the student creates a program to control a robotic or automated system.'''
            },
            {
                'title': 'Polling a Sensor in a Loop',
                'content': '''# Polling: Asking Over and Over

A sensor reading is a snapshot, not a subscription. Your program has to ask again every time it wants fresh information, and that repeated asking is called **polling**. The sense-think-act cycle you learned in Robotics 1 is a polling loop with a decision in the middle.

Every platform spells the read differently — one calls it `front_distance()`, another `distance.object_distance(MM)`, another reads an analog pin. In this lesson we use a stand-in function so the logic stays the same no matter what you are running:

```python
def front_distance_mm():
    """Stand-in for the platform sensor call; returns millimeters."""
    return 275

for _ in range(5):
    reading = front_distance_mm()
    print("front:", reading, "mm")
```

## Deciding on Each Pass

The point of polling is that each reading gets a decision. Here a list of samples stands in for a robot rolling toward a wall:

```python
samples = [812, 640, 455, 300, 180]

for reading_mm in samples:
    if reading_mm < 200:
        print(reading_mm, "-> STOP")
    else:
        print(reading_mm, "-> keep going")
```

The first four print `keep going`; the last prints `STOP`.

## How Fast Should You Poll?

Fast enough that the robot cannot get into trouble between two readings. A robot moving 50 cm per second that polls ten times a second travels **5 cm between looks** — plenty of time to overshoot a line. Poll fifty times a second and it moves 1 cm. That said, polling far faster than the sensor updates just wastes cycles reading the same value twice; an ultrasonic sensor that refreshes 20 times a second cannot tell you anything new at 200 Hz.

## Read Once Per Pass, Store It

There is a subtle bug worth naming now:

```python
def front_distance_mm():
    return 185

distance_mm = front_distance_mm()

if distance_mm < 200:
    print("stopping at", distance_mm)
```

Compare that to calling `front_distance_mm()` twice — once in the `if` and once in the `print`. The two calls can return different numbers, because the robot moved in between. Your log then shows a distance that never triggered the branch, and you spend an hour doubting your own `if` statement. **Read once, store in a variable, use the variable everywhere in that pass.** Every reading in the pass then describes the same instant in time.'''
            },
            {
                'title': 'Thresholds and Debouncing',
                'content': '''# Thresholds That Do Not Chatter

A **threshold** is the number where behavior changes: closer than 200 mm, stop. Written naively, thresholds misbehave in exactly two ways, and both have standard fixes.

## Problem 1: Chattering at the Edge

If the true distance hovers right at 200 mm, noise pushes readings to 198, 202, 199, 201 — and the robot stops, starts, stops, starts, several times a second. The fix is **hysteresis**: use two thresholds, one to switch on and a different one to switch off.

```python
NEAR_MM = 180
FAR_MM = 220
stopped = False

for reading_mm in [400, 210, 175, 190, 205, 260]:
    if not stopped and reading_mm < NEAR_MM:
        stopped = True
    elif stopped and reading_mm > FAR_MM:
        stopped = False
    print(reading_mm, "stopped =", stopped)
```

Follow the `stopped` column: `False, False, True, True, True, False`. The robot stops at 175, and the readings at 190 and 205 — which are on the far side of a naive 180 mm line — do not restart it. It takes a genuine 220 mm of clearance to go again. The gap between the two thresholds is the noise you are choosing to ignore.

## Problem 2: A Single Bad Sample

Sensors produce occasional garbage: an ultrasonic echo bouncing off a chair leg, a light sensor catching a camera flash. Acting on one sample means acting on that garbage. The fix is **debouncing**: require the same result several passes in a row before believing it.

```python
CONFIRM_COUNT = 3
hits = 0
confirmed = False

for reading_mm in [400, 150, 400, 150, 148, 152]:
    if reading_mm < 200:
        hits = hits + 1
    else:
        hits = 0
    if hits >= CONFIRM_COUNT:
        confirmed = True

print("obstacle confirmed:", confirmed)
```

The counter climbs to 1 on the first close reading, then resets to 0 when a far reading interrupts the streak. Only the final run of three consecutive close readings — 150, 148, 152 — reaches the confirm count, so the program prints `obstacle confirmed: True`. The isolated 150 in the middle is correctly ignored.

## Choosing the Numbers

Both techniques trade **responsiveness for reliability**. A wide hysteresis gap or a large confirm count makes the robot unshakeable and slow; a narrow gap or a count of one makes it twitchy. Pick numbers by measurement, not by feel: print raw readings while the robot sits still, note how much they wander, and set the gap a little wider than that wander. Ten seconds of logging beats an hour of guessing.'''
            },
            {
                'title': 'Units, Averaging and Filtering',
                'content': '''# Making a Signal Usable

Two jobs stand between the raw number and your control code: getting it into the units you think in, and getting the noise out.

## Convert Units Once, at the Edge

Sensors report in whatever the manufacturer chose — millimeters, inches, raw counts from 0 to 4095. Convert immediately, in one place, into the unit your whole program uses, and keep the unit in every variable name.

```python
def inches_to_mm(inches):
    return inches * 25.4

distance_mm = 914.4
print(round(distance_mm / 10.0, 1), "cm")     # 91.4 cm
print(round(inches_to_mm(6.0), 1), "mm")      # 152.4 mm
```

Scattering conversions through the code is how a program ends up comparing millimeters to centimeters and stopping ten times too late. NASA lost a Mars orbiter to exactly this class of mistake.

## Averaging a Window

The simplest filter is the **moving average**: keep the last few readings and use their mean.

```python
def average(values):
    return sum(values) / len(values)

window = [498, 512, 505, 700, 501]
print(round(average(window), 1))   # 543.2
```

Averaging smooths ordinary jitter well — but look at that result. One bad sample of 700 dragged the answer 40 mm away from the truth, because an average gives the outlier a full vote.

## Median: Better Against Spikes

The **median** is the middle value after sorting. A single wild sample cannot move it at all.

```python
def median(values):
    ordered = sorted(values)
    middle = len(ordered) // 2
    return ordered[middle]

print(median([498, 512, 505, 700, 501]))   # 505
```

(This version assumes an odd-length window, which is the usual choice precisely because it makes the middle unambiguous.) Rule of thumb: **average** for steady random noise, **median** for occasional spikes.

## The Filter With No List: Exponential Smoothing

Storing a window costs memory and bookkeeping. This one-liner keeps a running estimate instead, blending each new reading into it by a factor `alpha` between 0 and 1.

```python
smoothed = 500.0
alpha = 0.3

for raw in [505, 498, 700, 502, 499]:
    smoothed = alpha * raw + (1 - alpha) * smoothed
    print(round(smoothed, 1))
```

When the 700 spike arrives, the estimate moves only about 60 mm instead of 200, then settles back as normal readings resume. A small `alpha` (0.1) smooths hard but lags behind real changes; a large `alpha` (0.8) tracks quickly but keeps most of the noise. Every filter costs you **delay** in exchange for **calm**, and a robot that reacts to a wall 200 ms late is its own kind of broken. Filter as little as the job allows.'''
            },
            {
                'title': 'Combining Sensors and Bad Readings',
                'content': '''# Two Sensors, and What to Do When One Lies

## Sensor Fusion, the Simple Kind

One sensor tells you one thing about the world, and usually that is not enough. A front distance sensor cannot see a drop-off; a line sensor cannot see a wall. Combining them is called **sensor fusion**, and at this level it is just boolean logic in a well-named function.

```python
def is_path_clear(front_mm, left_mm, right_mm):
    return front_mm > 250 and left_mm > 120 and right_mm > 120

print(is_path_clear(400, 300, 90))    # False
print(is_path_clear(400, 300, 200))   # True
```

Wrapping the rule in a function pays off twice: the main loop reads like English (`if is_path_clear(...)`), and when you retune the numbers you touch one line.

Sometimes sensors disagree, and you have to decide in advance who wins. A useful default in robotics: **the sensor that reports danger wins.** If the bumper says it hit something and the distance sensor says the path is clear, believe the bumper — one of those two errors dents the robot and the other only wastes a second.

## Rejecting Impossible Readings

Every sensor has a valid range, and outside it the number is meaningless. Ultrasonic sensors typically report a huge value or zero when the echo never comes back. Acting on that garbage produces spectacular failures.

```python
MIN_VALID_MM = 20
MAX_VALID_MM = 2000

last_good_mm = 500

for raw_mm in [480, 3000, 495, -1, 470]:
    if MIN_VALID_MM <= raw_mm <= MAX_VALID_MM:
        last_good_mm = raw_mm
    else:
        print("ignoring out-of-range reading:", raw_mm)
    print("using", last_good_mm, "mm")
```

The 3000 and the -1 are rejected with a message, and the robot keeps steering on the last value it trusted. Notice the chained comparison `MIN_VALID_MM <= raw_mm <= MAX_VALID_MM` — Python allows that, and it reads exactly like the math.

## Do Not Coast Forever

Reusing the last good reading is safe for a pass or two. If it goes on, the robot is driving on a memory of the world instead of the world. Production code counts consecutive rejects and takes a safe action — stop, slow down, or raise an alert — once the count crosses a limit. Deciding what "safe" means for your robot *before* the sensor fails is part of designing the program, not part of debugging it.'''
            }
        ])
        self._create_lesson_questions(lesson, [
            {
                'text': 'Why does a threshold with hysteresis use two different values (for example, stop below 180 mm but resume above 220 mm)?',
                'choices': [
                    ('It stops the robot from chattering on and off when readings hover near a single threshold', True),
                    ('It makes the sensor read twice as fast', False),
                    ('It converts millimeters to centimeters automatically', False),
                    ('It is required by Python when comparing two numbers', False),
                ]
            },
            {
                'text': 'A five-reading window is 498, 512, 505, 700, 501, where 700 is a spike caused by a bad echo. Which filter is least affected by that spike?',
                'choices': [
                    ('The median, because sorting puts the spike at the end where it cannot move the middle value', True),
                    ('The average, because it divides by five', False),
                    ('The maximum, because it picks the largest reading', False),
                    ('The sum, because it adds every reading', False),
                ]
            },
            {
                'text': 'An ultrasonic sensor whose valid range is 20 to 2000 mm reports -1. What should the program do?',
                'choices': [
                    ('Reject the reading, keep using the last good value, and count how long the sensor stays bad', True),
                    ('Treat -1 as zero distance and stop immediately', False),
                    ('Add 2000 to the reading to make it positive', False),
                    ('Use the reading as-is, since the sensor reported it', False),
                ]
            },
            {
                'text': 'Why should a program read a sensor once per pass and store it in a variable instead of calling the read function separately in the if and in the print?',
                'choices': [
                    ('The two calls can return different values, so the log would not match the decision the robot made', True),
                    ('Python does not allow a function to be called twice in one loop pass', False),
                    ('Storing the value converts it to the correct units', False),
                    ('Calling the function twice would make the sensor read backwards', False),
                ]
            }
        ])

        # Lesson 4: Closed-Loop Control & Tuning in Code
        lesson = self._lesson(
            unit, 'rob201-closed-loop-control-and-tuning', 3,
            title='Closed-Loop Control & Tuning in Code',
        )
        self._create_sections(lesson, [
            {
                'title': 'Overview',
                'content': '''# Closed-Loop Control & Tuning in Code

Telling a motor to run at 40 percent for two seconds is a guess. Measuring where the robot actually is and correcting the difference, fifty times a second, is control. This lesson turns the feedback ideas you met in Robotics 1 into Python you can run: error, gain, the P in PID, and a tuning procedure that does not rely on luck.

## Learning Objectives

By the end of this lesson, you will be able to:
- Distinguish open-loop from closed-loop control in code and explain the risk of each
- Compute error as target minus measured and apply a proportional gain
- Explain why pure proportional control oscillates or leaves steady-state error, and what the I and D terms add
- Tune a controller systematically and clamp its output to the valid motor range

> **TEKS alignment:** §127.750(c)(8) — the student creates a program to control a robotic or automated system.'''
            },
            {
                'title': 'Open Loop vs Closed Loop in Code',
                'content': '''# Two Ways to Command a Motor

## Open Loop: Command and Hope

An **open-loop** program sends a command and never checks the result.

```python
def drive(power_percent):
    print("drive at", power_percent)

def wait_seconds(seconds):
    print("wait", seconds)

# Open loop: 40% power for 2 seconds is *assumed* to be one meter.
drive(40)
wait_seconds(2.0)
drive(0)
```

On a fully charged battery, on the practice carpet, this drives one meter. It also drives 1.15 meters on a fresh battery, 0.8 meters on a tired one, less on a ramp, and less again when a teammate leaves a slightly tighter screw in the drivetrain. The program has no idea any of that happened, because it never looks.

Open loop is not always wrong — it is simple, it needs no sensor, and for "spin the intake for a second" it is perfectly appropriate. It fails whenever accuracy matters or conditions change.

## Closed Loop: Measure, Compare, Correct

A **closed-loop** program measures the thing it is trying to control and uses the difference to decide what to do next.

```python
TARGET_MM = 300

def front_distance_mm(step):
    """Stand-in: the robot creeps 40 mm closer on each pass."""
    return 700 - 40 * step

for step in range(6):
    measured = front_distance_mm(step)
    error = TARGET_MM - measured
    print("step", step, "measured", measured, "error", error)
```

The **error** is the heart of it: how far off you are, right now. Here it starts at -400 (the robot is 400 mm farther away than it wants to be) and shrinks toward zero as the robot approaches. Sign matters — a positive and a negative error mean opposite corrections.

## The Vocabulary

| Term | Meaning |
|------|---------|
| Setpoint / target | The value you want |
| Measured / process variable | What the sensor reports right now |
| Error | Target minus measured |
| Output | What you send to the motor |
| Gain | The number you multiply the error by |

Everything in the rest of this lesson is a different answer to one question: given the error, what output should I send?'''
            },
            {
                'title': 'Proportional Control',
                'content': '''# The P in PID

The simplest useful answer is: **make the correction proportional to the error**. Far away, push hard; close, ease off. In code that is a single multiplication by a constant called `KP` — the proportional gain — written `output = KP * error`.

That one line is proportional control, and it is genuinely most of what a competition robot needs.

## A Complete Example

```python
KP = 0.25
TARGET_MM = 300

def clamp(value, low, high):
    if value < low:
        return low
    if value > high:
        return high
    return value

measured_mm = 900

for _ in range(5):
    error = measured_mm - TARGET_MM        # positive means too far away
    power = clamp(KP * error, -100, 100)
    print("measured", measured_mm, "error", error, "power", power)
    measured_mm = measured_mm - power * 2  # simulated movement toward the wall
```

Trace the output. The robot starts 600 mm too far out, asks for 150 percent power, and gets clamped to 100. As it closes in, the requested power falls to 100, then 50, then 25, then 12.5 — the robot **decelerates on its own**, without a single extra line of code. That smooth approach is why proportional control feels so much better than a bang-bang `if` statement that only knows full speed and stop.

## Sign Convention

Notice this example uses `measured - target`, while the previous section used `target - measured`. Both are used in the real world; what matters is that the sign of your output drives the robot **toward** the target. If your robot races away from the line the instant you enable control, you have the sign backwards — negate the error or swap the motors, and never fix it by making `KP` negative and forgetting you did.

## Proportional Line Following

The same one-liner steers:

```python
KP = 0.6
BASE_SPEED = 40

def clamp(value, low, high):
    return max(low, min(high, value))

def motor_powers(left_sensor, right_sensor):
    error = left_sensor - right_sensor
    correction = KP * error
    left = clamp(BASE_SPEED + correction, -100, 100)
    right = clamp(BASE_SPEED - correction, -100, 100)
    return left, right

print(motor_powers(60, 40))   # (52.0, 28.0)
```

Both wheels start at the base speed; the correction is added to one and subtracted from the other, so the robot curves back toward the line by an amount that matches how far off it is. Perfectly centered means `error` is 0, `correction` is 0, and both wheels run at 40.'''
            },
            {
                'title': 'Why P Is Not Enough: Adding I and D',
                'content': '''# The Two Failure Modes of Pure P

Run proportional control long enough and you meet both of its weaknesses. They pull in opposite directions, which is exactly why tuning is a balancing act.

## Failure 1: Oscillation (KP too high)

A large `KP` produces a big correction, the robot overshoots the target, the error flips sign, the controller slams back the other way — and the robot wobbles across the line forever, or shakes so hard it climbs off it. The correction is too aggressive for how fast the system can actually respond, and the delay between commanding and moving turns the correction into a push in the wrong direction.

## Failure 2: Steady-State Error (KP too low)

With a small `KP` the robot glides in smoothly and then **stops short**. When the error is 8 mm, `0.25 * 8` asks for 2 percent power, which is not enough to overcome friction, so the robot sits there — forever — a little off target. That leftover gap is called **steady-state error**, and no amount of patience closes it, because P has already given up.

## The I Term: Fixing the Leftover

The **integral** term accumulates error over time. A small error that will not go away keeps adding up until the accumulated total is large enough to push through friction, and the robot finally arrives.

## The D Term: Damping the Overshoot

The **derivative** term looks at how fast the error is *changing*. If you are closing on the target quickly, D subtracts from the output — hitting the brakes before you arrive. It is what lets you raise `KP` for a snappy response without paying for it in oscillation.

## PID in Python

```python
KP = 0.5
KI = 0.05
KD = 0.2

def pid_step(error, integral, previous_error, dt):
    integral = integral + error * dt
    derivative = (error - previous_error) / dt
    output = KP * error + KI * integral + KD * derivative
    return output, integral, error

integral = 0.0
previous_error = 0.0
dt = 0.02   # seconds between loop passes

for error in [100.0, 80.0, 55.0, 30.0]:
    output, integral, previous_error = pid_step(error, integral, previous_error, dt)
    print(round(output, 1))
```

The function returns the new state alongside the output so the loop can carry it forward. Two things to notice:

- The **first** output is enormous, because `previous_error` starts at 0 and the derivative reads a jump from 0 to 100 in 0.02 s. Real code skips the D term on the first pass, or seeds `previous_error` with the first reading.
- `dt` must match reality. If you claim 0.02 s but your loop actually takes 0.05 s, both I and D are computed on a lie.

Most classroom robots never need the I term at all, and many do fine with P plus D. Add a term only when you can name the specific misbehavior it is fixing.'''
            },
            {
                'title': 'Tuning and Clamping the Output',
                'content': '''# Tuning: A Procedure, Not a Guessing Game

Gains cannot be calculated from first principles on a classroom robot — friction, battery sag, and wheel slip make sure of that. They are found experimentally, and the experiment has a standard order.

## The Procedure

1. **Zero everything.** Set `KI` and `KD` to 0. Tune P alone first.
2. **Raise KP until it oscillates.** Double it each run until the robot visibly wobbles around the target. Now you know the ceiling.
3. **Back off.** Cut `KP` to roughly half the oscillation value. The robot should approach briskly with at most a small overshoot.
4. **Add KD if it still overshoots.** Start small — around a tenth of `KP` — and raise it until the overshoot is damped. Too much D makes the robot sluggish and amplifies sensor noise, because D multiplies the *difference* between readings and noise is nothing but difference.
5. **Add KI only if the robot stops short.** Start very small. If the response starts to swing slowly and hunt, KI is too big.
6. **Change one gain at a time, and write down every value with the result.** A tuning log turns three hours of flailing into a table you can reason about — and it is exactly the kind of evidence an engineering notebook is for.

Retune whenever the robot changes weight, the surface changes, or the battery habits change. Gains are not universal constants.

## Clamping: Never Send an Illegal Command

Motor commands live on a fixed scale, typically -100 to 100 percent. A controller does not know that: multiply a 600 mm error by a gain of 0.25 and it will happily ask for 150. Clamp before you send.

```python
def clamp(value, low, high):
    return max(low, min(high, value))

print(clamp(150.0, -100, 100))   # 100
print(clamp(-260.0, -100, 100))  # -100
print(clamp(42.0, -100, 100))    # 42.0
```

Some platforms silently truncate an illegal value, some throw an error, and some do something worse. Clamping yourself makes the behavior yours.

## Integral Windup

Clamping the output creates a second problem. While the output is saturated at 100, the robot cannot correct any faster — but the integral keeps piling up error. By the time the robot reaches the target, the accumulated term is gigantic, and it drives a huge overshoot before it drains back down. That is **integral windup**, and the standard fix is to clamp the integral too.

```python
MAX_INTEGRAL = 200.0

def clamp(value, low, high):
    return max(low, min(high, value))

integral = 0.0
dt = 0.2

for error in [500.0, 500.0, 500.0, 500.0]:
    integral = clamp(integral + error * dt, -MAX_INTEGRAL, MAX_INTEGRAL)
    print(integral)
```

The running total climbs 100, 200, and then stays pinned at 200 no matter how long the error persists. The controller keeps its memory of the error without letting that memory take over the robot.'''
            }
        ])
        self._create_lesson_questions(lesson, [
            {
                'text': 'In a closed-loop controller, how is the error normally computed?',
                'choices': [
                    ('Target value minus the measured value', True),
                    ('Measured value multiplied by the gain', False),
                    ('The motor power sent on the previous pass', False),
                    ('The time elapsed since the loop started', False),
                ]
            },
            {
                'text': 'A robot using proportional control wobbles back and forth across the line instead of settling on it. Which change should you try first?',
                'choices': [
                    ('Lower KP, then add a small KD to damp the overshoot', True),
                    ('Raise KP so the corrections are stronger', False),
                    ('Remove the sensor reading from the loop', False),
                    ('Increase the base driving speed', False),
                ]
            },
            {
                'text': 'A proportional controller glides in and then stops 8 mm short of the target and stays there. What causes this, and which term fixes it?',
                'choices': [
                    ('Steady-state error: a small error produces too little power to overcome friction, and the integral term accumulates until it does', True),
                    ('Integral windup: the derivative term must be removed', False),
                    ('Oscillation: KP must be doubled to push through', False),
                    ('A sensor fault: the target must be moved 8 mm closer', False),
                ]
            },
            {
                'text': 'Why should a controller output be clamped to the motor valid range before it is sent?',
                'choices': [
                    ('A large error can produce a value outside the legal range, and clamping makes the resulting behavior predictable', True),
                    ('Clamping makes the robot accelerate faster', False),
                    ('Clamping converts the output from float to int', False),
                    ('Python cannot multiply numbers larger than 100', False),
                ]
            }
        ])

        self._create_unit4_quiz(unit)

    def _create_unit4_quiz(self, unit):
        quiz = self._quiz(
            unit, 'rob201-quiz-programming-robots-in-python', 0,
            title='Programming Robots in Python Quiz',
            description='Test your understanding of Python fundamentals, loops and functions, sensor code, and closed-loop control.',
            passing_score=70,
            points=20,
            max_attempts=3,
        )
        self._create_quiz_questions(quiz, [
            {
                'text': 'What does this program print?  total = 0, then "for i in range(4):" with the indented line "total = total + i", then print(total) at the left margin.',
                'choices': [
                    ('6, because i takes the values 0, 1, 2, 3', True),
                    ('10, because i takes the values 1, 2, 3, 4', False),
                    ('4, because the loop runs four times', False),
                    ('3, because range stops before 4', False),
                ]
            },
            {
                'text': 'This loop is broken:  distance_mm = front_distance_mm()  followed by  "while distance_mm > 200:"  whose only indented line is  drive(40).  What is wrong with it?',
                'choices': [
                    ('The sensor is never re-read inside the loop, so the condition never changes and the loop runs forever', True),
                    ('A while loop cannot call a function in its body', False),
                    ('The comparison should use = instead of >', False),
                    ('The loop needs a range() to know how many times to repeat', False),
                ]
            },
            {
                'text': 'Which statement about indentation in Python is correct?',
                'choices': [
                    ('Indentation determines which lines belong to a block, so changing it changes what the program does', True),
                    ('Indentation is cosmetic and Python ignores it', False),
                    ('Indentation is only required inside functions, not inside loops', False),
                    ('Python requires exactly one space of indentation per level', False),
                ]
            },
            {
                'text': 'A distance sensor produces occasional single garbage readings. Which technique keeps one bad sample from triggering an action?',
                'choices': [
                    ('Debouncing: require the same result on several consecutive passes before acting', True),
                    ('Increasing the polling rate so the bad reading is seen more often', False),
                    ('Comparing the reading with == instead of <', False),
                    ('Moving the threshold check outside the loop', False),
                ]
            },
            {
                'text': 'What is the main risk of open-loop control, such as "drive at 40 percent for 2 seconds to travel one meter"?',
                'choices': [
                    ('The program never measures the result, so battery level, surface, and friction silently change the distance travelled', True),
                    ('Open-loop code cannot use functions or loops', False),
                    ('Open-loop control requires more sensors than closed-loop control', False),
                    ('Open-loop control always overshoots by exactly the same amount', False),
                ]
            },
            {
                'text': 'A student writes  power = KP * error  with KP = 0.25 and an error of 600, then sends power straight to the motor. Why is this a problem?',
                'choices': [
                    ('It asks for 150 percent power, which is outside the valid motor range, so the output must be clamped first', True),
                    ('Multiplying a float by an int is not allowed in Python', False),
                    ('The error should have been multiplied by the measured value instead', False),
                    ('KP must always be greater than 1 for the robot to move', False),
                ]
            }
        ])

    # ================== UNIT 5: Artificial Intelligence & Autonomous Systems ==================
    def _create_unit5(self, course):
        unit = self._unit(course, 4, 'Artificial Intelligence & Autonomous Systems')

        # Lesson 1: What Artificial Intelligence Means in Robotics
        lesson = self._lesson(
            unit, 'rob201-what-ai-means-in-robotics', 0,
            title='What Artificial Intelligence Means in Robotics',
        )
        self._create_sections(lesson, [
            {
                'title': 'Overview',
                'content': '''# What Artificial Intelligence Means in Robotics

"AI-powered" is printed on everything from vacuum cleaners to welding cells, and most of the time it means something much narrower than the marketing suggests. In this lesson you will learn what artificial intelligence actually is inside a robotic system, how a learned system differs from a scripted one, and how to judge honestly whether AI is the right tool for a given job.

## Learning Objectives

By the end of this lesson, you will be able to:
- Define artificial intelligence as it is used in the robotics and automation industry
- Contrast a rule-based (scripted) robot with a system whose behavior is learned from data
- Describe levels of autonomy and identify where AI genuinely outperforms classic control
- Explain the ethical and safety responsibilities that come with deploying an autonomous system

> **TEKS alignment:** §127.750(c)(6) — the student analyzes technological systems, including the role of artificial intelligence in the robotic and automation industry.'''
            },
            {
                'title': 'What Artificial Intelligence Actually Means',
                'content': '''# What Artificial Intelligence Actually Means

**Artificial intelligence** is an umbrella term for software that performs tasks we normally associate with human judgment: recognizing objects, understanding speech, making decisions under uncertainty, planning a sequence of actions. That is a description of *what the software does*, not *how it works* — which is exactly why the term is so easy to abuse.

## The Nested Circles

It helps to picture three circles inside one another:

- **Artificial intelligence** — the whole field, including approaches with no learning at all. A chess program that searches millions of moves with hand-written rules is AI.
- **Machine learning** — the subset of AI where behavior is derived from data instead of written by a programmer. You supply examples; an algorithm fits a model to them.
- **Deep learning** — the subset of machine learning that uses large multi-layer neural networks. This is what powers modern image recognition and speech systems, and it is what most people mean when they say "AI" today.

## Narrow AI vs General AI

Every AI system deployed in industry today is **narrow AI**: it does one task within one domain. A model that sorts recyclables with 98% accuracy cannot read a shipping label, cannot explain its own reasoning, and has no concept of what a bottle *is*. It maps inputs to outputs within the range of situations it was trained on.

**General AI** — a single system with flexible, human-level competence across unfamiliar domains — does not exist. It is a research goal and a science-fiction premise, not a product you can buy. When you evaluate a vendor claim, the useful question is never "is it intelligent?" It is: *what exact task, under what exact conditions, at what measured accuracy?*

## Why the Distinction Matters on the Floor

Confusing narrow AI for general capability causes real failures. A team that assumes a defect-detection model "understands quality" will deploy it on a new product line and be shocked when accuracy collapses. A team that understands the model is a narrow statistical function will ask the right question first: *has it seen this product before?*'''
            },
            {
                'title': 'Scripted Rules vs Learned Behavior',
                'content': '''# Scripted Rules vs Learned Behavior

Almost every robot you have programmed so far is **rule-based**. You, the human, wrote the logic: if the distance sensor reads under 20 cm, stop. If the line sensor sees dark, steer left. The robot contains no knowledge you did not put there, and its behavior is fully determined by code you can read line by line.

A **learned system** works differently. Nobody writes the rule. Instead, engineers collect thousands of labeled examples and an algorithm adjusts internal numbers until the system reproduces the labels. The resulting behavior is real, but it lives in a table of millions of weights that no person can read as logic.

## Comparing the Two Approaches

| Property | Rule-based (scripted) | Learned (machine learning) |
|----------|----------------------|----------------------------|
| Where the behavior comes from | A programmer writes it | Fitted from labeled examples |
| Effort to build | Hours of coding | Weeks of data collection and labeling |
| Behavior on inputs it has never seen | Predictable — follows the written rule | Unpredictable — may fail silently |
| Can a human audit it? | Yes, read the code | Only indirectly, through testing |
| Best for | Well-defined, measurable conditions | Messy perception with no clean rule |

## A Concrete Comparison

Suppose a robot must reject cracked tiles on a conveyor. If every crack is a dark line on a light tile under fixed lighting, a five-line brightness threshold solves it — cheap, fast, and inspectable. But if tiles arrive in twenty colors, with printed patterns that also look like lines, no threshold works. There is no rule to write, because the distinction lives in a visual pattern humans recognize but cannot describe. That is the honest signal that machine learning may be worth its cost.

## The Default Should Be the Simple Thing

Industry practice is to reach for the simplest method that meets the specification. A learned model adds a data pipeline, a labeling budget, a retraining cycle, and a permanent uncertainty about edge cases. If a threshold, a PID loop, or a lookup table hits the accuracy target, that is the professional answer — not the boring one.'''
            },
            {
                'title': 'Levels of Autonomy and Where AI Pays Off',
                'content': '''# Levels of Autonomy and Where AI Pays Off

"Autonomous" is not a yes-or-no property. Engineers describe a spectrum, borrowed loosely from the automotive industry, that clarifies who is responsible at any moment.

## The Spectrum

| Level | Name | Who decides | Example |
|-------|------|-------------|---------|
| 0 | Manual | Human does everything | A hand-driven forklift |
| 1 | Assisted | Human drives, machine corrects | Collision-warning braking |
| 2 | Partial autonomy | Machine acts, human supervises continuously | Lane-keeping on a highway |
| 3 | Conditional autonomy | Machine acts within limits, human takes over on request | A warehouse robot that stops and calls for help |
| 4 | High autonomy | Machine handles all cases inside a defined area | A driverless shuttle on a fixed campus route |
| 5 | Full autonomy | Machine handles any condition, anywhere | Does not currently exist |

Notice that levels 3 and 4 are defined by **boundaries**, not by intelligence. A level 4 shuttle is not smarter than a level 2 car; it operates inside a mapped, controlled area where the designers can enumerate what might happen.

## Where AI Genuinely Helps

- **Visual inspection.** Detecting scratches, weld defects, or contamination on varied surfaces is a pattern-recognition problem with no clean rule. Learned models outperform threshold logic here by a wide margin.
- **Bin picking.** Parts dumped in a bin land in random poses, overlapping and occluded. A model that estimates a graspable pose from a depth image solves a problem that fixture-based automation cannot.
- **Predictive maintenance.** Vibration, current draw, and temperature histories contain early failure signatures too subtle for a fixed alarm threshold. A model trained on past failures can flag a bearing weeks ahead.
- **Speech and natural-language interfaces.** Letting a technician talk to a machine is only possible with learned language models.

## Where Classic Control Is Still Right

Anything with a measurable setpoint belongs to classic control. Holding a motor at 1,500 RPM, keeping an arm on a trajectory, regulating oven temperature — a PID loop does this better, faster, and with mathematical stability guarantees no neural network offers. Safety interlocks in particular are deliberately built from simple, verifiable logic: a light curtain must stop the machine every time, not 99.7% of the time.'''
            },
            {
                'title': 'Ethics, Safety, and the Human in the Loop',
                'content': '''# Ethics, Safety, and the Human in the Loop

An autonomous system makes decisions that affect people, so the people who build it inherit responsibilities. These are not abstract classroom questions — they show up in deployment reviews, in purchasing contracts, and in court.

## Bias Comes From Data

A model learns the patterns in the data it was shown, including the accidental ones. A defect detector trained only on parts from the day shift may fail on the night shift because the lighting differs. A face-recognition system trained mostly on one demographic performs measurably worse on others. Neither model is malicious; both are faithfully reproducing a skewed sample.

The engineering response is procedural, not clever: audit what is in the dataset, deliberately collect the underrepresented cases, and measure accuracy *separately* for each subgroup rather than reporting one overall number that hides the failure.

## Accountability Does Not Become Automatic

When an autonomous forklift injures someone, "the algorithm decided" is not an answer anyone accepts. Responsibility distributes across the people who specified the operating limits, trained and validated the model, installed the safety hardware, and authorized the deployment. Professional practice is to write those responsibilities down before deployment, along with the conditions under which the system must refuse to operate.

## Jobs Change More Often Than They Vanish

Automation genuinely eliminates specific tasks, and pretending otherwise is dishonest — repetitive material handling and manual inspection roles have shrunk. But the same deployments create demand for technicians, integrators, data labelers, and maintenance staff, and they change surviving jobs more than they delete them. The realistic risk is not mass unemployment; it is that displacement and creation land on *different people in different places*, which is why retraining programs are part of a serious automation plan.

## Keep a Human in the Loop Where It Counts

For safety-critical or irreversible decisions, a human should authorize the action or be able to stop it instantly:

- **Human in the loop** — the system proposes, a person approves each action
- **Human on the loop** — the system acts, a person monitors and can intervene
- **Human out of the loop** — no live oversight; appropriate only for low-stakes, well-bounded tasks

Emergency stops, light curtains, and speed limits are intentionally *outside* the AI. They are simple, testable, independently powered systems, because the last line of defense should never depend on a model being right.'''
            }
        ])
        self._create_lesson_questions(lesson, [
            {
                'text': 'A vendor claims their inspection system "understands quality." Which question best evaluates that claim like an engineer?',
                'choices': [
                    ('What exact task does it perform, under what conditions, and at what measured accuracy?', True),
                    ('How many layers does its neural network have?', False),
                    ('Does the company describe the product as artificial intelligence?', False),
                    ('How fast does the system boot up after a power cycle?', False),
                ]
            },
            {
                'text': 'A cell must hold a spindle at exactly 1,500 RPM under changing load. Which approach is the professionally correct choice?',
                'choices': [
                    ('A classic closed-loop controller such as PID, because the task has a measurable setpoint', True),
                    ('A deep neural network trained on recorded spindle video', False),
                    ('A large language model that reasons about the motor in text', False),
                    ('A machine learning model, because learned systems always outperform written rules', False),
                ]
            },
            {
                'text': 'A driverless shuttle operates without a driver, but only on one mapped campus loop. What best describes it?',
                'choices': [
                    ('High autonomy inside a defined operating area, not full autonomy everywhere', True),
                    ('Full autonomy, since no human touches the controls', False),
                    ('General artificial intelligence, since it handles a real environment', False),
                    ('Manual operation, since the route was chosen by humans', False),
                ]
            },
            {
                'text': 'Why are emergency stops and light curtains built from simple hard-wired logic rather than from the AI system itself?',
                'choices': [
                    ('The last line of defense must work every time and be independently verifiable, not depend on a model being right', True),
                    ('Safety hardware is too slow to be connected to software', False),
                    ('AI systems are legally forbidden from reading sensors', False),
                    ('Neural networks cannot process signals from switches', False),
                ]
            }
        ])

        # Lesson 2: Machine Learning Basics: Training vs Programming
        lesson = self._lesson(
            unit, 'rob201-machine-learning-basics-for-robots', 1,
            title='Machine Learning Basics: Training vs Programming',
        )
        self._create_sections(lesson, [
            {
                'title': 'Overview',
                'content': '''# Machine Learning Basics: Training vs Programming

When you program a robot, you write the rule. When you train a model, you supply examples and let an algorithm find the rule for you. That trade sounds like magic until you meet the bill: data collection, labeling, validation, and a system that cannot tell you why it decided anything. This lesson walks through how supervised learning actually works and where its limits are.

## Learning Objectives

By the end of this lesson, you will be able to:
- Distinguish programming a rule from training a model on labeled examples
- Identify the features and labels in a robotics machine learning problem
- Explain training, validation, and test splits and how they expose overfitting
- Describe what inference means on a robot and state the honest limits of a trained model

> **TEKS alignment:** §127.750(c)(8) — the student applies programming concepts to develop, test, and evaluate programs that control robotic and automated systems.'''
            },
            {
                'title': 'Writing a Rule vs Training a Model',
                'content': '''# Writing a Rule vs Training a Model

Traditional programming is a one-way street: you supply data *and* rules, and the computer produces answers. Machine learning reverses one arrow: you supply data *and* answers, and the computer produces the rule.

## The Same Task, Two Ways

Imagine sorting bolts into "long" and "short" using a measured length in millimeters. As a written rule it is trivial:

```python
def classify_bolt(length_mm):
    if length_mm >= 40.0:
        return "long"
    return "short"
```

You chose 40.0 because you knew the specification. Now suppose nobody knows the cutoff, but you have 500 bolts a technician already sorted. A learning algorithm can search for the threshold that misclassifies the fewest examples:

```python
def best_threshold(samples):
    # samples: list of (length_mm, label) pairs
    candidates = sorted({length for length, _ in samples})
    best_value, best_errors = candidates[0], len(samples)
    for value in candidates:
        errors = sum(
            1 for length, label in samples
            if (length >= value and label != "long")
            or (length < value and label != "short")
        )
        if errors < best_errors:
            best_value, best_errors = value, errors
    return best_value
```

That is a complete, if very small, machine learning algorithm. It has the two defining ingredients: a **model** with an adjustable parameter, and a **training procedure** that tunes the parameter to fit examples.

## What Scales Up and What Does Not

Real models replace one threshold with thousands or millions of parameters, and replace exhaustive search with gradient descent. What does not change is the shape of the process:

1. Collect examples that are representative of the real job
2. Label them correctly
3. Fit the model's parameters to reduce error on those examples
4. Measure performance on examples the model has never seen

## When to Reverse the Arrow

Reverse it when you cannot state the rule. If a person can explain the decision in one sentence, write that sentence as code — it will be faster, cheaper, and auditable. If the best a person can do is "I know it when I see it," you have a candidate for learning.'''
            },
            {
                'title': 'Features, Labels, and Supervised Learning',
                'content': '''# Features, Labels, and Supervised Learning

**Supervised learning** is the flavor of machine learning used in most robotics applications. Supervised means every training example carries a correct answer supplied by a human. The model is being corrected, example by example, toward those answers.

## The Vocabulary

- **Feature** — one measurable input the model sees. Length in millimeters, motor current in amps, the brightness of a single pixel.
- **Feature vector** — all features for one example, packed together as a list of numbers.
- **Label** — the correct answer for that example, supplied by a human or a trusted instrument.
- **Example (sample)** — one feature vector plus its label.
- **Dataset** — the whole collection of examples.

## Two Kinds of Answers

| Task type | The label is | Robotics example |
|-----------|--------------|------------------|
| Classification | A category | Is this weld good or defective? |
| Regression | A continuous number | How many hours until this bearing fails? |

## Building a Feature Vector

Suppose you want to predict whether a conveyor motor is about to jam. You could log four numbers every second:

```python
def features(current_a, temp_c, vibration_g, belt_speed_mps):
    return [current_a, temp_c, vibration_g, belt_speed_mps]

example = (features(4.2, 48.0, 0.31, 0.85), "normal")
```

The label "normal" came from a maintenance record. Collect months of these, including the runs that ended in a jam, and you have a supervised dataset.

## Labeling Is the Real Work

Newcomers assume the algorithm is the hard part. It is not — the algorithm is usually a few lines calling a library. The hard part is producing thousands of correctly labeled examples that cover the situations the robot will actually meet. Labeling is slow, it requires the domain expert whose time is expensive, and it is where most of the errors enter.

Two labeling failures cause the most damage:

- **Inconsistent labels** — two inspectors disagree about borderline defects, so the model learns contradictions and settles on an unpredictable middle.
- **Missing cases** — the dataset contains no examples of a condition that occurs monthly, so the model has no basis whatsoever for handling it.

Write down the labeling standard before anyone starts labeling, and have two people label the same subset to measure how often they agree.'''
            },
            {
                'title': 'Splitting Data, Overfitting, and Data Diversity',
                'content': '''# Splitting Data, Overfitting, and Data Diversity

A model that scores 100% on its own training examples has proven nothing. It may have found a real pattern, or it may have memorized the answer key. Telling those apart is the entire purpose of splitting your data.

## The Three Splits

| Split | Typical share | What it is for |
|-------|---------------|----------------|
| Training set | ~70% | Fitting the model's parameters |
| Validation set | ~15% | Comparing model choices and settings while developing |
| Test set | ~15% | One final, honest estimate of real-world accuracy |

The rule that protects you: **the test set is touched once**, at the very end. Every time you look at test results and then change your model, you leak a little information about the test set into your design, and the number stops being an honest prediction.

## Overfitting

**Overfitting** is when a model learns the noise in the training data instead of the underlying pattern. The classic signature is easy to spot:

- Training accuracy: 99%
- Validation accuracy: 71%

The gap says the model memorized specifics that do not generalize — the exact shadow in one photo, one technician's habit of placing parts at a slight angle. **Underfitting** is the opposite: both numbers are low, because the model is too simple to capture the real pattern at all.

Common responses to overfitting are to collect more data, simplify the model, or stop training earlier.

## Why Diversity Beats Volume

More data helps, but *more of the same* data helps far less than people expect. Ten thousand photos of the same part, in the same fixture, under the same lamp, teach the model one narrow situation very thoroughly.

A useful dataset spans the variation the robot will actually meet:

- Every shift, because lighting and operators change
- Every supplier and material lot, because color and finish drift
- Every fixture and camera the system will be deployed on
- The rare cases — the failures are precisely the examples you have fewest of and need most

## Class Imbalance

If 1 part in 500 is defective, a model that answers "good" every single time scores 99.8% accuracy and is completely useless. This is why practitioners report **precision** (of the parts flagged, how many were truly defective) and **recall** (of the truly defective parts, how many were flagged) instead of accuracy alone.'''
            },
            {
                'title': 'Inference on a Robot and the Limits of a Model',
                'content': '''# Inference on a Robot and the Limits of a Model

Training and using a model are two different activities with different costs, and confusing them causes bad hardware decisions.

## Training vs Inference

**Training** is the expensive, offline phase: thousands of passes over a dataset, often on powerful shared computers, taking hours or days. It happens once, or on a scheduled retraining cycle.

**Inference** is running a finished model on one new input to get one answer. On a robot, inference happens continuously — perhaps 30 times a second — and it must finish inside the control loop's time budget. A perception model that takes 200 ms to answer cannot support a robot that must react in 50 ms, no matter how accurate it is.

This is why deployed models are often shrunk after training, and why a model is usually stored as a file the robot simply loads:

```python
def running_average(values, window=5):
    # Smooth noisy per-frame model outputs before acting on them
    recent = values[-window:]
    return sum(recent) / len(recent)
```

Averaging several frames before acting is a standard, cheap defense against a model that flickers between answers on borderline inputs.

## The Limits You Must State Out Loud

- **A model is only as good as its data.** Outside the range of conditions it was trained on, its output is not a cautious guess — it is meaningless, and often delivered with high confidence.
- **Confidence is not correctness.** A softmax output of 0.98 means "this input resembles that training category," not "there is a 98% chance this is right."
- **It cannot explain itself.** You can see which pixels influenced a decision, but you cannot get a sentence of reasoning you could put in a report.
- **It drifts.** The world changes — new suppliers, worn fixtures, a repainted wall — and accuracy silently decays. Deployed models need monitoring and periodic retraining.
- **It is not deterministic across versions.** Retraining on new data can change behavior on inputs that used to work, so every retrained model must be revalidated before deployment.

## The Practical Consequence

Because of these limits, learned components in industrial systems are wrapped in conventional safeguards: sanity checks on the output range, a confidence floor below which the robot stops and asks a human, and independent safety hardware that does not consult the model at all.'''
            }
        ])
        self._create_lesson_questions(lesson, [
            {
                'text': 'What do you supply to a supervised machine learning algorithm that you do NOT supply to a traditional program?',
                'choices': [
                    ('The correct answers (labels) for many examples, so the algorithm can derive the rule', True),
                    ('A faster processor, which is what makes learning possible', False),
                    ('The rule itself, written more precisely than usual', False),
                    ('A random number generator to make the output unpredictable', False),
                ]
            },
            {
                'text': 'A defect model reaches 99% accuracy on its training set but 70% on the validation set. What is happening?',
                'choices': [
                    ('Overfitting — the model memorized details of the training data that do not generalize', True),
                    ('Underfitting — the model is too simple for the pattern', False),
                    ('The validation set was accidentally used during training', False),
                    ('The model is performing normally; a 29-point gap is expected', False),
                ]
            },
            {
                'text': 'Only 1 part in 500 on a line is defective. Why is a model reporting 99.8% accuracy not proof that it works?',
                'choices': [
                    ('A model that labels every part "good" scores 99.8% while catching zero defects, so precision and recall must be reported', True),
                    ('Accuracy above 99% always means the test set was too small', False),
                    ('Accuracy cannot be measured for classification problems', False),
                    ('The model must reach 100% before it can be deployed at all', False),
                ]
            },
            {
                'text': 'A perception model is 97% accurate but takes 200 ms per frame, while the robot control loop must react within 50 ms. What is the correct conclusion?',
                'choices': [
                    ('Inference is too slow for this loop, so the model must be shrunk or the design changed regardless of its accuracy', True),
                    ('Accuracy is what matters, so deploy it and accept the delay', False),
                    ('Retrain the model on more data, which will make inference faster', False),
                    ('Run the control loop at 200 ms so the safety response is also slower', False),
                ]
            }
        ])

        # Lesson 3: Computer Vision & Perception
        lesson = self._lesson(
            unit, 'rob201-computer-vision-and-perception', 2,
            title='Computer Vision & Perception',
        )
        self._create_sections(lesson, [
            {
                'title': 'Overview',
                'content': '''# Computer Vision & Perception

A camera does not send a robot a picture. It sends a grid of numbers, and every bit of "seeing" the robot does is arithmetic on that grid. This lesson takes you from raw pixels through classic techniques like thresholding and edge detection to modern detection models, and it is blunt about the factor that decides most vision projects: the lighting.

## Learning Objectives

By the end of this lesson, you will be able to:
- Explain how a camera image is represented as numbers, including resolution and color channels
- Apply thresholding, color blob detection, and edge detection conceptually to a vision task
- Distinguish classification, object detection, and segmentation and choose the right one
- Describe depth sensing methods and explain why lighting is the top practical failure cause

> **TEKS alignment:** §127.750(c)(6) — the student analyzes technological systems, including sensing and perception subsystems used in robotic and automated systems.'''
            },
            {
                'title': 'How a Camera Becomes Numbers',
                'content': '''# How a Camera Becomes Numbers

A digital camera sensor is a grid of tiny light buckets. Each bucket collects photons for a fraction of a second, and the electronics report how full it got as a number. That grid of numbers is the image — there is nothing else.

## Resolution and Pixels

A **pixel** is one cell in the grid. **Resolution** is the size of the grid: a 640x480 image has 307,200 pixels arranged in 480 rows of 640. Higher resolution captures finer detail and costs proportionally more memory and processing time, which is why robot vision often runs at deliberately low resolution. Doubling resolution in each direction quadruples the pixel count and roughly quadruples the processing time — a real constraint when the control loop runs 30 times a second.

## Grayscale and Color

In a **grayscale** image, each pixel is a single number, conventionally 0 for black through 255 for white. In an **RGB color** image, each pixel is three numbers — red, green, and blue intensity — so the image is really three stacked grids called **channels**.

| Representation | Numbers per pixel | 640x480 size | Good for |
|----------------|-------------------|--------------|----------|
| Grayscale | 1 | ~307 KB | Edges, shapes, speed |
| RGB color | 3 | ~921 KB | Sorting by color |
| HSV color | 3 | ~921 KB | Color detection under changing brightness |

**HSV** deserves attention. It stores hue (which color), saturation (how vivid), and value (how bright) separately. Because brightness is isolated in one channel, a red object stays roughly the same hue as lighting dims, while its RGB values all shift. Practitioners doing color detection convert to HSV for exactly this reason.

## Reading a Pixel

Treating an image as a list of rows makes the arithmetic obvious:

```python
def pixel_brightness(frame, row, col):
    # frame: list of rows, each row a list of (r, g, b) tuples
    r, g, b = frame[row][col]
    return 0.299 * r + 0.587 * g + 0.114 * b
```

Those weights are not arbitrary — human eyes are most sensitive to green and least to blue, so a perceptually correct grayscale conversion weights the channels unequally.

## What the Robot Does Not Get

The image contains no objects, no edges, and no depth. It contains brightness values. Every one of those higher-level ideas is something an algorithm must compute, and every computation can be wrong.'''
            },
            {
                'title': 'Classic Vision: Thresholding, Blobs, and Edges',
                'content': '''# Classic Vision: Thresholding, Blobs, and Edges

Before machine learning, and still today for a large share of industrial tasks, vision is done with straightforward arithmetic. These methods are fast, inspectable, and require no training data — which makes them the right first choice far more often than beginners expect.

## Thresholding

**Thresholding** turns a grayscale image into a black-and-white mask by comparing every pixel to a cutoff:

```python
def threshold(frame_rows, cutoff=128):
    return [
        [1 if value >= cutoff else 0 for value in row]
        for row in frame_rows
    ]
```

A dark part on a bright conveyor becomes a clean mask of 1s and 0s, and counting the 1s tells you the part's area in pixels. On a line-following robot the same operation separates tape from floor.

The weakness is right there in the constant: a fixed cutoff that works at noon fails at dusk. **Adaptive thresholding** computes a local cutoff for each region of the image instead, which survives uneven lighting much better.

## Color Blob Detection

To find a red part, convert to HSV and keep only pixels whose hue falls in the red range and whose saturation is high enough to be a real color rather than a gray shadow. Connected groups of surviving pixels are **blobs**. For each blob you can compute:

- **Area** — pixel count, used to reject specks of noise and to estimate distance
- **Centroid** — the average row and column, which is where the robot aims
- **Bounding box** — the rectangle enclosing it, used for a quick shape sanity check

A blob detector is often all a sorting robot needs, and it runs in milliseconds on hardware with no accelerator.

## Edge Detection

An **edge** is a place where brightness changes sharply — a boundary between object and background, or a crack in a surface. Edge detectors compare each pixel to its neighbors and report the size of the change, producing an outline image. Sobel and Canny are the two names you will meet most often.

Edges are useful because they survive lighting changes better than absolute brightness: dimming the lamp lowers every value, but the *difference* across a boundary stays. They feed directly into measuring part dimensions, finding straight lines to align to, and checking whether a hole is present.

## Why Classic Methods Still Win

When the scene is controlled — fixed camera, fixed lighting, known part — these methods are deterministic, take microseconds, need no labeled dataset, and fail in ways an engineer can debug by looking at the intermediate mask.'''
            },
            {
                'title': 'Classification, Detection, and Segmentation',
                'content': '''# Classification, Detection, and Segmentation

When the scene is too variable for thresholds, learned vision models take over. Three tasks are commonly confused, and picking the wrong one wastes an entire labeling budget.

## The Three Tasks

| Task | Question it answers | Output | Labeling cost |
|------|--------------------|--------|---------------|
| Classification | What is in this image? | One category for the whole image | Low — one tag per image |
| Object detection | What is here, and where? | Boxes plus a category and confidence for each | Medium — draw a box per object |
| Segmentation | Which exact pixels belong to what? | A category for every pixel | High — trace outlines |

## Choosing Correctly

- **Classification** suits a fixed camera looking at one part at a time: "good" or "defective," "bolt A" or "bolt B." If the part is always in the same place, you do not need to be told where it is.
- **Object detection** suits scenes with several items at unknown positions: locating every bottle on a conveyor, spotting people in a robot's work area. The box gives the robot a target to aim at.
- **Segmentation** suits tasks where the exact boundary matters: measuring how much of a surface is corroded, or separating touching parts that a box would lump together.

Each step up costs dramatically more labeling effort. Tracing outlines for 5,000 images is weeks of work; tagging 5,000 images takes days. Choose the cheapest task that answers your actual question.

## Confidence Scores and Thresholds

Detection models emit a **confidence** with every box. Setting where to accept a detection is a real engineering decision with a trade-off:

- A **low** threshold catches nearly every real object but also reports things that are not there (false positives)
- A **high** threshold reports only certain detections but misses borderline real ones (false negatives)

Which error is worse depends entirely on the job. For a robot that must not strike a person, a false positive means an unnecessary stop and a false negative means an injury — so you set the threshold low and accept nuisance stops. For a defect sorter, an over-eager threshold throws away good product, so you tune the other way.

## What Detection Does Not Give You

A bounding box tells you where something is *in the image*, in pixel coordinates. It does not tell you where the object is in the world, how far away it is, or which way it is facing. Turning pixels into a real-world position requires calibration and, usually, depth.'''
            },
            {
                'title': 'Depth, Pose, and Why Lighting Decides Everything',
                'content': '''# Depth, Pose, and Why Lighting Decides Everything

A single camera flattens the world. To pick something up, a robot needs the third dimension back, plus the object's orientation.

## Ways to Measure Depth

- **Stereo vision.** Two cameras a known distance apart see the same point at slightly different image positions. That shift, called disparity, gives distance by triangulation — the same trick your two eyes use. Stereo is cheap and passive, but it fails on blank surfaces where there is no texture to match between the two views.
- **Time of flight.** The sensor emits a light pulse and measures how long the reflection takes. It works on blank walls and in the dark, with resolution that is typically lower than a camera's.
- **Structured light.** A projector casts a known pattern of dots or stripes; distortions in the pattern reveal shape. Excellent at close range on matte objects, easily washed out by bright sunlight.
- **Lidar.** A scanning laser rangefinder that returns precise distances over a wide field. It is the workhorse for mobile-robot navigation, and it struggles with glass, mirrors, and heavy dust.

| Method | Works in darkness | Struggles with | Typical robotics use |
|--------|-------------------|----------------|----------------------|
| Stereo | No | Blank, untextured surfaces | General-purpose 3D vision |
| Time of flight | Yes | Reflective and absorbing surfaces | Short-range obstacle sensing |
| Structured light | Yes | Bright ambient light | Close-range bin picking |
| Lidar | Yes | Glass, mirrors, dust, rain | Mapping and navigation |

## Pose Estimation for Pick-and-Place

To grasp a part, a robot needs its **pose**: position (x, y, z) plus orientation (roll, pitch, yaw) — six numbers. A depth image plus a model of the part lets software search for the placement that best explains the measured points, then compute a graspable approach. This is what makes **bin picking** hard: parts overlap, occlude one another, and lie at angles that no fixture ever produces.

## Lighting Is the Number One Practical Problem

Ask an integrator why a vision system failed and you will hear about lighting far more often than algorithms. The classic failures:

- **Sunlight through a window** that moves across the cell during the day and disappears at night
- **Shadows** cast by the robot arm itself as it moves through the scene
- **Specular glare** on shiny metal, saturating pixels to pure white and erasing all detail
- **Flicker** from mains-powered lamps beating against the camera exposure, so brightness varies frame to frame

The fixes are physical, not computational: enclose the cell, add controlled diffuse lighting, use polarizing filters against glare, and choose a background color that contrasts with the parts. A team that spends a week on lighting usually saves a month on software — and a model trained under one lighting condition is, in effect, a model that only works under that lighting condition.'''
            }
        ])
        self._create_lesson_questions(lesson, [
            {
                'text': 'A color-sorting robot works in the morning but misses red parts in the afternoon as the room brightens. Which change addresses the cause most directly?',
                'choices': [
                    ('Detect color in HSV, where hue is separate from brightness, and control the cell lighting', True),
                    ('Raise the camera resolution so more pixels are available', False),
                    ('Switch from color detection to counting total image brightness', False),
                    ('Increase the robot speed so it passes the part sooner', False),
                ]
            },
            {
                'text': 'A robot must report how much of a painted panel is corroded, tracing the exact corroded area. Which vision task fits?',
                'choices': [
                    ('Segmentation, because a category is needed for every pixel', True),
                    ('Classification, because the panel gets one label', False),
                    ('Object detection, because a bounding box gives the exact area', False),
                    ('Edge detection alone, because corrosion boundaries are edges', False),
                ]
            },
            {
                'text': 'A stereo camera returns good depth for textured cardboard boxes but almost no depth for a blank white wall. Why?',
                'choices': [
                    ('Stereo works by matching the same visual feature in both images, and a blank surface offers nothing to match', True),
                    ('Stereo cameras cannot measure distances beyond one meter', False),
                    ('White surfaces absorb the laser pulse the stereo camera emits', False),
                    ('The wall is too far away for any depth sensor to work', False),
                ]
            },
            {
                'text': 'A vision-guided arm must never strike a person who walks into its cell. How should the person-detection confidence threshold be set?',
                'choices': [
                    ('Low, accepting nuisance stops, because a missed detection is far worse than a false alarm', True),
                    ('High, so the robot never stops unnecessarily and keeps throughput up', False),
                    ('Exactly 0.5, since that is the mathematically neutral value', False),
                    ('It does not matter, because the model reports certainty rather than confidence', False),
                ]
            }
        ])

        # Lesson 4: Autonomous Navigation & Path Planning
        lesson = self._lesson(
            unit, 'rob201-autonomous-navigation-and-path-planning', 3,
            title='Autonomous Navigation & Path Planning',
        )
        self._create_sections(lesson, [
            {
                'title': 'Overview',
                'content': '''# Autonomous Navigation & Path Planning

A robot that must cross a warehouse on its own has to answer three questions continuously: where am I, what does the world look like, and what should I do next? This lesson covers localization and mapping, the grid representation planners search, the path-planning algorithms that run on it, and how a planner and a controller divide the work.

## Learning Objectives

By the end of this lesson, you will be able to:
- Explain odometry drift and describe how SLAM builds a map while localizing in it
- Interpret an occupancy grid and explain why obstacles are inflated on it
- Trace how a grid search such as A* finds a low-cost path using cost and a heuristic
- Describe replanning and explain how a global planner and a local controller work together

> **TEKS alignment:** §127.750(c)(8) — the student applies programming concepts to develop, test, and evaluate programs that control robotic and automated systems.'''
            },
            {
                'title': 'Where Am I? Odometry, Drift, and SLAM',
                'content': '''# Where Am I? Odometry, Drift, and SLAM

**Localization** is the problem of knowing where the robot is. Everything else in navigation depends on it, because a perfect path is useless if the robot is wrong about its starting point.

## Odometry and Its Drift

**Odometry** estimates position by counting wheel rotations with encoders. Knowing wheel circumference and how far each wheel turned, you integrate motion step by step from a known start:

```python
import math


def update_pose(x, y, heading, left_mm, right_mm, track_mm):
    distance = (left_mm + right_mm) / 2.0
    turn = (right_mm - left_mm) / track_mm
    new_heading = heading + turn
    return (
        x + distance * math.cos(new_heading),
        y + distance * math.sin(new_heading),
        new_heading,
    )
```

Odometry is cheap, fast, and always available — and it is always wrong, increasingly so. Every source of error accumulates and never gets corrected:

- **Wheel slip** on a dusty or wet floor reports motion that did not happen
- **Tire wear and inflation** change the effective circumference by a percent or two
- **Encoder rounding** loses a fraction of a tick every reading
- **Heading error is the worst offender** — a one-degree error in heading becomes a large lateral error many meters later

This accumulation is called **drift**. Ten meters down a hallway, a robot trusting odometry alone may believe it is half a meter from where it truly stands, and it has no way to notice.

## Correcting With the World

Drift is fixed by looking at something external and stable. Compare what a lidar or camera currently sees against a map, and you can correct the estimate — recognizing a corner, a doorway, or a fiducial marker at a known location snaps the estimate back into place.

## SLAM

**SLAM** stands for Simultaneous Localization and Mapping, and it addresses an apparent chicken-and-egg problem: building a map requires knowing where you are, and knowing where you are requires a map. SLAM solves both at once. The robot drives, accumulates sensor scans, and continuously adjusts both its estimated path and the map so they agree with each other.

The moment that makes SLAM work is **loop closure**: the robot recognizes a place it visited before, notices the discrepancy between where drift says it is and where the earlier observation says it is, and redistributes that error backward across the whole path. A map that looked like a hallway drawn twice at a slight angle snaps into a single consistent corridor.'''
            },
            {
                'title': 'Occupancy Grids: A Map the Robot Can Search',
                'content': '''# Occupancy Grids: A Map the Robot Can Search

A planner cannot search a photograph. It needs a data structure with clear rules about where the robot may go, and the most common one in mobile robotics is the occupancy grid.

## What an Occupancy Grid Is

An **occupancy grid** divides the floor into equal square cells and stores one value per cell:

- **Free** — sensors have observed this space and found nothing
- **Occupied** — something was detected here
- **Unknown** — no sensor has seen it yet

Most real implementations store a probability rather than three states, because a single lidar return is weak evidence. Each new scan nudges the probability up or down, so a cell becomes confidently occupied only after repeated agreement — which filters out dust, a passing person, and stray reflections.

## Cell Size Is a Real Trade-Off

| Cell size | Memory for a 50m x 50m area | Effect |
|-----------|-----------------------------|--------|
| 5 cm | 1,000,000 cells | Fine detail; slow to search; noisy |
| 10 cm | 250,000 cells | Common compromise for indoor robots |
| 50 cm | 10,000 cells | Fast; may erase a doorway entirely |

Too coarse and a real gap disappears, so the planner reports no route through a door the robot could easily fit. Too fine and the search becomes slow and every sensor speck creates a phantom obstacle.

## Inflating Obstacles

An occupancy grid records where obstacles are, not where the *robot* fits. A planner treating the robot as a dimensionless point will happily route it through a gap narrower than the chassis.

The standard fix is **inflation**: grow every obstacle outward by the robot's radius plus a safety margin, producing a **costmap**. Now the robot can be planned as a point again, because the geometry is baked into the map. Many implementations also add a gradient — cells near obstacles are passable but expensive — so the planner prefers the middle of a corridor and only hugs a wall when there is no alternative.

## Static and Dynamic Layers

Practical systems keep two layers. The **static layer** is the map built by SLAM: walls, shelving, fixed machinery. The **dynamic layer** is rebuilt continuously from live sensors and holds the pallet someone just set down and the person walking past. Merging them gives the planner a current picture without discarding hard-won knowledge every time the view is blocked.'''
            },
            {
                'title': 'Planning a Path: Waypoints, Grid Search, and A*',
                'content': '''# Planning a Path: Waypoints, Grid Search, and A*

With a costmap in hand and a known starting cell, planning becomes a search problem: find a sequence of free cells from start to goal that keeps total cost low.

## Waypoints First

The simplest form of navigation is a list of **waypoints** — coordinates the robot visits in order. A human places them, and the robot drives from one to the next. This is genuinely useful for fixed routes on a factory floor, and it is how many competition autonomous routines are built. Its limitation is that the route is frozen: move a shelf and a human has to re-record the waypoints.

## Searching the Grid

Automatic planners explore outward from the start cell, cell by cell, tracking the cheapest known cost to reach each one.

**Breadth-first search** and **Dijkstra's algorithm** expand in every direction equally, like a puddle spreading. They are guaranteed to find the lowest-cost path, and they waste enormous effort exploring away from the goal.

**A\\*** adds one idea: an estimate of the remaining distance to the goal, called a **heuristic**. Each cell is ranked by

```python
def priority(cost_so_far, row, col, goal_row, goal_col):
    remaining = abs(goal_row - row) + abs(goal_col - col)
    return cost_so_far + remaining
```

The search always expands the most promising cell next, so it stretches toward the goal instead of spreading uniformly. As long as the heuristic never *overestimates* the true remaining distance, A* is still guaranteed to return the lowest-cost path — it simply gets there after examining far fewer cells.

| Algorithm | Uses cost so far | Uses goal estimate | Finds cheapest path | Cells explored |
|-----------|------------------|--------------------|--------------------|----------------|
| Breadth-first | No (counts steps) | No | Only if all steps cost the same | Very many |
| Dijkstra | Yes | No | Yes | Many |
| A* | Yes | Yes | Yes, with an admissible heuristic | Fewest |

## Cost Is Not Only Distance

Because the costmap holds a value per cell, "cheapest" can mean more than "shortest." Adding cost near obstacles buys clearance; adding cost to a ramp or a rough surface teaches the planner to prefer smooth floor; adding cost to a busy aisle routes the robot around foot traffic. Tuning these weights is much of the practical work of getting a navigation stack to behave sensibly.'''
            },
            {
                'title': 'Reacting to a Changing World: Planner and Controller',
                'content': '''# Reacting to a Changing World: Planner and Controller

A path computed thirty seconds ago describes a warehouse that no longer exists. Real navigation systems therefore split the job in two, running at very different rates.

## The Two-Layer Architecture

| Layer | Also called | Sees | Runs at | Job |
|-------|-------------|------|---------|-----|
| Global planner | Path planner | The whole static map | Every few seconds, or on demand | Find a complete route to the goal |
| Local planner | Controller | A few meters of live sensor data | 10-50 times per second | Follow the route while dodging what appears |

The global planner answers "which way around the building." The local controller answers "what wheel speeds, right now." Neither can do the other's job: the global planner is too slow to react to a person stepping out, and the local controller, seeing only a few meters, would happily drive into a dead-end room.

## Obstacle Avoidance Behaviors

Local controllers use reactive strategies layered from simple to sophisticated:

- **Stop and wait.** The safest response to something directly ahead, and correct when the obstacle is a person who will move on.
- **Slow down near obstacles.** Speed scaled by clearance reduces both risk and the severity of any contact.
- **Steer around.** Generate several candidate short trajectories, score each for collision risk, progress toward the path, and smoothness, then execute the winner for one cycle and repeat.
- **Back up and retry.** For a robot wedged in a corner where no forward motion scores well.

Purely reactive avoidance has a well-known failure: the robot slides along an obstacle, gets trapped in a concave pocket, and oscillates. This is precisely why the global plan exists — it supplies the direction that reactive rules cannot infer.

## Replanning

When the local controller cannot make progress — the corridor is blocked by a pallet, not a passerby — the system **replans**. The blockage is written into the costmap, and the global planner runs again from the robot's current pose. The result may be a long detour, and it may be that no path exists at all, in which case the correct behavior is to stop and report rather than to keep nudging at a wall.

Well-behaved systems have an escalation ladder: retry locally, then replan globally, then wait a bounded time in case the obstacle is temporary, then call for human help. Silently retrying forever is a bug, not patience — a robot that has been "navigating" for twenty minutes in one aisle should have raised its hand nineteen minutes ago.'''
            }
        ])
        self._create_lesson_questions(lesson, [
            {
                'text': 'A warehouse robot using only wheel encoders believes it is at the loading dock, but it is actually half a meter off after a long run. What is the underlying cause?',
                'choices': [
                    ('Odometry drift — small wheel-slip and heading errors accumulate with no external correction', True),
                    ('The encoders have failed and are reporting no counts at all', False),
                    ('The goal coordinates were entered in the wrong units', False),
                    ('The robot drove faster than its maximum rated speed', False),
                ]
            },
            {
                'text': 'Why do navigation systems inflate obstacles on the costmap by the robot radius plus a margin?',
                'choices': [
                    ('So the planner can treat the robot as a point and still never route it through a gap narrower than the chassis', True),
                    ('To reduce the memory the occupancy grid needs', False),
                    ('To make the map look clearer to a human operator', False),
                    ('Because lidar always underestimates the size of obstacles', False),
                ]
            },
            {
                'text': 'A* usually examines far fewer cells than Dijkstra while still returning the cheapest path. What makes that possible?',
                'choices': [
                    ('A heuristic estimate of the remaining distance that never overestimates, so the search expands toward the goal first', True),
                    ('It skips cells at random to save time, which is why it runs faster', False),
                    ('It ignores the cost of cells already traveled', False),
                    ('It searches the map backward from the goal only', False),
                ]
            },
            {
                'text': 'A robot on a planned route meets a pallet that permanently blocks the aisle. What should a well-designed navigation system do?',
                'choices': [
                    ('Add the blockage to the costmap and replan globally, escalating to a human if no route exists', True),
                    ('Keep nudging forward until the obstacle is pushed out of the way', False),
                    ('Delete the global map and rebuild it from scratch before moving', False),
                    ('Switch off obstacle avoidance so the original path can be followed', False),
                ]
            }
        ])

        self._create_unit5_quiz(unit)

    def _create_unit5_quiz(self, unit):
        quiz = self._quiz(
            unit, 'rob201-quiz-ai-and-autonomous-systems', 0,
            title='Artificial Intelligence & Autonomous Systems Quiz',
            description=(
                'Test your understanding of what AI means in robotics, machine '
                'learning fundamentals, computer vision, and autonomous navigation.'
            ),
            passing_score=70,
            points=20,
            max_attempts=3,
        )
        self._create_quiz_questions(quiz, [
            {
                'text': 'A conveyor must reject tiles that are darker than a fixed brightness under controlled lighting. Which solution should an engineer choose first?',
                'choices': [
                    ('A simple brightness threshold, because it meets the specification and is fast and auditable', True),
                    ('A deep learning model, because learned systems are more modern', False),
                    ('A SLAM system, because it builds a map of the conveyor', False),
                    ('A general artificial intelligence, because the task involves judgment', False),
                ]
            },
            {
                'text': 'A bin-picking model works all through day shift and starts failing on night shift. What is the most likely cause?',
                'choices': [
                    ('The training data came from day-shift lighting only, so the night-shift images fall outside what the model has seen', True),
                    ('The model file becomes corrupted when the robot runs for many hours', False),
                    ('Neural networks require sunlight to operate correctly', False),
                    ('The robot motors lose torque at night, changing the grasp', False),
                ]
            },
            {
                'text': 'Which situation is the honest signal that machine learning may be worth its cost instead of a written rule?',
                'choices': [
                    ('Experts can recognize the correct answer reliably but cannot state a rule that produces it', True),
                    ('The task has a clear numeric setpoint that must be held steady', False),
                    ('The team wants to describe the product as AI-powered', False),
                    ('Only fifteen labeled examples are available in total', False),
                ]
            },
            {
                'text': 'A detection model reports a person in the robot cell with confidence 0.98. What does that number actually mean?',
                'choices': [
                    ('The input strongly resembles the training examples of that category, which is not the same as a 98% chance of being correct', True),
                    ('There is exactly a 98% probability that a person is present', False),
                    ('The model has verified the detection against a second sensor', False),
                    ('The model is 98% finished processing the current frame', False),
                ]
            },
            {
                'text': 'Why do navigation stacks run a global planner every few seconds and a local controller many times per second?',
                'choices': [
                    ('The global planner finds a route across the whole map, while the local controller reacts to obstacles that appear in real time', True),
                    ('The two layers run the same algorithm at different speeds as a redundancy check', False),
                    ('The global planner handles motor currents and the local controller handles the map', False),
                    ('Running two planners is required to keep encoder counts synchronized', False),
                ]
            },
            {
                'text': 'A team is deploying an autonomous mobile robot in an aisle shared with workers. Which practice reflects professional responsibility for an autonomous system?',
                'choices': [
                    ('Independent safety hardware that stops the robot without consulting the model, plus written operating limits and named accountability', True),
                    ('Relying on the perception model alone, since it scored highest on the test set', False),
                    ('Documenting responsibility only after the first incident occurs', False),
                    ('Removing the emergency stop so the robot is never interrupted mid-task', False),
                ]
            }
        ])

    # ================== UNIT 6: Design, Project Management & Production Capstone ==================
    def _create_unit6(self, course):
        unit = self._unit(course, 5, 'Design, Project Management & Production Capstone')

        # Lesson 1: The Design Process for a Real Client
        lesson = self._lesson(
            unit, 'rob201-design-process-for-a-real-client', 0, title='The Design Process for a Real Client',
        )
        self._create_sections(lesson, [
            {
                'title': 'Overview',
                'content': '''# The Design Process for a Real Client

In Robotics 1 you ran the design cycle on problems a teacher handed you, already tidy. Real engineering starts messier: a client describes what they want in their own words, contradicts themselves twice, and forgets to mention the budget. This lesson is about turning that conversation into measurable requirements, acceptance criteria, and a defensible design choice.

## Learning Objectives

By the end of this lesson, you will be able to:
- Elicit requirements from a client interview and separate needs from wants
- Write measurable design requirements paired with verifiable acceptance criteria
- Classify budget, schedule, safety, and space limits as constraints on the design envelope
- Run a weighted trade study and defend the result at a formal design review

> **TEKS alignment:** §127.750(c)(10) — apply engineering design methodologies to develop, evaluate, and refine robotic solutions.'''
            },
            {
                'title': 'Eliciting Requirements from a Client',
                'content': '''# Eliciting Requirements from a Client

A client is anyone who will live with the result: a warehouse supervisor, a science teacher, a hospital lab manager, or the makerspace coordinator down the hall. They are experts in their problem and usually not experts in robots. Your first job is translation.

## The Interview

Clients almost never open with a requirement. They open with a story: "Every afternoon two of my students spend half an hour sorting returned parts into the wrong bins, and then I re-sort them." Buried in that sentence are a time budget, an error rate, and a hint that accuracy matters more than speed.

Techniques that pull the real information out:

- **Ask about the current process first.** How is the job done today, step by step, and where does it hurt? You cannot improve a process you have not watched.
- **Ask for numbers.** "How many parts per day?" "How long does one cycle take now?" "What error rate would you accept?" Vague answers become requirements only after they become numbers.
- **Ask about the exceptions.** "What happens when a part is damaged?" Edge cases sink more student projects than main cases do.
- **Play back what you heard.** "So the robot must sort at least 40 parts an hour with no more than one misplacement per 40 — is that right?" Misunderstandings are cheap to fix in a conversation and expensive to fix in a build.

## Needs Versus Wants

Not every statement a client makes carries the same weight. Sort them before you design:

| Category | Meaning | Example from the Interview |
|----------|---------|----------------------------|
| Must have | The project fails without it | Sorts parts into the correct bin |
| Should have | Important, but the project survives without it | Runs unattended for a full class period |
| Could have | Nice if it is free | Displays a running count on a screen |
| Will not have | Explicitly out of scope this round | Reads printed part numbers |

Writing that last row down is as valuable as the first. **Scope creep** — the slow drift of new features into a fixed schedule — is the most common reason student capstones miss their deadline, and a signed "will not have" list is the cheapest defense against it.

Finish the interview by sending the client a written summary and asking them to confirm it. That document is the foundation everything else in this unit rests on.'''
            },
            {
                'title': 'Measurable Requirements and Acceptance Criteria',
                'content': '''# Measurable Requirements and Acceptance Criteria

A requirement that cannot be tested is a wish. "The robot should be fast and reliable" cannot be argued about productively, because two reasonable people will disagree forever about what it means.

## Anatomy of a Good Requirement

Every requirement gets an ID, a single testable statement, and a verification method. The verification method is the part beginners skip, and it is what turns a requirement into something you can actually sign off.

| ID | Requirement | Acceptance Criterion | Verification |
|----|-------------|----------------------|--------------|
| R-01 | The robot shall move a part from the intake zone to the correct bin | 30 of 30 parts land in the specified bin | Test, 30 trials |
| R-02 | The robot shall complete one sort cycle within 8 seconds | Mean cycle time under 8.0 s across 30 trials | Test, timed |
| R-03 | The robot shall detect and reject a damaged part | 10 of 10 seeded damaged parts diverted to the reject bin | Test, seeded defects |
| R-04 | The robot shall operate with no exposed pinch points above 5 N | Guarded per safety checklist | Inspection |
| R-05 | The delivered bill of materials shall total no more than 800 USD | BOM total, tax and shipping included | Analysis |

Note the vocabulary. **Shall** marks a binding requirement; **should** marks a goal. Standards bodies and contracts use this distinction, and adopting it early stops your team from arguing about which lines are optional the week before the deadline.

## The Four Verification Methods

- **Inspection** — look at it. Used for guards, labels, finishes.
- **Demonstration** — operate it and observe the outcome, no instruments required.
- **Test** — run a defined procedure and record data against a numeric threshold.
- **Analysis** — calculate or model the answer, used when testing is impractical (a battery life figure, a total cost, a torque margin).

## Traceability

Every requirement should trace back to something the client said, and forward to a test case that proves it. Keep a simple two-column trace table in your notebook. When a design review asks "why does the robot have a second sensor?", the answer is not "we thought it was cool" — it is "R-03, damaged-part rejection, verified by test case TC-07." That chain is what separates an engineered product from a class project.'''
            },
            {
                'title': 'Constraints and the Design Envelope',
                'content': '''# Constraints and the Design Envelope

Requirements describe what the solution must do. **Constraints** describe the box it must fit inside. Together they define the design envelope: the space of solutions that are even allowed to compete.

## The Four Constraints That Bind Every Real Project

- **Budget.** A hard ceiling on money. Note that budget constraints apply to the total delivered cost — parts, shipping, sales tax, and a contingency reserve — not just the sticker price of the parts.
- **Schedule.** A hard date. A design that would be excellent in fourteen weeks is worthless in a nine-week term. Schedule is the constraint students respect the least and regret the most.
- **Safety and regulation.** Guards over pinch points, secured batteries, emergency stop reachable from outside the work envelope, eye protection during machining. Safety limits are never traded away for performance.
- **Space and interface.** The robot must fit the client's actual table, doorway, power outlet, and network. Measure the real space; do not trust a remembered number.

## The Triple Constraint

Scope, schedule, and cost are linked. Fix any two and the third is determined:

| If the client adds scope and holds the date | Cost must rise, or quality falls |
|---------------------------------------------|----------------------------------|
| If the budget is cut and scope is held | The schedule must stretch |
| If the date moves in and cost is fixed | Scope must be cut |

There is no fourth option where all three improve at once. Saying this out loud to a client, politely and with numbers, is one of the most professional things an engineer does. "We can add the counter display, and that pushes delivery from week 9 to week 11 — which would you prefer?" is a much better sentence than a silent yes followed by a missed deadline.

## Turning Constraints into a Filter

Before any trade study, run each concept through the constraints as a pass/fail gate. A concept that needs a 1200 USD sensor in an 800 USD project does not score poorly — it is disqualified and never enters the matrix at all. Filtering first keeps the team from falling in love with an illegal design, which is a surprisingly hard feeling to reverse once it takes hold.'''
            },
            {
                'title': 'Trade Studies and Design Reviews',
                'content': '''# Trade Studies and Design Reviews

A **trade study** is a documented comparison of concepts against weighted criteria. You met the decision matrix in Robotics 1; the second-year version adds two things professionals insist on: sensitivity checking and a formal review.

## A Weighted Trade Study

Three concepts for the sorting mechanism, scored 1 (poor) to 5 (excellent):

| Concept | Accuracy (x5) | Cycle Time (x3) | Build Risk (x2) | Cost (x2) | Total |
|---------|---------------|-----------------|-----------------|-----------|-------|
| Two-axis gripper arm | 5 (25) | 3 (9) | 2 (4) | 3 (6) | **44** |
| Tilting chute with gate | 3 (15) | 5 (15) | 5 (10) | 5 (10) | **50** |
| Conveyor with push arm | 4 (20) | 4 (12) | 3 (6) | 2 (4) | **42** |

The chute wins on a 50-44 score, driven by low build risk and low cost.

## Sensitivity: Would a Small Change Flip the Answer?

Now stress the result. Accuracy carries the heaviest weight, and the client called accuracy the whole reason for the project. If accuracy is re-weighted from x5 to x7, the arm gains 10 points and the chute gains 6 — 54 for the arm against 56 for the chute. Still the chute, but barely. When a result flips or nearly flips under a plausible weight change, the honest conclusion is **not** "the chute wins." It is "these two are within the noise, so prototype both and let test data decide." A trade study that always confirms the team favorite is a trade study nobody actually ran.

## Design Reviews

Industry gates a project at fixed points, and each gate has an audience with the authority to say stop:

| Review | When | Question It Answers |
|--------|------|---------------------|
| Requirements review | After the client interview | Are we solving the right problem, measurably? |
| Preliminary design review | After the trade study | Is the chosen concept feasible within the constraints? |
| Critical design review | Before production begins | Are the drawings, BOM, and test plan complete enough to build from? |
| Test readiness review | Before formal testing | Is the test plan defined, with pass/fail criteria fixed in advance? |

Two rules make reviews useful rather than ceremonial. First, **send materials in advance** so reviewers arrive having read them. Second, every action item leaves the room with an owner and a date; "someone should look at the gripper" is not an action item, and "Maya re-tests the gripper by Friday" is.'''
            }
        ])
        self._create_lesson_questions(lesson, [
            {
                'text': 'A client says the robot "needs to be accurate." What should the design team do with that statement before it becomes a requirement?',
                'choices': [
                    ('Ask follow-up questions until it becomes a number with a verification method, such as no more than one misplacement per 40 parts, verified by a 30-trial test', True),
                    ('Record it word for word, since the client is the authority on the requirement', False),
                    ('Replace it with a mechanism choice, such as "the robot shall use a two-axis gripper arm"', False),
                    ('Move it to the "will not have" list because it cannot be measured', False),
                ]
            },
            {
                'text': 'Two weeks before delivery, a client asks to add a live part-count display that was on the original "could have" list. The date and budget are fixed. What is the professional response?',
                'choices': [
                    ('Explain the triple constraint and offer a choice: add the display and move the date, or cut something else of equal size to make room', True),
                    ('Agree to add it, since a good team absorbs late requests without changing the plan', False),
                    ('Refuse to discuss it, because the "could have" list was signed and is now closed forever', False),
                    ('Add it quietly and skip formal testing to recover the schedule', False),
                ]
            },
            {
                'text': 'A concept requires a sensor that costs more than the entire project budget. How should it be handled in the trade study?',
                'choices': [
                    ('Filter it out before scoring, because a violated constraint disqualifies a concept rather than lowering its score', True),
                    ('Score it a 1 on the cost criterion and let the weighted total decide', False),
                    ('Score it normally but double the weight of cost to compensate', False),
                    ('Keep it in as the baseline so the other concepts have something to beat', False),
                ]
            },
            {
                'text': 'In a trade study, raising the weight on the top criterion from x5 to x7 changes a 50-44 result into a 56-54 result. What is the correct engineering conclusion?',
                'choices': [
                    ('The two concepts are too close to separate on paper, so both should be prototyped and decided by test data', True),
                    ('The original winner is confirmed, because it won under both weightings', False),
                    ('The weights were chosen incorrectly and should be adjusted until one concept wins clearly', False),
                    ('Trade studies are unreliable and the team should choose by vote instead', False),
                ]
            }
        ])

        # Lesson 2: Scheduling, Budget & Bill of Materials
        lesson = self._lesson(
            unit, 'rob201-scheduling-budget-and-bill-of-materials', 1, title='Scheduling, Budget & Bill of Materials',
        )
        self._create_sections(lesson, [
            {
                'title': 'Overview',
                'content': '''# Scheduling, Budget & Bill of Materials

Most capstone projects fail on the calendar, not on the engineering. This lesson gives you the three artifacts professional teams use to keep that from happening: a work breakdown structure that turns a vague project into countable tasks, a schedule with a critical path so you know which delays actually matter, and a bill of materials that proves the design fits the budget.

## Learning Objectives

By the end of this lesson, you will be able to:
- Decompose a project into a work breakdown structure with task dependencies
- Compute a critical path and identify which tasks carry float
- Build a bill of materials with quantities, unit costs, extended costs, and contingency
- Track progress against a baseline plan and choose a recovery action when it slips

> **TEKS alignment:** §127.750(c)(4) — demonstrate project management skills, including scheduling, budgeting, and allocating resources to complete a robotics project.'''
            },
            {
                'title': 'Work Breakdown Structure and Dependencies',
                'content': '''# Work Breakdown Structure and Dependencies

You cannot schedule "build the robot." You can schedule "cut and drill the chassis rails." The **work breakdown structure (WBS)** is the decomposition that gets you from one to the other.

## Decomposing the Work

Break the project down until every task at the bottom satisfies three tests:

- **One owner.** If two people are equally responsible, nobody is.
- **A duration you can estimate.** A good rule of thumb: no task longer than one week and no shorter than half a day. Longer tasks hide their own delays; shorter ones drown the schedule in bookkeeping.
- **A visible finish.** "Chassis rails cut to length and deburred" is checkable. "Work on chassis" is not.

The WBS is organized by **deliverable**, not by person. Nest it: 1.0 Chassis, 1.1 Rails, 1.2 Drive mounts, 1.3 Assembly. That numbering becomes the vocabulary the whole team uses for the rest of the project, and it maps directly onto your bill of materials later.

## Dependencies

A dependency says one task cannot start until another finishes. Most are **finish-to-start**: you cannot mount the motors until the rails are drilled. Two questions expose fake dependencies:

- Is this a real physical or logical constraint, or just a habit of working in that order?
- Could these two tasks run in parallel if a second person picked one up?

Fake dependencies are expensive. Every one you remove shortens the schedule for free.

## The Capstone Task List

| ID | Task | Duration | Depends On |
|----|------|----------|------------|
| A | Client interview and requirements | 3 days | — |
| B | Concept sketches and trade study | 4 days | A |
| C | Chassis and mechanism model | 5 days | B |
| D | Drive and sensor programming | 6 days | B |
| E | Gripper prototype and fit testing | 4 days | C |
| F | Integration in the simulator | 3 days | D, E |
| G | Formal test runs and data collection | 4 days | F |
| H | Bill of materials and cost report | 2 days | B |
| I | Presentation and handoff package | 3 days | G, H |

Nine tasks, three parallel branches after B. In the next section you will find out which of those branches actually controls the delivery date.'''
            },
            {
                'title': 'The Critical Path and the Gantt Chart',
                'content': '''# The Critical Path and the Gantt Chart

Walk the task list forward, day by day, and each task gets an earliest finish. The longest chain from start to end is the **critical path**, and its length is the shortest possible project duration.

## Walking the Network Forward

| Task | Earliest Start | Duration | Earliest Finish | Float |
|------|----------------|----------|-----------------|-------|
| A | day 0 | 3 | day 3 | 0 |
| B | day 3 | 4 | day 7 | 0 |
| C | day 7 | 5 | day 12 | 0 |
| D | day 7 | 6 | day 13 | 3 |
| E | day 12 | 4 | day 16 | 0 |
| F | day 16 | 3 | day 19 | 0 |
| G | day 19 | 4 | day 23 | 0 |
| H | day 7 | 2 | day 9 | 14 |
| I | day 23 | 3 | day 26 | 0 |

Task F waits on both D (day 13) and E (day 16), so it starts at day 16 — the later of the two. That is the whole trick of forward-pass scheduling: a merge point takes the maximum, never the average.

**Critical path: A - B - C - E - F - G - I, 26 working days.** Every task on it has zero float.

## Float Is a Budget for Delay

**Float** (or slack) is how long a task can slip before it starts pushing the end date. Task D carries 3 days of float and task H carries 14. The consequences are precise:

- A one-day slip on **D** costs nothing. The end date stays at day 26.
- A five-day slip on **D** consumes its 3 days of float and pushes the project 2 days, to day 28. Note that D has now become critical.
- A one-day slip on **E**, which has zero float, moves the end date to day 27 immediately.

This is why "how far behind are we?" is the wrong question. The right question is "which task is behind, and does it have float?"

## Reading a Gantt Chart

A Gantt chart draws each task as a horizontal bar on a calendar, with arrows for dependencies and diamonds for milestones. A **milestone** is a zero-duration checkpoint — "requirements signed," "critical design review passed," "first full test run complete." Milestones are how a client tracks a project without reading nine task bars.

Draw the critical path in a contrasting color. On a real schedule that colored chain is the only thing a project manager watches every single day.'''
            },
            {
                'title': 'Building the Bill of Materials',
                'content': '''# Building the Bill of Materials

A **bill of materials (BOM)** is the complete parts list required to build one unit of your design: every item, how many, what each costs, and what the line costs in total. It is the document a client uses to decide whether your design is affordable, and the document a technician uses to actually order parts.

## Anatomy of a Line Item

Each line carries a line number, a specific description (a part a buyer could actually order, not "a motor"), a quantity, a unit cost, and an **extended cost** — quantity times unit cost. Extended cost is where arithmetic mistakes hide, so total the column twice.

| # | Part Description | Qty | Unit Cost | Extended |
|---|------------------|-----|-----------|----------|
| 1 | Aluminum C-channel, 1x2x35 hole | 4 | 12.50 | 50.00 |
| 2 | 11 W smart motor with encoder | 4 | 39.99 | 159.96 |
| 3 | Omni wheel, 4 in. | 4 | 11.25 | 45.00 |
| 4 | Robot controller / brain | 1 | 249.99 | 249.99 |
| 5 | Battery, 7.2 V 1300 mAh | 2 | 34.99 | 69.98 |
| 6 | Optical distance sensor | 2 | 19.99 | 39.98 |
| 7 | Shaft collars, 1/8 in., pack of 20 | 1 | 9.99 | 9.99 |
| 8 | Hardware kit, 8-32 screws and nylocks | 1 | 14.50 | 14.50 |
| 9 | Gripper jaw, 3D printed PLA, 45 g | 2 | 2.10 | 4.20 |
| 10 | Wire management, ties and sleeving | 1 | 6.00 | 6.00 |

## From Subtotal to Delivered Cost

| Line | Amount (USD) |
|------|--------------|
| Parts subtotal | 649.60 |
| Sales tax at 8.25% | 53.59 |
| Shipping | 24.00 |
| Contingency at 10% of subtotal | 64.96 |
| **Total delivered cost** | **792.15** |
| Budget constraint | 800.00 |
| Remaining margin | 7.85 |

## What the Bottom of That Table Is Telling You

The design fits the 800 USD constraint by 7.85 USD — under one percent. A margin that thin is a warning, not a victory: one price increase, one broken gripper, or one forgotten 12 USD sensor cable blows the budget.

**Contingency** is the reserve for the parts you have not thought of yet, and 10 percent is a common starting figure for a well-understood build. A first-of-its-kind design deserves 15 to 20 percent. Contingency is not padding you get to spend on upgrades — spending it silently is exactly how a project arrives at the deadline both over budget and surprised.

Two habits keep a BOM honest: quote real prices from a real supplier with a date on them, and version the BOM alongside your drawings so the parts list and the design never drift apart.'''
            },
            {
                'title': 'Tracking, Milestones and Recovery',
                'content': '''# Tracking, Milestones and Recovery

A plan is a prediction, and predictions are wrong. The point of tracking is not to be right; it is to find out you are wrong early enough to do something about it.

## Baseline Versus Actual

Freeze your schedule and BOM at the critical design review. That frozen copy is the **baseline**. From then on, you track actuals against it and never quietly edit the baseline to match reality — a plan rewritten every week records nothing and teaches nothing.

A weekly status table is enough for a capstone:

| Task | Baseline Finish | Percent Complete | Forecast Finish | Variance |
|------|-----------------|------------------|-----------------|----------|
| C Chassis model | day 12 | 100% | day 12 | 0 |
| D Programming | day 13 | 60% | day 15 | +2 (float 3) |
| E Gripper prototype | day 16 | 40% | day 19 | +3 (critical) |

Read it in ten seconds: D is late but harmless, E is late and is costing the project three days.

## The Percent-Complete Trap

Self-reported progress is famously optimistic — tasks sit at "90 percent done" for a week. Two defenses:

- Score tasks **0 / 50 / 100** only: not started, started, finished. It removes the wishful precision.
- Tie completion to the **visible finish** you wrote in the WBS. A gripper is not done because it exists; it is done when it has passed its fit test.

## Recovery Options

When a critical-path task slips, you have four honest moves and one dishonest one:

- **Fast-track:** run tasks in parallel that were planned in sequence. Cheap, but it raises rework risk if the earlier task changes.
- **Crash:** add people or hours to the critical task. Costs money, and only works on tasks that can actually be split — nine engineers do not write one function in one ninth of the time.
- **Reduce scope:** drop a "could have" feature. This is why you sorted needs from wants in lesson one.
- **Move the date:** with the client, in writing, as soon as you know.
- **Hope:** the dishonest one. Schedules never recover on their own.

Notice that crashing a task with float buys nothing at all. Recovery effort spent off the critical path is effort spent on the wrong problem, which is the single most common project-management mistake student teams make.'''
            }
        ])
        self._create_lesson_questions(lesson, [
            {
                'text': 'On the capstone schedule, task E (gripper prototype) is on the critical path and task D (programming) has 3 days of float. Task E slips by 3 days. What happens to the day-26 delivery date?',
                'choices': [
                    ('It moves to day 29, because a slip on a zero-float task pushes the end date one for one', True),
                    ('It stays at day 26, because task D has float that absorbs the slip', False),
                    ('It moves to day 27, because only the first day of any slip affects the end date', False),
                    ('It cannot be determined without knowing how many people are on the team', False),
                ]
            },
            {
                'text': 'Task D has 3 days of float and slips by 5 days. What is the effect on the project?',
                'choices': [
                    ('The end date moves out 2 days and task D becomes critical, since the slip exceeded its float', True),
                    ('Nothing changes, because a task with float can never affect the end date', False),
                    ('The end date moves out 5 days, since float applies only to milestones', False),
                    ('The critical path is unchanged and the end date moves out 8 days', False),
                ]
            },
            {
                'text': 'A BOM shows a parts subtotal of 649.60, tax and shipping of 77.59, and 10 percent contingency of 64.96 against an 800 USD budget. A teammate proposes spending the contingency on upgraded wheels. Why is that a poor decision?',
                'choices': [
                    ('Contingency is a reserve for unknown costs still to come, so spending it leaves nothing to absorb a price change or a broken part', True),
                    ('Contingency must legally be returned to the client if it is not spent', False),
                    ('Upgraded wheels would change the extended cost column but not the subtotal', False),
                    ('Contingency can only be spent on labor, never on parts', False),
                ]
            },
            {
                'text': 'A team is two days behind on a task that has 14 days of float, and also two days behind on a critical-path task. Where should the extra help go?',
                'choices': [
                    ('To the critical-path task, because effort spent on a task with float does not move the delivery date', True),
                    ('Split evenly, so both tasks return to their baseline finish dates', False),
                    ('To the high-float task, because it is easier to bring back on schedule', False),
                    ('To neither; the baseline should be rewritten so both tasks are on time again', False),
                ]
            }
        ])

        # Lesson 3: Prototyping, Tolerance & Quality Control
        lesson = self._lesson(
            unit, 'rob201-prototyping-tolerance-and-quality-control', 2, title='Prototyping, Tolerance & Quality Control',
        )
        self._create_sections(lesson, [
            {
                'title': 'Overview',
                'content': '''# Prototyping, Tolerance & Quality Control

A design that works once, on the bench, built by the person who designed it, is not a product. Production means the tenth copy works as well as the first, assembled by someone who has never seen your sketches. This lesson covers the practices that make that true: matched prototype fidelity, dimensional tolerance, inspection and sampling, root cause analysis, and revision control.

## Learning Objectives

By the end of this lesson, you will be able to:
- Match prototype fidelity to the question being asked and plan the path to production
- Interpret tolerance callouts, compute a fit, and estimate a tolerance stack-up
- Select measurement and inspection methods, including calipers and go/no-go gauges
- Run a 5 whys root cause analysis and maintain revision control on drawings

> **TEKS alignment:** §127.750(c)(12) — produce a product using appropriate tools, materials, and techniques, applying quality control throughout production.'''
            },
            {
                'title': 'From Prototype to Production Part',
                'content': '''# From Prototype to Production Part

A prototype is built to answer a question; a production part is built to be identical to the last one. Confusing the two wastes weeks in both directions — polishing a part that only needed to answer "does this shape reach?", or shipping a taped-together mock-up as a deliverable.

## Fidelity Ladder

| Stage | Typical Method | Question It Answers | Cost of a Change |
|-------|----------------|---------------------|------------------|
| Concept model | Cardboard, foam, paper cutouts | Is the geometry roughly right? | Minutes |
| Functional prototype | 3D print, scrap stock, simulator model | Does the mechanism actually work? | Hours |
| Engineering prototype | Correct materials, correct fasteners | Does it survive real loads and cycles? | Days |
| First article | Production process, production tooling | Can this be made repeatably? | Weeks |
| Production run | Same process, inspected to a plan | Is every unit within tolerance? | Very high |

The cost of change rises by roughly an order of magnitude at each rung. That single fact is the entire argument for iterating hard at the bottom of the ladder: a mistake caught in cardboard costs an afternoon, and the same mistake caught in the production run costs the run.

## Design for Manufacture

As you climb the ladder, the design itself should change to suit how it will be made:

- **Reduce part count.** Two parts that are always assembled together and never move relative to each other should usually be one part. Fewer parts means fewer tolerances, fewer fasteners, and fewer ways to assemble it wrong.
- **Standardize fasteners.** One screw size across the robot means one driver, one spare bin, and no chance of forcing an 8-32 screw into a metric hole.
- **Design in one orientation where possible.** Parts that can be assembled backwards eventually will be. Add an asymmetric feature or a keyed slot so the wrong way does not fit.
- **Leave access.** If the battery cannot be changed without removing the arm, the client will remove the arm every day for a year.

## Where Simulation Fits

For your capstone, the functional prototype lives in a free simulator. **VEXcode VR** answers behavioral questions — does the sensor logic drive the robot to the right bin, and how many cycles per minute does that take? **Tinkercad Circuits** answers electrical ones — does the sensor conditioning circuit produce a usable signal, and what happens when the input floats? Neither answers whether a printed bracket survives 500 grip cycles. Knowing what your prototype cannot tell you is as important as reading what it can.'''
            },
            {
                'title': 'Tolerance, Fits and Measurement',
                'content': '''# Tolerance, Fits and Measurement

No part is ever exactly its nominal dimension. **Tolerance** is the allowable deviation, and specifying it is how you convert a drawing into something a shop can actually make.

## Reading a Tolerance Callout

A shaft called out as 12.00 mm +0.00 / -0.05 may be made anywhere between 11.95 and 12.00 mm. The **tolerance band** is 0.05 mm wide. Tight bands cost money: halving a tolerance can double a machining cost, because it demands better equipment, slower cuts, and more inspection. The engineering skill is not specifying tight tolerances — it is specifying tight tolerances only where they matter and loose ones everywhere else.

## Fits

The relationship between a hole and the shaft that goes into it is a **fit**:

| Fit Type | Hole 12.10 +0.05/-0.00 vs Shaft | Result | Used For |
|----------|----------------------------------|--------|----------|
| Clearance | Shaft 12.00 +0.00/-0.05 | Gap of 0.10 to 0.20 mm | Rotating shafts, bolt holes |
| Transition | Shaft 12.10 +0.02/-0.02 | Slight gap or slight interference | Located parts that must come apart |
| Interference | Shaft 12.18 +0.02/-0.00 | Metal on metal, needs a press | Bearings, permanent hubs |

Compute the extremes, not the nominals. The worst-case clearance is the largest hole minus the smallest shaft, and the tightest is the smallest hole minus the largest shaft. A fit that works on the nominal numbers and jams at the limits is a fit that fails on roughly half the units you build.

## Tolerance Stack-Up

Tolerances add. Four spacers stacked on a shaft, each 10.00 mm +/- 0.10, give a nominal 40.00 mm and a worst-case range of 39.60 to 40.40. If the frame gap is 40.00 +/- 0.20, a stack at 40.40 will not fit. This is the classic capstone failure: every part measured in spec, and the assembly still refused to go together. Check the stack before you cut, not after.

## Measurement Tools

- **Digital calipers**, typically 0.01 mm resolution, are the workhorse for outside, inside, and depth measurements. Zero them before every session and measure the same feature three times — an unrepeatable reading means the technique is wrong, not the part.
- **Go / no-go gauges** answer pass/fail without a number. The go end must enter the feature; the no-go end must not. They are faster than calipers, they cannot be misread, and a new operator can use one correctly in a minute — which is exactly why production lines prefer them.
- **The rule of ten:** your measuring instrument should resolve about ten times finer than the tolerance you are checking. Checking a +/- 0.05 mm band with a 0.5 mm ruler tells you nothing at all.'''
            },
            {
                'title': 'Inspection, Sampling and Defect Tracking',
                'content': '''# Inspection, Sampling and Defect Tracking

Quality control is not a person squinting at finished parts. It is a plan written before production starts that says what gets checked, how, by whom, and what happens when a check fails.

## The Inspection Plan

| Feature | Spec | Method | When | Reaction to Failure |
|---------|------|--------|------|---------------------|
| Gripper jaw width | 24.0 +/- 0.2 mm | Calipers | First article, then 1 in 5 | Stop, re-measure 5, adjust printer |
| Pivot bore | 6.05 +0.05/-0.00 mm | Go/no-go pin | Every part | Ream to size or scrap |
| Fastener torque | 1.2 N-m +/- 0.2 | Torque driver | Every joint | Re-torque and re-inspect |
| Cable strain relief | Present and secured | Visual | Every unit | Rework before sign-off |

**First article inspection** is the highest-value entry in that table: before you make 50 of anything, make one and measure every single dimension against the drawing. Finding a mis-set fixture on part 1 costs one part; finding it on part 50 costs fifty.

## Sampling

Checking every feature on every part is often impossible, so you sample. Sampling logic hinges on the cost of a defect escaping:

- **100 percent inspection** for anything safety-critical or expensive to fix later.
- **Fixed-rate sampling**, such as 1 in 5, for stable processes with cheap defects.
- **Tightened sampling** the moment a defect appears — go back to 100 percent until the process proves itself again over a run of good parts.

Sampling detects a drifting process. It never guarantees a perfect lot, and any QC plan that claims otherwise is selling you something.

## The Defect Log

Every failed inspection gets a row: date, part, feature, measured value, disposition (rework, scrap, use-as-is with approval), and suspected cause. After a couple of dozen rows, sort by frequency. Almost always a short list of causes accounts for most defects — the **Pareto principle**, informally the 80/20 rule. Fixing the top two causes on that list will do more for your quality than fixing the other eight combined, and the log is what tells you which two they are. Without a log you are guessing, and teams that guess reliably fix the defect that annoyed them most recently rather than the one that costs the most.'''
            },
            {
                'title': 'Root Cause Analysis and Revision Control',
                'content': '''# Root Cause Analysis and Revision Control

A defect log tells you what is failing. Root cause analysis tells you why, and revision control makes sure the fix actually reaches the shop floor.

## The 5 Whys

Ask why until you reach a cause you can change. A real chain from a sorting robot:

1. **Why** did the robot drop the part? The gripper jaws did not close fully.
2. **Why** did they not close fully? The jaw hit the pivot before reaching the closed position.
3. **Why** did it hit early? The printed jaw is 0.4 mm thicker than the drawing.
4. **Why** is it thicker? The printer profile was changed to add a brim and the operator did not re-run the first article.
5. **Why** was no first article run? The inspection plan says "first article, then 1 in 5," but nothing requires a new first article after a process change.

The fix is not "print the jaw again." It is "the inspection plan shall require a first article after any change to the process parameters." Stopping at why number two produces a team that fixes the same defect forever. The number five is a guideline, not a rule — stop when you reach something within your control, and go further if you have not.

## Distinguishing Correction from Corrective Action

- **Correction:** reprint the bad jaws. Fixes the parts in front of you.
- **Corrective action:** change the inspection plan. Fixes the parts you have not made yet.

A quality system that only ever corrects is a treadmill.

## Revision Control for Drawings

Every drawing, BOM, and test procedure carries a revision letter and a change record. Nothing gets edited in place without a new revision.

| Rev | Date | Change | Reason | Approved |
|-----|------|--------|--------|----------|
| A | Mar 3 | Initial release | Critical design review | J. Ruiz |
| B | Mar 18 | Jaw thickness 6.0 to 6.4 mm | Print process change, RCA-004 | J. Ruiz |
| C | Apr 2 | Pivot bore tolerance tightened to +0.05/-0.00 | Defect log, 6 of 40 loose pivots | J. Ruiz |

Three rules keep this honest: superseded revisions are archived and never deleted, only the current revision is allowed at the build station, and every revision names the reason. A year later, the reason column is the most valuable thing on the page — it is the only thing standing between a future teammate and "undoing" a change whose purpose nobody remembers.'''
            }
        ])
        self._create_lesson_questions(lesson, [
            {
                'text': 'A hole is specified 12.10 +0.05/-0.00 mm and the mating shaft is 12.00 +0.00/-0.05 mm. What is the tightest possible clearance between them?',
                'choices': [
                    ('0.10 mm, from the smallest hole (12.10) minus the largest shaft (12.00)', True),
                    ('0.00 mm, because the nominal sizes are close enough to touch', False),
                    ('0.20 mm, from the largest hole minus the smallest shaft', False),
                    ('0.05 mm, because that is the size of each tolerance band', False),
                ]
            },
            {
                'text': 'Four spacers, each 10.00 +/- 0.10 mm, stack into a frame gap of 40.00 +/- 0.20 mm. Every spacer measures in spec, yet some assemblies will not fit. Why?',
                'choices': [
                    ('Tolerances stack, so four spacers can total 40.40 mm, which exceeds the largest allowed 40.20 mm gap', True),
                    ('Individual parts within tolerance always assemble correctly, so the frame must be out of spec', False),
                    ('The spacers were measured with the wrong tool, since calipers cannot read to 0.10 mm', False),
                    ('Stacked tolerances cancel out, so the problem must be thermal expansion', False),
                ]
            },
            {
                'text': 'A team runs a 5 whys and finds that a jaw printed too thick because the printer profile changed with no new first article inspection. Which response is the corrective action rather than a correction?',
                'choices': [
                    ('Update the inspection plan to require a first article after any process parameter change', True),
                    ('Reprint the out-of-spec jaws with the old profile', False),
                    ('Sand the thick jaws down to the drawing dimension', False),
                    ('Record the defect in the log and continue production', False),
                ]
            },
            {
                'text': 'Why do production lines often prefer a go/no-go gauge over digital calipers for a high-volume feature?',
                'choices': [
                    ('It gives an unambiguous pass/fail in seconds and is hard for a new operator to misread', True),
                    ('It measures features more precisely than any caliper can', False),
                    ('It records the measured dimension automatically for the defect log', False),
                    ('It removes the need to specify a tolerance on the drawing', False),
                ]
            }
        ])

        # Lesson 4: Capstone: Build, Test & Present
        lesson = self._lesson(
            unit, 'rob201-capstone-build-test-and-present', 3, title='Capstone: Build, Test & Present',
        )
        self._create_sections(lesson, [
            {
                'title': 'Overview',
                'content': '''# Capstone: Build, Test & Present

Everything in Robotics 2 has been preparation for this. You now have a client, a schedule, a budget, a tolerance stack, and a quality plan — and a project that will use all of them at once. This lesson is the capstone brief itself: what you will build, how it will be tested, what you will deliver, and exactly how it will be graded.

## Learning Objectives

By the end of this lesson, you will be able to:
- Execute an end-to-end robotics project from client requirements to delivered handoff
- Write and run a test plan with pass/fail criteria fixed before testing begins
- Record results in an engineering notebook and present findings with evidence
- Assemble a handoff package that lets someone else operate and maintain your work

> **TEKS alignment:** §127.750(c)(10) — apply engineering design methodologies through a complete design, build, and evaluation cycle.
> **TEKS alignment:** §127.750(c)(12) — produce a product using appropriate tools, materials, and techniques and document the result.'''
            },
            {
                'title': 'The Capstone Brief: Autonomous Sort Cell',
                'content': '''# The Capstone Brief: Autonomous Sort Cell

## The Client and the Problem

Your client is the campus makerspace coordinator. Returned components pile up in a single bin and volunteers sort them by hand for about 30 minutes a day, with frequent mistakes that cost more time later. The client wants a proposal for an autonomous sort cell, proven in simulation, with a costed design for the physical build.

You are delivering a **validated design**, not a machine: a working simulated prototype, real test data, a bill of materials inside the budget, and documentation complete enough for the client to build from. No robot kit is required, and no part of this project requires a purchase.

## Requirements Baseline

| ID | Requirement | Acceptance Criterion |
|----|-------------|----------------------|
| R-01 | Sort each item into the bin matching its category | 28 of 30 trials correct, minimum |
| R-02 | Complete a sort cycle within 8 seconds | Mean under 8.0 s over 30 trials |
| R-03 | Recover from a missed pickup without human help | 5 of 5 seeded misses recovered |
| R-04 | Detect a blocked path and stop safely | 5 of 5 blocked-path trials stop within 10 cm |
| R-05 | Delivered parts cost at or under 800 USD | BOM total including tax, shipping, contingency |
| R-06 | Operate at least 45 minutes on one battery charge | Analysis from current draw and capacity |

R-01 allows two failures in thirty on purpose. A requirement of "never fails" is untestable in thirty trials and is the kind of promise engineers learn not to make.

## The Build Environment

- **VEXcode VR** — build the robot behavior: drive control, sensor-based classification, bin navigation, and the recovery logic for R-03 and R-04. Run trials in a playground that includes objects to detect, move, and place.
- **Tinkercad Circuits** — build and simulate one electrical subsystem: the sensor input circuit, including the pull-up or pull-down resistor, the signal path to the controller input, and a status LED. Capture a screenshot of the working circuit and its code.
- **Any free 2D or 3D drawing tool** — produce the gripper jaw drawing with dimensions and tolerances, and a block diagram of the full system.

## Team Roles

Teams of three or four, with named owners. Every member owns at least one deliverable and presents the part they owned.

- **Project lead** — schedule, status table, client communication
- **Mechanical lead** — mechanism design, drawing, tolerance and fit analysis
- **Controls lead** — VR program, sensor logic, Tinkercad subsystem
- **Quality lead** — test plan, data collection, defect log, notebook custody

On a team of three, the project lead also carries quality. Roles are about accountability, not walls: everybody tests.'''
            },
            {
                'title': 'Deliverables and Schedule',
                'content': '''# Deliverables and Schedule

## Deliverable List

| # | Deliverable | Due | Owner |
|---|-------------|-----|-------|
| D1 | Requirements document with acceptance criteria, client-confirmed | end of week 1 | Project lead |
| D2 | Trade study with weights, scores, and a sensitivity check | end of week 2 | Mechanical lead |
| D3 | WBS, schedule with critical path marked, and baseline BOM | end of week 3 | Project lead |
| D4 | Gripper drawing with tolerances and a stack-up calculation | end of week 4 | Mechanical lead |
| D5 | Tinkercad Circuits subsystem, screenshot and code | end of week 5 | Controls lead |
| D6 | VEXcode VR program, integrated and running end to end | end of week 6 | Controls lead |
| D7 | Test plan with pass/fail criteria, reviewed before testing | end of week 6 | Quality lead |
| D8 | Test report: 30 trials, data tables, defect log, one RCA | end of week 7 | Quality lead |
| D9 | Engineering notebook, dated entries from all members | continuous | All |
| D10 | Final presentation, 8 minutes, plus handoff package | week 8 | All |

Notice that D7 is due **before** D8. Fixing the pass/fail criteria after seeing the data is the most tempting form of dishonesty in engineering, and putting the test plan under review a week early is the structural defense against it.

## Milestones

- **M1, end of week 1** — requirements signed. Nothing gets built before this.
- **M2, end of week 2** — preliminary design review passed. Concept selected and defensible.
- **M3, end of week 4** — critical design review passed. Schedule and BOM baselined and frozen.
- **M4, end of week 6** — test readiness review passed. Build integrated, test plan approved.
- **M5, week 8** — delivery and handoff.

## Weekly Rhythm

Every week the project lead posts a five-line status: what finished, what is in progress, what is blocked, schedule variance against baseline, and top risk. Fifteen minutes a week of this makes the difference between finding out you are behind in week 3 and finding out in week 7, when the only remaining option is to cut scope.

## Scope Discipline

If a great idea arrives after M3, it goes on a "next revision" list. That list is a deliverable too, and it is the honest answer to the presentation question "what would you do with another month?"'''
            },
            {
                'title': 'The Test Plan and Data Collection',
                'content': '''# The Test Plan and Data Collection

A test plan is written before testing and reviewed by someone who did not write it. Each test case names the requirement it verifies, the setup, the procedure, the number of trials, and the exact threshold that separates pass from fail.

## Test Cases

| ID | Verifies | Procedure | Trials | Pass Criterion |
|----|----------|-----------|--------|----------------|
| TC-01 | R-01 | Present items in a fixed randomized order, log destination bin | 30 | At least 28 correct |
| TC-02 | R-02 | Time from grip start to release, logged per trial | 30 | Mean under 8.0 s |
| TC-03 | R-03 | Seed a missed pickup by offsetting the item 3 cm | 5 | 5 of 5 recovered without help |
| TC-04 | R-04 | Place an obstacle in the path mid-run | 5 | 5 of 5 stop within 10 cm |
| TC-05 | R-06 | Compute run time from measured current draw and capacity | n/a | At least 45 minutes, shown |

## Recording the Data

Build the data table before the first trial. A per-trial row beats a summary, because a summary throws away the pattern:

| Trial | Item | Destination | Correct? | Cycle Time (s) | Note |
|-------|------|-------------|----------|----------------|------|
| 1 | red | bin A | yes | 7.2 | — |
| 2 | blue | bin B | yes | 7.5 | — |
| 3 | red | bin B | no | 8.9 | grabbed at corner, sensor read late |
| 4 | green | bin C | yes | 7.4 | — |

Trial 3 is the most valuable row on the page. "Grabbed at corner, sensor read late" is a hypothesis you can test; "failed" is not.

## Reporting Honestly

- Report **all** trials. Deleting a bad run because "the simulator glitched" is data fabrication unless you can name the glitch and say so in the report.
- Give results as counts and means with the trial count attached: "28/30 correct, mean cycle 7.6 s (n = 30)."
- State the result against the criterion plainly: **R-01 PASS at 28/30. R-02 PASS at 7.6 s mean. R-03 FAIL at 3/5 recovered.**
- A failed requirement is a normal, reportable outcome. Run a 5 whys on it, propose the corrective action, and put it on the next-revision list. A team that reports one honest failure with a root cause is graded higher than a team whose every requirement mysteriously passed.

## The Engineering Notebook

Dated entries, every session, from every member: the goal, what happened, the numbers, the decision and its reason, and the next step. The notebook is what turns eight weeks of work into evidence, and it is worth ten points of the final grade on its own.'''
            },
            {
                'title': 'Presentation, Handoff and Rubric',
                'content': '''# Presentation, Handoff and Rubric

## The Final Presentation

Eight minutes, every member speaking about the work they owned, followed by four minutes of questions. Structure it as the story of the project, not a tour of the robot:

1. **The client and the problem** — in the client's own words, with the numbers from the interview (45 seconds)
2. **Requirements and constraints** — the table, and the one requirement that shaped everything (1 minute)
3. **The trade study** — the concepts you rejected and why, including the sensitivity check (1.5 minutes)
4. **The design** — drawing, tolerances, and the electrical subsystem (1.5 minutes)
5. **The evidence** — test results against each acceptance criterion, failures included (2 minutes)
6. **Cost and schedule** — BOM total against budget, actual finish against baseline, with the variance explained (45 seconds)
7. **Next revision** — what you would do with another month, from your own defect log (30 seconds)

Rules that carry over from Robotics 1 and still decide presentations: one idea per slide, numbers instead of adjectives, a recorded clip ready in case the live simulator misbehaves, and a rehearsal against a clock.

## The Handoff Package

Handoff is the deliverable teams forget, and it is what separates a project from a product. Assume the person receiving it has never met you:

- Requirements document and the final trace table, requirement to test case
- Drawings and BOM at their current revision, with the revision history
- The VR program and the Tinkercad circuit, with a short setup guide
- Test report with all raw data
- **Operating instructions** — how to start it, what normal looks like, what to do when it stops
- **Known issues and next-revision list** — honest, specific, and prioritized

## Grading Rubric

| Component | Weight | What Earns Full Marks |
|-----------|--------|-----------------------|
| Requirements and acceptance criteria | 10 | Measurable, traceable to the client, verification method named |
| Project management artifacts | 15 | WBS, critical path identified, baseline held, variance tracked honestly |
| Design and trade study | 15 | Weighted, sensitivity checked, decision defended at review |
| Build: simulation and subsystem | 20 | Integrated and running, drawing with tolerances and stack-up |
| Test and data | 20 | Criteria set in advance, all trials reported, failures analyzed |
| Engineering notebook | 10 | Dated, all members, decisions with reasons and numbers |
| Presentation and handoff | 10 | Clear story, evidence based, package usable by a stranger |

## One Last Thing

Look at where the points are. Forty of the hundred sit on project management, testing, and documentation — the work that is invisible in a demo video. That weighting is not a teacher's preference. It is what the profession actually values, because a brilliant mechanism nobody can schedule, cost, verify, or maintain never ships.'''
            }
        ])
        self._create_lesson_questions(lesson, [
            {
                'text': 'The capstone schedule requires the test plan (D7) to be reviewed before testing begins (D8). What problem does that ordering prevent?',
                'choices': [
                    ('Adjusting the pass/fail criteria after seeing the results so that the design appears to pass', True),
                    ('Running more trials than the test plan calls for', False),
                    ('Testing a requirement that has no owner assigned to it', False),
                    ('Spending contingency funds before the critical design review', False),
                ]
            },
            {
                'text': 'Requirement R-01 asks for at least 28 correct sorts out of 30 rather than a perfect record. Why is the requirement written that way?',
                'choices': [
                    ('A "never fails" claim cannot be verified by a 30-trial test, so the criterion states a threshold the test can actually confirm', True),
                    ('Because two failures are acceptable to the client under any circumstances', False),
                    ('Because acceptance criteria are always written as percentages of a round number', False),
                    ('To leave room in the schedule in case testing runs late', False),
                ]
            },
            {
                'text': 'During testing, one trial fails and a team member suggests deleting it because "the simulator glitched." What is the correct action?',
                'choices': [
                    ('Report the trial, describe what was observed, and investigate whether the glitch is real or the design is at fault', True),
                    ('Delete it, since a tool malfunction is not a design failure', False),
                    ('Re-run only that trial and record whichever of the two results is better', False),
                    ('Keep it but lower the pass criterion so the requirement still passes', False),
                ]
            },
            {
                'text': 'The rubric puts 40 of 100 points on project management, testing, and documentation. What does that weighting reflect?',
                'choices': [
                    ('A design that cannot be scheduled, costed, verified, or maintained by someone else never reaches production', True),
                    ('Written work is easier to grade than a working simulation', False),
                    ('The build is worth less because simulation is not real engineering', False),
                    ('Documentation is weighted heavily only in school projects, not in industry', False),
                ]
            }
        ])

        self._create_unit6_quiz(unit)

    def _create_unit6_quiz(self, unit):
        quiz = self._quiz(
            unit, 'rob201-quiz-design-project-management-capstone', 0,
            title='Design, Project Management & Production Quiz',
            description='Test your understanding of client-driven design, project scheduling and budgeting, production quality control, and the capstone delivery process.',
            passing_score=70,
            points=20,
            max_attempts=3,
        )
        self._create_quiz_questions(quiz, [
            {
                'text': 'Which of these is written as a usable engineering requirement?',
                'choices': [
                    ('The robot shall complete one sort cycle in under 8.0 seconds, verified as a mean over 30 timed trials', True),
                    ('The robot should be fast enough to satisfy the client', False),
                    ('The robot shall use a two-axis gripper arm with rubber pads', False),
                    ('The robot will be tested until the team is confident in its speed', False),
                ]
            },
            {
                'text': 'A client asks for an extra feature two weeks before delivery while holding both the budget and the date fixed. What does the triple constraint say must happen?',
                'choices': [
                    ('Something else must give: scope gets cut elsewhere, or the date or cost has to move', True),
                    ('Nothing, because scope can always be added if the team works longer hours', False),
                    ('The contingency reserve automatically covers any late scope addition', False),
                    ('The critical path shortens, since more work means more parallel tasks', False),
                ]
            },
            {
                'text': 'A project has a 26-day critical path. A task with 4 days of float slips by 6 days. What is the new project duration?',
                'choices': [
                    ('28 days, because 4 days were absorbed by float and the remaining 2 pushed the end date', True),
                    ('26 days, because a task with float can never delay the project', False),
                    ('32 days, because the full slip adds directly to the critical path', False),
                    ('30 days, because float is added to the slip rather than subtracted', False),
                ]
            },
            {
                'text': 'A bill of materials shows a 649.60 parts subtotal, 77.59 in tax and shipping, and 64.96 of contingency against an 800 USD cap, leaving 7.85 of margin. What does that margin indicate?',
                'choices': [
                    ('The design fits, but the margin is under one percent, so any price change or missed part breaks the budget', True),
                    ('The design has comfortable room and could support an upgrade', False),
                    ('The contingency line should be removed since the total already fits', False),
                    ('The extended cost column was calculated incorrectly', False),
                ]
            },
            {
                'text': 'Four spacers, each 10.00 +/- 0.10 mm, are stacked into a 40.00 +/- 0.20 mm gap. Every spacer passes inspection, but some assemblies will not fit. What is the cause?',
                'choices': [
                    ('Tolerance stack-up: the four parts can total 40.40 mm, more than the largest allowed gap', True),
                    ('The inspection sampling rate was too low to catch out-of-spec parts', False),
                    ('The spacers must have been measured before they reached room temperature', False),
                    ('Tolerances on separate parts cancel out, so the gap dimension must be wrong', False),
                ]
            },
            {
                'text': 'A 5 whys analysis traces a defect to a process change that was never re-verified. Which follow-up is the corrective action?',
                'choices': [
                    ('Change the inspection plan to require a first article after every process change', True),
                    ('Rework the defective parts and return them to the build', False),
                    ('Add the defect to the log and increase the sampling rate for one day', False),
                    ('Note the cause in the presentation as a lesson learned', False),
                ]
            }
        ])

    # ================== Helper Methods ==================
    def _stable_choice_order(self, question_text, choices):
        """Rotate a question's choices by a deterministic offset.

        Content is authored with the correct choice first, and the quiz player
        renders choices in stored order — without this every answer would be
        option 1. Hashing the question text keeps the rotation stable across
        re-runs, preserving the command's idempotency.
        """
        digest = hashlib.md5(question_text.encode(), usedforsecurity=False).hexdigest()
        offset = int(digest, 16) % len(choices)
        return choices[offset:] + choices[:offset]

    def _create_sections(self, lesson, sections_data):
        """Upsert a lesson's sections; trailing extras (and their blobs) go."""
        upsert_sections(lesson, sections_data)

    def _create_lesson_questions(self, lesson, questions_data):
        """Upsert a lesson's comprehension questions, and gate on them.

        Phase-55 invariant (see populate_java_course): a seeded lesson has the
        `requires_quiz` gate on if and only if it has questions. Setting it in
        the shared helper rather than at each lesson site makes the invariant
        structural.

        The choice rotation happens here, before the upsert, so the stored
        order the helper matches on is the same one the player renders.
        """
        upsert_lesson_questions(lesson, self._rotate_choices(questions_data))

    def _create_quiz_questions(self, quiz, questions_data):
        """Upsert a unit quiz's questions."""
        upsert_quiz_questions(quiz, self._rotate_choices(questions_data))

    def _rotate_choices(self, questions_data):
        """Apply `_stable_choice_order` to every question's choices."""
        return [
            {**q, 'choices': self._stable_choice_order(q['text'], q['choices'])}
            for q in questions_data
        ]

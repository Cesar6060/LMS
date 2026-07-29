"""
Management command to create/refresh the ROB101 course ("Robotics 1") with a
complete TEKS-aligned robotics curriculum (Texas TEKS Robotics I,
19 TAC §127.749, one credit, recommended grades 9-10, STEM CTE cluster).

Content is platform-agnostic: no hardware kit is assumed, and hands-on work
uses free simulators (VEXcode VR, Tinkercad Circuits). Six thematic units
group the 11 TEKS knowledge-and-skills strands (c)(1)-(c)(11); every lesson
cites the strand(s) it covers.

This command is NON-DESTRUCTIVE:
1. Does NOT delete or create any users
2. Does NOT touch any other course
3. Creates (or idempotently refreshes) only the ROB101 course and its content
   (units -> lessons -> paginated sections + comprehension quizzes, plus a unit
   quiz per unit)
"""
import hashlib

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from courses.models import (
    Course, Unit, Lesson, LessonSection, LessonQuestion, LessonQuestionChoice
)
from quizzes.models import Quiz, Question, Choice

User = get_user_model()


class Command(BaseCommand):
    help = 'Create or refresh the ROB101 Robotics 1 course (non-destructive; no user or other-course changes)'

    def handle(self, *args, **options):
        self.stdout.write('Populating ROB101 course...\n')

        # Find the instructor (never modifies users)
        instructor = self._get_instructor()
        if not instructor:
            return

        # Get or create ROB101 (touches no other course)
        course = self._get_or_update_course(instructor)

        # Clear only this course's content, then rebuild it
        self._clear_course_content(course)
        self._create_course_content(course)

        self.stdout.write(self.style.SUCCESS('\nROB101 population complete (non-destructive).'))

    def _get_instructor(self):
        """Find the instructor Cesar Villarreal."""
        try:
            instructor = User.objects.get(first_name='Cesar', last_name='Villarreal')
            self.stdout.write(f'Found instructor: {instructor.email}')
            return instructor
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR('Instructor "Cesar Villarreal" not found!'))
            return None
        except User.MultipleObjectsReturned:
            instructor = User.objects.filter(first_name='Cesar', last_name='Villarreal').first()
            self.stdout.write(f'Found instructor: {instructor.email}')
            return instructor

    def _get_or_update_course(self, instructor):
        """Get or create the ROB101 course (non-destructive; no other course touched)."""
        title = 'Robotics 1'
        description = (
            'Explore how robots sense, think, and move. Aligned to the Texas '
            'TEKS for Robotics I, this course covers robotics careers and '
            'teamwork, safety and tools, mechanisms and the physics of motion, '
            'sensors and feedback, programming, and the engineering design '
            'process - with hands-on exercises in free simulators like '
            'VEXcode VR and Tinkercad Circuits. No robot kit required.'
        )
        course, created = Course.objects.get_or_create(
            code='ROB101',
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

    def _clear_course_content(self, course):
        """Delete all existing units, lessons, and quizzes (this course only)."""
        # Delete units (cascades to lessons, sections, questions, unit quizzes)
        deleted = course.units.all().delete()
        self.stdout.write(f'Cleared existing content: {deleted}')

    def _create_course_content(self, course):
        """Create all units, lessons, sections, and quizzes."""
        self._create_unit1(course)
        self._create_unit2(course)
        self._create_unit3(course)
        self._create_unit4(course)
        self._create_unit5(course)
        self._create_unit6(course)
        self.stdout.write('Created 6 units with lessons and quizzes')

    # ================== UNIT 1: Robots, Careers & Teamwork ==================
    def _create_unit1(self, course):
        unit = Unit.objects.create(course=course, title='Robots, Careers & Teamwork', order=0)

        # Lesson 1: What Is a Robot?
        lesson = Lesson.objects.create(unit=unit, title='What Is a Robot?', order=0)
        self._create_sections(lesson, [
            {
                'title': 'Overview',
                'content': '''# What Is a Robot?

A vending machine, a dishwasher, and a Mars rover are all machines - but only one of them is a robot. In this lesson you'll learn the test engineers use to decide what counts as a robot, break a robot down into its major systems, and see where robots are already working around you.

## Learning Objectives

By the end of this lesson, you will be able to:
- Explain the sense-think-act cycle and use it to decide whether a machine is a robot
- Identify the four major systems of a robot: power, mechanical, control, and sensing
- Describe real-world settings where robots work and what jobs they do there
- List the work habits - initiative, adaptability, and quality work - that successful robotics students and professionals practice

> **TEKS alignment:** §127.749(c)(1) — demonstrates employability skills such as initiative, adaptability, and producing quality work.'''
            },
            {
                'title': 'Sense, Think, Act',
                'content': '''# The Sense-Think-Act Cycle

What separates a robot from an ordinary machine? Engineers use a simple three-part test called the **sense-think-act cycle**. A robot must do all three, over and over, on its own:

1. **Sense** — gather information about its environment using sensors (a camera, a distance sensor, a bump switch)
2. **Think** — process that information with a program running on a controller and decide what to do
3. **Act** — carry out the decision using motors, arms, wheels, or grippers

## Applying the Test

| Machine | Senses? | Thinks? | Acts? | Robot? |
|---------|---------|---------|-------|--------|
| Toaster | No — runs a fixed timer | No | Yes | No |
| Remote-control car | No — a human senses for it | No — a human decides | Yes | No |
| Robot vacuum | Yes — bump and cliff sensors | Yes — reroutes around obstacles | Yes — drives and sweeps | Yes |
| Self-driving car | Yes — cameras, radar, lidar | Yes — plans a path | Yes — steers and brakes | Yes |

Notice the remote-control car: it moves like a robot, but the *human* is doing the sensing and thinking. That is why competition teams distinguish between **driver control** (a person in the loop) and **autonomous mode** (the robot runs the full cycle by itself).

The cycle repeats many times per second. A line-following robot might check its light sensor 50 times a second, adjusting its motors each time. That constant loop of sensing, deciding, and acting is what makes a robot feel "smart."'''
            },
            {
                'title': 'Robot Systems and Components',
                'content': '''# The Four Systems Inside Every Robot

Whether it is a classroom kit like VEX or LEGO, an Arduino project, or a two-ton industrial arm welding car frames, every robot is built from the same four systems working together.

## 1. Power System

Every robot needs energy. Mobile robots usually carry rechargeable **batteries**; industrial arms are often wired directly into a building's electrical supply. The power system also includes wiring, switches, and fuses that deliver energy safely to every other system.

## 2. Mechanical System

This is the robot's body: the **frame** (or chassis) that holds everything together, plus the parts that move — wheels, gears, arms, and **end effectors** such as grippers or claws. Gears matter here: a gear ratio can trade speed for torque, letting a small motor lift a heavy load.

## 3. Control System

The robot's brain. A **controller** (a microcontroller like an Arduino, or the "brain" module in a classroom kit) runs the program you write. It reads sensor values, makes decisions, and sends signals to the motors. No program, no robot — the control system is where *think* happens.

## 4. Sensing System

Sensors are the robot's eyes and ears. Common examples:

- **Touch/bump sensors** — detect collisions
- **Distance sensors** (ultrasonic, lidar) — measure how far away objects are
- **Light and color sensors** — follow lines or sort objects
- **Encoders** — count wheel rotations so the robot knows how far it has driven

When you troubleshoot a robot, think in systems. Robot not moving? Check power first, then mechanical (is a gear jammed?), then control (is the program running?), then sensing (is a sensor feeding it bad data?).'''
            },
            {
                'title': 'Robots in the Real World',
                'content': '''# Where Robots Work Today

Robots are no longer science fiction — they are coworkers. Here is where you will find them.

## Manufacturing

Factories were the first big employers of robots. **Industrial arms** weld, paint, and assemble products with precision no human can match for eight straight hours. Newer **collaborative robots (cobots)** are designed to work safely right beside people, handing parts to human assemblers.

## Warehouses and Delivery

In large fulfillment centers, fleets of wheeled robots carry shelves to human packers, cutting walking time dramatically. Delivery robots and drones are being tested on sidewalks and in the air.

## Medicine

Surgical robots let doctors operate through tiny incisions with steadier-than-human hands. Rehabilitation robots help stroke patients relearn to walk, and hospital robots deliver medications between floors.

## Dangerous and Distant Places

Robots go where people should not:

- **Bomb-disposal robots** keep technicians at a safe distance
- **Underwater robots** inspect pipelines and shipwrecks
- **Space rovers** like Perseverance explore Mars, since a round-trip radio signal can take over 20 minutes — the rover must sense, think, and act on its own

## Everyday Life

Robot vacuums, lawn mowers, and smart assistants bring robotics into homes. Agriculture uses robots to pick fruit and pull weeds, reducing pesticide use.

The common thread: robots take on jobs that are **dull, dirty, dangerous, or distant** — the "four Ds." That frees humans for work requiring judgment and creativity, and it creates new careers for the people who design, build, program, and repair the robots.'''
            },
            {
                'title': 'Habits of Successful Roboticists',
                'content': '''# Habits of Successful Robotics Students and Professionals

Talent gets you started in robotics; **work habits** keep you employed. Employers surveyed about entry-level robotics hires consistently name the same qualities — and they are the same habits that separate strong robotics students from struggling ones.

## Initiative

Successful roboticists do not wait to be told what to do. When a match ends, they check the robot for damage without being asked. When they hit an error they cannot solve, they search documentation and test small fixes before asking for help — then ask good, specific questions. In the workplace, initiative looks like spotting a problem on the production line and flagging it before it becomes expensive.

## Adaptability

Robots break. Parts arrive late. Competition rules change mid-season. The plan you made Monday may be useless by Friday. Adaptable team members treat surprises as the normal state of engineering: they redesign, re-plan, and keep moving instead of getting stuck on how things "should" have gone.

## Quality Work

In robotics, sloppy work fails publicly — a loose screw or an untested line of code can end a match or halt a factory line. Quality work means:

- **Testing before trusting** — run the code, tug the connector, verify the fix
- **Documenting as you go** — an engineering notebook entry today saves an hour of confusion next week
- **Finishing the boring parts** — cable management and labeling are not glamorous, but they make every future repair faster

## Time Management and Reliability

Deadlines in robotics are real: the competition happens whether your robot is ready or not. Professionals break large jobs into small tasks, estimate honestly, and show up when they said they would. Start practicing these habits now — this course will give you plenty of deadlines to practice on.'''
            }
        ])
        self._create_lesson_questions(lesson, [
            {
                'text': 'A machine must do which three things, repeatedly and on its own, to be considered a robot?',
                'choices': [
                    ('Sense, think, and act', True),
                    ('Roll, lift, and grab', False),
                    ('Charge, connect, and update', False),
                    ('Record, store, and transmit', False),
                ]
            },
            {
                'text': 'Why is a remote-control car NOT considered a true robot?',
                'choices': [
                    ('A human does the sensing and thinking, so the machine only acts', True),
                    ('It is too small to be a robot', False),
                    ('It does not have a power system', False),
                    ('It has wheels instead of legs', False),
                ]
            },
            {
                'text': 'Which robot system contains the controller that runs the program and makes decisions?',
                'choices': [
                    ('The control system', True),
                    ('The mechanical system', False),
                    ('The power system', False),
                    ('The sensing system', False),
                ]
            },
            {
                'text': 'Which of the following best shows the employability skill of initiative on a robotics team?',
                'choices': [
                    ('Checking the robot for damage after a match without being asked', True),
                    ('Waiting for the teacher to assign every task', False),
                    ('Skipping documentation to save time', False),
                    ('Only working on the parts of the robot you enjoy', False),
                ]
            }
        ])

        # Lesson 2: Careers in Robotics
        lesson = Lesson.objects.create(unit=unit, title='Careers in Robotics', order=1)
        self._create_sections(lesson, [
            {
                'title': 'Overview',
                'content': '''# Careers in Robotics

Robotics is one of the fastest-growing career fields in the world, and it needs far more than just engineers. In this lesson you'll map out the main career paths, compare the education each one requires, and learn what employers actually expect from the people they hire — including how professionals handle information and technology ethically.

## Learning Objectives

By the end of this lesson, you will be able to:
- Compare the roles of robotics technician, technologist, and engineer
- Describe education paths into robotics, including industry certifications and ABET-accredited degree programs
- Identify the skills and behaviors employers expect from robotics professionals
- Explain what ethical and appropriate use of information and technology looks like in a robotics workplace

> **TEKS alignment:** §127.749(c)(2) — investigates careers in robotics, the education they require, and employer expectations.
> **TEKS alignment:** §127.749(c)(1) — demonstrates employability skills such as initiative, adaptability, and producing quality work.'''
            },
            {
                'title': 'Technician, Technologist, Engineer',
                'content': '''# Three Paths, One Field

Robotics careers form a ladder of roles that work together on every project. The main difference between them is *what question they answer*.

## Robotics Technician — "How do I fix it?"

Technicians are the hands-on experts who **install, maintain, troubleshoot, and repair** robots. When a factory arm stops mid-shift, a technician diagnoses the fault, swaps the failed part, and gets the line running again. Typical preparation is a **certificate or two-year associate degree**, and technicians are in high demand — every robot sold needs someone to keep it running.

## Robotics Technologist — "How do I make it work here?"

Technologists bridge the gap between design and the factory floor. They **integrate, test, and improve** robotic systems: programming an arm for a new task, designing the fixtures that hold parts, and collecting data to make a work cell faster. Typical preparation is a **four-year bachelor of engineering technology** degree, which emphasizes applied, hands-on coursework.

## Robotics Engineer — "How do I design it?"

Engineers **design new robots and robotic systems** from the ground up: selecting motors, doing the math on loads and speeds, writing control software, and proving the design is safe. Typical preparation is a **four-year bachelor of science in engineering** (mechanical, electrical, computer, or mechatronics), often followed by graduate study for research roles.

## Which Is "Best"?

None of them — they are different jobs, not ranked ones. A repair-savvy technician can out-earn a new engineer, and many people move between roles: technicians become technologists through experience and night classes; engineers who love hands-on work move toward integration. The skills you build in this course — building, wiring, programming, documenting — are the entry point for all three.'''
            },
            {
                'title': 'Education Paths and Certifications',
                'content': '''# Getting There: Education Paths

There is no single road into robotics. Here are the main routes, from shortest to longest.

## Industry Certifications

Certifications prove a specific skill to employers and can be earned in high school or shortly after:

- **Robot manufacturer certifications** (for example, FANUC or similar industrial-robot operation and programming credentials) — often available through high school and community college programs
- **OSHA safety certification** — workplace safety basics that nearly every industrial employer wants
- **Electronics and automation certifications** (such as those from SACA or PMMI) — validate skills in wiring, sensors, and programmable controllers

Certifications stack: each one you add makes your resume stronger, and many count toward later degrees.

## Two-Year Degrees

Community colleges offer **associate degrees** in robotics/automation technology, mechatronics, or electronics — the standard path to technician roles. They cost far less than universities, and credits often transfer.

## Four-Year Degrees and ABET Accreditation

Technologist and engineer roles usually require a bachelor degree. When comparing programs, look for **ABET accreditation**. ABET is the nonprofit organization that reviews college engineering and technology programs to verify they meet professional standards. Why it matters:

- Many employers require or strongly prefer graduates of ABET-accredited programs
- An ABET-accredited degree is required to become a **licensed Professional Engineer (PE)** in most states
- It guarantees the program covers the math, science, and design fundamentals the profession expects

## Keep Learning Forever

Robotics changes fast. Professionals at every level keep learning through short courses, new certifications, and on-the-job training — a degree is a starting line, not a finish line.'''
            },
            {
                'title': 'What Employers Expect',
                'content': '''# What Employers Actually Expect

Ask robotics employers what they look for, and technical skill is only half the answer. Here is the full picture.

## Technical Foundations

- **Programming basics** — reading and writing simple code, even for mechanical roles
- **Mechanical and electrical literacy** — using hand tools, reading a wiring diagram, understanding gears and circuits
- **Troubleshooting method** — isolating a problem step by step instead of guessing
- **Documentation** — writing clear notes, labeling work, updating records

## Professional Behaviors

| Expectation | What it looks like on the job |
|-------------|-------------------------------|
| Reliability | Arriving on time, meeting deadlines, doing what you said you would |
| Safety mindset | Wearing required protection, following lockout procedures, never bypassing a guard |
| Communication | Explaining a technical problem clearly to a non-technical manager |
| Teamwork | Sharing information, accepting feedback, helping teammates finish |
| Honesty | Reporting your own mistakes immediately — a hidden error in automation can hurt someone |

## The Interview Question Behind Every Interview

Employers are really asking three things: *Can you do the work? Will you do the work? Can we stand working with you?* Grades and certifications answer the first. Your track record of showing up and following through answers the second. How you treat teammates answers the third.

## Building Evidence Now

Everything in this course is resume material. A well-kept engineering notebook, a competition role you can describe in detail, a teammate who will vouch for you — these are exactly the evidence employers and college programs ask for. Treat class like the job it is preparing you for.'''
            },
            {
                'title': 'Ethics and Appropriate Use of Technology',
                'content': '''# Ethics: Using Information and Technology Responsibly

Robotics professionals wield powerful tools — machines that can injure, software that can fail, and data that can be misused. That power comes with ethical responsibilities that employers take seriously enough to fire over.

## Intellectual Property

Designs, code, and processes are valuable property:

- **Respect copyrights and patents** — you cannot copy a competitor's design or use unlicensed software at work
- **Give credit** — using a teammate's code or an open-source library without attribution is plagiarism; most open-source licenses legally require credit
- **Protect trade secrets** — what you learn inside a company stays there, even after you leave

## Data and Privacy

Robots collect data constantly — camera feeds, location logs, performance records. Professionals ask: *Was this data collected with permission? Who can see it? Is it stored securely?* A warehouse robot's camera that happens to record employees raises real privacy questions someone must answer before deployment.

## Safety and Honesty

The most serious ethical duty in robotics is refusing to cut corners on safety:

- Never disable a safety sensor or guard to save time
- Never report a test as passed when it was not run
- Raise concerns when you believe a system is unsafe — even when it is unpopular

## Appropriate Use at School and Work

Company (and school) equipment, networks, and accounts are for authorized work. That means no snooping in files you were not given access to, no sharing passwords, and no using lab equipment for unapproved projects. These rules exist in every **acceptable use policy** you will ever sign — and violating them ends careers.

Ethical habits, like technical ones, are built through practice. Start now: cite your sources, ask before you borrow, and tell the truth about what you tested.'''
            }
        ])
        self._create_lesson_questions(lesson, [
            {
                'text': 'A factory robot arm stops working mid-shift. Which robotics professional would typically diagnose and repair it?',
                'choices': [
                    ('A robotics technician', True),
                    ('A robotics research scientist', False),
                    ('A patent attorney', False),
                    ('A sales representative', False),
                ]
            },
            {
                'text': 'What is ABET?',
                'choices': [
                    ('An organization that accredits college engineering and technology programs to verify they meet professional standards', True),
                    ('A brand of industrial robot arm', False),
                    ('A programming language used in robotics', False),
                    ('A government agency that licenses robots', False),
                ]
            },
            {
                'text': 'Which role focuses primarily on designing new robots and robotic systems from the ground up?',
                'choices': [
                    ('Robotics engineer', True),
                    ('Robotics technician', False),
                    ('Machine operator', False),
                    ('Quality inspector', False),
                ]
            },
            {
                'text': 'Which action is an example of ethical use of technology in a robotics workplace?',
                'choices': [
                    ('Giving credit when you use an open-source library in your code', True),
                    ('Disabling a safety sensor to finish a test faster', False),
                    ('Reporting a test as passed without running it', False),
                    ('Sharing your login password with a coworker to save time', False),
                ]
            }
        ])

        # Lesson 3: Working on a Robotics Team
        lesson = Lesson.objects.create(unit=unit, title='Working on a Robotics Team', order=2)
        self._create_sections(lesson, [
            {
                'title': 'Overview',
                'content': '''# Working on a Robotics Team

No competition robot — and no industrial robot — is built by one person. Robotics is a team sport, and the teams that win are rarely the ones with the single best builder; they are the ones that organize, communicate, and recover from conflict the best. In this lesson you'll learn how effective robotics teams are structured and how to be the teammate everyone wants.

## Learning Objectives

By the end of this lesson, you will be able to:
- Describe the common roles on a robotics team and what each one contributes
- Compare leadership styles and identify when each is effective
- Apply communication and conflict-resolution strategies to team problems
- Explain why diverse teams design and build better robots

> **TEKS alignment:** §127.749(c)(3) — works productively in teams, demonstrating leadership, communication, and conflict-resolution skills.'''
            },
            {
                'title': 'Team Roles',
                'content': '''# Who Does What: Robotics Team Roles

Successful teams divide the work into clear roles. On a small team one person may hold two roles; on a large team a role may be a whole sub-team. The names vary, but the jobs are universal.

## The Core Roles

| Role | Main responsibility | Key skills |
|------|--------------------|-----------|
| Builder | Designs and assembles the frame, drivetrain, and mechanisms | Mechanical reasoning, tool use, patience |
| Programmer | Writes and tests the code for driver control and autonomous routines | Logic, debugging, attention to detail |
| Documenter | Maintains the engineering notebook: decisions, designs, test results | Writing, organization, consistency |
| Driver / Operator | Practices with and operates the robot during matches or demos | Reflexes, calm under pressure, practice hours |
| Project Manager | Tracks tasks and deadlines, runs meetings, keeps the team on schedule | Planning, communication, follow-through |

## Why Clear Roles Matter

Without roles, teams fall into two failure modes: **everyone crowds around the robot** doing the fun part while the notebook goes blank, or **nobody owns a task** so it silently never happens. Clear ownership means every job has a name attached — and every person knows what they are accountable for.

## Roles Are Not Walls

The best teams cross-train. The programmer should understand the drivetrain well enough to know what the code is controlling; the builder should be able to run a test program. Cross-training protects the team when someone is absent, and it is exactly how professional engineering teams operate: specialists with overlapping knowledge, not isolated silos.

Pick roles based on interest *and* team need — then rotate over the season so everyone grows.'''
            },
            {
                'title': 'Leadership Styles',
                'content': '''# Leadership on a Robotics Team

Every team needs leadership — but leadership is not one personality type, and it is not the same as being the boss. Researchers describe several distinct styles, and effective leaders switch between them depending on the situation.

## Three Common Styles

- **Directive (autocratic):** the leader decides and the team executes. Fast and clear — but team members get little voice, and morale suffers if it is the *only* style used.
- **Democratic (participative):** the leader gathers input and the team decides together. Produces buy-in and better ideas — but it is slow, which is a problem when the match starts in four minutes.
- **Delegative (laissez-faire):** the leader sets the goal and trusts members to manage their own work. Great for skilled, motivated members — risky when people need structure or the deadline is close.

## Matching Style to Situation

| Situation | Style that fits | Why |
|-----------|----------------|-----|
| Robot fails inspection 10 minutes before a match | Directive | No time to debate; someone must assign fixes now |
| Choosing the robot design at season start | Democratic | Big decision, plenty of time, buy-in matters |
| Experienced documenter maintaining the notebook | Delegative | They know the job; trust them and check in weekly |

## Leadership Without a Title

You do not need to be team captain to lead. Leadership is behavior: staying calm when the robot breaks, making sure the quietest teammate gets heard, volunteering for the unglamorous task, and admitting your own mistakes first. Teams follow the person who does these things regardless of who holds the title — and colleges and employers notice exactly this kind of leadership.'''
            },
            {
                'title': 'Communication and Conflict Resolution',
                'content': '''# Communicating and Resolving Conflict

Most robotics team failures are not technical — they are communication failures. A programmer changes the code without telling the driver; two builders modify the same mechanism differently; a deadline lives in one person's head. Here is how strong teams prevent and repair those breakdowns.

## Habits of Well-Communicating Teams

- **Brief regular check-ins.** Start each work session with two minutes: what got done, what is next, what is blocked.
- **Write decisions down.** If it is not in the notebook or the task list, it did not happen. Memory is not a plan.
- **Close the loop.** When someone gives you a task, confirm it; when you finish, report it. Silence creates uncertainty.
- **Listen actively.** Restate the other person's point before arguing with it: "So you're saying the claw is too heavy — is that right?" Half of all arguments dissolve at this step because the two sides were solving different problems.

## When Conflict Happens

Conflict on an engineering team is normal — two smart people *should* sometimes disagree about a design. The goal is not to avoid conflict but to keep it **about the problem, not the person**.

A simple resolution process:

1. **Cool down first.** No productive conversation happens mid-frustration.
2. **State the problem neutrally.** "We have two claw designs and one robot" — not "your design is bad."
3. **Let each side present evidence.** Test data beats opinions. If there is no data, run the test.
4. **Decide by agreed criteria.** Weight, cycle time, reliability — pick the measures *before* comparing.
5. **Commit to the decision.** Once the team decides, everyone supports it — including whoever argued for the other option.

If the team truly deadlocks, escalate to the mentor or coach as a tiebreaker — that is what they are for. What is never acceptable: personal insults, silent grudges, or sabotaging a decision you disagreed with.'''
            },
            {
                'title': 'Why Diverse Teams Build Better Robots',
                'content': '''# Why Diverse Teams Build Better Robots

Here is an engineering fact backed by decades of research on team performance: groups with a wider range of backgrounds, skills, and perspectives solve hard problems better than uniform groups of equal talent. For robotics teams, this is not about politics — it is about winning.

## More Perspectives, Fewer Blind Spots

Every designer has blind spots shaped by their own experience. A team where everyone thinks alike shares the *same* blind spots, so nobody catches the flaw. A team with different perspectives — different strengths, hobbies, classes, and life experiences — attacks a problem from more angles:

- The gamer thinks about driver controls nobody else considered
- The artist notices the mechanism is impossible to service because parts block access
- The athlete asks how the design holds up to repeated impacts
- The writer spots that the notebook will not make sense to a judge

## The Groupthink Trap

Uniform teams fall into **groupthink**: agreement feels good, so nobody challenges the plan, and the first idea proposed becomes the final design. Diverse teams argue more — and that friction is productive. Studies of problem-solving groups consistently find that diverse teams check facts more carefully and generate more original solutions, precisely *because* agreement cannot be assumed.

## Skill Diversity Counts Too

A team of five brilliant programmers still cannot build a frame, write a notebook, and drive a match. Recruit for the skills your team lacks, not for copies of the members you already have.

## What This Asks of You

Diversity only pays off if every voice is actually heard. That means inviting the quiet teammate's opinion, taking an idea seriously before rejecting it, and never dismissing someone based on who they are rather than what they said. The best teams make disagreement safe — because the next uncomfortable question might be the one that saves your robot.'''
            }
        ])
        self._create_lesson_questions(lesson, [
            {
                'text': 'Which team role is responsible for maintaining the engineering notebook with decisions, designs, and test results?',
                'choices': [
                    ('Documenter', True),
                    ('Driver/operator', False),
                    ('Builder', False),
                    ('Programmer', False),
                ]
            },
            {
                'text': 'The robot fails inspection 10 minutes before a match. Which leadership style fits this situation best?',
                'choices': [
                    ('Directive — assign fixes immediately because there is no time to debate', True),
                    ('Democratic — hold a full team vote on what to do', False),
                    ('Delegative — let everyone decide individually what to work on', False),
                    ('No leadership — wait and see what happens', False),
                ]
            },
            {
                'text': 'Two teammates disagree about which claw design to use. According to the conflict-resolution process, what should the team rely on to decide?',
                'choices': [
                    ('Test data compared against criteria the team agreed on in advance', True),
                    ('Whichever teammate argues the loudest', False),
                    ('A coin flip to avoid any discussion', False),
                    ('Seniority — the oldest member always decides', False),
                ]
            },
            {
                'text': 'Why do diverse teams tend to build better robots than uniform teams of equal talent?',
                'choices': [
                    ('Different perspectives catch blind spots and prevent groupthink', True),
                    ('Diverse teams are required to have more members', False),
                    ('Diverse teams never disagree with each other', False),
                    ('Uniform teams are not allowed to compete', False),
                ]
            }
        ])

        self._create_unit1_quiz(unit)

    def _create_unit1_quiz(self, unit):
        quiz = Quiz.objects.create(
            unit=unit,
            title='Unit 1 Quiz: Robots, Careers & Teamwork',
            description='Test your understanding of what makes a robot, robotics career paths, and effective teamwork.',
            passing_score=70,
            points=20,
            max_attempts=3,
            order=0
        )
        self._create_quiz_questions(quiz, [
            {
                'text': 'A robot vacuum detects a wall with its bump sensor, decides to turn, and drives in a new direction. Which cycle is it demonstrating?',
                'choices': [
                    ('The sense-think-act cycle', True),
                    ('The build-test-repair cycle', False),
                    ('The charge-discharge cycle', False),
                    ('The design-document-deliver cycle', False),
                ]
            },
            {
                'text': 'A robot will not move, and you discover its battery is dead. Which of the four robot systems failed?',
                'choices': [
                    ('The power system', True),
                    ('The sensing system', False),
                    ('The control system', False),
                    ('The mechanical system', False),
                ]
            },
            {
                'text': 'Robots are often used for jobs described by the "four Ds." What are they?',
                'choices': [
                    ('Dull, dirty, dangerous, and distant', True),
                    ('Digital, durable, dynamic, and dependable', False),
                    ('Design, develop, deploy, and debug', False),
                    ('Drive, detect, decide, and deliver', False),
                ]
            },
            {
                'text': 'Which education path most directly prepares someone for a robotics technician role?',
                'choices': [
                    ('A certificate or two-year associate degree in robotics or automation technology', True),
                    ('A doctoral degree in theoretical physics', False),
                    ('A law degree with a focus on patents', False),
                    ('No education path exists for technicians', False),
                ]
            },
            {
                'text': 'Why do many employers prefer engineering graduates from ABET-accredited programs?',
                'choices': [
                    ('Accreditation verifies the program meets professional standards, and it is required for PE licensure in most states', True),
                    ('ABET-accredited programs are always free to attend', False),
                    ('ABET graduates are exempt from workplace safety rules', False),
                    ('Only ABET graduates may join robotics teams', False),
                ]
            },
            {
                'text': 'A team leader gathers input from every member before the team votes on the season robot design. Which leadership style is this?',
                'choices': [
                    ('Democratic (participative)', True),
                    ('Directive (autocratic)', False),
                    ('Delegative (laissez-faire)', False),
                    ('Groupthink', False),
                ]
            }
        ])

    # ================== UNIT 2: Safety, Tools & Project Management ==================
    def _create_unit2(self, course):
        unit = Unit.objects.create(course=course, title='Safety, Tools & Project Management', order=1)

        # Lesson 1: Shop & Electrical Safety
        lesson = Lesson.objects.create(unit=unit, title='Shop & Electrical Safety', order=0)
        self._create_sections(lesson, [
            {
                'title': 'Overview',
                'content': '''# Shop & Electrical Safety

Before you build a single robot, you need to know how to keep yourself and your teammates safe. A robotics lab has spinning motors, sharp edges, live circuits, and batteries that store a surprising amount of energy. Safety is not a list of rules to memorize once — it is a habit you practice every time you pick up a tool.

## Learning Objectives

By the end of this lesson, you will be able to:
- Explain why a safety mindset matters in a robotics lab
- Identify the four main hazard classes: electrical, mechanical, chemical/battery, and eye/hearing
- Choose the correct personal protective equipment (PPE) for a task
- Store, charge, and handle batteries safely, including LiPo batteries
- Describe the emergency procedures for your lab

> **TEKS alignment:** §127.749(c)(5) — The student demonstrates safe practices and follows safety guidelines when working with tools, equipment, and materials.'''
            },
            {
                'title': 'The Safety Mindset',
                'content': '''# The Safety Mindset

Most lab accidents are not caused by broken equipment — they are caused by people rushing, guessing, or showing off. A safety mindset means you slow down and think before you act.

## Three Habits of Safe Builders

1. **Ask before you assume.** If you have never used a tool before, get trained first. "It looked easy" is how fingers get cut.
2. **Plan the whole task.** Before you drill a hole, know where the drill will go *after* it passes through the material. Before you power a circuit, know what should happen — and what you will do if it does not.
3. **Speak up.** If you see a frayed wire, a puddle near an outlet, or a teammate about to do something risky, say something. In a real workplace this is required, not optional.

## OSHA and Your School Lab

In the United States, the Occupational Safety and Health Administration (**OSHA**) sets workplace safety standards. Your school lab follows the same core ideas:

- **Hazard communication:** chemicals and materials must be labeled, and safety data sheets (SDS) must be available.
- **Machine guarding:** moving parts like gears and blades must have guards in place.
- **Housekeeping:** clear walkways, no clutter on work surfaces, spills cleaned immediately.

Learning these habits now means you will already know the rules when you walk into a college lab or a job site.'''
            },
            {
                'title': 'Hazard Classes and PPE',
                'content': '''# Hazard Classes and PPE

Engineers group dangers into **hazard classes** so they can match each one with the right protection. Here are the four you will meet most often in robotics.

| Hazard class | Examples in a robotics lab | Protection |
|--------------|---------------------------|------------|
| Electrical | Live circuits, frayed wires, short circuits | Power off before rewiring; one hand rule; inspect cords |
| Mechanical | Spinning motors, gears, drill bits, sharp metal edges | Guards in place; tie back hair; no loose sleeves or jewelry |
| Chemical / battery | Damaged batteries, solder fumes, adhesives | Ventilation, gloves when needed, proper storage |
| Eye / hearing | Flying debris from cutting or drilling, loud power tools | Safety glasses, hearing protection |

## Personal Protective Equipment (PPE)

PPE is your **last** line of defense — it protects you when other safeguards fail.

- **Safety glasses** are the number one rule: wear them whenever anyone in the room is cutting, drilling, grinding, or soldering.
- **Hearing protection** (earplugs or earmuffs) when power tools run for more than a few seconds.
- **Closed-toe shoes** every day in the lab. A dropped battery pack or metal plate lands on *something*.
- **Tie back long hair and remove dangling jewelry** near anything that spins. A motor cannot tell the difference between a wire and a hoodie string.

PPE only works if it is worn correctly, every time — not pushed up on your forehead.'''
            },
            {
                'title': 'Battery Safety and LiPo Care',
                'content': '''# Battery Safety and LiPo Care

Robot batteries pack a lot of energy into a small case. Treated well, they are safe. Treated badly, they can overheat, leak, or even catch fire. **Lithium polymer (LiPo)** batteries — common in drones and competition robots — need the most care.

## Rules for All Batteries

- Never short-circuit the terminals. Keep batteries away from loose metal parts, keys, and steel wool.
- Inspect before use. A swollen ("puffed"), dented, or leaking battery is retired immediately — tell your instructor.
- Match the charger to the battery. Chargers are chemistry-specific; a NiMH charger can destroy a LiPo.

## Extra Rules for LiPo Batteries

- **Charge in a LiPo-safe bag or fireproof container**, never on carpet or a wooden desk.
- **Never charge unattended.** Someone stays in the room until charging finishes.
- **Stop using any pack that is puffed, punctured, or hot.** Place it in a safe container away from anything flammable and report it.
- **Store at partial charge** (a "storage charge") if the battery will sit unused for weeks — most smart chargers have a storage mode.

## Safe Storage

Store batteries in a cool, dry, labeled location — not in a random parts bin. Keep charged and depleted packs separated or clearly marked so nobody grabs a dead battery before a demo, or double-charges a full one.'''
            },
            {
                'title': 'Emergency Procedures',
                'content': '''# Emergency Procedures

Knowing what to do in the first ten seconds of an emergency matters more than anything you can look up later. Learn your lab's specific procedures on day one.

## Know Before You Need It

- **Where is the fire extinguisher, and what class is it?** Electrical fires need a Class C (or ABC) extinguisher — never water.
- **Where is the first aid kit?** Know what is in it and who is trained to use it.
- **Where is the emergency power cutoff?** Many labs have a master switch or clearly marked outlets. If a robot or tool goes out of control, cut power first.
- **Where are the exits and the eyewash station?**

## If Something Goes Wrong

1. **Stop and make the area safe.** Cut power, step back, and keep others away.
2. **Alert the instructor immediately** — even for "small" incidents. A minor cut or a briefly smoking wire still gets reported.
3. **Do not fight a growing fire.** Small, contained, and you are trained? Use the extinguisher. Otherwise evacuate and pull the alarm.
4. **Report and record.** Workplaces document every incident so it does not happen twice. Your lab should too — a short note in the engineering notebook about what happened and how to prevent it.

> A near-miss is a free lesson. Treat "that almost hit me" with the same seriousness as an actual injury, and you will prevent the real one.'''
            }
        ])
        self._create_lesson_questions(lesson, [
            {
                'text': 'What is the single most important piece of PPE to wear whenever anyone in the lab is cutting, drilling, or soldering?',
                'choices': [
                    ('Safety glasses', True),
                    ('A lab coat', False),
                    ('Rubber boots', False),
                    ('A hard hat', False),
                ]
            },
            {
                'text': 'You notice a LiPo battery is swollen ("puffed"). What should you do?',
                'choices': [
                    ('Stop using it, isolate it safely, and report it to your instructor', True),
                    ('Squeeze it back to shape and keep using it', False),
                    ('Charge it fully to see if the swelling goes away', False),
                    ('Throw it in the regular trash can', False),
                ]
            },
            {
                'text': 'Which hazard class does a spinning motor with exposed gears belong to?',
                'choices': [
                    ('Mechanical', True),
                    ('Chemical', False),
                    ('Electrical', False),
                    ('Hearing', False),
                ]
            },
            {
                'text': 'A power strip catches fire in the lab. Which type of fire extinguisher is safe to use?',
                'choices': [
                    ('A Class C (or ABC) extinguisher rated for electrical fires', True),
                    ('A bucket of water', False),
                    ('Any extinguisher, since they all work the same', False),
                    ('A wet towel placed over the flames', False),
                ]
            }
        ])

        # Lesson 2: Tools & Precision Measurement
        lesson = Lesson.objects.create(unit=unit, title='Tools & Precision Measurement', order=1)
        self._create_sections(lesson, [
            {
                'title': 'Overview',
                'content': '''# Tools & Precision Measurement

A robot is only as good as the hands — and tools — that build it. In this lesson you will learn to pick the right tool for the job, measure with real precision, choose fasteners that hold, and keep your equipment in working order. You will also see that some of your most powerful tools are software.

## Learning Objectives

By the end of this lesson, you will be able to:
- Distinguish hand tools from power tools and choose the right tool for a task
- Measure accurately with rulers and calipers, and convert between metric and imperial units
- Explain what tolerance means and why it matters in robot builds
- Identify common fasteners and when to use each
- Maintain tools and equipment so they stay safe and accurate
- Describe how software tools like CAD and circuit simulators fit into a robotics workflow

> **TEKS alignment:** §127.749(c)(10) — The student selects and safely uses appropriate tools, equipment, and materials, and maintains them in proper working order.'''
            },
            {
                'title': 'Hand Tools vs. Power Tools',
                'content': '''# Hand Tools vs. Power Tools

## Hand Tools

Hand tools are powered by you: screwdrivers, hex (Allen) keys, pliers, wrenches, hacksaws, and files. They are slower but give you **control and feel** — you can sense when a screw is snug and stop before you strip it.

- **Screwdrivers and hex keys:** match the tip to the screw head exactly. A loose fit rounds out the head, and a rounded screw may never come out.
- **Pliers:** needle-nose for gripping small parts and bending wire; diagonal cutters for trimming wire and zip ties.
- **Wrenches:** hold the nut while the screwdriver turns the screw — the classic two-tool robot assembly move.

## Power Tools

Power tools — drills, rotary tools, saws — trade control for speed. That trade is exactly why they demand training, guards, and PPE before every use.

## Choosing the Right Tool

The right tool is the one **designed for the task**, not the one within reach:

- Do not use pliers as a wrench — they round off nuts.
- Do not use a screwdriver as a pry bar or chisel — tips snap.
- Cutting one aluminum bar? A hacksaw is fine. Cutting twenty? Ask about the bandsaw and get trained.

> Rule of thumb: if you find yourself forcing a tool, you probably have the wrong tool — or the wrong technique. Stop and rethink.'''
            },
            {
                'title': 'Precision Measurement',
                'content': '''# Precision Measurement

"Measure twice, cut once" survives because it works. In robotics, a hole drilled 2 mm off can mean a motor mount that never lines up.

## Rulers and Calipers

- A **steel ruler** is fine for rough layout — accurate to about half a millimeter.
- **Calipers** are the precision workhorse. Digital calipers read to 0.01 mm and measure three ways: outside jaws (width of a part), inside jaws (diameter of a hole), and the depth rod (depth of a slot). Always close the jaws and zero the display before measuring.

## Metric vs. Imperial

Robotics mixes both systems, so you must move between them.

| Metric | Imperial equivalent |
|--------|--------------------|
| 1 mm | ~0.0394 in |
| 25.4 mm | exactly 1 in |
| 1 m | ~3.28 ft |

Most robot hardware (like M3 and M4 screws) is metric; some kits and lumber are imperial. **Never mix them in one measurement** — pick one system per drawing and label your units every time. A number without a unit is a guess.

## Tolerance

No part is ever exactly the size on the drawing. **Tolerance** is the acceptable amount of error, written like `10 mm ± 0.2 mm` — meaning anywhere from 9.8 to 10.2 mm is acceptable.

- A shaft that must spin freely in a hole needs **clearance** (hole slightly larger).
- A bearing pressed into a plate needs a **tight fit** (hole barely smaller).

Tight tolerances cost time and money, so engineers specify them only where they matter.'''
            },
            {
                'title': 'Fasteners',
                'content': '''# Fasteners: Holding It All Together

Robots shake, twist, and crash. Fasteners are what keep them from becoming a box of loose parts.

## The Common Fasteners

| Fastener | Best for | Watch out for |
|----------|----------|---------------|
| Machine screws + nuts | Most structural connections; removable | Can vibrate loose |
| Nylon-insert lock nuts (nyloc) | Joints that vibrate — drivetrains, arms | Slower to install; nylon wears out after reuse |
| Self-tapping screws | Cutting their own threads in plastic | Easy to strip if over-tightened |
| Zip ties | Wire management, quick prototypes | Not structural; trim ends flush |
| Velcro straps | Mounting batteries — removable in seconds | Only for parts that must come out often |

## Screw Sizes

Metric screws are named by diameter and length: an **M3 x 10** is 3 mm across and 10 mm long. Match the screw to the nut — an M3 nut will not thread onto an M4 screw, and forcing it destroys both.

## Tightening Technique

- Snug, then a small extra turn. Over-tightening strips threads and cracks plastic.
- On a part with multiple screws, tighten in a **cross pattern** so the part seats evenly instead of tilting.
- If a joint keeps loosening, switch to a lock nut or add a lock washer — do not just crank it harder.'''
            },
            {
                'title': 'Tool Care and Software Tools',
                'content': '''# Tool Care and Software Tools

## Maintaining Your Equipment

Well-maintained tools are safer, more accurate, and last for years. Maintenance is part of using a tool, not an extra chore.

- **Clean and return.** Wipe tools down and put them back in their labeled spot. A shadow board (an outline for each tool) makes missing tools obvious at a glance.
- **Inspect as you go.** Frayed cords, cracked handles, dull blades, and wobbly chucks get tagged "out of service" and reported — never quietly returned to the drawer.
- **Protect precision instruments.** Calipers live in their case, not loose in a bin. Drop a caliper once and its accuracy may be gone for good.
- **Charge and rotate batteries** for cordless tools so a dead battery never stalls the team.

## Software Is a Tool Too

Some of the most important tools in robotics never touch the robot:

- **CAD (computer-aided design)** software — such as Tinkercad, Onshape, or Fusion 360 — lets you design and test-fit parts on screen before cutting any material. Finding a mistake in CAD costs minutes; finding it in metal costs a rebuild.
- **Circuit simulators** like Tinkercad Circuits let you wire up an Arduino-style microcontroller, LEDs, and sensors virtually — and even run code — with zero risk of frying real components.
- **Version control and shared documents** keep the whole team working from the same design instead of three conflicting copies.

Treat software tools like physical ones: learn them properly, keep your files organized, and save your work often.'''
            }
        ])
        self._create_lesson_questions(lesson, [
            {
                'text': 'Which measuring tool can read to 0.01 mm and measure outside width, inside diameter, and depth?',
                'choices': [
                    ('Digital calipers', True),
                    ('A steel ruler', False),
                    ('A tape measure', False),
                    ('A protractor', False),
                ]
            },
            {
                'text': 'A drawing calls for a part that is 10 mm ± 0.2 mm. Which measured part is acceptable?',
                'choices': [
                    ('10.1 mm', True),
                    ('10.4 mm', False),
                    ('9.7 mm', False),
                    ('Only a part measuring exactly 10.0 mm', False),
                ]
            },
            {
                'text': 'Which fastener is the best choice for a drivetrain joint that vibrates constantly?',
                'choices': [
                    ('A machine screw with a nylon-insert lock nut', True),
                    ('A zip tie', False),
                    ('A Velcro strap', False),
                    ('A self-tapping screw in plastic, tightened as hard as possible', False),
                ]
            },
            {
                'text': 'Why do robotics teams build designs in CAD software before cutting real material?',
                'choices': [
                    ('Mistakes found on screen cost minutes to fix instead of a rebuild', True),
                    ('CAD files are required before any tool may be used', False),
                    ('Software designs never contain errors', False),
                    ('It is the only way to know what color the robot will be', False),
                ]
            }
        ])

        # Lesson 3: Managing a Robotics Project
        lesson = Lesson.objects.create(unit=unit, title='Managing a Robotics Project', order=2)
        self._create_sections(lesson, [
            {
                'title': 'Overview',
                'content': '''# Managing a Robotics Project

Great robots are rarely built by the team with the best ideas — they are built by the team that manages its time. This lesson gives you the project management toolkit engineers actually use: phases, schedules, milestones, task assignments, and the engineering notebook that ties it all together.

## Learning Objectives

By the end of this lesson, you will be able to:
- Name and describe the four phases of a project: define, plan, execute, review
- Break a project into tasks, set milestones, and read a simple Gantt chart
- Assign tasks fairly and track progress as a team
- Keep an engineering notebook that documents decisions, tests, and results

> **TEKS alignment:** §127.749(c)(4) — The student applies project management concepts, including planning, scheduling, and documenting work, to complete projects.'''
            },
            {
                'title': 'The Four Project Phases',
                'content': '''# The Four Project Phases

Every project — a competition robot, an app, a bridge — moves through the same four phases. Skipping one is how projects fail.

## 1. Define

Ask: **what exactly are we building, and how will we know it works?** Write down the goal, the requirements, and the constraints (deadline, budget, parts available). A goal like "build a robot that can lift a 200 g cube 30 cm in under 5 seconds" is testable. "Build a cool robot" is not.

## 2. Plan

Break the goal into tasks, estimate how long each takes, decide the order, and assign owners. This is where schedules, milestones, and Gantt charts live. Teams that skip planning do not save time — they just move the chaos to the last week.

## 3. Execute

Build, code, and test — **following the plan**, and updating it when reality disagrees. Reality always disagrees somewhere: a part arrives late, a mechanism does not fit. Good teams adjust the plan on purpose instead of abandoning it.

## 4. Review

After the deadline (or the competition), look back: What worked? What went wrong? What will we do differently next time? Engineers call this a **retrospective** or post-mortem. Ten honest minutes of review is worth more than a week of guessing on the next project.

> The phases loop. The review of this project becomes the definition of the next one — that is how teams improve season after season.'''
            },
            {
                'title': 'Schedules, Milestones, and Gantt Charts',
                'content': '''# Schedules, Milestones, and Gantt Charts

## Milestones

A **milestone** is a checkpoint with a date and a clear "done" test: *drive base moving by Feb 14*, *arm lifts a cube by Feb 28*. Milestones turn one scary deadline into a series of small, checkable ones — and tell you that you are behind while there is still time to fix it.

## The Gantt Chart

A **Gantt chart** lays tasks down the left side and time across the top. Each bar shows when a task starts and ends, so overlaps and bottlenecks are visible at a glance. Here is a mini Gantt chart for a four-week build:

| Task | Week 1 | Week 2 | Week 3 | Week 4 |
|------|--------|--------|--------|--------|
| Define requirements | X | | | |
| Design in CAD | X | X | | |
| Build drive base | | X | X | |
| Write drive code | | X | X | |
| Attach arm + test | | | X | X |
| Practice + fix bugs | | | | X |

Read it like a story: design overlaps the end of requirements, building and coding run **in parallel** (different people, same weeks), and the last week is protected for practice — not for building.

## Scheduling Rules That Save Teams

- **Schedule backward from the deadline**, and leave buffer. Something always takes longer than planned.
- **Put testing on the schedule.** "We will test if there is time" means you will not test.
- **Watch the dependencies.** Code cannot be tested on a drive base that is not built — so the drive base is on the critical path.'''
            },
            {
                'title': 'Task Assignment and Tracking Progress',
                'content': '''# Task Assignment and Tracking Progress

## Assigning Tasks

A task without an owner belongs to no one. For every task, decide:

- **Who owns it** — one name, even if others help
- **What "done" means** — "arm code done" is vague; "arm raises to 30 cm on button press" is testable
- **When it is due** — tied to a milestone

Assign by a mix of **strength and growth**: your best programmer should not write every line, or you graduate one programmer and lose the skill. Pair an experienced member with a learner on important tasks.

## Tracking Progress

Plans go stale in days unless the team checks in. Two lightweight habits keep everyone honest:

1. **The stand-up.** Start each meeting with a 5-minute round: each person says what they finished, what they are doing next, and what is blocking them. Blockers are the whole point — a blocked task caught today costs one day, not a week.
2. **The task board.** Three columns — **To Do, In Progress, Done** — on a whiteboard with sticky notes or in a free tool like Trello. Sliding a note to Done feels good; a crowded In Progress column is a warning sign that the team has started everything and finished nothing.

## When You Fall Behind

Every team falls behind. The professional response is to say so early and re-plan: cut a nice-to-have feature, move a person to the critical path, or simplify a mechanism. Hiding a slip until the deadline is the one unforgivable project-management sin.'''
            },
            {
                'title': 'The Engineering Notebook',
                'content': '''# The Engineering Notebook

The **engineering notebook** is the project management tool that outlives the project. It is the team's official record of what was decided, built, tested, and learned — and in competitions like VEX and FIRST, judges score it directly.

## What Goes In

- **Date and attendees** for every session
- **Decisions and the reasons behind them** — "chose 4 omni wheels *because* turning was slipping with 2" is worth ten pages of description
- **Sketches and calculations** — quick drawings with dimensions beat perfect art
- **Test results** — what you tried, what happened, including the failures. Failed tests are data, not embarrassments
- **Plan updates** — milestones hit or moved, tasks reassigned

## Rules of a Good Notebook

1. **Write during the work, not from memory.** A messy entry made today beats a neat one invented next week.
2. **Never erase.** Cross out mistakes with a single line so the history stays readable. In professional engineering, notebooks are legal documents used to prove who invented what, and when.
3. **Make it findable.** Number the pages and keep a table of contents so "where did we write down the gear ratio?" takes seconds, not a meeting.

## Why It Matters Beyond the Grade

Six weeks from now, nobody will remember why the team abandoned the first arm design. The notebook will. Teams with good records fix problems once; teams without them fix the same problem every season.'''
            }
        ])
        self._create_lesson_questions(lesson, [
            {
                'text': 'Which sequence lists the four project phases in the correct order?',
                'choices': [
                    ('Define, plan, execute, review', True),
                    ('Execute, plan, define, review', False),
                    ('Plan, review, define, execute', False),
                    ('Define, execute, plan, review', False),
                ]
            },
            {
                'text': 'What does a Gantt chart show?',
                'choices': [
                    ('When each task starts and ends across the project timeline', True),
                    ('How much each team member is paid', False),
                    ('The electrical wiring diagram of the robot', False),
                    ('Which parts of the robot weigh the most', False),
                ]
            },
            {
                'text': 'What is a milestone in a project schedule?',
                'choices': [
                    ('A dated checkpoint with a clear, testable definition of done', True),
                    ('Any task that takes more than one week', False),
                    ('The list of tools the project requires', False),
                    ('A penalty for missing the final deadline', False),
                ]
            },
            {
                'text': 'You make an error in your engineering notebook. What is the correct way to handle it?',
                'choices': [
                    ('Cross it out with a single line so it stays readable', True),
                    ('Erase it completely or use correction fluid', False),
                    ('Tear out the page and rewrite it', False),
                    ('Leave errors unmarked so the notebook looks complete', False),
                ]
            }
        ])

        self._create_unit2_quiz(unit)

    def _create_unit2_quiz(self, unit):
        quiz = Quiz.objects.create(
            unit=unit,
            title='Safety, Tools & Project Management Quiz',
            description='Show what you know about lab safety, choosing and maintaining tools, precision measurement, and managing a robotics project.',
            passing_score=70,
            points=20,
            max_attempts=3,
            order=0
        )
        questions = [
            {
                'text': 'Why is PPE such as safety glasses called the "last line of defense"?',
                'choices': [
                    ('It protects you only when other safeguards, like guards and safe procedures, fail', True),
                    ('It should only be worn after an accident happens', False),
                    ('It replaces the need for training and machine guards', False),
                    ('It is the least important safety measure', False),
                ]
            },
            {
                'text': 'Which practice is required when charging a LiPo battery?',
                'choices': [
                    ('Charge it in a LiPo-safe bag or fireproof container with someone present', True),
                    ('Charge it overnight while the lab is empty', False),
                    ('Use any charger that fits the connector', False),
                    ('Charge it on carpet to prevent it from sliding', False),
                ]
            },
            {
                'text': 'Exactly how many millimeters are in one inch?',
                'choices': [
                    ('25.4 mm', True),
                    ('10 mm', False),
                    ('2.54 mm', False),
                    ('100 mm', False),
                ]
            },
            {
                'text': 'What does a tolerance of ± 0.2 mm on a 10 mm dimension mean?',
                'choices': [
                    ('Any size from 9.8 mm to 10.2 mm is acceptable', True),
                    ('The part must be exactly 10.2 mm', False),
                    ('The part may be any size under 10 mm', False),
                    ('The part must be measured 0.2 seconds after cutting', False),
                ]
            },
            {
                'text': 'During which project phase does the team break the goal into tasks, estimate times, and assign owners?',
                'choices': [
                    ('Plan', True),
                    ('Define', False),
                    ('Execute', False),
                    ('Review', False),
                ]
            },
            {
                'text': 'Why do robotics teams keep an engineering notebook?',
                'choices': [
                    ('It records decisions, tests, and reasons so the team can learn from and prove its work', True),
                    ('It is only used to track which students attended each meeting', False),
                    ('It replaces the need to test the robot', False),
                    ('It is where finished code is stored instead of a computer', False),
                ]
            },
        ]
        self._create_quiz_questions(quiz, questions)

    # ================== UNIT 3: Mechanisms & the Physics of Motion ==================
    def _create_unit3(self, course):
        unit = Unit.objects.create(course=course, title='Mechanisms & the Physics of Motion', order=2)

        # Lesson 1: Newton's Laws for Robots
        lesson = Lesson.objects.create(unit=unit, title="Newton's Laws for Robots", order=0)
        self._create_sections(lesson, [
            {
                'title': 'Overview',
                'content': '''# Newton's Laws for Robots

Why does a heavy robot lurch when it stops? Why do wheels spin out on a slick floor? Isaac Newton answered these questions over 300 years ago, and his three laws of motion still decide whether your robot wins or tips over.

## Learning Objectives

By the end of this lesson, you will be able to:
- State Newton's three laws of motion and connect each one to robot behavior
- Use `F = ma` to reason about how mass affects a robot's acceleration
- Explain how friction and traction determine whether wheels grip or slip
- Distinguish between mass and weight and explain why the difference matters

> **TEKS alignment:** §127.749(c)(7) — apply concepts of physics such as motion, forces, and energy to robotic systems.'''
            },
            {
                'title': "Newton's First Law: Inertia",
                'content': '''# Newton's First Law: Inertia

**An object at rest stays at rest, and an object in motion stays in motion, unless acted on by an outside force.**

This tendency to resist changes in motion is called **inertia**, and the more mass an object has, the more inertia it has.

## What This Means for Robots

- A **heavy robot** takes real force to get moving — and just as much force to stop. If your drivetrain cuts power, the robot keeps coasting until friction drags it to a halt.
- A robot carrying a load up high (say, a lifted arm holding a game piece) has a lot of inertia far from its wheels. Stop suddenly and that mass *wants* to keep going forward — which is how robots tip over.
- Lightweight robots change direction quickly. Heavy robots are hard to push around by opponents. Both are consequences of the same law.

## Design Takeaways

| Situation | First-law effect |
|-----------|------------------|
| Sudden stop | Robot pitches forward; tall loads may tip it |
| Sudden start | Wheels may slip before the frame accelerates |
| Getting bumped | High-mass robots barely move; low-mass robots get shoved |

A common trick in competition robotics is to **ramp** motor power up and down gradually instead of slamming it from 0 to 100. That gives friction time to keep up with inertia, so the robot accelerates smoothly instead of jerking or tipping.'''
            },
            {
                'title': "Newton's Second Law: F = ma",
                'content': '''# Newton's Second Law: F = ma

The second law is an equation you can actually calculate with:

`F = m x a`  (force = mass x acceleration)

Rearranged for acceleration:

`a = F / m`

## Reading the Equation Like a Robot Builder

- **More force, more acceleration.** Stronger motors (or better gearing) push the robot forward harder.
- **More mass, less acceleration.** Every part you bolt on makes the same motors accelerate the robot more slowly.

## A Quick Example

Suppose your drivetrain can apply 20 newtons (N) of force to the floor.

- Robot mass 5 kg: `a = 20 / 5 = 4 m/s^2`
- Robot mass 10 kg: `a = 20 / 10 = 2 m/s^2`

Double the mass, half the acceleration — with the exact same motors.

## Why Builders Obsess Over Weight

This is why competitive teams weigh every component. Metal structure adds strength but costs acceleration. Batteries are heavy but necessary. The design question is never just "will it fit?" — it is "is this part worth its mass?"

The second law also explains **braking**: stopping is just acceleration in the reverse direction. A heavier robot needs more force (and more distance) to stop, which matters when the goal is inches from a wall.'''
            },
            {
                'title': "Newton's Third Law: Action and Reaction",
                'content': '''# Newton's Third Law: Action and Reaction

**For every action, there is an equal and opposite reaction.**

Forces always come in pairs. When object A pushes on object B, object B pushes back on A with the same strength in the opposite direction.

## How Robots Actually Move

Here is the surprising part: a robot's wheels do not push the robot forward. They push the **floor backward**, and the floor pushes the **robot forward**. No backward push on the ground, no forward motion — which is why a robot on ice or a freshly waxed floor spins its wheels and goes nowhere.

The same is true for:

- **Tank treads** — each tread segment grips the ground and shoves it backward; the ground shoves the robot ahead.
- **Robot arms** — when an arm pushes down hard on an object, the object pushes back up on the arm and frame. Push hard enough and the reaction force can lift the robot's own wheels off the ground.
- **Launchers** — a robot that flings a ball forward gets kicked backward. Small ball, big robot, small kick — but it is there, and precision shooters have to account for it.

## Spotting Reaction Forces

A good habit: whenever your robot exerts a force, ask "what pushes back, and on what?" If the reaction force lands somewhere your frame is weak — a loose axle, a flimsy bracket — that is where things bend or break first.'''
            },
            {
                'title': 'Friction, Traction, Mass and Weight',
                'content': '''# Friction, Traction, Mass and Weight

## Friction: Enemy and Best Friend

**Friction** is the force that resists sliding between two surfaces. In a drivetrain it plays both roles:

- **Friction you want (traction):** grip between wheels and floor. Without it, wheels spin uselessly (Newton's third law needs something to push against).
- **Friction you do not want:** rubbing in axles, bearings, and gears. This wastes motor power as heat and slows everything down.

Traction depends on two things: the **materials** touching (rubber on foam mats grips far better than plastic on tile) and the **force pressing them together**. That is one reason a slightly heavier robot can actually drive better — its weight presses the wheels into the floor harder.

## Mass vs Weight

These get mixed up constantly, but they are different:

| Property | What it is | Units | Changes on the Moon? |
|----------|------------|-------|----------------------|
| **Mass** | Amount of matter; resistance to acceleration | kilograms (kg) | No |
| **Weight** | Force of gravity pulling on that mass | newtons (N) | Yes — about 1/6 |

Weight is calculated as `W = m x g`, where `g` is about `9.8 m/s^2` on Earth. A 5 kg robot weighs about 49 N here, but only about 8 N on the Moon — yet it would be exactly as hard to accelerate, because its **mass** is unchanged.

For Earth-bound robots the practical summary: mass determines how sluggish your robot is; weight determines how hard it presses on its wheels, and therefore how much traction it can get.'''
            }
        ])
        self._create_lesson_questions(lesson, [
            {
                'text': "A robot moving at full speed suddenly cuts power to its motors but keeps rolling forward for a moment. Which of Newton's laws best explains this?",
                'choices': [
                    ('The first law — the robot has inertia and stays in motion until friction stops it', True),
                    ('The second law — cutting power increases the force on the robot', False),
                    ('The third law — the floor pushes the robot forward when power is cut', False),
                    ('None — Newton\'s laws only apply to objects at rest', False),
                ]
            },
            {
                'text': 'A drivetrain applies 30 N of force. Using a = F / m, what is the acceleration of a 6 kg robot?',
                'choices': [
                    ('5 m/s^2', True),
                    ('180 m/s^2', False),
                    ('0.2 m/s^2', False),
                    ('36 m/s^2', False),
                ]
            },
            {
                'text': "According to Newton's third law, what actually pushes a wheeled robot forward?",
                'choices': [
                    ('The floor, reacting to the wheels pushing backward against it', True),
                    ('The motor shaft pushing directly on the frame', False),
                    ('Air pressure behind the robot', False),
                    ('The battery discharging energy forward', False),
                ]
            },
            {
                'text': 'Which statement about mass and weight is correct?',
                'choices': [
                    ('Mass stays the same on the Moon, but weight decreases', True),
                    ('Mass and weight are two names for the same thing', False),
                    ('Weight is measured in kilograms and mass in newtons', False),
                    ('Weight stays the same everywhere, but mass changes with gravity', False),
                ]
            }
        ])

        # Lesson 2: Simple Machines & Mechanical Advantage
        lesson = Lesson.objects.create(unit=unit, title='Simple Machines & Mechanical Advantage', order=1)
        self._create_sections(lesson, [
            {
                'title': 'Overview',
                'content': '''# Simple Machines & Mechanical Advantage

Every robot mechanism — arms, lifts, intakes, claws — is built from a handful of ancient inventions called **simple machines**. Understand these six building blocks and you can look at any robot and see how it multiplies force.

## Learning Objectives

By the end of this lesson, you will be able to:
- Identify the six classical simple machines and find them in robot designs
- Classify levers into first, second, and third class by the position of the fulcrum
- Calculate mechanical advantage using `MA = load / effort` and distance ratios
- Explain the trade-off: multiplying force means moving a greater distance

> **TEKS alignment:** §127.749(c)(7) — apply physics concepts including simple machines and mechanical advantage to robotic systems.'''
            },
            {
                'title': 'Levers and Lever Classes',
                'content': '''# Levers and Lever Classes

A **lever** is a rigid bar that pivots on a point called the **fulcrum**. You apply an **effort** force at one spot, and the lever moves a **load** somewhere else. Levers are everywhere on robots — arms, flippers, latches, and lifts are all levers in disguise.

## The Three Classes

The class of a lever depends on what sits in the middle:

| Class | In the middle | Everyday example | Robot example |
|-------|---------------|------------------|---------------|
| First | Fulcrum | Seesaw, crowbar | A pivoting arm counterweighted behind its pivot |
| Second | Load | Wheelbarrow | A flipper that pries a game piece up, pivot at the front edge |
| Third | Effort | Tweezers, your forearm | A motor mounted near the pivot swinging a long arm |

## Force vs Distance

- **First and second class** levers can multiply force: a small effort moves a big load, as long as the effort acts farther from the fulcrum than the load does.
- **Third class** levers do the opposite — they *reduce* force but *increase* speed and reach. That sounds like a bad deal, but it is exactly what a robot arm usually wants: the motor is near the pivot, and the far end sweeps quickly through a big arc.

## The Lever Rule

The balance condition is:

`effort x effort-arm = load x load-arm`

A 10 N effort applied 0.4 m from the fulcrum can hold a 40 N load placed 0.1 m from the fulcrum, because `10 x 0.4 = 40 x 0.1`. Longer arm on your side of the fulcrum means more lifting power.'''
            },
            {
                'title': 'Pulleys and Wheel-and-Axle',
                'content': '''# Pulleys and Wheel-and-Axle

## Pulleys

A **pulley** is a wheel with a rope, cable, or belt running over it.

- A **single fixed pulley** does not multiply force — it just redirects it. Pulling down 10 N lifts 10 N up. Useful when your motor is at the bottom of the robot but the load goes up (like a cascading lift).
- A **movable pulley** rides on the rope with the load. Now **two** rope segments share the weight, so the effort is roughly halved: mechanical advantage of 2.
- **Combining pulleys** (a block and tackle) stacks the effect. Count the rope segments supporting the load — that count is the ideal mechanical advantage. Four supporting segments means you pull with 1/4 the force... but you must pull 4 times as much rope.

Robot lifts and elevators very often use pulley-and-string (or chain) systems because a single motor at the base can drive multiple lift stages.

## Wheel-and-Axle

A **wheel-and-axle** is a large wheel rigidly attached to a smaller axle so they turn together. Think of a doorknob or a screwdriver handle.

- Turn the **big wheel** and the axle turns with multiplied force — that is a steering wheel.
- Turn the **axle** (as a motor does) and the wheel rim moves faster but with less force — that is every drive wheel on a robot.

Its mechanical advantage is the ratio of the radii: `MA = wheel radius / axle radius`. Notice this is the reverse trade-off of a drive wheel: bigger drive wheels give you more floor speed but less pushing force from the same motor. That trade-off returns in full force in the next lesson on gears.'''
            },
            {
                'title': 'Inclined Planes, Wedges, and Screws',
                'content': '''# Inclined Planes, Wedges, and Screws

The last three simple machines are all really the same idea — a slope — used three different ways.

## Inclined Plane (Ramp)

Rolling a load up a **ramp** takes less force than lifting it straight up, in exchange for moving it a longer distance. The gentler the slope, the bigger the advantage:

`MA = ramp length / ramp height`

A 2 m ramp rising 0.5 m has `MA = 2 / 0.5 = 4`: you push with about 1/4 the force of a straight lift. Robots meet inclined planes constantly — driving up field ramps, or using a sloped intake surface that guides game pieces upward as the robot drives forward.

## Wedge

A **wedge** is a moving inclined plane. Instead of the load moving up the slope, the slope drives into the load and pushes it sideways. Axe blades and doorstops are wedges. On robots, wedges show up as:

- **Passive intakes** that slide under a game piece and pop it up off the floor
- **Defensive skirts** — angled panels that make opposing robots ride up your frame instead of pushing you

## Screw

A **screw** is an inclined plane wrapped around a cylinder. Each full turn advances the screw by one thread spacing (the **pitch**), which is a tiny distance — so the force multiplication is huge. Robot uses include:

- **Lead screws** that turn motor rotation into slow, strong, precise linear motion for lifts
- Ordinary **fasteners**, where the screw's advantage is what lets a small wrench clamp parts together tightly

All three trade distance for force, exactly like levers and pulleys: nothing is free, the work is just spread over a longer path.'''
            },
            {
                'title': 'Computing Mechanical Advantage',
                'content': '''# Computing Mechanical Advantage

**Mechanical advantage (MA)** is a plain number that answers: *how many times does this machine multiply my force?*

`MA = load force / effort force`

An MA of 4 means the machine turns 10 N of effort into 40 N of output.

## The Universal Trade-off

Simple machines do not create energy. If force goes up 4x, the distance you move must go down 4x:

`effort distance = MA x load distance`

This is why you can also compute ideal MA from distances alone:

`MA = effort distance / load distance`

## Worked Examples

**Lever:** Effort applied 0.6 m from the fulcrum, load 0.2 m from it.

- `MA = 0.6 / 0.2 = 3`
- A 15 N push can lift a load of up to `15 x 3 = 45 N`.

**Pulley system:** 3 rope segments support the load.

- `MA = 3`
- Lifting a 60 N load takes about `60 / 3 = 20 N` of pull — but raising the load 0.5 m requires pulling `3 x 0.5 = 1.5 m` of rope.

**Ramp:** 1.8 m long, 0.6 m high.

- `MA = 1.8 / 0.6 = 3`

## Real Machines Lose a Little

Friction always eats some of the effort, so **actual** MA is a bit lower than the ideal numbers above. Engineers compare the two as **efficiency**: `efficiency = actual MA / ideal MA`. A well-built pulley lift might reach 90 percent; a dry, gritty lead screw might waste half its input. Keeping joints clean and aligned is not just tidiness — it is free force.'''
            }
        ])
        self._create_lesson_questions(lesson, [
            {
                'text': 'In a second-class lever, what is located between the fulcrum and the effort?',
                'choices': [
                    ('The load', True),
                    ('The fulcrum', False),
                    ('A second effort force', False),
                    ('Nothing — second-class levers have no load', False),
                ]
            },
            {
                'text': 'A pulley system has 4 rope segments supporting the load. About how much effort is needed to lift an 80 N load, and what is the catch?',
                'choices': [
                    ('About 20 N, but you must pull 4 times as much rope', True),
                    ('About 320 N, but the load moves 4 times faster', False),
                    ('About 80 N — pulleys never change the required force', False),
                    ('About 4 N, with no trade-off at all', False),
                ]
            },
            {
                'text': 'A ramp is 3 m long and rises 1 m. What is its ideal mechanical advantage?',
                'choices': [
                    ('3', True),
                    ('1/3', False),
                    ('4', False),
                    ('2', False),
                ]
            },
            {
                'text': 'Why do many robot arms use a third-class lever arrangement even though it reduces force?',
                'choices': [
                    ('The far end of the arm moves faster and sweeps a larger arc', True),
                    ('Third-class levers multiply force more than any other class', False),
                    ('It eliminates the need for a fulcrum', False),
                    ('It removes all friction from the joint', False),
                ]
            }
        ])

        # Lesson 3: Gears, Torque & Speed
        lesson = Lesson.objects.create(unit=unit, title='Gears, Torque & Speed', order=2)
        self._create_sections(lesson, [
            {
                'title': 'Overview',
                'content': '''# Gears, Torque & Speed

A motor gives you one combination of spin speed and turning force. Gears let you trade one for the other — the single most important tool a robot builder has for matching a motor to a job.

## Learning Objectives

By the end of this lesson, you will be able to:
- Calculate a gear ratio from tooth counts and predict output speed and torque
- Explain the torque-vs-speed trade-off and choose a ratio for a given task
- Trace compound gear trains and multiply their stage ratios
- Compare gears, sprockets-and-chain, and belts-and-pulleys for transferring rotation

> **TEKS alignment:** §127.749(c)(7) — apply physics concepts of motion, force, and mechanical advantage to robotic drive systems.'''
            },
            {
                'title': 'Gear Ratios',
                'content': '''# Gear Ratios

A **gear** is a wheel with teeth. Mesh two gears together and turning one turns the other — in the opposite direction, and usually at a different speed.

## Counting Teeth

The **gear ratio** compares the driven (output) gear to the driving (input) gear:

`gear ratio = teeth on driven gear : teeth on driving gear`

**Example:** a 12-tooth gear on the motor drives a 36-tooth gear on the wheel.

`ratio = 36 : 12 = 3 : 1`

Read "3 to 1": the motor turns **3 times** for every **1 turn** of the wheel.

## What the Ratio Does

- **Output speed** is divided by the ratio: a motor spinning at 300 RPM through a 3:1 ratio turns the wheel at `300 / 3 = 100 RPM`.
- **Output torque** is multiplied by the ratio: the wheel turns with about 3x the motor's torque (minus a little friction).

This is called **gearing down** (or a torque ratio). Flip the gears — big gear on the motor, small gear on the output — and you get **gearing up** (a speed ratio): a 12:36 arrangement gives `1:3`, tripling speed but cutting torque to a third.

## Terms to Know

- **Driving gear (input):** the one the motor turns
- **Driven gear (output):** the one connected to the mechanism
- **Idler gear:** a gear in between that changes the spin direction back but does **not** change the ratio — only the first and last gears matter for the math

Gear teeth must be the same size (same pitch) to mesh. You cannot mix tooth sizes on the same pair.'''
            },
            {
                'title': 'The Torque vs Speed Trade-off',
                'content': '''# The Torque vs Speed Trade-off

**Torque** is rotational force — the twisting strength of a shaft, measured in newton-meters (N-m). **Speed** here means rotational speed, usually RPM (revolutions per minute).

Gears cannot increase both. The product of torque and speed is set by the motor's power, so every ratio is a trade:

`output torque = input torque x ratio`
`output speed  = input speed / ratio`

## One Motor, Three Gearings

Take a motor producing 0.5 N-m at 200 RPM:

| Ratio | Output torque | Output speed | Good for |
|-------|---------------|--------------|----------|
| 1:3 (geared up) | 0.17 N-m | 600 RPM | Flywheels, fast light spinners |
| 1:1 (direct) | 0.5 N-m | 200 RPM | Balanced, general drivetrain |
| 5:1 (geared down) | 2.5 N-m | 40 RPM | Arms, lifts, pushing matches |

Same motor, wildly different personalities.

## Choosing a Ratio

Ask two questions:

1. **Does the mechanism ever stall?** Arms holding a load and robots pushing against walls need torque headroom. If the motor stalls (stops while powered), it overheats and drains the battery — gear down until it does not.
2. **How fast does it really need to move?** Speed you never use is torque you threw away. A lift that only travels half a meter does not need to travel it at highway speed.

Rule of thumb: when in doubt, gear down. A slightly slow robot finishes the task; a stalled robot finishes nothing.'''
            },
            {
                'title': 'Gear Trains',
                'content': '''# Gear Trains

One pair of gears can only give you so much. Need a 25:1 reduction? A 25-times-bigger gear will not fit on the robot. The answer is a **gear train**: several gear pairs in a row.

## Compound Gearing

In a **compound gear train**, two gears share each middle axle: a big gear receives power, and a small gear on the *same shaft* passes it on to the next stage. The stage ratios **multiply**:

`total ratio = stage 1 ratio x stage 2 ratio x ...`

**Example:** two stages, each 12-tooth driving 60-tooth.

- Each stage: `60 / 12 = 5:1`
- Total: `5 x 5 = 25:1`

A motor at 500 RPM comes out at `500 / 25 = 20 RPM` with roughly 25x the torque — from four modest gears.

## Simple vs Compound

- A **simple train** (one gear meshing with the next in a line) has its ratio set only by the first and last gears; the middle ones are idlers that just fill space and flip direction.
- A **compound train** (paired gears sharing shafts) multiplies every stage — this is how small gearboxes reach big numbers like 100:1.

## Watching for Losses

Each mesh loses a few percent of power to friction, so a five-stage train might waste 15 to 20 percent of the motor's effort. More stages also add **backlash** — the tiny slop between teeth — which makes precise positioning harder. Use the fewest stages that reach your target ratio.'''
            },
            {
                'title': 'Sprockets, Chains, and Belts',
                'content': '''# Sprockets, Chains, and Belts

Gears must touch to work. When the motor and the mechanism are far apart, you have two classic options for sending rotation across the gap.

## Sprockets and Chain

A **sprocket** is a toothed wheel that grips a **chain** — a bicycle drivetrain is the everyday example. The ratio works exactly like gears, using sprocket tooth counts:

`ratio = driven sprocket teeth : driving sprocket teeth`

- **Pros:** no slipping (positive drive), handles high torque, spans long distances, both shafts turn the **same** direction
- **Cons:** heavier than a belt, noisier, needs correct tension, can derail if misaligned

Chains are the usual choice for drivetrains — sending one motor's power to front and back wheels on the same side, for instance.

## Belts and Pulleys

A **belt** is a flexible loop running over smooth or toothed pulleys.

- **Pros:** lightweight, quiet, smooth; a plain belt can even slip on purpose, acting as a built-in clutch that protects the motor during a jam
- **Cons:** smooth belts slip under high load (bad when you need exact motion); toothed **timing belts** fix the slipping but still transmit less torque than chain

Belts shine on fast, low-torque jobs like spinning intake rollers and flywheels.

## Choosing at a Glance

| Need | Best pick |
|------|-----------|
| Short distance, high precision | Gears |
| Long distance, high torque | Sprockets and chain |
| Long distance, high speed, low weight | Belt and pulleys |
| Built-in overload protection | Smooth belt (intentional slip) |

Many real robots use all three — gears in the gearbox, chain to the wheels, belts on the intake.'''
            }
        ])
        self._create_lesson_questions(lesson, [
            {
                'text': 'A 12-tooth gear on a motor drives a 60-tooth gear on an arm. What is the gear ratio, and what does it do?',
                'choices': [
                    ('5:1 — the arm turns 5 times slower but with about 5 times the torque', True),
                    ('5:1 — the arm turns 5 times faster with 5 times the torque', False),
                    ('1:5 — the arm turns 5 times faster but with less torque', False),
                    ('1:1 — tooth counts never change speed or torque', False),
                ]
            },
            {
                'text': 'A motor spins at 400 RPM. After a 4:1 gear reduction, what is the output speed?',
                'choices': [
                    ('100 RPM', True),
                    ('1600 RPM', False),
                    ('400 RPM', False),
                    ('40 RPM', False),
                ]
            },
            {
                'text': 'What does an idler gear placed between the driving and driven gears change?',
                'choices': [
                    ('Only the direction of rotation — not the overall ratio', True),
                    ('The overall gear ratio, multiplying it by its own tooth count', False),
                    ('The torque, but not the speed', False),
                    ('Nothing at all — idler gears are purely decorative', False),
                ]
            },
            {
                'text': 'Which power-transfer choice is best for a fast, lightweight intake roller far from its motor, where occasional jams should not stall the motor?',
                'choices': [
                    ('A belt, since it is light and can slip during a jam like a clutch', True),
                    ('A chain, since it can never slip under any load', False),
                    ('Direct gear mesh, since gears span long distances best', False),
                    ('A lead screw, since it maximizes roller speed', False),
                ]
            }
        ])

        # Lesson 4: Motors: DC vs Servo
        lesson = Lesson.objects.create(unit=unit, title='Motors: DC vs Servo', order=3)
        self._create_sections(lesson, [
            {
                'title': 'Overview',
                'content': '''# Motors: DC vs Servo

Motors are the muscles of a robot — they turn electrical energy into motion. This lesson looks inside the two motor types you will meet first, and gives you a checklist for picking the right one for a mechanism.

## Learning Objectives

By the end of this lesson, you will be able to:
- Explain, at an introductory level, how electromagnetism makes a DC motor spin
- Describe why gearmotors pair a fast DC motor with a reduction gearbox
- Contrast continuous-rotation DC motors with position-controlled servo motors
- Choose between motor options by comparing torque, speed, and power draw

> **TEKS alignment:** §127.749(c)(7) — apply concepts of physics, including electricity and energy conversion, to robotic actuators.'''
            },
            {
                'title': 'How a DC Motor Works',
                'content': '''# How a DC Motor Works

**DC** stands for direct current — the steady, one-direction electricity a battery provides. A DC motor turns that current into continuous rotation using one physics fact:

**A wire carrying current through a magnetic field feels a force.**

## The Recipe Inside the Case

1. **Permanent magnets** line the inside of the motor housing, creating a magnetic field.
2. A **coil of wire** (the armature) sits on the spinning shaft between the magnets.
3. Current flows through the coil, the field pushes one side of the coil up and the other side down — and the shaft starts to turn.
4. A small switch on the shaft called a **commutator** reverses the current direction every half turn, so the push always acts the same way around. Without it, the coil would just wiggle to a stop; with it, the motor spins continuously.

## Controlling a DC Motor

- **More voltage, more speed.** Robot controllers fake in-between voltages by switching power on and off very fast (called PWM, pulse-width modulation).
- **Reverse the current, reverse the spin.** Swap the two wires and the motor runs backward.
- **Load it down and it draws more current.** A motor forced to a stop while powered (a **stall**) pulls maximum current, gets hot fast, and can burn out. Stalling is the number-one way beginners kill motors.

An electric current creating motion through magnetism is the same principle behind speakers and hard-drive arms — robots just use it with a shaft attached.'''
            },
            {
                'title': 'Gearmotors: Adding Torque',
                'content': '''# Gearmotors: Adding Torque

A bare DC motor has an awkward personality: it loves to spin **very fast** — often 5,000 to 15,000 RPM — but with almost no torque. Pinch the bare shaft of a small hobby motor with two fingers and you can stop it. That combination is nearly useless for robots: no wheel needs 10,000 RPM, and no arm lifts anything with fingertip-stoppable torque.

## The Fix: Build the Gearbox In

A **gearmotor** is simply a DC motor with a compound gear train (from the last lesson) sealed onto its output. A typical hobby gearmotor might have a 100:1 reduction:

| | Bare motor | After 100:1 gearbox |
|---|-----------|---------------------|
| Speed | 10,000 RPM | 100 RPM |
| Torque | tiny | about 100x (minus friction) |

100 RPM with real torque is exactly the range wheels and mechanisms live in — which is why nearly every "robot motor" sold for VEX, LEGO, or Arduino projects is secretly a gearmotor.

## Reading a Gearmotor Listing

When you shop for or are issued a gearmotor, three numbers tell most of the story:

- **Rated voltage** — what battery it expects (commonly 6 V or 12 V)
- **No-load speed** — RPM with nothing attached; real speed under load is lower
- **Stall torque** — the twisting force at which it stops completely; never plan to operate near it

Plan mechanisms to run at roughly a quarter to a half of stall torque. That leaves headroom, keeps current draw reasonable, and makes the motor last the season instead of the afternoon.'''
            },
            {
                'title': 'Servo Motors and Position Control',
                'content': '''# Servo Motors and Position Control

A DC gearmotor answers "how fast should I spin?" A **servo motor** answers a different question: "what angle should I hold?"

## What Is Inside a Servo

A standard hobby servo is a clever bundle of three parts in one case:

1. A small **DC motor** (the muscle)
2. A **gear train** (the torque multiplier)
3. A **position sensor** (a potentiometer on the output shaft) plus a tiny **control circuit**

The control circuit constantly compares the shaft's actual angle to the angle you asked for. Off target? It drives the motor toward the target. On target? It holds there — actively pushing back if something tries to move it. This compare-and-correct loop is called **closed-loop control**, and it is your first taste of feedback, one of the biggest ideas in robotics.

## Commanding a Servo

You send a servo a target angle (in code, something like `servo.write(90)` on an Arduino), and it goes there and stays. Most standard servos travel about 0 to 180 degrees — they cannot spin all the way around.

## Where Each Motor Type Wins

| Task | Best choice | Why |
|------|-------------|-----|
| Drive wheels | DC gearmotor | Continuous rotation, speed control |
| Gripper open/close | Servo | Move to an angle and hold it |
| Steering a sensor mount | Servo | Precise, repeatable angles |
| Flywheel launcher | DC motor (geared up) | Raw sustained speed |

A **continuous-rotation servo** is a modified servo that gives up position control to spin freely — handy as a compact, easy-to-command drive motor on small robots, but it is really just a gearmotor in a servo costume.'''
            },
            {
                'title': 'Choosing the Right Motor',
                'content': '''# Choosing the Right Motor

Motor choice is a budgeting problem. Every mechanism needs enough torque and speed, and every motor spends battery current to provide them. Here is a practical checklist.

## 1. Does It Need to Hold a Position?

If yes — gripper, steering, aiming — reach for a **servo**. If it needs continuous rotation — wheels, rollers, flywheels — use a **DC gearmotor** and pick a gear ratio.

## 2. How Much Torque, Really?

Estimate the worst case: the heaviest game piece at the end of the longest arm. Torque needed is roughly `force x distance from the pivot`. Holding 2 N of load 0.3 m from the shoulder takes `2 x 0.3 = 0.6 N-m` — before adding the arm's own weight, which often matters more than the load. Then apply the headroom rule: choose a motor-plus-gearing whose stall torque is at least 2 to 4 times your estimate.

## 3. How Fast Is Fast Enough?

Convert the motion you want into RPM. A drive wheel of circumference 0.3 m at 1.5 m/s must spin at `1.5 / 0.3 = 5` revolutions per second, or 300 RPM. Gear the motor's no-load speed down to land a comfortable margin above that.

## 4. What Will It Cost the Battery?

Torque comes from current. A drivetrain of four motors pushing hard can pull more current than everything else on the robot combined. Symptoms of an overdrawn battery include controller brownouts and resets mid-match. If a mechanism demands huge current, gear it down further — trading speed for torque also trades current draw down.

## The Habit to Build

Write the numbers down *before* building: needed torque, needed speed, chosen ratio, expected current. Robots designed on paper first fail less often — and when they do fail, the numbers tell you why.'''
            }
        ])
        self._create_lesson_questions(lesson, [
            {
                'text': 'What does the commutator in a DC motor do?',
                'choices': [
                    ('Reverses the current in the coil every half turn so the motor keeps spinning one way', True),
                    ('Converts the AC from the battery into DC', False),
                    ('Measures the angle of the shaft for position control', False),
                    ('Increases the voltage supplied to the coil', False),
                ]
            },
            {
                'text': 'Why is nearly every practical robot drive motor a gearmotor rather than a bare DC motor?',
                'choices': [
                    ('Bare DC motors spin very fast with little torque; the gearbox trades speed for usable torque', True),
                    ('Bare DC motors have too much torque and must be geared up to spin at all', False),
                    ('Gearboxes convert DC power into AC power', False),
                    ('Bare DC motors can only rotate 180 degrees', False),
                ]
            },
            {
                'text': 'A robot needs a gripper that moves to a set angle and actively holds it there. Which motor is the best fit?',
                'choices': [
                    ('A standard servo motor, because its closed-loop control holds a commanded angle', True),
                    ('A bare DC motor, because it spins at the highest RPM', False),
                    ('A DC gearmotor, because it cannot be stalled', False),
                    ('A flywheel motor geared up for maximum speed', False),
                ]
            },
            {
                'text': 'What happens when a powered DC motor is stalled (forced to a stop under power)?',
                'choices': [
                    ('It draws maximum current and can overheat and burn out', True),
                    ('It draws zero current and safely waits', False),
                    ('It automatically reverses direction', False),
                    ('It converts the extra energy into higher speed later', False),
                ]
            }
        ])

        # Lesson 5: Arms, Linkages & End Effectors
        lesson = Lesson.objects.create(unit=unit, title='Arms, Linkages & End Effectors', order=4)
        self._create_sections(lesson, [
            {
                'title': 'Overview',
                'content': '''# Arms, Linkages & End Effectors

Driving around is only half of robotics — the other half is interacting with the world. This lesson covers the manipulators that do that work: arms that reach, linkages that guide motion, and the "hands" at the end that actually grab things.

## Learning Objectives

By the end of this lesson, you will be able to:
- Count the degrees of freedom of an arm or mechanism
- Describe how a four-bar linkage guides motion and why builders love it
- Compare end effector types — grippers, claws, suction, and specialized designs — and match them to objects
- Explain how payload and center of gravity limit what an arm (and its robot) can safely do

> **TEKS alignment:** §127.749(c)(8) — design and use manipulators and end effectors to perform robotic tasks.'''
            },
            {
                'title': 'Degrees of Freedom',
                'content': '''# Degrees of Freedom

A **degree of freedom** (DOF) is one independent way a mechanism can move. Every motorized joint an arm has typically adds one DOF.

## Counting DOF

Picture building up an arm one joint at a time:

- **1 DOF:** a single shoulder joint pivots up and down. The arm sweeps one arc — every reachable point lies on that curve.
- **2 DOF:** add an elbow. Now the arm reaches a whole flat region of positions.
- **3 DOF:** add a rotating base. The arm now reaches a 3D volume of space around the robot.

Your own arm, shoulder to wrist, has **7** degrees of freedom — which is why you can hold a cup steady while your elbow moves. Industrial robot arms commonly have **6**, the minimum needed to place an object at any position *and* any orientation within reach.

## More Is Not Automatically Better

Each DOF costs a motor, adds mass out on the arm (which the joints below must lift), adds a joint that can flex or wobble, and adds a value your code must control. Strong designs use the **fewest DOF that accomplish the task**:

| Task | DOF usually needed |
|------|--------------------|
| Flip a game piece over a wall | 1 (a single flipper joint) |
| Pick from the floor, place on a shelf | 2 (shoulder + elbow, or lift + tilt) |
| Place at any position and angle | 6 |

Ask "what motions does the task require?" first — then give the arm exactly those, and no more.'''
            },
            {
                'title': 'Linkages and the Four-Bar',
                'content': '''# Linkages and the Four-Bar

A **linkage** is a set of rigid bars connected by pivots, arranged so that moving one bar makes the others move in a planned, repeatable way. Linkages let one motor produce motion far more useful than a simple swing.

## The Four-Bar Linkage

The star of robot design is the **four-bar linkage**: four bars joined in a loop by four pivots (one "bar" is usually the robot's frame itself). Its famous trick is the **parallel four-bar**: make the two moving side bars the same length and keep them parallel, and the far bar stays at a **constant angle** while it travels.

Why that matters: bolt a tray or claw to the far bar of a parallel four-bar lift, and the tray stays level from the floor to the top of the lift — with zero extra motors and zero code. The geometry itself does the stabilizing. A single-pivot arm, by contrast, tilts its claw more and more as it rises, spilling whatever it carried.

## Where You Have Seen Four-Bars

- Wheelbarrow-style robot lifts that keep a game piece level
- Parallel-jaw grippers whose fingertips stay parallel as they close
- Vehicle hood hinges and desk-lamp arms (the lamp head stays aimed)

## Other Linkages to Recognize

- **Crank-rocker:** a continuously spinning motor bar drives another bar that sweeps back and forth — a way to turn rotation into a repeating wiper or kicker motion.
- **Scissor linkage:** crossed bars in an X pattern that extend like a folding gate, reaching a long way from a compact folded package.

The shared idea: choose the geometry so the *mechanism* enforces the motion you want, instead of asking motors and software to fight for it.'''
            },
            {
                'title': 'End Effectors: The Robot Hand',
                'content': '''# End Effectors: The Robot Hand

The **end effector** is whatever sits at the working end of an arm — the part that actually touches the object. Choosing one is a matching game between the effector and the object it must handle.

## The Main Families

| Type | How it works | Best for | Watch out for |
|------|--------------|----------|---------------|
| Parallel gripper | Two flat jaws close straight together | Boxes, blocks, flat-sided parts | Round objects can squirt out |
| Claw (angular gripper) | Jaws pivot closed like tongs | Balls, irregular shapes | Grip force varies with opening angle |
| Suction cup | Vacuum pulls object against a cup | Smooth, flat, non-porous surfaces | Useless on mesh, fabric, or dusty parts |
| Specialized | Custom shape for one object | Hooks for rings, forks for tubes, rollers that swallow balls | Only does its one job |

## Grip Strategy

Two different philosophies show up in gripper design:

- **Force closure:** squeeze hard enough that friction holds the object. Simple, but heavy squeezing risks crushing, and Newton's third law says the object pushes back on your arm.
- **Form closure:** shape the effector so the object *cannot* escape — a hook through a ring, a cradle under a ball. Needs almost no grip force at all.

Competition robots overwhelmingly favor specialized, form-closure designs: a passive hook never drops the ring, never needs a motor, and never runs out of grip strength. A general-purpose hand is impressive; a shaped scoop that cannot miss is effective.

## Compliance

Good effectors often include a little **compliance** — rubber pads, foam, flexible fingers — so small aiming errors are absorbed by the material instead of causing a miss. Soft beats precise more often than beginners expect.'''
            },
            {
                'title': 'Payload, Center of Gravity, and Stability',
                'content': '''# Payload, Center of Gravity, and Stability

An arm that can *reach* an object is not necessarily an arm that can *lift* it — and a robot that can lift it might tip over trying. Two ideas govern this: payload and center of gravity.

## Payload

**Payload** is the maximum load a manipulator can handle at its working end. It shrinks with reach: torque at the shoulder is `force x distance`, so the same shoulder motor that holds 9 N at 0.2 m can hold only 3 N at 0.6 m. Real payload budgets must also count the arm's **own weight** — a long metal arm may spend most of its motor torque just lifting itself. This is why good arm designs put motors near the base and make the far end as light as possible.

## Center of Gravity

The **center of gravity (CG)** is the single point where the robot's whole weight effectively acts. The stability rule is simple:

**A robot stays upright while its CG is above its support polygon** — the outline traced around its wheels' contact points.

Raise an arm high while holding a load, and the combined CG rises and shifts toward that load. Combine that with braking (inertia throwing mass forward — the first law again) and the CG can swing past the wheels. The moment it does, gravity finishes the tip.

## Designing for Stability

- **Keep heavy parts low:** batteries and motors belong at the bottom of the frame.
- **Widen the wheelbase** in the direction the arm reaches.
- **Counterweight** long arms behind the pivot, like a crane.
- **Move gently when extended:** slow accelerations keep inertia from lending gravity a hand.

Watch any competition and you will see this lesson enforced live: the robots that tip are almost always tall, extended, and stopping fast — all three risk factors at once.'''
            }
        ])
        self._create_lesson_questions(lesson, [
            {
                'text': 'A robot arm has a rotating base, a shoulder joint, and an elbow joint, each driven by its own motor. How many degrees of freedom is that?',
                'choices': [
                    ('3', True),
                    ('1', False),
                    ('2', False),
                    ('6', False),
                ]
            },
            {
                'text': 'Why do builders use a parallel four-bar linkage for a lift that carries a tray?',
                'choices': [
                    ('The geometry keeps the tray at a constant angle through the whole lift, with no extra motors', True),
                    ('It doubles the motor torque with every bar added', False),
                    ('It lets the tray spin continuously like a wheel', False),
                    ('It removes the need for any pivots in the mechanism', False),
                ]
            },
            {
                'text': 'Which end effector is the worst choice for picking up a mesh bag full of small parts?',
                'choices': [
                    ('A suction cup, because vacuum cannot seal against a porous surface', True),
                    ('A claw gripper, because claws cannot close around soft objects', False),
                    ('A hook, because hooks require perfectly flat surfaces', False),
                    ('A parallel gripper, because flat jaws only work on spheres', False),
                ]
            },
            {
                'text': 'A robot raises a heavy load high on its arm, drives forward, and brakes hard — and tips over. What best explains the tip?',
                'choices': [
                    ('The raised load moved the center of gravity high, and braking inertia pushed it past the support polygon', True),
                    ('The battery voltage dropped, which reduced the weight of the wheels', False),
                    ('The center of gravity always drops when a load is lifted, destabilizing the robot', False),
                    ('The gear ratio was too low, which reverses the direction of gravity', False),
                ]
            }
        ])

        self._create_unit3_quiz(unit)

    def _create_unit3_quiz(self, unit):
        quiz = Quiz.objects.create(
            unit=unit,
            title='Mechanisms & Physics of Motion Quiz',
            description='Check your understanding of Newton\'s laws, simple machines, gears, motors, and manipulators.',
            passing_score=70,
            points=20,
            max_attempts=3,
            order=0
        )
        self._create_quiz_questions(quiz, [
            {
                'text': 'A drivetrain applies 24 N of force to an 8 kg robot. Using a = F / m, what is its acceleration?',
                'choices': [
                    ('3 m/s^2', True),
                    ('192 m/s^2', False),
                    ('0.33 m/s^2', False),
                    ('32 m/s^2', False),
                ]
            },
            {
                'text': 'A lever lets a 10 N effort lift a 40 N load. What is the mechanical advantage, and what is the trade-off?',
                'choices': [
                    ('MA = 4; the effort must move 4 times farther than the load', True),
                    ('MA = 4; the load moves 4 times farther than the effort', False),
                    ('MA = 0.25; the machine multiplies distance and force together', False),
                    ('MA = 30; the difference of the forces, with no trade-off', False),
                ]
            },
            {
                'text': 'A 10-tooth gear on a motor drives a 50-tooth gear on a wheel. Which describes the output?',
                'choices': [
                    ('5:1 reduction — the wheel turns 5 times slower with about 5 times the torque', True),
                    ('5:1 increase — the wheel turns 5 times faster with 5 times the torque', False),
                    ('1:5 reduction — the wheel turns 5 times faster with less torque', False),
                    ('No change — only idler gears alter speed and torque', False),
                ]
            },
            {
                'text': 'Which motor should drive a mechanism that must rotate to a commanded angle and actively hold that position?',
                'choices': [
                    ('A standard servo motor', True),
                    ('A bare high-RPM DC motor', False),
                    ('A DC gearmotor geared up for maximum speed', False),
                    ('Any motor, since all motors hold position when unpowered', False),
                ]
            },
            {
                'text': 'What is the stability rule that decides whether a robot tips over?',
                'choices': [
                    ('It stays upright while its center of gravity is above its support polygon', True),
                    ('It stays upright as long as its total mass is under 10 kg', False),
                    ('It stays upright whenever its arm is made of metal', False),
                    ('It stays upright if its wheels spin faster than its arm moves', False),
                ]
            },
            {
                'text': 'Why do competition robots often use a shaped hook or scoop (form closure) instead of a squeezing gripper (force closure)?',
                'choices': [
                    ('The shape itself traps the object, so almost no grip force or extra motor is needed', True),
                    ('Form closure crushes objects more effectively than squeezing', False),
                    ('Squeezing grippers violate competition rules', False),
                    ('Hooks and scoops work on every possible object shape', False),
                ]
            }
        ])

    # ================== UNIT 4: Sensors, Systems & Feedback ==================
    def _create_unit4(self, course):
        unit = Unit.objects.create(course=course, title='Sensors, Systems & Feedback', order=3)

        # Lesson 1: Robot Subsystems
        lesson = Lesson.objects.create(unit=unit, title='Robot Subsystems', order=0)
        self._create_sections(lesson, [
            {
                'title': 'Overview',
                'content': '''# Robot Subsystems

A robot is not one machine — it is a **system of systems**. In this lesson you will break a robot down into its major subsystems and see how they work together to sense, think, and act.

## Learning Objectives

By the end of this lesson, you will be able to:
- Name the three major subsystems of a robot: power, drive, and control
- Describe what each subsystem contributes to the robot as a whole
- Explain the inputs-process-outputs model of a technological system
- Trace how a failure in one subsystem affects the others

> **TEKS alignment:** §127.749(c)(6) — the student explores the components and functions of technological systems, including how subsystems interact within a complete robotic system.'''
            },
            {
                'title': 'The Power Subsystem',
                'content': '''# The Power Subsystem

Every robot needs energy, and the power subsystem is how it stores and delivers it. Take away power and the smartest robot on Earth becomes an expensive paperweight.

## Batteries and Voltage

Most classroom and competition robots run on **rechargeable battery packs**. Two numbers matter most:

| Term | What it means | Everyday comparison |
|------|---------------|---------------------|
| Voltage (V) | The electrical "push" the battery provides | Water pressure in a hose |
| Capacity (mAh) | How much energy the battery stores | The size of the water tank |

A typical educational robot battery might supply 7.2 V or 12 V. If the voltage sags — for example, when the battery is nearly drained — motors turn slower and sensors can give unreliable readings. That is a subsystem interaction: a power problem shows up as a *driving* problem.

## Power Distribution

The battery does not connect straight to every part. Power flows through:

- A **main switch** so you can safely turn the robot on and off
- A **controller or power distribution board** that routes electricity where it is needed
- **Fuses or current limits** that cut power if something draws too much, protecting wiring from overheating

## Why It Matters

Robotics teams learn quickly to check the battery first when a robot misbehaves. A "broken" autonomous routine is often just a low battery making the motors run 10% slower than they did in testing.'''
            },
            {
                'title': 'The Drive Subsystem',
                'content': '''# The Drive Subsystem: How Robots Move

The drive (or **locomotion**) subsystem converts electrical energy into motion. Engineers choose a drive style based on the terrain and the task.

## Common Drive Types

| Drive type | Strengths | Weaknesses | Example |
|-----------|-----------|------------|---------|
| Wheels | Fast, efficient, simple | Struggles on stairs and rough ground | Warehouse delivery robots |
| Treads (tracks) | Grips loose or uneven surfaces | Slower, wears down, turns by skidding | Bomb-disposal robots |
| Legs | Handles stairs, rubble, and gaps | Complex, expensive, needs constant balancing | Boston Dynamics research robots |

## Motors and Gears

At the heart of the drive subsystem are **motors**. Most educational robots use DC motors paired with **gears**:

- **Gearing down** (big gear driven by small gear) trades speed for **torque** — turning force. Good for pushing or climbing.
- **Gearing up** does the opposite: more speed, less torque. Good for a fast, light robot on flat ground.

## Steering Without a Steering Wheel

Many robots use **differential drive**: one motor per side. Run both sides forward to go straight; run the left side faster to curve right; run the sides in opposite directions to spin in place. This simple idea powers everything from robot vacuums to Mars rovers.

Notice the interaction again: the drive subsystem can only be as good as the power feeding it and the control signals telling it what to do.'''
            },
            {
                'title': 'The Control Subsystem',
                'content': '''# The Control Subsystem: The Robot Brain

The control subsystem decides *what the robot does*. It is usually a small computer called a **controller** (or microcontroller) — the "brain" that runs your program.

## What the Controller Does

Every fraction of a second, the controller:

1. **Reads inputs** — values from sensors, buttons, or a wireless gamepad
2. **Runs your program** — the logic you wrote deciding what should happen
3. **Writes outputs** — commands to motors, lights, speakers, or displays

## Inputs and Outputs (I/O)

Controllers have **ports** where devices plug in:

- **Input devices**: bumper switches, distance sensors, cameras, gamepads
- **Output devices**: drive motors, arm motors, LEDs, buzzers

A helpful habit: whenever you see a robot do something, ask *"what input triggered that, and what output carried it out?"* The controller sits in the middle of every answer.

## The Program Is Part of the System

Hardware alone is not enough. The same robot with two different programs is effectively two different machines — one program might make it follow a line, another might make it dance. When you debug a robot, the fault can live in:

- The **hardware** (loose wire, dead battery, broken gear)
- The **software** (a bug in your logic)
- The **interaction** between them (a sensor plugged into the wrong port)

Good roboticists check all three, because in a system of systems, problems love to hide at the boundaries.'''
            },
            {
                'title': 'Inputs, Process, Outputs',
                'content': '''# Systems Thinking: Inputs, Process, Outputs

Engineers describe any technological system with a simple model:

> **Inputs → Process → Outputs** (with **feedback** looping back in)

## Applying the Model to a Robot

| Stage | In a robot | Example |
|-------|-----------|---------|
| Inputs | Energy from the battery, data from sensors, commands from a driver | Distance sensor reports a wall 20 cm ahead |
| Process | The controller runs your program on that data | Program decides the robot is too close |
| Outputs | Motion, light, sound — actions in the world | Motors stop; warning LED turns on |

## Subsystems Depend on Each Other

Try this thought experiment — predict what happens to the *whole* robot when one subsystem fails:

- **Battery dies** → controller shuts off → no processing, no motion. Total failure.
- **A drive motor jams** → controller still runs, sensors still read, but outputs cannot act. The robot "thinks" but cannot move.
- **Controller crashes** → power and motors are fine, yet nothing coordinates them. The robot may freeze or behave unpredictably.

No subsystem is optional. This is why engineers test subsystems separately (does the motor spin on its own?) before testing the whole robot — it narrows down where a failure lives.

## Looking Ahead

The most interesting arrow in the model is **feedback**: outputs that change the inputs. A robot that drives forward changes what its distance sensor sees. The next two lessons dig into sensors and feedback — the ingredients that turn a remote-controlled machine into a truly autonomous robot.'''
            }
        ])
        self._create_lesson_questions(lesson, [
            {
                'text': 'Which three major subsystems make up a typical robot?',
                'choices': [
                    ('Power, drive, and control', True),
                    ('Wheels, wings, and propellers', False),
                    ('Keyboard, monitor, and printer', False),
                    ('Software, firmware, and apps', False),
                ]
            },
            {
                'text': 'In the inputs-process-outputs model, what role does the controller play?',
                'choices': [
                    ('It processes input data and decides what outputs to produce', True),
                    ('It stores the electrical energy for the motors', False),
                    ('It physically moves the robot across the floor', False),
                    ('It only charges the battery', False),
                ]
            },
            {
                'text': 'A robot runs slower than expected and its sensors give unreliable readings. Which subsystem should you check first?',
                'choices': [
                    ('The power subsystem, because a low battery affects motors and sensors', True),
                    ('The paint on the chassis', False),
                    ('The color of the wheels', False),
                    ('The robot name in the program', False),
                ]
            },
            {
                'text': 'Why might an engineer choose treads instead of wheels for a robot?',
                'choices': [
                    ('Treads grip loose or uneven surfaces better than wheels', True),
                    ('Treads are always faster than wheels', False),
                    ('Treads never wear out', False),
                    ('Treads use no power at all', False),
                ]
            }
        ])

        # Lesson 2: Sensors: How Robots Perceive
        lesson = Lesson.objects.create(unit=unit, title='Sensors: How Robots Perceive', order=1)
        self._create_sections(lesson, [
            {
                'title': 'Overview',
                'content': '''# Sensors: How Robots Perceive

Humans have eyes, ears, and skin. Robots have **sensors** — electronic devices that measure the world and turn it into numbers a controller can use. Without sensors, a robot is blind and can only follow a fixed script.

## Learning Objectives

By the end of this lesson, you will be able to:
- Describe what touch, distance, light/color, encoder, and gyro sensors measure
- Distinguish analog signals from digital signals at an introductory level
- Match a sensor to a task based on what needs to be measured
- Explain why sensor data is essential for autonomous behavior

> **TEKS alignment:** §127.749(c)(6) — the student examines the components of technological systems, including the sensors that provide input to a robotic system.'''
            },
            {
                'title': 'Touch and Distance Sensors',
                'content': '''# Feeling and Seeing Ahead: Touch and Distance

## Touch Sensors (Bumper Switches)

The simplest sensor is a **bumper switch** — a physical button on the front of the robot. When the robot hits something, the switch closes and reports "pressed."

- Reports only two states: **pressed** or **not pressed**
- Cheap, rugged, and nearly impossible to fool
- The catch: the robot must *actually collide* with the obstacle to detect it

## Distance Sensors

Distance sensors detect obstacles *before* contact, like eyes that measure range.

| Sensor | How it works | Typical use |
|--------|--------------|-------------|
| Ultrasonic | Sends a sound pulse and times the echo, like a bat | Stopping before a wall; parking sensors on cars |
| Infrared (IR) | Bounces invisible light off nearby objects | Short-range obstacle detection |
| Lidar | Sweeps a laser to measure distance in many directions | Mapping a whole room; self-driving car research |

An **ultrasonic sensor** might report "the nearest object is 32 cm away." Your program can then decide: keep driving, slow down, or stop.

## Contact vs. Non-Contact

A useful design question: *does the robot need to know about the obstacle before touching it?* A robot vacuum can afford gentle bumps, so bumper switches are fine. A warehouse robot carrying fragile boxes needs distance sensing so it never collides at all. Many real robots use both — distance sensors as the first line of defense, bumpers as the backup.'''
            },
            {
                'title': 'Light, Color, and Motion Sensors',
                'content': '''# Light, Color, Rotation, and Balance

## Light and Color Sensors

A **light sensor** measures brightness; a **color sensor** goes further and identifies hue (red vs. blue vs. green). Classic uses:

- **Line following**: the sensor points at the floor and detects the dark tape line against the light surface
- **Sorting**: a robot arm checks the color of each object and sorts it into the matching bin

## Rotation Encoders

An **encoder** counts how far a motor shaft or wheel has turned, usually in degrees or "ticks."

- Wheel turned 360 degrees, wheel circumference is 20 cm → the robot moved about 20 cm
- Encoders let a robot drive a *measured distance* instead of guessing with a timer
- They also reveal problems: if the motor is powered but the encoder count is not changing, the wheel is stuck

## Gyro and IMU

A **gyroscope (gyro)** measures rotation — how many degrees the robot has turned. An **IMU** (inertial measurement unit) bundles a gyro with an accelerometer to track turning and tilting.

- Want a precise 90-degree turn? Turn until the gyro reports 90, instead of spinning for a fixed time
- A balancing robot reads its IMU hundreds of times per second to keep from tipping over

## The Big Picture

Each sensor answers one specific question — *Am I touching something? How far? What color? How far have I driven? Which way am I facing?* Autonomous robots combine several answers at once, just as you combine sight, touch, and balance when walking through a crowded hallway.'''
            },
            {
                'title': 'Analog vs Digital Signals',
                'content': '''# Analog vs. Digital Signals

Sensors report their measurements as electrical signals, and those signals come in two flavors.

## Digital Signals: On or Off

A **digital** signal has exactly two states — like a light switch.

- A bumper switch is digital: **pressed (1)** or **not pressed (0)**
- There is no in-between; the answer is always yes or no

## Analog Signals: A Smooth Range

An **analog** signal varies smoothly across a range — like a dimmer knob.

- A light sensor might output any value from 0 (total darkness) to 100 (bright light)
- An ultrasonic sensor reports a distance that could be 31.5 cm, 32 cm, 32.4 cm — any value in its range

| | Digital | Analog |
|---|---------|--------|
| States | Two (on/off) | Many (a continuous range) |
| Everyday example | Light switch | Volume knob |
| Robot example | Bumper switch | Light sensor reading |
| Best for | Yes/no questions | How-much questions |

## Why Programmers Care

Your code treats them differently. A digital input needs a simple check: *is the bumper pressed?* An analog input needs a **threshold** — a cutoff you choose: *is the light reading below 20? Then the sensor is over the dark line.* Picking good thresholds is a real engineering skill: set the line-follower threshold too high or too low and the robot wanders off the tape. Testing in the actual environment, under the actual lighting, is the only way to get it right.'''
            },
            {
                'title': 'Choosing the Right Sensor',
                'content': '''# Choosing Sensors for a Task

Real engineering is not about knowing every sensor — it is about matching the sensor to the job. Start with one question: **what does the robot need to know?**

## A Decision Guide

| The robot needs to know... | Good sensor choice |
|---------------------------|--------------------|
| Did I hit something? | Bumper switch |
| How far away is the obstacle? | Ultrasonic or IR distance sensor |
| Am I on the line? | Light or color sensor aimed at the floor |
| How far have I driven? | Rotation encoder |
| How many degrees have I turned? | Gyro / IMU |
| What color is this object? | Color sensor |

## Trade-Offs to Weigh

No sensor is perfect. Engineers balance:

- **Cost** — lidar gives rich data but costs far more than a bumper switch
- **Reliability** — a color sensor can be confused by changing room lighting; a bumper switch almost never lies
- **Range and precision** — an IR sensor works up close; ultrasonic reaches farther but can miss soft, sound-absorbing surfaces
- **Simplicity** — every extra sensor is more wiring, more code, and more that can break

## Worked Example: Maze-Solving Robot

A robot must drive a maze without touching the walls. A strong sensor package:

1. **Front distance sensor** — see walls ahead and stop in time
2. **Gyro** — make accurate 90-degree turns at each corner
3. **Encoders** — travel one maze cell at a time by distance
4. **Bumper switch** — a last-resort backup if the distance sensor misses

Four sensors, each answering one question the task actually requires. That is sensor selection done well.'''
            }
        ])
        self._create_lesson_questions(lesson, [
            {
                'text': 'Which sensor lets a robot detect an obstacle before touching it?',
                'choices': [
                    ('An ultrasonic distance sensor', True),
                    ('A bumper switch', False),
                    ('A rotation encoder', False),
                    ('A battery voltage meter', False),
                ]
            },
            {
                'text': 'What does a rotation encoder measure?',
                'choices': [
                    ('How far a motor shaft or wheel has turned', True),
                    ('The color of the floor beneath the robot', False),
                    ('The temperature of the motor', False),
                    ('The loudness of nearby sounds', False),
                ]
            },
            {
                'text': 'Which statement correctly describes a digital signal?',
                'choices': [
                    ('It has exactly two states, such as pressed or not pressed', True),
                    ('It varies smoothly across a continuous range of values', False),
                    ('It can only be produced by a lidar sensor', False),
                    ('It always measures distance in centimeters', False),
                ]
            },
            {
                'text': 'A robot must turn exactly 90 degrees at each corner of a maze. Which sensor is the best fit?',
                'choices': [
                    ('A gyro or IMU that measures rotation', True),
                    ('A color sensor pointed at the ceiling', False),
                    ('A bumper switch on the back of the robot', False),
                    ('A light sensor measuring room brightness', False),
                ]
            }
        ])

        # Lesson 3: Open- vs Closed-Loop Control
        lesson = Lesson.objects.create(unit=unit, title='Open- vs Closed-Loop Control', order=2)
        self._create_sections(lesson, [
            {
                'title': 'Overview',
                'content': '''# Open- vs Closed-Loop Control

Two robots get the same command: "drive one meter." One drives blind and hopes for the best. The other measures as it goes and corrects itself. The difference is **feedback**, and it is one of the most important ideas in all of engineering.

## Learning Objectives

By the end of this lesson, you will be able to:
- Define open-loop and closed-loop control and give an example of each
- Describe the sense-compare-adjust cycle of a feedback loop
- Explain why closed-loop control makes robots more reliable
- Recognize, at a conceptual level, what proportional control adds to feedback

> **TEKS alignment:** §127.749(c)(6) — the student analyzes how technological systems use feedback and control processes to produce reliable behavior.'''
            },
            {
                'title': 'Open-Loop Control',
                'content': '''# Open-Loop Control: Acting Blind

An **open-loop** system performs an action without ever checking the result. It follows the plan — no measuring, no correcting.

## Everyday Example: The Toaster

A basic toaster runs its heating element for a fixed time and pops up. It does not look at the bread.

- Thick bagel? Undercooked.
- Thin slice on a hot day? Burnt.

The toaster cannot tell the difference, because nothing in the loop measures *toastiness*.

## Robot Example: Drive-for-Time

The open-loop way to move a robot one meter:

```
set motors to 50% power
wait 2 seconds
stop motors
```

This *seems* fine — until conditions change:

| Condition changes | Result |
|-------------------|--------|
| Battery is low, motors run slower | Robot stops short |
| Floor changes from carpet to tile | Wheels slip, distance varies |
| Robot carries a heavy load | Slower acceleration, stops short |

Run it ten times and you get ten slightly different distances.

## When Open-Loop Is Acceptable

Open-loop is not evil — it is simple and cheap, and it works when conditions are predictable and precision does not matter much. A sprinkler that runs 20 minutes each morning is open-loop and perfectly fine. The trouble starts when the world varies and accuracy matters. That is when you need to close the loop.'''
            },
            {
                'title': 'Closed-Loop Control and Feedback',
                'content': '''# Closed-Loop Control: Sense, Compare, Adjust

A **closed-loop** system measures its own results and corrects itself. The measurement feeding back into the decision is what "closes" the loop.

## Everyday Example: The Thermostat

A thermostat holds your home at a target temperature by looping forever:

1. **Sense** — measure the current temperature
2. **Compare** — is it below the target (say, 21°C)?
3. **Adjust** — if too cold, run the heater; if warm enough, turn it off

The gap between where you are and where you want to be is called the **error**. Feedback systems exist to shrink the error toward zero.

## Robot Example: Drive-with-Encoders

The closed-loop way to move one meter uses the encoder from the last lesson:

```
target = 1 meter of wheel rotation
repeat:
    distance = read encoder
    if distance < target: keep driving
    else: stop
```

Now the pesky variables lose their power:

- **Low battery?** Motors run slower, so the loop simply runs a little longer — the robot still travels one meter.
- **Slippery floor?** The encoder reports actual rotation, and the robot keeps adjusting until the target is truly reached.

## The Universal Pattern

Sense → compare → adjust, repeated many times per second. A line follower senses the tape, compares to the edge it wants, and adjusts steering. A drone senses its tilt, compares to level, and adjusts each propeller. Once you know this cycle, you will spot it everywhere — cruise control, ovens, even your own body holding its balance.'''
            },
            {
                'title': 'Why Feedback Makes Robots Reliable',
                'content': '''# Why Feedback Wins (and a Peek at Proportional Control)

## Reliability in an Unpredictable World

The real world refuses to stay constant: batteries drain, floors change, wheels wear down, loads shift. Open-loop systems bake in assumptions about all of these — and break when any assumption fails.

Closed-loop systems measure **reality** instead of trusting assumptions:

| | Open-loop | Closed-loop |
|---|-----------|-------------|
| Checks its result? | Never | Constantly |
| Handles a low battery? | No — stops short | Yes — drives until the target is measured |
| Consistency across runs | Drifts run to run | Repeatable |
| Cost and complexity | Lower | Higher (needs sensors + logic) |

The price of reliability is a sensor and a smarter program. For almost any serious robot, that trade is worth it.

## A Smarter Adjustment: Proportional Control

Basic closed-loop logic is all-or-nothing: motors full on, then stop. A robot doing this often **overshoots** the target — it cannot stop instantly from full speed.

**Proportional control** improves the "adjust" step with one idea:

> Make the correction **proportional to the error**. Far from the target → act strongly. Close to the target → act gently.

Think of stopping a car at a stop sign. You do not hold the gas until the line and then slam the brakes — you ease off as you approach. A robot with proportional control does the same: full speed a meter from the wall, slowing smoothly as the distance sensor counts down, stopping gently right on target.

You will see this behave beautifully in the next lesson, where you build a sensor-driven stop in a simulator. Fair warning: once you understand feedback, you will never look at a thermostat the same way again.'''
            }
        ])
        self._create_lesson_questions(lesson, [
            {
                'text': 'What is the key difference between open-loop and closed-loop control?',
                'choices': [
                    ('Closed-loop systems measure their results and correct themselves; open-loop systems do not', True),
                    ('Open-loop systems use more sensors than closed-loop systems', False),
                    ('Closed-loop systems never need any sensors', False),
                    ('Open-loop systems are always more accurate', False),
                ]
            },
            {
                'text': 'A basic toaster that heats for a fixed time is an example of which kind of system?',
                'choices': [
                    ('Open-loop, because it never checks how toasted the bread is', True),
                    ('Closed-loop, because it pops up when finished', False),
                    ('Proportional control, because it has a dial', False),
                    ('A feedback loop, because heat flows in a circle', False),
                ]
            },
            {
                'text': 'In a feedback loop, what does the "error" refer to?',
                'choices': [
                    ('The gap between the measured value and the target value', True),
                    ('A bug in the program code', False),
                    ('A broken wire in the power subsystem', False),
                    ('The time the loop takes to run once', False),
                ]
            },
            {
                'text': 'What does proportional control add to a basic feedback loop?',
                'choices': [
                    ('The correction gets stronger when the error is large and gentler when the error is small', True),
                    ('The robot ignores its sensors when close to the target', False),
                    ('The motors always run at exactly full power', False),
                    ('The loop runs only once instead of repeatedly', False),
                ]
            }
        ])

        # Lesson 4: Simulation Exercise: Sensor-Driven Behavior in VEXcode VR
        lesson = Lesson.objects.create(unit=unit, title='Simulation Exercise: Sensor-Driven Behavior in VEXcode VR', order=3)
        self._create_sections(lesson, [
            {
                'title': 'Overview',
                'content': '''# Simulation Exercise: Sensor-Driven Behavior in VEXcode VR

Time to put sensors and feedback to work. In this hands-on lesson you will program a simulated robot in **VEXcode VR** — a free simulator that runs entirely in your web browser at **vr.vex.com**. No hardware, no downloads, no account required to start.

## Learning Objectives

By the end of this lesson, you will be able to:
- Navigate the VEXcode VR interface and run programs on a virtual robot
- Use the distance sensor to stop the robot before it hits a wall (closed-loop control)
- Compare the reliability of drive-for-time versus drive-until-sensed behavior
- Extend a sensor-driven program to obstacle detection or wall following

> **TEKS alignment:** §127.749(c)(6) — the student applies knowledge of technological systems by using sensors and feedback to control a simulated robotic system.'''
            },
            {
                'title': 'Getting Started with VEXcode VR',
                'content': '''# Step 1: Meet Your Virtual Robot

## Open the Simulator

1. In a web browser, go to **vr.vex.com**
2. The editor opens with a block-based coding workspace (you can switch to Python later if you prefer)
3. Click the **Playground** window to see the 3D arena where your robot lives

## Choose a Playground

Click the playground selector and choose **Wall Maze** (or any playground with walls). Take a moment to explore:

- **Drag** in the playground window to orbit the camera around the arena
- Find the robot start position and look at where the walls are
- Locate the **dashboard**, which shows live sensor values while your program runs

## Know Your Robot

The virtual robot has the same subsystems you studied in Lesson 1, plus a full sensor package from Lesson 2:

| Component | What it gives you |
|-----------|-------------------|
| Drivetrain | Drive forward/reverse, turn left/right |
| Distance sensor (front) | How far to the nearest object, in mm |
| Bumper switch (front) | Pressed or not pressed |
| Gyro | Heading in degrees |
| Down-facing eye sensor | Color of the floor below |

## Warm-Up Run

Build this tiny program and click **Start**:

- **when started** → **drive forward** for **200 mm**

Watch the robot move, then check the dashboard to see the sensor values change. When you can run a program and read the dashboard, you are ready for the real challenge.'''
            },
            {
                'title': 'Challenge 1: Stop Before the Wall',
                'content': '''# Step 2: Stop Before the Wall

Your mission: make the robot drive toward a wall and **stop about 50 mm before touching it** — using its distance sensor, not a stopwatch.

## First, Try It Open-Loop

1. Point the robot at a wall in the playground
2. Program: **when started** → **drive forward** for a fixed distance you guess, such as **600 mm**
3. Run it. Did it stop 50 mm from the wall? Now move the robot start position slightly and run again.

**What to observe:** the fixed-distance version only works from one exact starting spot. Change the start and it either stops far short or smacks the wall. This is the open-loop problem from Lesson 3, live on screen.

## Now, Close the Loop

Rebuild the program with the distance sensor:

1. **when started**
2. **drive forward** (no fixed distance — just start driving)
3. **wait until** → **distance found object is less than 50 mm**
4. **stop driving**

Run it from several different start positions.

**What to observe:**

- The robot stops about 50 mm from the wall **no matter where it starts** — the sensor closes the loop
- Watch the distance value fall on the dashboard as the robot approaches
- Try changing the threshold to 150 mm, then 20 mm. What is the trade-off between stopping early and stopping close?

## If It Hits the Wall

Slow the drivetrain velocity down. At high speed the robot travels a long way between sensor checks — a real-world lesson: feedback loops need to run fast relative to how fast the robot moves.'''
            },
            {
                'title': 'Challenge 2: Extend Your Program',
                'content': '''# Step 3: Extend to Smarter Behavior

Pick **one** of these extensions (or do both). Each one layers new logic on the sense-compare-adjust cycle you just built.

## Option A: Obstacle-Avoiding Explorer

Make the robot wander the playground without ever hitting a wall:

1. **when started** → **forever** loop:
2. Inside the loop: **if** distance to object **< 100 mm** → **turn right** for **90 degrees**
3. **else** → **drive forward**

**What to observe:** the robot roams and pivots away from every wall it approaches. Add the **bumper switch** as a backup — if it is ever pressed, reverse a little, then turn. You now have a two-sensor safety system, just like real robots that pair distance sensing with contact sensing.

## Option B: Wall Follower

Make the robot drive parallel to a wall, holding a steady gap:

1. Turn the robot so a wall is on its right side
2. **forever** loop: read the distance to the right
3. **if** the gap is too big (> 120 mm) → steer slightly right, toward the wall
4. **if** the gap is too small (< 80 mm) → steer slightly left, away from the wall
5. **else** → drive straight

**What to observe:** the robot weaves at first, then settles into hugging the wall. Try making the steering corrections smaller — smoother, right? You have just discovered *why* proportional control exists: gentle corrections for small errors beat harsh zigzags.

## Stretch Goal

Combine both: follow the wall on the right until the front distance sensor sees a wall ahead, then turn left and keep following. That is the classic maze-escape algorithm.'''
            },
            {
                'title': 'Reflection and Going Further',
                'content': '''# Step 4: Reflect on What You Built

Simulation work only sticks when you stop and think about what the robot showed you. Write short answers to these prompts (your teacher may collect them or use them for discussion).

## Reflection Prompts

1. In Challenge 1, why did the sensor-driven program succeed from any starting position while the fixed-distance program did not? Use the terms **open-loop** and **closed-loop** in your answer.
2. Describe the **sense-compare-adjust** cycle in your wall-stop program: what was sensed, what was it compared to, and what was the adjustment?
3. When you changed the stopping threshold (50 mm vs. 150 mm vs. 20 mm), what trade-off did you observe?
4. Name one thing the simulator cannot capture about a physical robot. (Hint: think about battery sag, wheel slip, or sensor noise from Lessons 1-3.)

## Why Simulators Matter

Professional robotics teams test in simulation first — it is free, fast, safe, and infinitely repeatable. A crashed virtual robot costs nothing. The habits you practiced here (test, observe, adjust the threshold, test again) are exactly how engineers tune real robots.

## Going Further: Tinkercad Circuits

VEXcode VR simulates the robot at the *behavior* level. If you want to see how sensors work at the *circuit* level — wiring an ultrasonic sensor to a microcontroller, reading its raw signal — try **Tinkercad Circuits** (tinkercad.com), another free browser tool. You can build a virtual circuit with an Arduino, a distance sensor, and an LED that lights up when an object gets close: the same feedback idea, one layer deeper in the system.'''
            }
        ])
        self._create_lesson_questions(lesson, [
            {
                'text': 'What is VEXcode VR?',
                'choices': [
                    ('A free browser-based simulator for programming a virtual robot', True),
                    ('A physical robot kit that must be purchased', False),
                    ('A word processor for writing lab reports', False),
                    ('A battery charger for VEX robots', False),
                ]
            },
            {
                'text': 'In the wall-stop challenge, why does the sensor-driven program work from any starting position?',
                'choices': [
                    ('It measures the actual distance to the wall and stops based on that feedback', True),
                    ('It drives for a carefully chosen fixed amount of time', False),
                    ('The simulator always places the robot in the same spot', False),
                    ('It uses the color sensor to detect the wall', False),
                ]
            },
            {
                'text': 'The robot keeps hitting the wall even though the stop threshold is set correctly. Based on the lesson, what is a good fix?',
                'choices': [
                    ('Lower the drivetrain velocity so the feedback loop can react in time', True),
                    ('Remove the distance sensor from the program', False),
                    ('Repaint the virtual wall a brighter color', False),
                    ('Increase the speed so the robot finishes sooner', False),
                ]
            },
            {
                'text': 'In the wall-following extension, why did smaller steering corrections make the robot smoother?',
                'choices': [
                    ('Gentle corrections for small errors reduce zigzagging, which is the idea behind proportional control', True),
                    ('Smaller corrections turn off the distance sensor', False),
                    ('The simulator only allows small numbers', False),
                    ('Large corrections drain the virtual battery', False),
                ]
            }
        ])

        self._create_unit4_quiz(unit)

    def _create_unit4_quiz(self, unit):
        quiz = Quiz.objects.create(
            unit=unit,
            title='Sensors, Systems & Feedback Quiz',
            description='Test your understanding of robot subsystems, sensors, and open- versus closed-loop control.',
            passing_score=70,
            points=20,
            max_attempts=3,
            order=0
        )
        self._create_quiz_questions(quiz, [
            {
                'text': 'Which subsystem of a robot stores energy and delivers it to the motors and controller?',
                'choices': [
                    ('The power subsystem', True),
                    ('The drive subsystem', False),
                    ('The control subsystem', False),
                    ('The sensor dashboard', False),
                ]
            },
            {
                'text': 'A robot needs to travel exactly one meter even when its battery is low. Which approach is most reliable?',
                'choices': [
                    ('Drive while reading an encoder and stop when the measured distance reaches one meter', True),
                    ('Drive at full power for exactly two seconds', False),
                    ('Drive until the program guesses it has gone far enough', False),
                    ('Drive until the battery runs out', False),
                ]
            },
            {
                'text': 'Which pairing of sensor and measurement is correct?',
                'choices': [
                    ('Gyro — how many degrees the robot has turned', True),
                    ('Bumper switch — the exact distance to a wall in millimeters', False),
                    ('Ultrasonic sensor — the color of the floor', False),
                    ('Color sensor — how far a wheel has rotated', False),
                ]
            },
            {
                'text': 'A light sensor that outputs any value from 0 to 100 is producing what kind of signal?',
                'choices': [
                    ('An analog signal, because it varies across a continuous range', True),
                    ('A digital signal, because it comes from an electronic device', False),
                    ('An open-loop signal, because it has no feedback', False),
                    ('A proportional signal, because it changes size', False),
                ]
            },
            {
                'text': 'A thermostat that measures room temperature and turns the heater on or off to hold a target is an example of what?',
                'choices': [
                    ('A closed-loop control system using feedback', True),
                    ('An open-loop control system with no measurement', False),
                    ('A power distribution board', False),
                    ('A rotation encoder', False),
                ]
            },
            {
                'text': 'In the sense-compare-adjust cycle of a robot stopping before a wall, which step does the distance sensor perform?',
                'choices': [
                    ('Sense — it measures how far away the wall currently is', True),
                    ('Compare — it decides whether the robot is too close', False),
                    ('Adjust — it applies power to the motors', False),
                    ('None — distance sensors are not part of feedback loops', False),
                ]
            }
        ])

    # ================== UNIT 5: Programming Robots ==================
    def _create_unit5(self, course):
        unit = Unit.objects.create(course=course, title='Programming Robots', order=4)

        # Lesson 1: Programs, Algorithms & Pseudocode
        lesson = Lesson.objects.create(unit=unit, title='Programs, Algorithms & Pseudocode', order=0)
        self._create_sections(lesson, [
            {
                'title': 'Overview',
                'content': '''# Programs, Algorithms & Pseudocode

A robot without a program is just an expensive paperweight. In this lesson you will learn what a program actually is, how algorithms shape everything a robot does, and how to plan your logic with pseudocode and flowcharts before you write a single line of code.

## Learning Objectives

By the end of this lesson, you will be able to:
- Define *program* and *algorithm* and explain how they relate
- Identify algorithms in everyday life and in robot behavior
- Write clear, step-by-step pseudocode for a simple task
- Read a simple flowchart and trace its path
- Compare block-based and text-based robot programming

> **TEKS alignment:** §127.749(c)(6) — The student uses computer programming to control the behavior of robotic systems.'''
            },
            {
                'title': 'What Is a Program?',
                'content': '''# What Is a Program?

A **program** is a list of instructions a computer follows, in order, exactly as written. The computer inside a robot — often called a *controller* or *brain* — cannot guess what you meant. It does precisely what the program says, nothing more.

An **algorithm** is the plan behind a program: a step-by-step method for solving a problem. The program is the algorithm translated into a language the robot understands.

## Algorithms Are Everywhere

You already run algorithms every day:

- **Making a sandwich**: get bread, add filling, close sandwich, cut in half
- **Following a recipe**: measure, mix, bake for 20 minutes, check, serve
- **Getting to class**: exit room, turn left, walk 40 steps, enter room 204

Notice the pattern: each step is *specific*, the steps have an *order*, and the process *ends*.

## Why Robots Need Exact Instructions

Tell a friend to "go to the door" and they figure out the details. A robot cannot. It needs:

| A human hears | A robot needs |
|---------------|---------------|
| Go to the door | Drive forward 2 meters, turn right 90 degrees, drive forward 1 meter |
| Stop when you get close | If distance to object is less than 100 mm, stop |
| Do that a few times | Repeat 4 times |

This is the central skill of robot programming: breaking a fuzzy goal into exact, ordered steps. Every lesson in this unit builds on that idea.'''
            },
            {
                'title': 'Writing Pseudocode',
                'content': '''# Writing Pseudocode

**Pseudocode** is a plain-language draft of a program. It is not real code — no robot can run it — but it lets you design your logic without worrying about syntax. Professional engineers pseudocode first, code second.

## Rules of Good Pseudocode

- One action per line
- Start each line with a verb (drive, turn, wait, check)
- Use indentation to show which steps belong inside a loop or decision
- Be specific with numbers and units

## Example: Robot Delivers a Package Across the Room

```text
start at the charging station
drive forward 300 cm
turn left 90 degrees
drive forward 150 cm
open the claw to release the package
turn around 180 degrees
drive back to the charging station
stop
```

Anyone — teammate, teacher, or future you — can read that and understand the plan. Compare it to a vague plan like "take the package over there and come back," which leaves out every detail a robot needs.

## Pseudocode Is a Thinking Tool

When your robot misbehaves later in this unit, the first debugging question is: *does my code match my pseudocode, and does my pseudocode match my intent?* Two documents to compare beats one mystery. Write the plan before the program, every time.'''
            },
            {
                'title': 'Flowcharts: Seeing the Logic',
                'content': '''# Flowcharts: Seeing the Logic

A **flowchart** is a diagram of an algorithm. Where pseudocode is a list, a flowchart is a map — especially useful when the program makes decisions and can take more than one path.

## Standard Flowchart Shapes

| Shape | Meaning | Example |
|-------|---------|---------|
| Oval | Start or End | Start |
| Rectangle | Action step | Drive forward 200 mm |
| Diamond | Decision (yes/no question) | Is the bumper pressed? |
| Arrow | Flow from one step to the next | — |

## A Simple Flowchart, Written as a List

Here is a flowchart for a robot that drives until it hits a wall, described top to bottom:

- **(Oval)** Start
- **(Rectangle)** Begin driving forward
- **(Diamond)** Is the bumper pressed?
  - **No** → loop back to the diamond and check again
  - **Yes** → continue down
- **(Rectangle)** Stop driving
- **(Oval)** End

The diamond is the interesting part: the program *branches*. One question, two possible paths. Complex robot behavior is mostly just many small diamonds chained together.

## When to Use Which

- **Pseudocode**: fast to write, great for straight-line sequences
- **Flowchart**: better when there are decisions and loops, because you can *see* every possible path

For the maze project at the end of this unit, you will use both.'''
            },
            {
                'title': 'Block-Based vs Text-Based Programming',
                'content': '''# Block-Based vs Text-Based Programming

Robot platforms generally offer two ways to write programs. Both produce real, working robot code — they just look different.

## Block-Based Programming

You snap graphical blocks together like puzzle pieces. Each block is one instruction, and blocks only fit together in ways that make sense.

- **Strengths**: no typos or missing punctuation, easy to read, fast to start
- **Limits**: large programs become long towers of blocks that are hard to scroll and reorganize

## Text-Based Programming

You type instructions in a programming language such as Python or C++.

- **Strengths**: compact, powerful, searchable, and it is how professional robotics is done
- **Limits**: a single typo — a missing colon or bracket — stops the whole program

## Same Algorithm, Two Forms

Block version (described): a **when started** block, then **drive forward 200 mm**, then **turn right 90 degrees**.

Text version (pseudocode-style):

```text
when program starts
    drive forward 200 mm
    turn right 90 degrees
```

## The Key Insight

The *algorithm* is identical in both. Blocks and text are just two costumes for the same logic. If you can pseudocode a solution, you can build it in either form. That is why this unit teaches logic first and treats any specific programming tool as a detail you can pick up in an afternoon.'''
            }
        ])
        self._create_lesson_questions(lesson, [
            {
                'text': 'What is an algorithm?',
                'choices': [
                    ('A step-by-step method for solving a problem', True),
                    ('A type of robot sensor', False),
                    ('A programming language used only by robots', False),
                    ('The physical brain of a robot', False),
                ]
            },
            {
                'text': 'What is pseudocode?',
                'choices': [
                    ('A plain-language draft of a program used for planning', True),
                    ('Code that contains errors', False),
                    ('A language that robots can run directly', False),
                    ('A diagram made of shapes and arrows', False),
                ]
            },
            {
                'text': 'In a flowchart, what does a diamond shape represent?',
                'choices': [
                    ('A decision point with more than one possible path', True),
                    ('The start or end of the program', False),
                    ('A single action step', False),
                    ('A comment for the reader', False),
                ]
            },
            {
                'text': 'Which statement about block-based and text-based programming is TRUE?',
                'choices': [
                    ('The same algorithm can be expressed in either form', True),
                    ('Only text-based programs can control real robots', False),
                    ('Block-based programs cannot contain loops', False),
                    ('Text-based programming prevents typing mistakes', False),
                ]
            }
        ])

        # Lesson 2: Sequencing, Loops & Conditionals for Robots
        lesson = Lesson.objects.create(unit=unit, title='Sequencing, Loops & Conditionals for Robots', order=1)
        self._create_sections(lesson, [
            {
                'title': 'Overview',
                'content': '''# Sequencing, Loops & Conditionals for Robots

Three ideas power almost every robot program ever written: do steps **in order** (sequence), **repeat** steps (loops), and **choose** between steps (conditionals). Master these three and you can read or write nearly any robot behavior.

## Learning Objectives

By the end of this lesson, you will be able to:
- Explain why the order of instructions changes a robot's behavior
- Use repeat loops to eliminate duplicated instructions
- Use while loops for repetition that depends on a condition
- Write if/else logic to let a robot make decisions
- Trace short block-style pseudocode and predict what the robot does

> **TEKS alignment:** §127.749(c)(6) — The student uses computer programming to control the behavior of robotic systems.'''
            },
            {
                'title': 'Sequence: Order Matters',
                'content': '''# Sequence: Order Matters

A **sequence** is instructions executed one after another, top to bottom. Simple — but the *order* is everything.

## Two Programs, Same Instructions, Different Result

**Program A:**

```text
drive forward 400 mm
turn right 90 degrees
drive forward 400 mm
```

**Program B:**

```text
turn right 90 degrees
drive forward 400 mm
drive forward 400 mm
```

Both programs contain two drives and one turn. Program A traces an L-shape: forward, corner, forward. Program B turns first, then drives 800 mm in a straight line. Same ingredients, completely different paths.

## Tracing: Be the Robot

To **trace** a program, walk through it line by line and track the robot state (position and heading). Try tracing this one — where does the robot end up facing?

```text
drive forward 200 mm
turn right 90 degrees
drive forward 200 mm
turn right 90 degrees
```

Answer: 200 mm forward and 200 mm to the right of the start, facing *backwards* (two right turns of 90 degrees is a 180). If you predicted that correctly, you traced it like a programmer.

## Why This Matters for Robots

When a robot misbehaves, the most common cause is not a broken part — it is correct instructions in the wrong order. Tracing on paper before running on the robot catches these bugs for free.'''
            },
            {
                'title': 'Loops: Repeat Without Repeating Yourself',
                'content': '''# Loops: Repeat Without Repeating Yourself

Suppose you want a robot to drive in a square. Without loops:

```text
drive forward 200 mm
turn right 90 degrees
drive forward 200 mm
turn right 90 degrees
drive forward 200 mm
turn right 90 degrees
drive forward 200 mm
turn right 90 degrees
```

Eight lines, and the same two lines copied four times. A **repeat loop** says it once:

```text
repeat 4 times
    drive forward 200 mm
    turn right 90 degrees
```

The indented lines are the **loop body** — the robot runs them, jumps back to the top, and counts. After 4 passes, it moves on.

## Why Loops Beat Copy-Paste

- **Fewer bugs**: change the side length in one place, not four
- **Easy variations**: a triangle is `repeat 3 times` with 120-degree turns; a hexagon is `repeat 6 times` with 60-degree turns
- **Readability**: the loop announces the *intent* (make a square) instead of burying it in repetition

## While Loops: Repeat Until Something Changes

A repeat loop runs a fixed number of times. A **while loop** repeats as long as a condition stays true:

```text
while battery level is above 20 percent
    patrol the hallway
drive to charging station
```

Nobody knows in advance how many laps the robot will make — the *condition* decides. Repeat loops count; while loops watch. Choosing the right one is half the design of any robot behavior.'''
            },
            {
                'title': 'Conditionals: Robots That Decide',
                'content': '''# Conditionals: Robots That Decide

A sequence always does the same thing. A **conditional** lets the program choose between paths based on a question that is either true or false.

## If / Else

```text
if the path ahead is clear
    drive forward 500 mm
else
    turn right 90 degrees
```

The robot asks one question and takes exactly one of the two branches — never both, never neither.

## If Without Else

Sometimes there is no alternate action:

```text
if the cargo bay is open
    close the cargo bay
drive to the loading zone
```

If the bay is already closed, the robot simply skips the indented line and continues. The `drive` line is *not* indented, so it runs either way.

## Combining All Three Structures

Real behavior mixes sequence, loops, and conditionals. Trace this patrol program:

```text
repeat 4 times
    drive forward 300 mm
    if an obstacle is ahead
        turn left 90 degrees
    else
        turn right 90 degrees
```

Each lap: drive, then choose a turn direction based on what the robot sees at that moment. Four laps, and each lap can turn out differently — that is what makes conditionals powerful. The program is fixed; the *behavior* adapts.

## Check Yourself

In the patrol program, what is the greatest number of turns the robot can make? (Answer: 4 — exactly one turn per loop pass, because if/else always picks exactly one branch.)'''
            }
        ])
        self._create_lesson_questions(lesson, [
            {
                'text': 'A robot runs: drive forward 200 mm, turn right 90 degrees, repeated in a loop 4 times. What shape does it trace?',
                'choices': [
                    ('A square', True),
                    ('A straight line', False),
                    ('A triangle', False),
                    ('A circle', False),
                ]
            },
            {
                'text': 'What is the main difference between a repeat loop and a while loop?',
                'choices': [
                    ('A repeat loop runs a fixed number of times; a while loop runs as long as a condition is true', True),
                    ('A repeat loop is faster than a while loop', False),
                    ('A while loop can only be used with sensors', False),
                    ('There is no difference between them', False),
                ]
            },
            {
                'text': 'In an if/else statement, how many of the two branches run each time it is reached?',
                'choices': [
                    ('Exactly one branch runs', True),
                    ('Both branches run, one after the other', False),
                    ('Neither branch runs unless a loop surrounds it', False),
                    ('It depends on how many times the program has looped', False),
                ]
            },
            {
                'text': 'Why do programmers prefer a loop over copying the same instructions many times?',
                'choices': [
                    ('Changes only need to be made in one place, which reduces bugs', True),
                    ('Loops make the robot physically move faster', False),
                    ('Copied instructions are ignored by the robot', False),
                    ('Loops are required for the program to compile', False),
                ]
            }
        ])

        # Lesson 3: Sensor-Driven Decisions
        lesson = Lesson.objects.create(unit=unit, title='Sensor-Driven Decisions', order=2)
        self._create_sections(lesson, [
            {
                'title': 'Overview',
                'content': '''# Sensor-Driven Decisions

A program with only fixed distances is blind — it works until the world changes. Sensors give a robot eyes and touch, and conditionals turn those readings into decisions. This lesson connects the logic you learned last lesson to live sensor data.

## Learning Objectives

By the end of this lesson, you will be able to:
- Write conditionals that use sensor readings as their condition
- Use while loops and wait-until patterns to react to events
- Explain why sensor-driven programs handle changing environments better than fixed sequences
- Describe line following as a repeated sensor decision

> **TEKS alignment:** §127.749(c)(6) — The student uses computer programming to control the behavior of robotic systems.'''
            },
            {
                'title': 'Conditions from Sensors',
                'content': '''# Conditions from Sensors

Last lesson, conditions were plain statements like "the path is clear." In a real program, a condition is a **comparison against a sensor reading** — a live number or true/false value coming from hardware.

## Common Robot Sensors and Their Readings

| Sensor | What it reports | Example condition |
|--------|-----------------|-------------------|
| Distance (ultrasonic or laser) | Distance to nearest object, in mm | distance < 50 mm |
| Bumper (touch) | Pressed or not pressed | bumper is pressed |
| Light / color | Brightness or color under the robot | surface is dark |
| Gyro | Heading angle in degrees | heading > 90 degrees |

## From Reading to Decision

```text
if distance sensor reads less than 50 mm
    stop driving
else
    keep driving forward
```

The sensor supplies a fresh number every time the condition is checked. That single fact changes everything: the same program now behaves correctly whether the wall is 2 meters away or 20 centimeters away.

## Fixed vs Sensor-Driven

A fixed program says `drive forward 800 mm` and *hopes* the wall is 800 mm away. A sensor-driven program says *drive until you are close* and measures. If someone moves the wall, the fixed program crashes; the sensor-driven program still stops in time. When the environment can change — and it always can — sense, do not assume.'''
            },
            {
                'title': 'While Loops and Wait-Until Patterns',
                'content': '''# While Loops and Wait-Until Patterns

The most useful sensor pattern in robotics: keep doing something *while* a sensor condition holds.

## Drive Until Contact

```text
start driving forward
while the bumper is not pressed
    keep driving
stop driving
```

Each pass through the loop, the robot re-checks the bumper. The instant the reading flips to pressed, the loop exits and the robot stops. Note the word *not* — the loop continues while contact has NOT happened.

## The Wait-Until Shortcut

Many robot languages offer **wait until**, which reads even more naturally:

```text
start driving forward
wait until distance sensor reads less than 100 mm
stop driving
turn right 90 degrees
```

`wait until` pauses the program at that line, checking the sensor over and over, and releases it the moment the condition becomes true. It is a while loop with an empty body — same logic, cleaner page.

## Checking Often Matters

A sensor read is a snapshot. If your loop only checks the distance once per second on a fast robot, the robot can travel a long way between snapshots and blow past its stopping point. Real robot loops check sensors many times per second. When a robot overshoots a target, ask first: *how often was I checking?*

## Pattern Summary

- **while (condition): act** — repeat an action as long as things stay one way
- **wait until (condition)** — hold position in the program until things change'''
            },
            {
                'title': 'Thinking in States: Line Following',
                'content': '''# Thinking in States: Line Following

**Line following** — steering along a dark line on a light floor — is the classic sensor-driven behavior, and it is astonishingly simple: one sensor, one decision, repeated forever.

## The Core Algorithm

The robot aims to ride the **edge** of the line, with its light sensor straddling dark and light:

```text
while the run button has not been pressed again
    if the sensor sees dark
        curve left
    else
        curve right
```

That is the whole program. Seeing dark means the sensor has drifted onto the line, so curve one way; seeing light means it drifted off, so curve back. The robot wobbles along the edge in a zigzag — never balanced, always correcting.

## States: A Way to Think

At any moment the robot is in one **state** — "on dark" or "on light" — and each state has its own action. A sensor reading changes the state; the state selects the behavior. Bigger robots just have more states:

| State | Action | Switch when |
|-------|--------|-------------|
| Searching | Spin slowly | Target seen → Chasing |
| Chasing | Drive toward target | Distance < 50 mm → Arrived |
| Arrived | Stop and signal | — |

## Why This Scales

Self-driving cars, warehouse robots, and Mars rovers all use state-based thinking — just with thousands of states instead of two. Decompose behavior into states, give each state one job, and define exactly what reading causes each switch. You will use this style directly in the maze project next lesson.'''
            }
        ])
        self._create_lesson_questions(lesson, [
            {
                'text': 'A program says: while the bumper is not pressed, keep driving. When does the robot stop?',
                'choices': [
                    ('As soon as the bumper is pressed', True),
                    ('After a fixed number of loop passes', False),
                    ('When the battery runs out', False),
                    ('It never stops', False),
                ]
            },
            {
                'text': 'What does a wait-until instruction do?',
                'choices': [
                    ('Pauses the program at that line until the condition becomes true', True),
                    ('Ends the program immediately', False),
                    ('Runs the next instruction exactly once per second', False),
                    ('Turns off the sensors to save power', False),
                ]
            },
            {
                'text': 'In simple edge line following, what does the robot do when its sensor sees dark?',
                'choices': [
                    ('Curves one way, and curves the other way when it sees light', True),
                    ('Stops and waits for a human', False),
                    ('Drives straight at full speed', False),
                    ('Reverses direction completely', False),
                ]
            },
            {
                'text': 'Why does a sensor-driven program handle a changing environment better than a program with only fixed distances?',
                'choices': [
                    ('It measures the world each time it runs instead of assuming distances in advance', True),
                    ('Sensors make the motors more powerful', False),
                    ('Fixed distances are not allowed in robot programs', False),
                    ('Sensor programs skip conditionals entirely', False),
                ]
            }
        ])

        # Lesson 4: Simulation Project — Maze Navigation in VEXcode VR
        lesson = Lesson.objects.create(unit=unit, title='Simulation Project: Maze Navigation in VEXcode VR', order=3)
        self._create_sections(lesson, [
            {
                'title': 'Overview',
                'content': '''# Simulation Project: Maze Navigation in VEXcode VR

Time to put the whole unit together. In this project you will program a simulated robot to escape a maze — planning with pseudocode, driving with sequences and loops, and reacting to walls with sensor-driven conditionals.

We will use **VEXcode VR** (vr.vex.com) because it is free, runs in any browser, and needs no hardware or account to start. Everything you build, though, is platform-agnostic logic: the same algorithm would drive any robot with a distance sensor and a bumper.

## Learning Objectives

By the end of this project, you will be able to:
- Plan a navigation algorithm in pseudocode before implementing it
- Use distance and bumper sensors to detect and avoid walls
- Iterate on a program using test results to guide each change
- Evaluate your own solution against a rubric

> **TEKS alignment:** §127.749(c)(6) — The student uses computer programming to control the behavior of robotic systems.
> **TEKS alignment:** §127.749(c)(10) — The student uses appropriate software tools to design, build, and test robotic systems.'''
            },
            {
                'title': 'Setup and Mission Briefing',
                'content': '''# Setup and Mission Briefing

## Getting In

1. Open a browser and go to **vr.vex.com** — no install, no sign-up required to start
2. Choose a project type (blocks are fine; text works too — the logic is identical)
3. Click the playground selector and choose the **Wall Maze** playground
4. Press Start once with an empty program just to see the maze and where your robot begins

## Know Your Simulated Robot

The VR robot carries the same kinds of sensors you studied last lesson:

| Sensor | Use in this project |
|--------|---------------------|
| Distance sensor (front) | Detect a wall before touching it |
| Bumper | Detect a wall by contact |
| Location / heading | Check position and direction while debugging |

## The Mission

Drive from the starting position to the maze exit **without a human touching the controls after Start**. Your program must handle every wall on its own.

## The Cardinal Rule: Plan First

Before writing any code, study the maze from above and write pseudocode for your route. A first plan might be a pure sequence:

```text
drive forward until near a wall
turn left 90 degrees
drive forward until near a wall
turn right 90 degrees
```

Will a fixed route work? In this maze, yes, it can — but a sensor-driven solution is shorter, more elegant, and keeps working if the maze changes. You will build toward that. Write your pseudocode down; you will compare your code against it at every step.'''
            },
            {
                'title': 'Milestones: Build It in Steps',
                'content': '''# Milestones: Build It in Steps

Do not try to solve the maze in one sitting of typing. Professionals build incrementally — each milestone is a small program that *runs and proves something*.

## Milestone 1 — Move and Turn

Drive forward a fixed distance, turn right 90 degrees, drive again. Run it.
*Proves:* you can command motion and your turns are truly 90 degrees.

## Milestone 2 — Detect a Wall

```text
start driving forward
wait until distance sensor reads less than 50 mm
stop driving
```

Run it facing a wall. The robot should stop just short of contact.
*Proves:* you can read the distance sensor and react.

## Milestone 3 — Detect, Turn, Continue

Extend milestone 2: after stopping, turn 90 degrees toward the open path and keep driving to the next wall.
*Proves:* one full wall-handling cycle works.

## Milestone 4 — Loop to the Exit

Wrap the cycle in a loop:

```text
repeat until the robot reaches the exit
    drive forward until a wall is near
    decide which way to turn
    turn 90 degrees
```

The *decide* step is your design choice: a fixed list of turns, or a sensor check for the open direction.
*Proves:* the full mission.

## Iterate: The Test Cycle

For every milestone: **predict** what the robot will do, **run**, **compare** to your prediction, **change one thing**, repeat. If you change three things between runs and it works, you will not know which change mattered — and if it fails, you will not know which change broke it. One change per run.'''
            },
            {
                'title': 'Debugging Tips and Stretch Goals',
                'content': '''# Debugging Tips and Stretch Goals

## When It Goes Wrong (It Will)

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Robot grinds into the wall | Stop threshold too small, or sensor checked too late | Raise the threshold (try 100 mm); check the sensor continuously, not once |
| Turns drift off 90 degrees | Turning by time instead of by angle | Turn using heading, not a timed spin |
| Robot turns the wrong way at a junction | If/else branches swapped | Trace the pseudocode by hand at that junction |
| Works once, fails on rerun | Program depends on leftover state | Press the reset button in the playground before every run |
| Robot stops for no visible reason | Threshold too large — it is seeing a distant wall | Lower the threshold and reprint the sensor value |

The universal move: make the robot *tell you what it senses*. Print or display the distance reading while driving. Nearly every mystery dissolves once you can see the numbers the robot sees.

## Stretch Goal: The Right-Hand Rule

Classic maze wisdom: keep your right hand on the wall and you will eventually reach the exit of any simply-connected maze. As an algorithm:

```text
repeat until at the exit
    if there is no wall to the right
        turn right and drive forward one cell
    else if there is no wall ahead
        drive forward one cell
    else
        turn left
```

This version knows nothing about your specific maze — it solves *any* maze of this type. That leap, from a route to a general strategy, is the difference between a script and an algorithm.

## More Stretch Ideas

- Count the turns your robot makes and report the total at the exit
- Minimize total time: where can you safely drive faster?
- Solve the maze twice with different algorithms and compare run times'''
            },
            {
                'title': 'Reflection and Self-Check Rubric',
                'content': '''# Reflection and Self-Check Rubric

Engineering is not finished when the robot exits the maze — it is finished when you can explain *why* it works and *what you would change*. Complete both parts below.

## Reflection Prompts

Answer in a few sentences each:

1. Compare your final program to your original pseudocode. What changed, and what did you learn at the moment you changed it?
2. Describe one bug you hit. What did the robot *do*, what did you *expect*, and what single observation cracked the case?
3. Where does your program use each structure: sequence, loop, conditional, and a sensor-driven condition?
4. If the maze walls moved tomorrow, would your program still solve it? What would make your solution more general?
5. What surprised you most about programming in a simulator versus following worked examples?

## Self-Check Rubric

Check every line honestly before calling the project done:

- [ ] Pseudocode was written **before** the program, and both are saved
- [ ] The robot travels from start to exit with no human input after Start
- [ ] At least one **loop** removes repeated instructions
- [ ] At least one **conditional** chooses between two actions
- [ ] At least one decision uses a **sensor reading** (distance or bumper), not only fixed distances
- [ ] The robot never grinds against a wall for more than a moment
- [ ] The program succeeds on **three consecutive runs** after a playground reset
- [ ] All five reflection prompts are answered

## Level Up (Optional Honors Row)

- [ ] The right-hand rule (or another general strategy) solves the maze with **zero** maze-specific numbers in the code

If every box is checked, congratulations — you have designed, implemented, tested, and evaluated a complete robot behavior. That is the full engineering cycle, and it is exactly how you will approach every project from here on.'''
            }
        ])
        self._create_lesson_questions(lesson, [
            {
                'text': 'Why should you write pseudocode before programming the maze robot?',
                'choices': [
                    ('It lets you design and check the logic before dealing with code details', True),
                    ('The simulator refuses to run without uploaded pseudocode', False),
                    ('Pseudocode makes the simulated robot drive faster', False),
                    ('It is only needed for text-based programs, not blocks', False),
                ]
            },
            {
                'text': 'In the milestone approach, why do you change only one thing between test runs?',
                'choices': [
                    ('So you know exactly which change caused any new success or failure', True),
                    ('Because the simulator only allows one edit per run', False),
                    ('To keep the program under a size limit', False),
                    ('Because multiple changes always crash the robot', False),
                ]
            },
            {
                'text': 'Which pattern lets the robot stop before touching a wall?',
                'choices': [
                    ('Drive forward and wait until the distance sensor reads below a threshold, then stop', True),
                    ('Drive forward for exactly ten seconds and then stop', False),
                    ('Turn 90 degrees after every wheel rotation', False),
                    ('Repeat 4 times: drive forward 200 mm', False),
                ]
            },
            {
                'text': 'What makes the right-hand rule more general than a fixed list of turns?',
                'choices': [
                    ('It can solve mazes it has never seen, because it decides using walls it senses', True),
                    ('It uses more lines of code, which makes it more powerful', False),
                    ('It memorizes the maze on the first run', False),
                    ('It only works in the VEXcode VR Wall Maze playground', False),
                ]
            }
        ])

        self._create_unit5_quiz(unit)

    def _create_unit5_quiz(self, unit):
        quiz = Quiz.objects.create(
            unit=unit,
            title='Programming Robots Quiz',
            description='Show what you know about algorithms, sequencing, loops, conditionals, and sensor-driven robot programs.',
            passing_score=70,
            points=20,
            max_attempts=3,
            order=0
        )
        questions = [
            {
                'text': 'A robot program contains: turn right 90 degrees, then drive forward 300 mm. A second program contains the same two instructions in the opposite order. Why can the robots end up in different places?',
                'choices': [
                    ('Instructions run in sequence, so changing the order changes the path', True),
                    ('Robots randomly choose which instruction to run first', False),
                    ('The turn instruction cancels the drive instruction', False),
                    ('They cannot end up in different places if the instructions match', False),
                ]
            },
            {
                'text': 'Which pseudocode makes a robot trace a triangle?',
                'choices': [
                    ('repeat 3 times: drive forward 200 mm, then turn 120 degrees', True),
                    ('repeat 4 times: drive forward 200 mm, then turn 90 degrees', False),
                    ('repeat 3 times: turn 90 degrees', False),
                    ('drive forward 600 mm, then stop', False),
                ]
            },
            {
                'text': 'When is a while loop a better choice than a repeat loop?',
                'choices': [
                    ('When the number of repetitions depends on a condition, such as a sensor reading', True),
                    ('When you know the exact number of repetitions in advance', False),
                    ('When the loop body has more than one instruction', False),
                    ('When the program has no sensors at all', False),
                ]
            },
            {
                'text': 'A robot runs: if distance < 50 mm then stop, else keep driving. The sensor currently reads 120 mm. What does the robot do?',
                'choices': [
                    ('It keeps driving, because the condition is false', True),
                    ('It stops, because 120 is greater than 50', False),
                    ('It runs both branches to be safe', False),
                    ('It waits for a human to decide', False),
                ]
            },
            {
                'text': 'In edge line following, the robot curves left on dark and right on light, checking the sensor over and over. What overall behavior results?',
                'choices': [
                    ('It zigzags along the edge of the line, constantly correcting', True),
                    ('It drives perfectly straight down the center of the line', False),
                    ('It stops at the first dark reading', False),
                    ('It spins in place forever', False),
                ]
            },
            {
                'text': 'Why is a wall-following strategy like the right-hand rule considered a general algorithm rather than a script for one maze?',
                'choices': [
                    ('Its decisions come from sensed walls, so it works in mazes it was never written for', True),
                    ('It contains more instructions than a fixed route', False),
                    ('It only runs in a browser-based simulator', False),
                    ('It avoids using any loops or conditionals', False),
                ]
            },
        ]
        self._create_quiz_questions(quiz, questions)

    # ================== UNIT 6: Engineering Design Capstone ==================
    def _create_unit6(self, course):
        unit = Unit.objects.create(course=course, title='Engineering Design Capstone', order=5)

        # Lesson 1: The Engineering Design Process
        lesson = Lesson.objects.create(unit=unit, title='The Engineering Design Process', order=0)
        self._create_sections(lesson, [
            {
                'title': 'Overview',
                'content': '''# The Engineering Design Process

Every robot you have seen — from a competition bot to a Mars rover — was built using the same repeatable method: the engineering design process. In this lesson you will learn the steps of that process and why real engineers treat it as a loop, not a checklist.

## Learning Objectives

By the end of this lesson, you will be able to:
- Name and describe the eight steps of the engineering design cycle
- Explain why the design process is iterative rather than linear
- Identify where each step shows up in robotics competitions and industry
- Recognize the design process in a real product development story

> **TEKS alignment:** §127.749(c)(9) — apply the engineering design process to solve problems and develop robotic systems'''
            },
            {
                'title': 'The Design Cycle Step by Step',
                'content': '''# The Design Cycle Step by Step

Engineers around the world use versions of the same cycle. Here is one common form with eight steps:

| Step | What You Do | Robotics Example |
|------|-------------|------------------|
| 1. Identify | Define the problem clearly | "Our robot must move a ball into a goal" |
| 2. Research | Learn what already exists | Watch match videos, read the game rules |
| 3. Ideate | Brainstorm many possible solutions | Sketch a claw, a scoop, and a launcher |
| 4. Select | Choose the most promising idea | Pick the scoop using a decision matrix |
| 5. Prototype | Build a quick, rough version | Cardboard scoop taped to a test chassis |
| 6. Test | Try it and measure results | Time 10 attempts to collect the ball |
| 7. Iterate | Improve based on what you learned | Widen the scoop, retest |
| 8. Communicate | Share results and decisions | Notebook entry, team presentation |

## Two Steps People Skip (and Regret)

- **Research** feels slow, but it prevents you from reinventing a solution that already failed for another team.
- **Communicate** is not just the final slide deck. Engineers communicate constantly — notebook entries, sketches, and quick team check-ins keep everyone building the *same* robot.

Memorize the steps, but remember: the order can flex. What never changes is that every decision is backed by evidence from research or testing.'''
            },
            {
                'title': 'A Loop, Not a Line',
                'content': '''# A Loop, Not a Line

If you drew the design process as a straight line, it would suggest you get everything right on the first try. Nobody does — not students, not NASA.

## Why the Process Loops

- **Testing reveals surprises.** A gripper that works on a smooth table may drop objects on carpet. That result sends you back to *ideate* or *prototype*, not to the trash can.
- **Requirements change.** Competition rules get clarified mid-season. Customers change their minds. A looping process absorbs change; a linear one breaks.
- **Each loop is cheaper than the last.** Early loops use cardboard and sketches. Later loops refine details. Failing early on a cheap prototype saves failing late on an expensive build.

## Small Loops Inside Big Loops

A season-long robot build is one giant loop, but inside it are dozens of small ones. You might loop three times just on the shape of a single arm:

1. Sketch the arm, build it from spare parts, test it — too heavy.
2. Shorten the arm, test again — lifts well but blocks the sensor.
3. Move the sensor mount, test again — success.

Each mini-loop took an afternoon. Engineers call this **rapid iteration**, and teams that iterate more times almost always beat teams with one "perfect" plan.

> A design you have tested five times beats a design you have imagined fifty times.'''
            },
            {
                'title': 'Design in Competitions and Industry',
                'content': '''# Design in Competitions and Industry

The design process is not just a school diagram — it is how robotics actually gets done.

## In Robotics Competitions

Leagues such as FIRST and VEX release a new game challenge every season. Winning teams follow a recognizable pattern:

- **Kickoff week:** identify the problem by studying the game manual and scoring rules
- **Strategy phase:** research past robots and decide which tasks score the most points
- **Build phase:** ideate, select, and prototype mechanisms — often several in parallel
- **Practice and events:** every match is a test; pit crews iterate between matches
- **Judging:** teams communicate their process through notebooks and interviews

Many competition awards are given for the *process*, not just the robot. Judges want evidence that your design decisions came from testing, not luck.

## In Industry

A company designing a warehouse robot follows the same loop at a bigger scale:

- Engineers interview warehouse workers to **identify** real pain points
- They **research** competitors and existing patents
- Teams **prototype** with 3D-printed parts and software simulations before any factory tooling exists
- **Test** data from pilot warehouses drives the next design revision
- Formal design reviews are how the team **communicates** and gets approval to continue

The tools change — CAD software instead of cardboard, budgets in the millions — but the cycle you are learning now is the same one professionals use for their whole careers.'''
            }
        ])
        self._create_lesson_questions(lesson, [
            {
                'text': 'Which sequence best describes the engineering design process?',
                'choices': [
                    ('Identify, research, ideate, select, prototype, test, iterate, communicate', True),
                    ('Build first, then write a problem statement to match what you built', False),
                    ('Select a solution before researching so the team stays focused', False),
                    ('Test only once, at the very end, to avoid wasting time', False),
                ]
            },
            {
                'text': 'Why is the design process described as a loop rather than a line?',
                'choices': [
                    ('Test results and changing requirements send engineers back to earlier steps to improve the design', True),
                    ('Engineers repeat the same work to fill out timesheets', False),
                    ('Looping guarantees the first prototype will be perfect', False),
                    ('A line would require too many team members', False),
                ]
            },
            {
                'text': 'What is the main advantage of failing early on a cheap prototype?',
                'choices': [
                    ('Problems are found while changes are still fast and inexpensive to make', True),
                    ('It lets the team skip the research step entirely', False),
                    ('Early failures do not need to be documented', False),
                    ('Cheap prototypes always behave exactly like the final product', False),
                ]
            },
            {
                'text': 'In robotics competitions, why do judges review a team\'s design process and not just the finished robot?',
                'choices': [
                    ('They want evidence that design decisions came from research and testing', True),
                    ('The robot itself is never inspected at competitions', False),
                    ('Judges are not allowed to watch matches', False),
                    ('The process only matters for teams that lose their matches', False),
                ]
            }
        ])

        # Lesson 2: Defining Problems & Constraints
        lesson = Lesson.objects.create(unit=unit, title='Defining Problems & Constraints', order=1)
        self._create_sections(lesson, [
            {
                'title': 'Overview',
                'content': '''# Defining Problems & Constraints

A vague problem produces a vague robot. Before any building starts, engineers pin down exactly what problem they are solving, what success looks like, and what limits they must work within. This lesson gives you the tools: problem statements, criteria and constraints, decision matrices, and structured brainstorming.

## Learning Objectives

By the end of this lesson, you will be able to:
- Write a clear problem statement with a user, a need, and a goal
- Distinguish design criteria from design constraints
- Use a decision matrix to compare candidate solutions objectively
- Apply brainstorming ground rules that produce more and better ideas

> **TEKS alignment:** §127.749(c)(9) — apply the engineering design process to solve problems and develop robotic systems
> **TEKS alignment:** §127.749(c)(11) — apply product development and problem-solving skills to design solutions'''
            },
            {
                'title': 'Writing a Strong Problem Statement',
                'content': '''# Writing a Strong Problem Statement

A problem statement is one or two sentences that define the problem **without prescribing a solution**.

## The Formula

> **[User]** needs a way to **[need]** so that **[goal/benefit]**.

Examples:

- Weak: "We need to build a robot with a claw." (That is a solution, not a problem.)
- Strong: "Competition teams need a way to move foam cubes from the floor to a 30 cm platform so that they can score points during the 90-second autonomous period."

The strong version tells you what success means (cubes on the platform, within 90 seconds) but leaves the *how* open — claw, scoop, conveyor, or something nobody has thought of yet.

## Why Solution-Free Wording Matters

If your problem statement says "build a claw," your team will only brainstorm claws. Studies of design teams show that the way a problem is framed controls the range of ideas produced. Engineers call this **framing bias**, and a solution-free problem statement is the antidote.

## Checklist for Your Own Problem Statement

- Names a specific user or beneficiary
- Describes a need, not a gadget
- States a measurable goal (a number, a time limit, a distance)
- Contains no specific mechanism or technology
- Fits in one or two sentences

Rewrite it until every box checks. Ten careful minutes here saves weeks of building the wrong thing.'''
            },
            {
                'title': 'Criteria vs. Constraints',
                'content': '''# Criteria vs. Constraints

Two words that sound similar but play very different roles:

## Criteria — What "Better" Means

Criteria are the qualities that make one solution better than another. They are measured on a scale:

- Speed: collects a game piece in under 3 seconds
- Reliability: succeeds on at least 9 of 10 attempts
- Simplicity: fewer moving parts to break or maintain

A design can score *higher or lower* on a criterion.

## Constraints — What You Cannot Break

Constraints are hard limits. A design either satisfies them or it is disqualified — there is no partial credit:

| Constraint Type | Example |
|-----------------|---------|
| Time | The design must be finished before the first competition date |
| Budget | Total parts cost may not exceed the team budget |
| Materials | Only parts from the approved kit list may be used |
| Rules | The robot must fit inside the size limit at match start |
| Safety | No exposed pinch points; battery must be secured |

## Why the Difference Matters

Constraints filter first, criteria rank second. A brilliant launcher design that exceeds the size limit is not "a great idea with one flaw" — it is out. Engineers check constraints early so no one spends weeks perfecting an illegal design.

**Quick test:** if going over the limit means disqualification or failure, it is a constraint. If more (or less) of it just makes the design better, it is a criterion.'''
            },
            {
                'title': 'Decision Matrices',
                'content': '''# Decision Matrices

When your team has three good ideas and one build season, how do you choose without arguing in circles? A **decision matrix** turns the choice into numbers.

## How to Build One

1. List your candidate solutions as rows
2. List your criteria as columns, each with a **weight** showing its importance
3. Score each solution on each criterion (1 = poor, 5 = excellent)
4. Multiply each score by the weight, then total each row

## Example: Choosing a Cube-Collecting Mechanism

| Solution | Speed (x3) | Reliability (x4) | Build Time (x2) | Total |
|----------|-----------|------------------|-----------------|-------|
| Claw | 3 (9) | 4 (16) | 3 (6) | **31** |
| Scoop | 4 (12) | 5 (20) | 4 (8) | **40** |
| Conveyor | 5 (15) | 3 (12) | 1 (2) | **29** |

The scoop wins: it is not the fastest option, but reliability carries the most weight and the scoop scores highest there.

## Rules for Honest Matrices

- Agree on weights **before** scoring, so nobody tunes the math to favor a pet idea
- Score from evidence — test data, research, past experience — not enthusiasm
- If a solution violates a constraint, it never enters the matrix at all
- A close result (say, 40 vs. 38) is a signal to prototype both and let testing decide

A decision matrix does not think for you. It makes your reasoning visible so the whole team — and later, competition judges — can see *why* you chose what you chose.'''
            },
            {
                'title': 'Brainstorming Rules',
                'content': '''# Brainstorming Rules

Brainstorming looks unstructured, but productive teams follow strict ground rules. The goal of a brainstorm is **quantity and range** — evaluation comes later.

## The Four Classic Rules

1. **Defer judgment.** No criticism, no eye-rolling, no "that will never work" during the session. Judgment shuts down the flow of ideas.
2. **Go for quantity.** Thirty ideas beat five. Weak ideas often trigger strong ones in someone else.
3. **Welcome wild ideas.** An impossible idea ("What if the robot flew over the wall?") can be tamed into a practical one ("What if it extended an arm over the wall?").
4. **Build on ideas.** Say "yes, and..." to combine and improve. Group ideas usually beat any single first draft.

## Techniques That Help

- **Silent start:** everyone sketches or writes ideas alone for five minutes before sharing, so quiet teammates contribute and the loudest voice does not anchor the group
- **Sketch it:** a rough drawing communicates a mechanism far faster than a paragraph
- **Set a number:** "We are not done until the board has 25 ideas" pushes past the obvious ones

## After the Brainstorm

Only after the idea flood ends does evaluation begin: check each idea against constraints, then run the survivors through a decision matrix. Keep every rejected idea in your engineering notebook — next season, or when a chosen design fails testing, that list is treasure.'''
            }
        ])
        self._create_lesson_questions(lesson, [
            {
                'text': 'Which of these is the strongest problem statement?',
                'choices': [
                    ('Teams need a way to move cubes onto a 30 cm platform so they can score during the autonomous period', True),
                    ('We should build a four-bar claw with rubber grips', False),
                    ('Our robot needs to be really good this year', False),
                    ('The solution must use the motor our team already owns', False),
                ]
            },
            {
                'text': 'What is the key difference between a criterion and a constraint?',
                'choices': [
                    ('A constraint is a hard limit that must be satisfied; a criterion measures how good a valid design is', True),
                    ('Criteria are written by judges and constraints are written by students', False),
                    ('Constraints only apply to software, while criteria apply to hardware', False),
                    ('There is no difference; the two words are interchangeable', False),
                ]
            },
            {
                'text': 'In a weighted decision matrix, why should the team agree on weights before scoring the solutions?',
                'choices': [
                    ('So no one can adjust the math afterward to favor their preferred idea', True),
                    ('Because weights are required to be equal for every criterion', False),
                    ('So the matrix can include designs that violate constraints', False),
                    ('Because scores can only be assigned by the team captain', False),
                ]
            },
            {
                'text': 'During a brainstorming session, a teammate proposes a wild, seemingly impossible idea. According to brainstorming rules, what should the team do?',
                'choices': [
                    ('Welcome it and build on it, since wild ideas can lead to practical ones', True),
                    ('Immediately explain why it violates the constraints', False),
                    ('Stop the session and vote on the ideas collected so far', False),
                    ('Erase it so the idea board only shows realistic options', False),
                ]
            }
        ])

        # Lesson 3: Documentation & Schematics: The Engineering Notebook
        lesson = Lesson.objects.create(unit=unit, title='Documentation & Schematics: The Engineering Notebook', order=2)
        self._create_sections(lesson, [
            {
                'title': 'Overview',
                'content': '''# Documentation & Schematics: The Engineering Notebook

If it is not written down, it did not happen — that is how engineers, competition judges, and patent offices see it. This lesson covers the engineering notebook: what goes in it, how to keep it, and how to read and draw the schematics and diagrams that live inside it.

## Learning Objectives

By the end of this lesson, you will be able to:
- Explain why engineers document their work as they go
- Keep an engineering notebook with dated entries, sketches, decisions, and test data
- Read and draw simple schematics and diagrams using standard labeling conventions
- Describe how notebooks are used in competition judging and patent claims

> **TEKS alignment:** §127.749(c)(9) — document the engineering design process, including sketches, schematics, and test records'''
            },
            {
                'title': 'Why Engineers Document',
                'content': '''# Why Engineers Document

Writing things down feels slow when you would rather be building. Here is why professionals do it anyway.

## Memory Is Unreliable

Three weeks from now, will you remember which motor setting made the arm oscillate, or why the team rejected the conveyor design? Probably not — but your notebook will. Documentation turns one afternoon of testing into a permanent team asset.

## Teams Change, Notebooks Stay

Students graduate. Engineers switch projects. A well-kept notebook lets a new teammate pick up exactly where the last one left off, instead of re-running old experiments. In industry this is called **knowledge transfer**, and companies treat it as seriously as the hardware itself.

## Evidence Beats Opinion

When two teammates disagree — "the wide wheels were better!" "no, the narrow ones!" — a notebook with recorded test data ends the debate in seconds. Documentation is how a team argues with evidence instead of volume.

## Documentation Prevents Repeated Failures

Every failed test written down is a trap disarmed for the future. Teams without records famously rebuild the same broken mechanism twice, a season apart, because nobody wrote down why it failed the first time.

## The Habit That Matters Most

Document **as you work**, not from memory afterward. A five-line entry written during testing is worth more than a beautiful page reconstructed a week later, because reconstructed pages quietly fill their gaps with guesses.'''
            },
            {
                'title': 'Inside the Engineering Notebook',
                'content': '''# Inside the Engineering Notebook

An engineering notebook is a chronological record of your project. Paper or digital, the core rules are the same.

## Every Entry Includes

- **Date** and the names of who worked
- **Goal** for the session, in one line
- **What happened:** sketches, decisions, calculations, observations
- **Test data:** actual numbers, even (especially) when the test failed
- **Next steps:** what the results tell you to try next

## What a Good Entry Looks Like

> **March 4 — Ari, Jordan.** Goal: stop gripper from dropping cubes.
> Tested rubber pads on gripper jaws: 8/10 successful lifts, up from 3/10 with bare plastic (see table, p. 41). Cube slips when grabbed by a corner. Decision: add a wider jaw plate so corner grabs become face grabs. Sketch below. Next: cut plate, retest by Friday.

Notice: dated, specific numbers, a decision **with its reason**, and a plan.

## Notebook Conventions

- Write in ink; never erase — cross out mistakes with a single line so the original stays readable
- Number every page and never tear one out
- Record failures with the same care as successes
- Glue or link in photos, printouts, and data tables rather than describing them vaguely
- Sign and date the bottom of each page in formal notebooks

These rules exist because a notebook is a **legal-grade record**: crossed-out-but-readable mistakes and numbered pages prove nothing was rewritten after the fact.'''
            },
            {
                'title': 'Reading and Drawing Schematics',
                'content': '''# Reading and Drawing Schematics

A schematic is a diagram that shows how the parts of a system connect — not what they physically look like. Engineers use schematics because a clear symbol beats a photograph for explaining *function*.

## Types of Diagrams You Will Use

| Diagram | Shows | Example Use |
|---------|-------|-------------|
| Circuit schematic | Electrical connections using standard symbols | Battery, switch, motor controller wiring |
| Wiring diagram | Which physical port each wire plugs into | "Left motor into port 3" |
| Block diagram | Major components as labeled boxes with arrows | Sensor to controller to motor signal flow |
| Mechanical sketch | Shape and dimensions of a part | Gripper jaw with measurements |

## Standard Symbols and Labels

Circuit schematics use symbols shared by engineers worldwide: a battery is a pair of long and short parallel lines, a switch is a hinged line that opens a gap, a motor is a circle labeled **M**. Because the symbols are standard, an engineer in another country can read your schematic without reading your language.

## Labeling Conventions That Make Diagrams Useful

- Give every component a name and reference label (M1 = left drive motor, S2 = bumper switch)
- Label wire connections with port numbers so the diagram matches the real robot
- Add units to every measurement: 15 cm, 9 V, 200 RPM — a number without a unit is a guess
- Include a title, a date, and your name — a diagram is a notebook entry too

## Drawing Tips

Draw with a straightedge or a free online diagram tool, keep lines horizontal and vertical, and space components out. A schematic that is 20 percent larger and 100 percent clearer is always the right trade.'''
            },
            {
                'title': 'Notebooks in Competitions and Patents',
                'content': '''# Notebooks in Competitions and Patents

Engineering notebooks are not busywork — in two important arenas, the notebook itself is judged.

## Competition Judging

In leagues such as VEX and FIRST, notebook-based awards (Design Award, Excellence Award) rank among the most prestigious a team can win. Judges look for:

- A complete record of the **full design cycle** — problem definition through testing and iteration, not just glamour shots of the finished robot
- **Dated, chronological** entries proving the work happened over the season
- **Decisions with reasons:** decision matrices, test data tables, and explanations of why alternatives were rejected
- Contributions from the **whole team**, not one designated writer

At many events, judges read the notebook before they ever see the robot. A mediocre robot with an excellent notebook regularly out-scores a great robot with no paper trail.

## Patents and Invention Records

When an inventor applies for a patent, they must describe the invention precisely — and if a dispute arises about who developed what and when, dated engineering records become key evidence. This is why professional notebooks follow the strict rules you learned: ink, numbered pages, no removed sheets, dated and signed entries. Corporate research labs require them, and some have witnesses co-sign important pages.

## The Takeaway

The habits you practice in a class notebook — date everything, show your data, explain your decisions — are the exact habits that win design awards at seventeen and protect inventions at thirty. Start now and the habit is free.'''
            }
        ])
        self._create_lesson_questions(lesson, [
            {
                'text': 'When is the best time to write an engineering notebook entry?',
                'choices': [
                    ('During or immediately after the work session, while details are fresh', True),
                    ('At the end of the season, so the story reads smoothly', False),
                    ('Only after a test succeeds, since failures are not worth recording', False),
                    ('Whenever a judge or teacher asks to see the notebook', False),
                ]
            },
            {
                'text': 'Why do formal engineering notebooks require ink, numbered pages, and single-line cross-outs instead of erasing?',
                'choices': [
                    ('These rules prove the record was not altered after the fact, which matters for judging and patents', True),
                    ('Pencil marks are harder for teammates to read than ink', False),
                    ('Erasers are banned from most competition venues', False),
                    ('Numbered pages make the notebook heavier and more impressive', False),
                ]
            },
            {
                'text': 'What does a block diagram show?',
                'choices': [
                    ('Major components as labeled boxes with arrows showing how signals or information flow between them', True),
                    ('A photorealistic drawing of what the finished robot looks like', False),
                    ('The exact resistance value of every wire in the robot', False),
                    ('The schedule of matches at a competition', False),
                ]
            },
            {
                'text': 'A diagram in your notebook shows a motor labeled M1 connected to port 3, with an arm length marked 15 cm. Which labeling convention is still missing from this entry?',
                'choices': [
                    ('A title, date, and author for the diagram itself', True),
                    ('A reference label for the motor', False),
                    ('Units on the arm measurement', False),
                    ('The port number for the motor connection', False),
                ]
            }
        ])

        # Lesson 4: Prototype, Test, Iterate
        lesson = Lesson.objects.create(unit=unit, title='Prototype, Test, Iterate', order=3)
        self._create_sections(lesson, [
            {
                'title': 'Overview',
                'content': '''# Prototype, Test, Iterate

Ideas are cheap; evidence is gold. This lesson is about turning ideas into prototypes, testing them fairly, reading the data honestly, and looping until the design earns its place on the robot. You will also meet free tools that let you prototype with no hardware at all.

## Learning Objectives

By the end of this lesson, you will be able to:
- Match prototype fidelity (cardboard, CAD, simulator) to the question being asked
- Design a fair test that changes one variable at a time
- Record and analyze test data to make a design decision
- Explain why failure is information and describe a real iteration cycle

> **TEKS alignment:** §127.749(c)(9) — develop and test prototypes as part of the engineering design process
> **TEKS alignment:** §127.749(c)(11) — use problem-solving and product development skills to refine a design'''
            },
            {
                'title': 'From Cardboard to CAD to Simulator',
                'content': '''# From Cardboard to CAD to Simulator

A prototype is a model built to answer a question. The trick is matching the **fidelity** — how polished and realistic it is — to the question you are asking.

## Low Fidelity: Cardboard, Tape, and Spare Parts

- **Answers:** Is this shape roughly right? Can a scoop this wide even reach the game piece?
- **Cost:** minutes and pennies
- Cardboard mock-ups, paper cutouts, and hand-held "pretend it moves" models catch geometry mistakes before you cut a single real part

## Medium Fidelity: CAD Models

- **Answers:** Do the parts fit together? Does the arm collide with the frame? What will it weigh?
- Computer-aided design (CAD) tools let you assemble a virtual robot and measure everything exactly. **Tinkercad** is a free, browser-based CAD tool used in classrooms worldwide — no hardware or installation needed

## Virtual Circuits and Robots: Simulators

- **Answers:** Does the circuit work? Does the program drive the robot correctly?
- **Tinkercad Circuits** (free, browser-based) lets you wire virtual components — LEDs, sensors, microcontrollers — and run real code against them, with zero risk of releasing magic smoke from real parts
- **VEXcode VR** (also free and browser-based) puts a virtual robot in playground and maze worlds so you can prototype driving and sensor logic before touching a physical robot

## Choosing Fidelity

Start as low as the question allows. If cardboard can answer it, cardboard wins — it fails faster and cheaper. Save high-fidelity builds for questions that only realism can answer, like "does it survive a real match?"'''
            },
            {
                'title': 'Designing a Fair Test',
                'content': '''# Designing a Fair Test

A test is only useful if you can trust its result. Fair tests borrow their rules from science class.

## Change One Variable at a Time

Suppose you swap the gripper pads **and** increase motor power, and performance improves. Which change helped? You cannot know. Change one thing, test, record, then change the next.

## Control the Conditions

Keep everything else identical between trials:

- Same starting position and battery charge level
- Same game piece (a worn foam cube grips differently than a new one)
- Same surface — results on a slick floor do not transfer to a foam field

## Repeat the Trials

One success can be luck. Run each configuration enough times — ten is a good classroom default — that a pattern can show itself. Report results as a fraction or average ("8/10 lifts succeeded"), never as "it worked."

## Decide the Finish Line Before You Start

Write down your success threshold **before** testing: "We adopt the new pads if they succeed at least 9 of 10 times." Deciding afterward invites the temptation to move the goalposts to match whatever happened.

## Plan the Measurement

- Define exactly what counts as a success and as a failure
- Choose the number you will record: time in seconds, distance in centimeters, successes out of ten
- Prepare the data table in your notebook *before* the first trial, so recording takes seconds and no result gets skipped

A fair test can be simple. Ten repeated trials with one variable changed and honest counting will out-perform a fancy rig with sloppy method every time.'''
            },
            {
                'title': 'Reading the Data',
                'content': '''# Reading the Data

Numbers only help if you actually look at them. Here is a real-style comparison from a gripper test, ten trials per configuration:

| Configuration | Successful Lifts | Avg. Lift Time (s) | Failure Notes |
|---------------|------------------|--------------------|---------------|
| Bare plastic jaws | 3 / 10 | 2.1 | Cube slips on smooth faces |
| Rubber pads | 8 / 10 | 2.4 | Slips only on corner grabs |
| Rubber pads + wide plate | 10 / 10 | 2.9 | None observed |

## What the Table Tells Us

- **Reliability climbs** with each change: 30 percent, then 80, then 100
- **Speed drops** as reliability rises — the wide plate adds almost a second per lift
- The **failure notes** column is doing quiet heroic work: "slips only on corner grabs" is what pointed the team toward the wide plate in the first place

## Making the Decision

Is 10/10 at 2.9 seconds better than 8/10 at 2.4? Go back to your criteria and constraints. If match strategy needs at most 12 lifts in a 60-second period, 2.9 seconds each still fits — so reliability wins. If the strategy demanded 25 lifts, the team would need another iteration: keep the plate but hunt for the lost speed.

## Habits of Good Data Readers

- Record **why** each failure happened, not just that it happened — failure notes drive the next iteration
- Watch for trade-offs; improvements rarely come free
- Let the numbers argue with your hopes, and let the numbers win'''
            },
            {
                'title': 'Failure Is Information: An Iteration Case Study',
                'content': '''# Failure Is Information: An Iteration Case Study

When a prototype fails, beginners hear "you were wrong." Engineers hear "here is exactly what to fix." Reframing failure as information is the single biggest mindset upgrade in this course.

## Case Study: The Ball Launcher

A team needs to launch a ball into a goal 2 meters away. Watch the loop run four times:

**Iteration 1 — cardboard and rubber bands.** The angle test rig shows the ball needs roughly a 45 degree launch angle to have a chance. Distance: 0.8 m. *Verdict: angle validated, power hopeless — but the team now knows the geometry.*

**Iteration 2 — spring-loaded arm.** Distance jumps to 2.3 m, but ten trials land anywhere from 1.6 m to 2.6 m. *Verdict: power solved; consistency is now the problem. The failure named its own cause: the spring released differently each shot.*

**Iteration 3 — motor-driven flywheel.** A spinning wheel grips and throws each ball identically: 9 of 10 shots land within 10 cm of the target. But the flywheel takes 4 seconds to spin up between shots. *Verdict: accuracy solved; a new trade-off appears.*

**Iteration 4 — keep the flywheel spinning continuously.** Spin-up delay eliminated; fire rate now limited only by loading. Ship it.

## What to Notice

- No iteration was wasted — each one converted a vague problem ("it does not work") into a specific one ("spring release varies")
- The team never had to be right on the first try; they only had to **measure honestly and respond**
- Total cost of the three "failures": some cardboard, a spring, and a week — cheap tuition for a competition-winning launcher

> First tries fail; that is what they are for. Log the failure, name its cause, and let it aim your next iteration.'''
            }
        ])
        self._create_lesson_questions(lesson, [
            {
                'text': 'A team wants to know whether their scoop is wide enough to reach a game piece. What is the most appropriate first prototype?',
                'choices': [
                    ('A quick cardboard mock-up to check the geometry', True),
                    ('A fully machined aluminum scoop with final motors', False),
                    ('A season-long CAD project modeling every screw', False),
                    ('No prototype; width questions cannot be tested', False),
                ]
            },
            {
                'text': 'Why should a fair test change only one variable at a time?',
                'choices': [
                    ('So any change in the results can be traced to the one variable that changed', True),
                    ('Because test rigs physically cannot change two parts at once', False),
                    ('To make the test take as long as possible', False),
                    ('So the team can skip repeating trials', False),
                ]
            },
            {
                'text': 'In the gripper test data, adding the wide plate raised successful lifts from 8/10 to 10/10 but increased lift time from 2.4 to 2.9 seconds. What is this an example of?',
                'choices': [
                    ('A design trade-off that must be judged against the team\'s criteria', True),
                    ('A failed test that should be deleted from the notebook', False),
                    ('Proof that reliability and speed always improve together', False),
                    ('An unfair test, because two results changed at once', False),
                ]
            },
            {
                'text': 'In the ball launcher case study, what did the spring-loaded arm\'s inconsistent distances actually give the team?',
                'choices': [
                    ('Specific information — the spring released differently each shot — that aimed the next iteration', True),
                    ('Proof that the 2-meter goal was impossible to reach', False),
                    ('A reason to return to the cardboard prototype permanently', False),
                    ('Nothing, because failed trials contain no useful data', False),
                ]
            }
        ])

        # Lesson 5: Presenting Your Design
        lesson = Lesson.objects.create(unit=unit, title='Presenting Your Design', order=4)
        self._create_sections(lesson, [
            {
                'title': 'Overview',
                'content': '''# Presenting Your Design

Engineering that cannot be explained cannot be adopted, funded, or awarded. The final step of the design process — communicate — is a skill of its own, and it is the one that turns your months of work into something other people can understand and value. This capstone lesson covers presentations, demos, tough questions, critique, and a look back at everything the course has built toward.

## Learning Objectives

By the end of this lesson, you will be able to:
- Structure a design presentation that tells the story of your design process
- Explain trade-offs honestly using your own test data
- Plan and deliver a live demo with a backup plan
- Answer judge and stakeholder questions, and give and receive useful critique

> **TEKS alignment:** §127.749(c)(11) — communicate product development results and defend design decisions to an audience'''
            },
            {
                'title': 'Structuring a Design Presentation',
                'content': '''# Structuring a Design Presentation

A design presentation is not a list of features — it is the **story of your process**. Judges and stakeholders want to follow the same loop you lived: problem, options, evidence, decision, result.

## A Structure That Works

1. **The problem** — your problem statement, criteria, and constraints (30 seconds; the audience cannot judge a solution without knowing the problem)
2. **The options** — the ideas you brainstormed, shown as sketches
3. **The decision** — your decision matrix and the reasons the winner won
4. **The evidence** — prototypes and test data, including the failures that taught you the most
5. **The result** — what the final design does, measured against the original criteria
6. **Next steps** — what you would improve with more time (every real project has these)

## Delivery Rules of Thumb

- **One idea per slide.** A slide crowded with text competes with your voice and wins
- **Show, do not tell.** A 10-second video of the gripper lifting a cube beats a paragraph about it
- **Numbers over adjectives.** "Succeeds 9 times out of 10" convinces; "works really well" does not
- **Everyone speaks.** Judges probe whether the whole team understands the robot; a one-presenter team looks like a one-engineer team
- **Rehearse against the clock.** Time limits at competitions are enforced; a cut-off ending erases your strongest material

## The Opening Line

Skip "Hi, we are Team 42 and this is our robot." Try: "Foam cubes are worth two points, and our robot moves one every four seconds — here is how we got there." An opening built on the problem and a number earns the next five minutes of attention.'''
            },
            {
                'title': 'Explaining Trade-offs and Running the Demo',
                'content': '''# Explaining Trade-offs and Running the Demo

## Own Your Trade-offs

Every design gives something up. Weak presenters hide this; strong presenters lead with it, because a stated trade-off proves you understood the choice:

> "The wide jaw plate costs us half a second per lift, but it took our success rate from 80 to 100 percent. Our match strategy needs 12 lifts a minute, and 2.9 seconds per lift still clears that bar — so we paid the speed price on purpose."

That single sentence shows a criterion, a measurement, a constraint check, and a deliberate decision. It is the sound of engineering.

## Anatomy of an Honest Trade-off Statement

- What you gave up, with a number
- What you gained, with a number
- Why the gain mattered more, tied to your criteria or strategy

## Running a Live Demo

Demos are persuasive and dangerous — hardware fails precisely when an audience gathers. Treat the demo like any other engineered system:

- **Rehearse the exact demo**, in the exact order, on the exact table or field you will use if possible
- **Demo your reliable feature**, not your most impressive one; a smooth simple demo beats a flashy failure
- **Have a fallback:** a short pre-recorded video of the same task, ready to play if the hardware acts up
- **Narrate while it runs:** tell the audience what to watch for before it happens ("watch the arm pause to center the cube")
- **If it fails, debug out loud calmly.** Judges have watched a thousand demos fail; a composed "that is the sensor timeout we mentioned — here is the recording" often earns more respect than a flawless run.'''
            },
            {
                'title': 'Questions and Critique',
                'content': '''# Questions and Critique

The question-and-answer period is not an attack — it is the audience taking your design seriously. The same is true of critique from teammates. Both are free engineering labor if you handle them well.

## Answering Judge and Stakeholder Questions

- **Pause before answering.** A two-second think reads as confidence, not hesitation
- **Answer from evidence:** "Our notebook page 41 shows that test — 8 of 10 lifts" beats an improvised guess
- **Say "I do not know" honestly** — then follow with how you would find out. Judges reward honesty and punish bluffing, because professionals can tell the difference
- **Let the expert answer.** If a teammate ran the tests, hand the question over; routing questions to the right person is a team strength, not a weakness

Common question styles to rehearse: "Why did you reject the alternatives?", "What was your biggest failure?", "What would you change with another month?", "Show me where the notebook records that decision."

## Giving Useful Critique

- Critique the **design, never the designer**: "the arm blocks the sensor" rather than "you blocked the sensor"
- Be specific and actionable — "the intake stalls on corner grabs" gives the team a next step; "it seems unreliable" gives them nothing
- Lead with what works, so the team knows what to protect while they fix the rest
- Ask questions before prescribing: "what happens at full speed?" often teaches more than "make it faster"

## Receiving Critique

Write it down, ask clarifying questions, and resist defending for the first minute — you can evaluate the feedback later, but only if you actually heard it. Every critique session is a free round of testing performed by human reviewers.'''
            },
            {
                'title': 'Capstone Wrap-Up: Six Units, One Discipline',
                'content': '''# Capstone Wrap-Up: Six Units, One Discipline

Step back and look at what this course assembled, one unit at a time.

## How the Units Fit Together

| Unit | What It Gave You | Where It Shows Up in a Capstone |
|------|------------------|--------------------------------|
| 1 | What robots are and how the field evolved | Framing your problem and its context |
| 2 | Mechanical systems, motion, and structure | The chassis, arms, and grippers you prototype |
| 3 | Electricity, electronics, and circuits | Powering and wiring the design safely |
| 4 | Sensors and feedback | Making the design respond to its world |
| 5 | Programming and control | The behavior that turns hardware into a robot |
| 6 | The engineering design process | The method that ties every other unit together |

Unit 6 is last for a reason: the design process is the operating system that runs all the other knowledge. Mechanisms, circuits, sensors, and code are components; the design cycle is what assembles them into solutions.

## The Capstone Mindset

Whatever capstone challenge you take on, you now have a complete toolkit:

- Define the problem before touching parts
- Let constraints filter and criteria rank your ideas
- Prototype cheap, test fair, and treat failure as data
- Document everything, with dates and numbers
- Communicate the story of your process, trade-offs included

## Beyond This Course

The loop you practiced here is the same one used to design bridges, apps, vaccines, and spacecraft. Robotics happened to be the vehicle; **systematic problem solving** is the cargo, and it travels with you into every field you choose next.

Go build something, break it on purpose, and write down what it taught you. That is engineering.'''
            }
        ])
        self._create_lesson_questions(lesson, [
            {
                'text': 'What should a design presentation primarily communicate?',
                'choices': [
                    ('The story of the design process: problem, options, evidence, decisions, and results', True),
                    ('A complete list of every part number used on the robot', False),
                    ('Only the final robot, since earlier failed ideas would look bad', False),
                    ('The personal biography of each team member', False),
                ]
            },
            {
                'text': 'Which statement is the strongest way to present a design trade-off?',
                'choices': [
                    ('The wide plate costs 0.5 seconds per lift but raised our success rate from 80 to 100 percent, which our match strategy still allows', True),
                    ('The wide plate works really well and we love it', False),
                    ('We added a wide plate; there were no downsides to mention', False),
                    ('The plate is slower, so we prefer not to discuss it', False),
                ]
            },
            {
                'text': 'What is the recommended backup plan for a live hardware demo?',
                'choices': [
                    ('A short pre-recorded video of the same task, ready to play if the hardware fails', True),
                    ('Canceling the presentation if the robot misbehaves', False),
                    ('Blaming the venue for the failure and moving on quickly', False),
                    ('Demonstrating a different, untested feature on the spot', False),
                ]
            },
            {
                'text': 'A judge asks a question your team cannot answer. What is the best response?',
                'choices': [
                    ('Admit you do not know, then explain how you would find out', True),
                    ('Invent a plausible-sounding answer so the team appears prepared', False),
                    ('Stay silent until the judge moves to another question', False),
                    ('Answer a different question that the team rehearsed instead', False),
                ]
            }
        ])

        self._create_unit6_quiz(unit)

    def _create_unit6_quiz(self, unit):
        quiz = Quiz.objects.create(
            unit=unit,
            title='Engineering Design Capstone Quiz',
            description='Test your understanding of the engineering design process, from defining problems to presenting your finished design.',
            passing_score=70,
            points=20,
            max_attempts=3,
            order=0
        )
        self._create_quiz_questions(quiz, [
            {
                'text': 'Why do engineers describe the design process as a cycle rather than a straight line?',
                'choices': [
                    ('Test results and new information send the design back through earlier steps for improvement', True),
                    ('Each step must be performed exactly once and in strict order', False),
                    ('Cycles guarantee the first prototype will meet every requirement', False),
                    ('The communicate step is optional, so the line has no fixed end', False),
                ]
            },
            {
                'text': 'A rule states the robot must fit inside a 45 cm cube at the start of a match. In design terms, what is this?',
                'choices': [
                    ('A constraint — a hard limit the design must satisfy to be legal', True),
                    ('A criterion — a quality that makes one valid design better than another', False),
                    ('A problem statement describing the user and their need', False),
                    ('A trade-off between two competing criteria', False),
                ]
            },
            {
                'text': 'What is the purpose of a weighted decision matrix?',
                'choices': [
                    ('To compare candidate solutions objectively by scoring them against weighted criteria', True),
                    ('To prove that the fastest solution is always the correct choice', False),
                    ('To document which teammate proposed each idea', False),
                    ('To include designs that violate the constraints in the final ranking', False),
                ]
            },
            {
                'text': 'Which practice makes an engineering notebook trustworthy as evidence for judges or patent disputes?',
                'choices': [
                    ('Dated, chronological entries in ink on numbered pages, with mistakes crossed out rather than erased', True),
                    ('Rewriting all entries neatly at the end of the season', False),
                    ('Removing pages that describe failed tests', False),
                    ('Recording only the final design so the story stays simple', False),
                ]
            },
            {
                'text': 'A team tests a new gripper pad material. Which procedure makes the test fair?',
                'choices': [
                    ('Change only the pad material, keep all other conditions the same, and repeat the trial many times', True),
                    ('Change the pads and the motor power together to save testing time', False),
                    ('Run a single trial and adopt the pads if that one attempt succeeds', False),
                    ('Decide the success threshold after seeing the results', False),
                ]
            },
            {
                'text': 'During a presentation, why should a team openly explain the trade-offs in their design?',
                'choices': [
                    ('Stating what was given up, what was gained, and why shows the decision was deliberate and evidence-based', True),
                    ('Mentioning weaknesses guarantees a higher score regardless of the design', False),
                    ('Judges are not allowed to ask about anything the team discloses first', False),
                    ('It fills presentation time when the demo is too short', False),
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
        offset = int(hashlib.md5(question_text.encode()).hexdigest(), 16) % len(choices)
        return choices[offset:] + choices[:offset]

    def _create_sections(self, lesson, sections_data):
        """Create lesson sections from a list of dictionaries."""
        for i, section in enumerate(sections_data):
            LessonSection.objects.create(
                lesson=lesson,
                title=section.get('title', ''),
                content=section.get('content', ''),
                video_type=section.get('video_type', 'none'),
                video_id=section.get('video_id', ''),
                order=i
            )

    def _create_lesson_questions(self, lesson, questions_data):
        """Create comprehension questions for a lesson, and gate on them.

        Phase-55 invariant (see populate_java_course): a seeded lesson has the
        `requires_quiz` gate on if and only if it has questions. Setting it
        here rather than at each `Lesson.objects.create` site makes the
        invariant structural.
        """
        if not questions_data:
            return

        for i, q in enumerate(questions_data):
            question = LessonQuestion.objects.create(
                lesson=lesson,
                text=q['text'],
                order=i
            )
            choices = self._stable_choice_order(q['text'], q['choices'])
            for j, (choice_text, is_correct) in enumerate(choices):
                LessonQuestionChoice.objects.create(
                    question=question,
                    text=choice_text,
                    is_correct=is_correct,
                    order=j
                )

        if not lesson.requires_quiz:
            lesson.requires_quiz = True
            lesson.save(update_fields=['requires_quiz'])

    def _create_quiz_questions(self, quiz, questions_data):
        """Create quiz questions."""
        for i, q in enumerate(questions_data):
            question = Question.objects.create(
                quiz=quiz,
                text=q['text'],
                order=i
            )
            choices = self._stable_choice_order(q['text'], q['choices'])
            for j, (choice_text, is_correct) in enumerate(choices):
                Choice.objects.create(
                    question=question,
                    text=choice_text,
                    is_correct=is_correct,
                    order=j
                )


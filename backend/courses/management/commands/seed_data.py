"""
Management command to seed the database with demo data.
Usage: python manage.py seed_data
       python manage.py seed_data --clear  (clears existing demo data first)
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from accounts.models import User
from allauth.account.models import EmailAddress
from courses.models import (
    Course, Unit, Lesson, Enrollment, LessonProgress, CourseGradingConfig,
    LessonSection, LessonQuestion, LessonQuestionChoice,
)
from quizzes.models import Quiz, Question, Choice, QuizAttempt, AttemptAnswer


class Command(BaseCommand):
    help = 'Seeds the database with demo data for testing'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing data before seeding',
        )

    def handle(self, *args, **options):
        if options['clear']:
            self.stdout.write('Clearing existing demo data...')
            self.clear_data()

        self.stdout.write('Seeding database...')

        # Create users
        instructor = self.create_instructor()
        students = self.create_students()

        # Create main course (VGD101) with full content
        course = self.create_course(instructor)
        units = self.create_units(course)
        lessons = self.create_lessons(units)
        self.seed_demo_sections_and_quiz(lessons)
        quizzes = self.create_quizzes(units)

        # Enroll students and create activity for main course
        self.enroll_students(students, course)
        self.create_progress(students, lessons)
        self.create_quiz_attempts(students, quizzes)

        # Create additional courses (minimal content for demo variety)
        cs_course = self.create_cs_course(instructor)
        robotics_course = self.create_robotics_course(instructor)

        # Enroll some students in additional courses
        self.enroll_students(students[:3], cs_course)  # First 3 students
        self.enroll_students(students[1:4], robotics_course)  # Students 2-4

        self.stdout.write(self.style.SUCCESS('\nDatabase seeded successfully!'))
        self.stdout.write('')
        self.stdout.write('='*50)
        self.stdout.write('DEMO ACCOUNTS')
        self.stdout.write('='*50)
        self.stdout.write(f'\nInstructor:')
        self.stdout.write(f'  Name: Cesar Villarreal')
        self.stdout.write(f'  Email: instructor@demo.com')
        self.stdout.write(f'  Password: Admin123!')
        self.stdout.write(f'\nStudents:')
        for i in range(1, 6):
            self.stdout.write(f'  Email: student{i}@demo.com')
        self.stdout.write(f'  Password (all): Admin123!')
        self.stdout.write(f'\nCourses:')
        self.stdout.write(f'  {course.code}: {course.title}')
        self.stdout.write(f'  {cs_course.code}: {cs_course.title}')
        self.stdout.write(f'  {robotics_course.code}: {robotics_course.title}')
        self.stdout.write('='*50)

    def clear_data(self):
        """Clear all seeded data."""
        # Delete in order of dependencies
        AttemptAnswer.objects.all().delete()
        QuizAttempt.objects.all().delete()
        Choice.objects.all().delete()
        Question.objects.all().delete()
        Quiz.objects.all().delete()
        LessonProgress.objects.all().delete()
        Enrollment.objects.all().delete()
        Lesson.objects.all().delete()
        Unit.objects.all().delete()
        CourseGradingConfig.objects.all().delete()
        Course.objects.all().delete()
        User.objects.filter(email__endswith='@demo.com').delete()
        self.stdout.write('  Cleared existing demo data')

    def create_instructor(self):
        """Create demo instructor account."""
        instructor, created = User.objects.get_or_create(
            email='instructor@demo.com',
            defaults={
                'first_name': 'Cesar',
                'last_name': 'Villarreal',
                'is_instructor': True,
            }
        )
        # Always update password to ensure it's correct
        instructor.set_password('Admin123!')
        instructor.first_name = 'Cesar'
        instructor.last_name = 'Villarreal'
        instructor.save()

        # Create verified email address for login
        EmailAddress.objects.get_or_create(
            user=instructor,
            email=instructor.email,
            defaults={'verified': True, 'primary': True}
        )

        if created:
            self.stdout.write(f'  Created instructor: {instructor.email}')
        else:
            self.stdout.write(f'  Updated instructor: {instructor.email}')
        return instructor

    def create_students(self):
        """Create demo student accounts with diverse profiles."""
        # Diverse student profiles for realistic demo data
        student_names = [
            ('Emma', 'Martinez'),      # High achiever - completes everything, great grades
            ('James', 'Thompson'),     # Good student - mostly on track, some late work
            ('Sofia', 'Patel'),        # Average student - struggling with some concepts
            ('Marcus', 'Williams'),    # Behind student - missing work, needs help
            ('Aria', 'Kim'),           # New student - just started, minimal progress
        ]

        students = []
        for i, (first, last) in enumerate(student_names, 1):
            student, created = User.objects.get_or_create(
                email=f'student{i}@demo.com',
                defaults={
                    'first_name': first,
                    'last_name': last,
                    'is_instructor': False,
                }
            )
            # Always update to ensure correct data
            student.first_name = first
            student.last_name = last
            student.set_password('Admin123!')
            student.save()

            # Create verified email address for login
            EmailAddress.objects.get_or_create(
                user=student,
                email=student.email,
                defaults={'verified': True, 'primary': True}
            )

            if created:
                self.stdout.write(f'  Created student: {student.email} ({first} {last})')
            else:
                self.stdout.write(f'  Updated student: {student.email} ({first} {last})')
            students.append(student)
        return students

    def create_course(self, instructor):
        """Create demo course with grading config."""
        course, created = Course.objects.get_or_create(
            code='VGD101',
            defaults={
                'title': 'Introduction to Video Game Development',
                'description': '''Welcome to Video Game Development! In this course, you'll learn the fundamentals of creating video games using industry-standard tools and techniques.

## What You'll Learn
- Game design principles
- Programming basics with GDScript
- 2D and 3D game mechanics
- Asset creation and management
- Publishing your first game

## Prerequisites
No prior programming experience required!''',
                'instructor': instructor,
                'is_active': True,
            }
        )
        if created:
            self.stdout.write(f'  Created course: {course.code}')
            # Create grading config
            CourseGradingConfig.objects.create(
                course=course,
                quizzes_weight=80,
                participation_weight=20,
            )
        else:
            self.stdout.write(f'  Course exists: {course.code}')
        return course

    def create_cs_course(self, instructor):
        """Create Principles of Computer Science course."""
        course, created = Course.objects.get_or_create(
            code='CS101',
            defaults={
                'title': 'Principles of Computer Science',
                'description': '''An introduction to the fundamental concepts of computer science and computational thinking.

## Topics Covered
- Algorithms and problem solving
- Data structures basics
- Introduction to programming
- Computer architecture overview
- Software development lifecycle

## Who Should Take This Course
Students interested in understanding how computers work and how to think like a programmer.''',
                'instructor': instructor,
                'is_active': True,
            }
        )
        if created:
            self.stdout.write(f'  Created course: {course.code}')
            CourseGradingConfig.objects.create(
                course=course,
                quizzes_weight=85,
                participation_weight=15,
            )
            # Create units
            units_data = [
                ('Introduction to Computing', 1),
                ('Algorithms & Logic', 2),
                ('Data & Information', 3),
            ]
            for title, order in units_data:
                unit, _ = Unit.objects.get_or_create(
                    course=course, order=order, defaults={'title': title}
                )
                # Add a simple lesson to each unit
                Lesson.objects.get_or_create(
                    unit=unit, order=1,
                    defaults={
                        'title': f'Introduction to {title}',
                        'content': f'# {title}\n\nThis lesson covers the basics of {title.lower()}.',
                        'video_type': 'none',
                    }
                )
        else:
            self.stdout.write(f'  Course exists: {course.code}')
        return course

    def create_robotics_course(self, instructor):
        """Create Robotics Engineering course."""
        course, created = Course.objects.get_or_create(
            code='ROB201',
            defaults={
                'title': 'Robotics Engineering',
                'description': '''Learn the fundamentals of robotics including mechanical design, electronics, and programming.

## What You'll Build
- Line-following robot
- Obstacle avoidance system
- Remote-controlled vehicle
- Autonomous navigation project

## Prerequisites
- Basic understanding of physics
- Intro programming helpful but not required''',
                'instructor': instructor,
                'is_active': True,
            }
        )
        if created:
            self.stdout.write(f'  Created course: {course.code}')
            CourseGradingConfig.objects.create(
                course=course,
                quizzes_weight=60,
                participation_weight=40,
            )
            # Create units
            units_data = [
                ('Robotics Fundamentals', 1),
                ('Sensors & Actuators', 2),
                ('Programming Robots', 3),
            ]
            for title, order in units_data:
                unit, _ = Unit.objects.get_or_create(
                    course=course, order=order, defaults={'title': title}
                )
                # Add a simple lesson to each unit
                Lesson.objects.get_or_create(
                    unit=unit, order=1,
                    defaults={
                        'title': f'Understanding {title}',
                        'content': f'# {title}\n\nThis lesson introduces {title.lower()} concepts.',
                        'video_type': 'none',
                    }
                )
        else:
            self.stdout.write(f'  Course exists: {course.code}')
        return course

    def create_units(self, course):
        """Create demo units."""
        unit_data = [
            ('Getting Started', 1),
            ('Game Design Basics', 2),
            ('Programming Fundamentals', 3),
            ('Building Your First Game', 4),
        ]

        units = []
        for title, order in unit_data:
            unit, created = Unit.objects.get_or_create(
                course=course,
                order=order,
                defaults={'title': title}
            )
            units.append(unit)
            if created:
                self.stdout.write(f'    Created unit: {title}')

        return units

    def create_lessons(self, units):
        """Create demo lessons for each unit."""
        lessons_data = {
            1: [  # Getting Started
                ('Welcome to the Course', '''# Welcome!

Thank you for joining this video game development course. Over the next few weeks, you'll learn everything you need to create your own games.

## Course Structure
Each unit contains lessons and quizzes. Complete the lessons first, then take the quizzes.

## Getting Help
If you have questions, don't hesitate to reach out!''', 'youtube', 'dQw4w9WgXcQ'),
                ('Installing Godot', '''# Installing Godot Engine

Godot is a free, open-source game engine that we'll use throughout this course.

## Download
Visit [godotengine.org](https://godotengine.org) and download the latest stable version.

## System Requirements
- Windows 7+, macOS 10.12+, or Linux
- OpenGL 2.1 / OpenGL ES 2.0 compatible graphics
- 2GB RAM minimum''', 'none', ''),
            ],
            2: [  # Game Design Basics
                ('What Makes Games Fun?', '''# The Elements of Fun

Understanding what makes games enjoyable is crucial for any game developer.

## Core Elements
1. **Challenge** - Games should test players appropriately
2. **Feedback** - Players need to know how they're doing
3. **Goals** - Clear objectives keep players engaged
4. **Story** - Narrative can enhance engagement''', 'youtube', 'dQw4w9WgXcQ'),
                ('Game Loops and Mechanics', '''# Understanding Game Loops

The game loop is the heart of every game.

## The Core Loop
1. Input - Player does something
2. Process - Game responds
3. Output - Player sees result
4. Repeat!

## Mechanics vs Dynamics
- **Mechanics**: The rules
- **Dynamics**: Emergent behavior from rules''', 'none', ''),
            ],
            3: [  # Programming Fundamentals
                ('Variables and Data Types', '''# Variables in GDScript

Variables store data that your game uses.

```gdscript
var player_name = "Hero"
var health = 100
var is_alive = true
var position = Vector2(0, 0)
```

## Common Types
- String: Text
- int: Whole numbers
- float: Decimal numbers
- bool: True/False
- Vector2/Vector3: Positions''', 'youtube', 'dQw4w9WgXcQ'),
                ('Functions and Logic', '''# Functions in GDScript

Functions are reusable blocks of code.

```gdscript
func take_damage(amount):
    health -= amount
    if health <= 0:
        die()

func heal(amount):
    health = min(health + amount, max_health)
```

## Control Flow
- if/elif/else
- for loops
- while loops''', 'none', ''),
            ],
            4: [  # Building Your First Game
                ('Project Setup', '''# Setting Up Your First Project

Let's create a simple 2D game!

## Steps
1. Open Godot
2. Click "New Project"
3. Name it "MyFirstGame"
4. Choose a location
5. Select "OpenGL ES 3.0"
6. Click "Create & Edit"

You're ready to start building!''', 'none', ''),
                ('Adding Player Movement', '''# Player Movement

Time to make things move!

```gdscript
extends CharacterBody2D

var speed = 200

func _physics_process(delta):
    var velocity = Vector2.ZERO

    if Input.is_action_pressed("move_right"):
        velocity.x += 1
    if Input.is_action_pressed("move_left"):
        velocity.x -= 1
    if Input.is_action_pressed("move_down"):
        velocity.y += 1
    if Input.is_action_pressed("move_up"):
        velocity.y -= 1

    velocity = velocity.normalized() * speed
    move_and_slide()
```''', 'youtube', 'dQw4w9WgXcQ'),
            ],
        }

        all_lessons = []
        for unit in units:
            unit_lessons = lessons_data.get(unit.order, [])
            for order, (title, content, video_type, video_id) in enumerate(unit_lessons, 1):
                lesson, created = Lesson.objects.get_or_create(
                    unit=unit,
                    order=order,
                    defaults={
                        'title': title,
                        'content': content,
                        'video_type': video_type,
                        'video_id': video_id,
                    }
                )
                all_lessons.append(lesson)
                if created:
                    self.stdout.write(f'      Created lesson: {title}')

        return all_lessons

    def seed_demo_sections_and_quiz(self, lessons):
        """
        Give one existing lesson multi-page sections + a short comprehension quiz
        so learning-mode pagination and the end-of-lesson quiz gate are visible
        and testable. Idempotent: re-running does not duplicate sections/questions.
        """
        demo_lesson = next(
            (l for l in lessons if l.title == 'Variables and Data Types'),
            None
        )
        if not demo_lesson:
            self.stdout.write(
                '  Demo lesson "Variables and Data Types" not found; '
                'skipping sections/quiz seed'
            )
            return

        sections_data = [
            {
                'order': 0,
                'title': 'What Is a Variable?',
                'content': '''A **variable** is a named container that stores a value your game can read and change while it runs.

```gdscript
var player_name = "Hero"
var health = 100
```

Think of the name (`health`) as a label on a box, and the value (`100`) as what's inside.''',
                'video_type': 'none',
                'video_id': '',
            },
            {
                'order': 1,
                'title': 'Watch: Variables in Action',
                'content': '''Watch how variables are declared and updated as a game runs, then continue to the next page.''',
                'video_type': 'youtube',
                'video_id': 'dQw4w9WgXcQ',
            },
            {
                'order': 2,
                'title': 'Common Data Types',
                'content': '''Every variable holds a value of some **type**:

- `String` – text, e.g. `"Hero"`
- `int` – whole numbers, e.g. `100`
- `float` – decimal numbers, e.g. `2.5`
- `bool` – `true` / `false`
- `Vector2` – a 2D position or direction, e.g. `Vector2(0, 0)`

When you finish reading, take the short comprehension check to complete the lesson.''',
                'video_type': 'none',
                'video_id': '',
            },
        ]

        created_sections = 0
        for sec in sections_data:
            _, created = LessonSection.objects.get_or_create(
                lesson=demo_lesson,
                order=sec['order'],
                defaults={
                    'title': sec['title'],
                    'content': sec['content'],
                    'video_type': sec['video_type'],
                    'video_id': sec['video_id'],
                }
            )
            if created:
                created_sections += 1

        questions_data = [
            {
                'order': 1,
                'text': 'Which keyword is used to declare a variable in GDScript?',
                'choices': [
                    ('var', True),
                    ('let', False),
                    ('int', False),
                    ('define', False),
                ],
            },
            {
                'order': 2,
                'text': 'Which type would you use to store the text "Hero"?',
                'choices': [
                    ('String', True),
                    ('int', False),
                    ('bool', False),
                    ('Vector2', False),
                ],
            },
            {
                'order': 3,
                'text': 'What does a Vector2 represent?',
                'choices': [
                    ('A 2D position or direction', True),
                    ('A single whole number', False),
                    ('A true/false value', False),
                    ('A block of text', False),
                ],
            },
        ]

        created_questions = 0
        for q in questions_data:
            question, created = LessonQuestion.objects.get_or_create(
                lesson=demo_lesson,
                order=q['order'],
                defaults={'text': q['text']},
            )
            if created:
                created_questions += 1
                for c_order, (text, is_correct) in enumerate(q['choices'], 1):
                    LessonQuestionChoice.objects.create(
                        question=question,
                        text=text,
                        is_correct=is_correct,
                        order=c_order,
                    )

        self.stdout.write(
            f'  Demo lesson "{demo_lesson.title}": '
            f'{created_sections} new section(s), {created_questions} new question(s)'
        )

    def create_quizzes(self, units):
        """Create quizzes for units."""
        quizzes = []

        quiz_data = {
            1: {
                'title': 'Getting Started Quiz',
                'description': 'Test your knowledge of the course introduction and Godot setup.',
                'questions': [
                    {
                        'text': 'What game engine will we use in this course?',
                        'choices': [
                            ('Godot', True),
                            ('Unity', False),
                            ('Unreal Engine', False),
                            ('GameMaker', False),
                        ]
                    },
                    {
                        'text': 'Is Godot free to use?',
                        'choices': [
                            ('Yes, it is completely free and open-source', True),
                            ('No, it requires a license', False),
                            ('Only for educational use', False),
                        ]
                    },
                    {
                        'text': 'What is the minimum RAM recommended for Godot?',
                        'choices': [
                            ('2GB', True),
                            ('8GB', False),
                            ('16GB', False),
                            ('4GB', False),
                        ]
                    },
                ]
            },
            2: {
                'title': 'Game Design Quiz',
                'description': 'Test your understanding of game design principles.',
                'questions': [
                    {
                        'text': 'Which of the following is NOT a core element of fun in games?',
                        'choices': [
                            ('File size', True),
                            ('Challenge', False),
                            ('Feedback', False),
                            ('Goals', False),
                        ]
                    },
                    {
                        'text': 'What is the game loop?',
                        'choices': [
                            ('The cycle of Input, Process, Output, Repeat', True),
                            ('A type of roller coaster in theme park games', False),
                            ('The main menu of a game', False),
                            ('A marketing term', False),
                        ]
                    },
                    {
                        'text': 'Mechanics are the rules, and dynamics are:',
                        'choices': [
                            ('Emergent behavior from rules', True),
                            ('The graphics engine', False),
                            ('The sound effects', False),
                            ('The story', False),
                        ]
                    },
                ]
            },
            3: {
                'title': 'Programming Basics Quiz',
                'description': 'Test your knowledge of GDScript fundamentals.',
                'questions': [
                    {
                        'text': 'Which keyword is used to declare a variable in GDScript?',
                        'choices': [
                            ('var', True),
                            ('let', False),
                            ('int', False),
                            ('define', False),
                        ]
                    },
                    {
                        'text': 'What data type would you use to store "Hello World"?',
                        'choices': [
                            ('String', True),
                            ('int', False),
                            ('bool', False),
                            ('Vector2', False),
                        ]
                    },
                    {
                        'text': 'What is Vector2 used for?',
                        'choices': [
                            ('Storing 2D positions', True),
                            ('Storing text', False),
                            ('Storing true/false values', False),
                            ('Storing whole numbers', False),
                        ]
                    },
                    {
                        'text': 'How do you define a function in GDScript?',
                        'choices': [
                            ('func function_name():', True),
                            ('def function_name():', False),
                            ('function function_name():', False),
                            ('void function_name():', False),
                        ]
                    },
                ]
            },
        }

        for unit in units:
            if unit.order not in quiz_data:
                continue

            data = quiz_data[unit.order]
            quiz, created = Quiz.objects.get_or_create(
                unit=unit,
                title=data['title'],
                defaults={
                    'description': data['description'],
                    'passing_score': 70,
                    'points': 20,
                    'max_attempts': 3,
                    'order': 1,
                }
            )

            if created:
                self.stdout.write(f'      Created quiz: {quiz.title}')

                # Create questions and choices
                for q_order, q_data in enumerate(data['questions'], 1):
                    question = Question.objects.create(
                        quiz=quiz,
                        text=q_data['text'],
                        order=q_order,
                    )
                    for c_order, (text, is_correct) in enumerate(q_data['choices'], 1):
                        Choice.objects.create(
                            question=question,
                            text=text,
                            is_correct=is_correct,
                            order=c_order,
                        )

            quizzes.append(quiz)

        return quizzes

    def enroll_students(self, students, course):
        """Enroll all demo students in the course."""
        for student in students:
            enrollment, created = Enrollment.objects.get_or_create(
                user=student,
                course=course,
            )
            if created:
                self.stdout.write(f'  Enrolled: {student.email}')

    def create_progress(self, students, lessons):
        """Create varied lesson progress for students."""
        # Emma (1): Star student - all lessons complete, watched all videos
        # James (2): Good progress - 80% complete, some videos partially watched
        # Sofia (3): Moderate progress - 60% complete, skipped some videos
        # Marcus (4): Behind - 30% complete, struggling to keep up
        # Aria (5): New student - just started, 1-2 lessons only

        completion_rates = [1.0, 0.80, 0.60, 0.30, 0.12]
        video_progress = [1.0, 0.85, 0.5, 0.3, 0.0]  # How much video they watched

        for student, rate, vid_rate in zip(students, completion_rates, video_progress):
            lessons_to_complete = int(len(lessons) * rate)
            for i, lesson in enumerate(lessons[:lessons_to_complete]):
                # Vary completion dates - earlier students finished earlier
                days_ago = max(1, len(lessons) - i + (5 - students.index(student)) * 2)
                progress, created = LessonProgress.objects.get_or_create(
                    user=student,
                    lesson=lesson,
                    defaults={
                        'completed': True,
                        'completed_at': timezone.now() - timedelta(days=days_ago),
                        'video_position': int(100 * vid_rate) if lesson.video_id else 0,
                    }
                )
                if not created:
                    progress.completed = True
                    progress.completed_at = timezone.now() - timedelta(days=days_ago)
                    progress.video_position = int(100 * vid_rate) if lesson.video_id else 0
                    progress.save()

        self.stdout.write('  Created lesson progress with varied completion rates')

    def create_quiz_attempts(self, students, quizzes):
        """Create quiz attempts matching student profiles."""
        for quiz_idx, quiz in enumerate(quizzes):
            questions = list(quiz.questions.all())
            if not questions:
                continue

            # Emma - perfect or near-perfect scores on all quizzes
            self._create_attempt(students[0], quiz, questions, correct_count=len(questions))

            # James - good scores, occasionally misses one
            james_correct = len(questions) if quiz_idx == 0 else max(1, len(questions) - 1)
            self._create_attempt(students[1], quiz, questions, correct_count=james_correct)

            # Sofia - passing but not great, varies by quiz
            sofia_correct = int(len(questions) * (0.7 + quiz_idx * 0.05))
            self._create_attempt(students[2], quiz, questions, correct_count=min(sofia_correct + 1, len(questions)))

            # Marcus - struggles, failed first quiz, barely passed second
            if quiz_idx == 0:
                self._create_attempt(students[3], quiz, questions, correct_count=1)  # Failed
            elif quiz_idx == 1:
                passing_min = int(len(questions) * 0.7)
                self._create_attempt(students[3], quiz, questions, correct_count=passing_min)  # Barely passed
            # No attempt on quiz 3 for Marcus

            # Aria - only took first quiz (new student)
            if quiz_idx == 0:
                self._create_attempt(students[4], quiz, questions, correct_count=len(questions) - 1)

        self.stdout.write('  Created quiz attempts with varied performance')

    def _create_attempt(self, student, quiz, questions, correct_count):
        """Helper to create a quiz attempt."""
        score = (correct_count / len(questions)) * 100
        passed = score >= quiz.passing_score

        attempt = QuizAttempt.objects.create(
            quiz=quiz,
            student=student,
            score=score,
            passed=passed,
        )
        # Note: points_earned is a calculated property, not a field

        for i, question in enumerate(questions):
            choices = list(question.choices.all())
            correct_choice = next((c for c in choices if c.is_correct), choices[0])
            wrong_choices = [c for c in choices if not c.is_correct]

            if i < correct_count:
                selected = correct_choice
                is_correct = True
            else:
                selected = wrong_choices[0] if wrong_choices else correct_choice
                is_correct = selected.is_correct

            AttemptAnswer.objects.create(
                attempt=attempt,
                question=question,
                selected_choice=selected,
                is_correct=is_correct,
            )

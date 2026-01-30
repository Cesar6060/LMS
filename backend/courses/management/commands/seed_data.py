"""
Management command to seed the database with demo data.
Usage: python manage.py seed_data
       python manage.py seed_data --clear  (clears existing demo data first)
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from accounts.models import User
from allauth.account.models import EmailAddress
from courses.models import Course, Unit, Lesson, Enrollment, LessonProgress, CourseGradingConfig
from assignments.models import Assignment, Submission, Grade
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
        assignments = self.create_assignments(units)
        quizzes = self.create_quizzes(units)

        # Enroll students and create activity for main course
        self.enroll_students(students, course)
        self.create_progress(students, lessons)
        self.create_submissions(students, assignments, instructor)
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
        Grade.objects.all().delete()
        Submission.objects.all().delete()
        LessonProgress.objects.all().delete()
        Enrollment.objects.all().delete()
        Lesson.objects.all().delete()
        Assignment.objects.all().delete()
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
                assignments_weight=50,
                quizzes_weight=40,
                participation_weight=10,
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
                assignments_weight=40,
                quizzes_weight=50,
                participation_weight=10,
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
                assignments_weight=60,
                quizzes_weight=25,
                participation_weight=15,
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
Each unit contains lessons and assignments. Complete the lessons first, then work on the assignments.

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

    def create_assignments(self, units):
        """Create demo assignments."""
        now = timezone.now()
        assignments_data = {
            1: [  # Getting Started
                ('Environment Setup', 'Submit a screenshot showing Godot installed and running on your computer.', 10, now + timedelta(days=7), True),
            ],
            2: [  # Game Design Basics
                ('Game Analysis', '''Choose a game you enjoy and write a 300-word analysis covering:

1. What are the core mechanics?
2. What makes it fun?
3. What could be improved?''', 25, now + timedelta(days=14), True),
            ],
            3: [  # Programming Fundamentals
                ('Variable Practice', '''Create a GDScript file that:

1. Declares variables of at least 4 different types
2. Performs operations on them
3. Prints the results

Submit your .gd file.''', 30, now + timedelta(days=21), True),
            ],
            4: [  # Building Your First Game
                ('Final Project: Simple Game', '''Create a simple game with:

1. Player movement (arrow keys or WASD)
2. At least one collectible
3. A win condition
4. Basic UI (score or health)

Submit your project folder as a zip file.''', 100, now + timedelta(days=30), True),
            ],
        }

        # Add a past-due assignment for testing
        past_due_data = ('Past Due Practice', 'This assignment is past due for testing.', 20, now - timedelta(days=3), False)

        all_assignments = []
        for unit in units:
            unit_assignments = assignments_data.get(unit.order, [])
            for order, (title, description, max_points, due_date, allow_late) in enumerate(unit_assignments, 1):
                assignment, created = Assignment.objects.get_or_create(
                    unit=unit,
                    title=title,
                    defaults={
                        'description': description,
                        'max_points': max_points,
                        'due_date': due_date,
                        'order': order,
                        'allow_late': allow_late,
                        'available_from': now - timedelta(days=7),
                        'late_penalty_percent': Decimal('10') if allow_late else None,
                        'late_penalty_interval': 'day',
                        'max_late_penalty': Decimal('50') if allow_late else None,
                    }
                )
                all_assignments.append(assignment)
                if created:
                    self.stdout.write(f'      Created assignment: {title}')

        # Add past-due assignment to first unit
        if units:
            title, description, max_points, due_date, allow_late = past_due_data
            assignment, created = Assignment.objects.get_or_create(
                unit=units[0],
                title=title,
                defaults={
                    'description': description,
                    'max_points': max_points,
                    'due_date': due_date,
                    'order': 99,
                    'allow_late': allow_late,
                    'available_from': now - timedelta(days=14),
                }
            )
            if created:
                all_assignments.append(assignment)
                self.stdout.write(f'      Created assignment: {title} (past due)')

        return all_assignments

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

    def create_submissions(self, students, assignments, instructor):
        """Create demo submissions with diverse statuses reflecting student profiles."""
        now = timezone.now()

        # Emma (0): Star student - all graded with A/A+ grades
        # James (1): Good student - most submitted, awaiting grades, one late
        # Sofia (2): Average - some graded (B/C grades), some submitted, one draft
        # Marcus (3): Behind - drafts and missing work, one graded (low score)
        # Aria (4): New - only first assignment submitted

        for idx, assignment in enumerate(assignments):
            is_past_due = assignment.due_date and assignment.due_date < now

            # Emma - star student, all A grades
            sub, created = Submission.objects.get_or_create(
                assignment=assignment,
                student=students[0],
                defaults={
                    'content': f'''## {assignment.title} Submission

I've completed all the requirements for this assignment. Here are the key points:

1. Followed all instructions carefully
2. Added extra features for bonus points
3. Tested thoroughly before submitting

Looking forward to your feedback!''',
                    'status': 'graded',
                    'submitted_at': (assignment.due_date or now) - timedelta(days=3),
                }
            )
            if created:
                # High grades: 90-100%
                score_percent = 0.90 + (idx % 3) * 0.03
                Grade.objects.create(
                    submission=sub,
                    grader=instructor,
                    points=int(assignment.max_points * score_percent),
                    feedback='Excellent work, Emma! Your attention to detail is impressive. Keep it up!',
                )

            # James - good student, mix of graded and pending
            if not is_past_due:
                if idx < 2:  # First two graded
                    sub, created = Submission.objects.get_or_create(
                        assignment=assignment,
                        student=students[1],
                        defaults={
                            'content': f'Here is my submission for {assignment.title}. Let me know if anything needs revision.',
                            'status': 'graded',
                            'submitted_at': (assignment.due_date or now) - timedelta(days=1),
                        }
                    )
                    if created:
                        Grade.objects.create(
                            submission=sub,
                            grader=instructor,
                            points=int(assignment.max_points * 0.85),
                            feedback='Good work, James. A few minor improvements could push this to an A.',
                        )
                elif idx == 2 and assignment.allow_late:  # One late
                    sub, created = Submission.objects.get_or_create(
                        assignment=assignment,
                        student=students[1],
                        defaults={
                            'content': f'Apologies for the late submission. Had some technical issues.',
                            'status': 'graded',
                            'submitted_at': (assignment.due_date or now) + timedelta(days=1),
                            'late_penalty_applied': Decimal('10.00'),
                        }
                    )
                    if created:
                        Grade.objects.create(
                            submission=sub,
                            grader=instructor,
                            points=int(assignment.max_points * 0.80),
                            feedback='Solid work. Please try to submit on time next time. 10% late penalty applied.',
                        )
                else:  # Rest awaiting grade
                    Submission.objects.get_or_create(
                        assignment=assignment,
                        student=students[1],
                        defaults={
                            'content': f'Completed {assignment.title}. Ready for review.',
                            'status': 'submitted',
                            'submitted_at': now - timedelta(hours=6),
                        }
                    )

            # Sofia - average student, B/C grades, some still working
            if idx < 3 and not is_past_due:
                if idx < 2:  # First two graded with B/C
                    sub, created = Submission.objects.get_or_create(
                        assignment=assignment,
                        student=students[2],
                        defaults={
                            'content': f'My attempt at {assignment.title}. I think I understood most of it.',
                            'status': 'graded',
                            'submitted_at': (assignment.due_date or now) - timedelta(hours=12),
                        }
                    )
                    if created:
                        score_percent = 0.72 + (idx * 0.05)
                        Grade.objects.create(
                            submission=sub,
                            grader=instructor,
                            points=int(assignment.max_points * score_percent),
                            feedback='Good effort, Sofia. Review the feedback and consider visiting office hours for clarification.',
                        )
                else:  # Still working
                    Submission.objects.get_or_create(
                        assignment=assignment,
                        student=students[2],
                        defaults={
                            'content': 'Still working on this... almost done.',
                            'status': 'draft',
                        }
                    )

            # Marcus - behind, mostly drafts and missing
            if idx == 0:  # Only first assignment graded (low score)
                sub, created = Submission.objects.get_or_create(
                    assignment=assignment,
                    student=students[3],
                    defaults={
                        'content': 'Here is what I have so far.',
                        'status': 'graded',
                        'submitted_at': (assignment.due_date or now) - timedelta(hours=2),
                    }
                )
                if created:
                    Grade.objects.create(
                        submission=sub,
                        grader=instructor,
                        points=int(assignment.max_points * 0.65),
                        feedback='Marcus, this is incomplete. Please see me during office hours to discuss how to improve.',
                    )
            elif idx == 1 and not is_past_due:  # One draft
                Submission.objects.get_or_create(
                    assignment=assignment,
                    student=students[3],
                    defaults={
                        'content': 'Started working on this...',
                        'status': 'draft',
                    }
                )
            # Rest are missing for Marcus

            # Aria - new student, only first assignment
            if idx == 0:
                Submission.objects.get_or_create(
                    assignment=assignment,
                    student=students[4],
                    defaults={
                        'content': 'This is my first assignment! Excited to learn game development.',
                        'status': 'submitted',
                        'submitted_at': now - timedelta(hours=18),
                    }
                )

        self.stdout.write('  Created diverse submissions and grades')

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

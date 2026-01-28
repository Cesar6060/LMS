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

        # Create course with content
        course = self.create_course(instructor)
        units = self.create_units(course)
        lessons = self.create_lessons(units)
        assignments = self.create_assignments(units)
        quizzes = self.create_quizzes(units)

        # Enroll students and create activity
        self.enroll_students(students, course)
        self.create_progress(students, lessons)
        self.create_submissions(students, assignments, instructor)
        self.create_quiz_attempts(students, quizzes)

        self.stdout.write(self.style.SUCCESS('\nDatabase seeded successfully!'))
        self.stdout.write('')
        self.stdout.write('='*50)
        self.stdout.write('DEMO ACCOUNTS')
        self.stdout.write('='*50)
        self.stdout.write(f'\nInstructor:')
        self.stdout.write(f'  Email: instructor@demo.com')
        self.stdout.write(f'  Password: password123')
        self.stdout.write(f'\nStudents:')
        for i in range(1, 6):
            self.stdout.write(f'  Email: student{i}@demo.com')
        self.stdout.write(f'  Password (all): password123')
        self.stdout.write(f'\nCourse:')
        self.stdout.write(f'  Code: {course.code}')
        self.stdout.write(f'  Enrollment Code: {course.enrollment_code}')
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
                'first_name': 'Demo',
                'last_name': 'Instructor',
                'is_instructor': True,
            }
        )
        if created:
            instructor.set_password('password123')
            instructor.save()
            self.stdout.write(f'  Created instructor: {instructor.email}')
        else:
            self.stdout.write(f'  Instructor exists: {instructor.email}')
        return instructor

    def create_students(self):
        """Create demo student accounts."""
        student_names = [
            ('Alice', 'Anderson'),
            ('Bob', 'Brown'),
            ('Charlie', 'Chen'),
            ('Diana', 'Davis'),
            ('Evan', 'Edwards'),
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
            if created:
                student.set_password('password123')
                student.save()
                self.stdout.write(f'  Created student: {student.email}')
            else:
                self.stdout.write(f'  Student exists: {student.email}')
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
        """Create some lesson progress for students."""
        # Student 1 (Alice): Completed all lessons
        # Student 2 (Bob): Completed 75%
        # Student 3 (Charlie): Completed 50%
        # Student 4 (Diana): Completed 25%
        # Student 5 (Evan): Just started (1 lesson)

        completion_rates = [1.0, 0.75, 0.50, 0.25, 0.1]

        for student, rate in zip(students, completion_rates):
            lessons_to_complete = int(len(lessons) * rate)
            for i, lesson in enumerate(lessons[:lessons_to_complete]):
                LessonProgress.objects.get_or_create(
                    user=student,
                    lesson=lesson,
                    defaults={
                        'completed': True,
                        'completed_at': timezone.now() - timedelta(days=len(lessons) - i),
                    }
                )

        self.stdout.write('  Created lesson progress')

    def create_submissions(self, students, assignments, instructor):
        """Create demo submissions with various statuses."""
        now = timezone.now()

        # Student 1 (Alice): All submitted/graded
        # Student 2 (Bob): Some submitted, pending grade
        # Student 3 (Charlie): Has late submission
        # Student 4 (Diana): Has drafts
        # Student 5 (Evan): Missing assignments

        for assignment in assignments:
            # Skip past-due assignments for some students
            is_past_due = assignment.due_date and assignment.due_date < now

            # Alice - graded
            sub, created = Submission.objects.get_or_create(
                assignment=assignment,
                student=students[0],
                defaults={
                    'content': f'Here is my submission for {assignment.title}. I worked hard on this!',
                    'status': 'graded',
                    'submitted_at': now - timedelta(days=5),
                }
            )
            if created:
                Grade.objects.create(
                    submission=sub,
                    grader=instructor,
                    points=int(assignment.max_points * 0.92),
                    feedback='Excellent work! Very thorough submission.',
                )

            # Bob - submitted, pending grade
            if not is_past_due:
                Submission.objects.get_or_create(
                    assignment=assignment,
                    student=students[1],
                    defaults={
                        'content': f'My work for {assignment.title}.',
                        'status': 'submitted',
                        'submitted_at': now - timedelta(hours=12),
                    }
                )

            # Charlie - late submission with penalty (for applicable assignments)
            if assignment.allow_late and assignment.due_date:
                sub, created = Submission.objects.get_or_create(
                    assignment=assignment,
                    student=students[2],
                    defaults={
                        'content': f'Late submission for {assignment.title}. Sorry for the delay!',
                        'status': 'graded',
                        'submitted_at': assignment.due_date + timedelta(days=2),
                        'late_penalty_applied': Decimal('20.00'),
                    }
                )
                if created:
                    Grade.objects.create(
                        submission=sub,
                        grader=instructor,
                        points=int(assignment.max_points * 0.85),
                        feedback='Good work, but please try to submit on time. 20 point late penalty applied.',
                    )

            # Diana - draft
            if not is_past_due:
                Submission.objects.get_or_create(
                    assignment=assignment,
                    student=students[3],
                    defaults={
                        'content': 'Work in progress... still working on this.',
                        'status': 'draft',
                    }
                )

            # Evan - no submission (missing) for most, but one submitted
            if assignment == assignments[0]:
                Submission.objects.get_or_create(
                    assignment=assignment,
                    student=students[4],
                    defaults={
                        'content': 'Here is my first submission!',
                        'status': 'submitted',
                        'submitted_at': now - timedelta(days=1),
                    }
                )

        self.stdout.write('  Created submissions and grades')

    def create_quiz_attempts(self, students, quizzes):
        """Create quiz attempts for students."""
        for quiz in quizzes:
            questions = list(quiz.questions.all())
            if not questions:
                continue

            # Alice - perfect score
            self._create_attempt(students[0], quiz, questions, correct_count=len(questions))

            # Bob - one wrong
            self._create_attempt(students[1], quiz, questions, correct_count=max(0, len(questions) - 1))

            # Charlie - passing score
            passing_count = int(len(questions) * 0.7) + 1
            self._create_attempt(students[2], quiz, questions, correct_count=min(passing_count, len(questions)))

            # Diana - failing score
            self._create_attempt(students[3], quiz, questions, correct_count=1)

            # Evan - no attempt

        self.stdout.write('  Created quiz attempts')

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

"""
Management command to populate the VGD101 course with C# fundamentals content.
This command:
1. Deletes all users except the instructor "Cesar Villarreal"
2. Creates 5 new test users with password "Admin123!"
3. Clears existing course content (units, lessons, quizzes)
4. Populates with comprehensive C# fundamentals curriculum
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from courses.models import (
    Course, Unit, Lesson, LessonSection, LessonQuestion, LessonQuestionChoice
)
from quizzes.models import Quiz, Question, Choice

User = get_user_model()


class Command(BaseCommand):
    help = 'Populate VGD101 course with C# fundamentals content'

    def handle(self, *args, **options):
        self.stdout.write('Starting course population...\n')

        # Step 1: Find and preserve the instructor
        instructor = self._get_instructor()
        if not instructor:
            return

        # Step 2: Delete all other users
        self._delete_other_users(instructor)

        # Step 3: Create test users
        self._create_test_users()

        # Step 4: Get or update the course
        course = self._get_or_update_course(instructor)

        # Step 5: Clear existing content
        self._clear_course_content(course)

        # Step 6: Create units and lessons
        self._create_course_content(course)

        self.stdout.write(self.style.SUCCESS('\nCourse population complete!'))

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

    def _delete_other_users(self, instructor):
        """Delete all users except the instructor."""
        deleted_count = User.objects.exclude(id=instructor.id).delete()[0]
        self.stdout.write(f'Deleted {deleted_count} users')

    def _create_test_users(self):
        """Create 5 test student users."""
        test_users = [
            {'first_name': 'Alex', 'last_name': 'Johnson', 'email': 'alex.johnson@example.com'},
            {'first_name': 'Sarah', 'last_name': 'Williams', 'email': 'sarah.williams@example.com'},
            {'first_name': 'Michael', 'last_name': 'Chen', 'email': 'michael.chen@example.com'},
            {'first_name': 'Emma', 'last_name': 'Garcia', 'email': 'emma.garcia@example.com'},
            {'first_name': 'James', 'last_name': 'Brown', 'email': 'james.brown@example.com'},
        ]

        for user_data in test_users:
            user, created = User.objects.get_or_create(
                email=user_data['email'],
                defaults={
                    'first_name': user_data['first_name'],
                    'last_name': user_data['last_name'],
                    'is_instructor': False,
                }
            )
            if created:
                user.set_password('Admin123!')
                user.save()
                self.stdout.write(f'Created user: {user.email}')
            else:
                self.stdout.write(f'User already exists: {user.email}')

    def _get_or_update_course(self, instructor):
        """Get or create the VGD101 course."""
        course, created = Course.objects.get_or_create(
            code='VGD101',
            defaults={
                'title': 'Video Game Development - C# Fundamentals',
                'description': 'Learn C# programming fundamentals through game development concepts and hands-on projects. Master variables, operators, conditionals, and methods while building interactive console games.',
                'instructor': instructor,
            }
        )
        if not created:
            course.title = 'Video Game Development - C# Fundamentals'
            course.description = 'Learn C# programming fundamentals through game development concepts and hands-on projects. Master variables, operators, conditionals, and methods while building interactive console games.'
            course.save()
        self.stdout.write(f'Course: {course.code} - {course.title}')
        return course

    def _clear_course_content(self, course):
        """Delete all existing units, lessons, and quizzes."""
        # Delete units (cascades to lessons, sections, questions)
        deleted = course.units.all().delete()
        self.stdout.write(f'Cleared existing content: {deleted}')

    def _create_course_content(self, course):
        """Create all units, lessons, sections, and quizzes."""
        # Unit 1: Getting Started (4 lessons)
        unit1 = Unit.objects.create(course=course, title='Getting Started', order=0)
        self._create_unit1_getting_started_lessons(unit1)
        self._create_unit1_quiz(unit1)

        # Unit 2: Variables & Operators (4 lessons: 2 variables + 2 operators)
        unit2 = Unit.objects.create(course=course, title='Variables & Operators', order=1)
        self._create_unit2_variables_lessons(unit2)
        self._create_unit2_operators_lessons(unit2)
        self._create_unit2_quiz(unit2)

        # Unit 3: Strings & User Input (3 lessons)
        unit3 = Unit.objects.create(course=course, title='Strings & User Input', order=2)
        self._create_unit3_text_lessons(unit3)
        self._create_unit3_quiz(unit3)

        # Unit 4: Control Flow (7 lessons: 3 conditionals + 4 loops)
        unit4 = Unit.objects.create(course=course, title='Control Flow', order=3)
        self._create_unit4_conditionals_lessons(unit4)
        self._create_unit4_loops_lessons(unit4)
        self._create_unit4_quiz(unit4)

        # Unit 5: Methods & Functions (2 lessons)
        unit5 = Unit.objects.create(course=course, title='Methods & Functions', order=4)
        self._create_unit5_methods_lessons(unit5)
        self._create_unit5_quiz(unit5)

        self.stdout.write('Created 5 units with lessons and quizzes')

    # ================== UNIT 1: Getting Started ==================
    def _create_unit1_getting_started_lessons(self, unit):
        # Lesson 1: Hello World
        lesson1 = Lesson.objects.create(
            unit=unit, title='Hello World - Your First Program', order=0, max_quiz_attempts=3
        )
        self._create_sections(lesson1, [
            {
                'title': 'Overview',
                'content': '''# Hello World - Your First Program

Welcome to your first C# lesson! In this lesson, you'll write and run your very first program.

## Learning Objectives

By the end of this lesson, you will be able to:
- Understand the basic structure of a C# program
- Write and run a "Hello World" program
- Use `Console.WriteLine()` and `Console.Write()` to display output
- Identify the `Main` method as the program entry point

## Why This Matters

Every programmer starts with "Hello World" - it's a rite of passage! This simple program teaches you the fundamental structure that every C# program follows.'''
            },
            {
                'title': 'Video: Output in C#',
                'content': '''# Video Lesson: Output in C#

Watch this video from **Bro Code** to see Console output in action!

*After watching, continue to the next section to see the code examples.*''',
                'video_type': 'youtube',
                'video_id': 'b8BUFfgyjK4'
            },
            {
                'title': 'Introduction to C#',
                'content': '''# Welcome to C# Programming!

C# (pronounced "C-sharp") is a powerful programming language created by Microsoft. It's the primary language used in Unity, one of the world's most popular game engines.

## Why Learn C#?

- **Game Development**: Used in Unity for professional game development
- **Versatile**: Works for games, apps, websites, and more
- **Job Market**: High demand for C# developers
- **Beginner Friendly**: Clear syntax that's easy to read

By the end of this course, you'll be writing your own interactive programs!'''
            },
            {
                'title': 'Your First Program',
                'content': '''# Your First C# Program

Let's write the classic "Hello, World!" program:

```csharp
using System;

class HelloWorld
{
    static void Main(string[] args)
    {
        Console.WriteLine("Hello, World!");
        Console.WriteLine("This is my first C# program.");
    }
}
```

## Breaking It Down

| Code | Purpose |
|------|---------|
| `using System;` | Imports basic functionality |
| `class HelloWorld` | Container for our code |
| `static void Main()` | Entry point - where program starts |
| `Console.WriteLine()` | Prints text to the screen |

Every C# program needs a `Main` method - this is where the computer starts reading your code!'''
            },
            {
                'title': 'Console Output',
                'content': '''# Printing to the Console

There are two main ways to output text:

## Console.WriteLine()
Prints text and moves to a **new line**:
```csharp
Console.WriteLine("Line 1");
Console.WriteLine("Line 2");
```
Output:
```
Line 1
Line 2
```

## Console.Write()
Prints text but stays on the **same line**:
```csharp
Console.Write("Hello ");
Console.Write("World!");
```
Output:
```
Hello World!
```

## Try It Yourself
Experiment with different messages. What happens when you use `\\n` inside the quotes?'''
            }
        ])
        self._create_lesson_questions(lesson1, [
            {
                'text': 'Which method is the entry point of a C# program?',
                'choices': [
                    ('Main()', True),
                    ('Start()', False),
                    ('Begin()', False),
                    ('Run()', False),
                ]
            },
            {
                'text': 'What does Console.WriteLine() do?',
                'choices': [
                    ('Prints text and moves to a new line', True),
                    ('Prints text and stays on the same line', False),
                    ('Reads input from the user', False),
                    ('Clears the console screen', False),
                ]
            },
            {
                'text': 'What is the purpose of "using System;" at the top of a C# file?',
                'choices': [
                    ('It imports basic functionality like Console', True),
                    ('It starts the program', False),
                    ('It creates a new variable', False),
                    ('It ends the program', False),
                ]
            },
            {
                'text': 'What is the difference between Console.WriteLine() and Console.Write()?',
                'choices': [
                    ('WriteLine adds a new line after, Write stays on the same line', True),
                    ('WriteLine is faster than Write', False),
                    ('Write can only print numbers', False),
                    ('There is no difference', False),
                ]
            }
        ])

        # Lesson 2: Comments
        lesson2 = Lesson.objects.create(
            unit=unit, title='Comments - Documenting Your Code', order=1, max_quiz_attempts=3
        )
        self._create_sections(lesson2, [
            {
                'title': 'Overview',
                'content': '''# Comments - Documenting Your Code

Learn how to write notes in your code that help you and others understand what's happening.

## Learning Objectives

By the end of this lesson, you will be able to:
- Write single-line comments using `//`
- Write multi-line comments using `/* */`
- Explain why comments are important for code maintenance
- Follow best practices for writing useful comments

## Why This Matters

Comments are essential for teamwork and maintaining code over time. Even your future self will thank you for well-documented code!'''
            },
            {
                'title': 'Why Use Comments?',
                'content': '''# Comments in C#

Comments are notes in your code that the computer **ignores**. They're for humans!

## Why Comment Your Code?

1. **Explain complex logic** - Help others (and future you) understand
2. **Document purpose** - Describe what code does
3. **Disable code temporarily** - Test without deleting
4. **Leave reminders** - TODO notes for later

> "Code tells you *how*, comments tell you *why*"'''
            },
            {
                'title': 'Types of Comments',
                'content': '''# Comment Syntax

## Single-Line Comments
Use `//` for short notes:
```csharp
// This is a single-line comment
int score = 100;  // You can put comments at the end of lines too
```

## Multi-Line Comments
Use `/* */` for longer explanations:
```csharp
/*
 * This is a multi-line comment.
 * Use it for longer explanations
 * that span multiple lines.
 */
```

## XML Documentation Comments
Use `///` for documentation (advanced):
```csharp
/// <summary>
/// Calculates the player's damage
/// </summary>
int CalculateDamage() { ... }
```'''
            },
            {
                'title': 'Best Practices',
                'content': '''# Comment Best Practices

## DO:
- Explain *why* not *what* (the code shows what)
- Keep comments updated when code changes
- Use comments for complex algorithms

## DON'T:
- Comment obvious code
- Write novels in comments
- Leave commented-out code forever

## Example
```csharp
// BAD: Adds 1 to health
health = health + 1;

// GOOD: Regenerate health each second
health = health + 1;
```

Remember: Good code with good variable names often needs fewer comments!'''
            }
        ])
        self._create_lesson_questions(lesson2, [
            {
                'text': 'Which symbol starts a single-line comment in C#?',
                'choices': [
                    ('//', True),
                    ('/*', False),
                    ('#', False),
                    ('--', False),
                ]
            },
            {
                'text': 'How do you write a multi-line comment in C#?',
                'choices': [
                    ('/* comment */', True),
                    ('// comment //', False),
                    ('<!-- comment -->', False),
                    ('** comment **', False),
                ]
            },
            {
                'text': 'What is a good reason to use comments?',
                'choices': [
                    ('To explain WHY code does something', True),
                    ('To make the program run faster', False),
                    ('To add more features', False),
                    ('To fix bugs automatically', False),
                ]
            }
        ])

        # Lesson 3: Brackets and Code Blocks
        lesson3 = Lesson.objects.create(
            unit=unit, title='Code Organization - Brackets & Blocks', order=2, max_quiz_attempts=3
        )
        self._create_sections(lesson3, [
            {
                'title': 'Overview',
                'content': '''# Code Organization - Brackets & Blocks

Learn how C# uses curly braces to organize code into logical sections.

## Learning Objectives

By the end of this lesson, you will be able to:
- Understand the purpose of curly braces `{ }` in C#
- Create properly nested code blocks
- Apply consistent indentation for readable code
- Recognize common bracket-related errors

## Why This Matters

Clean code organization makes programs easier to read, debug, and maintain. Proper indentation is a mark of a professional developer!'''
            },
            {
                'title': 'Understanding Code Blocks',
                'content': '''# Brackets and Code Blocks

In C#, curly braces `{ }` create **code blocks** - sections of code that belong together.

```csharp
class MyGame
{                           // Block starts
    static void Main()
    {                       // Nested block starts
        Console.WriteLine("Hello!");
    }                       // Nested block ends
}                           // Block ends
```

## Key Rules
1. Every `{` must have a matching `}`
2. Blocks can be nested inside other blocks
3. Code inside a block is indented'''
            },
            {
                'title': 'Indentation Matters',
                'content': '''# Proper Indentation

Indentation shows structure - it's **crucial** for readable code!

## Good Indentation
```csharp
class Program
{
    static void Main()
    {
        if (health > 0)
        {
            Console.WriteLine("Still alive!");
        }
    }
}
```

## Bad Indentation (Don't Do This!)
```csharp
class Program{
static void Main(){
if(health>0){
Console.WriteLine("Still alive!");
}}}
```

Both compile, but which would you rather debug at 2 AM?'''
            }
        ])
        self._create_lesson_questions(lesson3, [
            {
                'text': 'What do curly braces { } define in C#?',
                'choices': [
                    ('A code block', True),
                    ('A comment', False),
                    ('A variable', False),
                    ('A string', False),
                ]
            },
            {
                'text': 'What happens if you forget a closing brace }?',
                'choices': [
                    ('The program will not compile (syntax error)', True),
                    ('The program runs normally', False),
                    ('The program runs slower', False),
                    ('The variable is deleted', False),
                ]
            },
            {
                'text': 'Why is proper indentation important?',
                'choices': [
                    ('It makes code easier to read and understand', True),
                    ('It makes the program run faster', False),
                    ('It is required for the code to compile', False),
                    ('It reduces file size', False),
                ]
            }
        ])

        # Lesson 4: Naming Conventions
        lesson4 = Lesson.objects.create(
            unit=unit, title='Naming Conventions', order=3, max_quiz_attempts=3
        )
        self._create_sections(lesson4, [
            {
                'title': 'Overview',
                'content': '''# Naming Conventions

Learn the standard naming rules that make C# code readable and professional.

## Learning Objectives

By the end of this lesson, you will be able to:
- Apply camelCase for variables and parameters
- Apply PascalCase for classes and methods
- Use UPPER_CASE for constants
- Write self-documenting code with descriptive names

## Why This Matters

Following naming conventions makes your code readable by any C# developer. It's the difference between amateur and professional code!'''
            },
            {
                'title': 'Why Naming Matters',
                'content': '''# Naming Conventions

Good names make code self-documenting. Compare:

```csharp
// BAD
int x = 100;
int y = 25;
int z = x - y;

// GOOD
int playerHealth = 100;
int damageDealt = 25;
int remainingHealth = playerHealth - damageDealt;
```

Which would you rather maintain?'''
            },
            {
                'title': 'C# Naming Rules',
                'content': '''# C# Naming Conventions

## camelCase
For variables and parameters:
```csharp
int playerScore = 0;
string userName = "Hero";
float moveSpeed = 5.5f;
```

## PascalCase
For classes, methods, and properties:
```csharp
class PlayerController { }
void CalculateDamage() { }
public int MaxHealth { get; set; }
```

## UPPER_CASE
For constants:
```csharp
const int MAX_LEVEL = 99;
const float GRAVITY = 9.81f;
```

## Quick Reference
| Type | Convention | Example |
|------|------------|---------|
| Variable | camelCase | `playerName` |
| Method | PascalCase | `TakeDamage()` |
| Class | PascalCase | `GameManager` |
| Constant | UPPER_CASE | `MAX_SCORE` |'''
            }
        ])
        self._create_lesson_questions(lesson4, [
            {
                'text': 'Which naming convention should be used for variables in C#?',
                'choices': [
                    ('camelCase', True),
                    ('PascalCase', False),
                    ('UPPER_CASE', False),
                    ('snake_case', False),
                ]
            },
            {
                'text': 'Which naming convention should be used for methods and classes?',
                'choices': [
                    ('PascalCase', True),
                    ('camelCase', False),
                    ('UPPER_CASE', False),
                    ('lowercase', False),
                ]
            },
            {
                'text': 'Which variable name is INVALID in C#?',
                'choices': [
                    ('2player', True),
                    ('playerScore', False),
                    ('_health', False),
                    ('maxLevel', False),
                ]
            },
            {
                'text': 'Why are good variable names important?',
                'choices': [
                    ('They make code self-documenting and easier to understand', True),
                    ('They make the program run faster', False),
                    ('They reduce file size', False),
                    ('They are required by the compiler', False),
                ]
            }
        ])

    def _create_unit1_quiz(self, unit):
        quiz = Quiz.objects.create(
            unit=unit,
            title='Script Structure Quiz',
            description='Test your knowledge of C# basics, comments, and code organization.',
            passing_score=70,
            points=20,
            max_attempts=3,
            order=0
        )
        questions = [
            {
                'text': 'What is the correct file extension for C# source files?',
                'choices': [('.cs', True), ('.c#', False), ('.csharp', False), ('.cpp', False)]
            },
            {
                'text': 'Which keyword is used to import namespaces in C#?',
                'choices': [('using', True), ('import', False), ('include', False), ('require', False)]
            },
            {
                'text': 'What must every C# program have?',
                'choices': [('A Main method', True), ('A Start method', False), ('A Run method', False), ('A Begin method', False)]
            },
            {
                'text': 'How do you write a multi-line comment?',
                'choices': [('/* comment */', True), ('// comment //', False), ('# comment #', False), ('-- comment --', False)]
            },
        ]
        self._create_quiz_questions(quiz, questions)

    # ================== UNIT 2: Variables & Operators ==================
    def _create_unit2_variables_lessons(self, unit):
        # Lesson 1: Number Types
        lesson1 = Lesson.objects.create(
            unit=unit, title='Number Types - int, float, double', order=0, max_quiz_attempts=3
        )
        self._create_sections(lesson1, [
            {
                'title': 'Overview',
                'content': '''# Number Types - int, float, double

Learn about the different ways C# stores numbers for games.

## Learning Objectives

By the end of this lesson, you will be able to:
- Declare and use `int` variables for whole numbers
- Declare and use `float` and `double` for decimal numbers
- Understand when to use each number type
- Create constants using the `const` keyword

## Why This Matters

Games are full of numbers - health, scores, positions, speeds. Choosing the right number type is crucial for both accuracy and performance!'''
            },
            {
                'title': 'Video: Variables in C#',
                'content': '''# Video Lesson: Variables in C#

Watch this video from **Bro Code** to learn about variables and data types!

*After watching, continue to the next section for detailed examples.*''',
                'video_type': 'youtube',
                'video_id': 'IxBMVztdlr4'
            },
            {
                'title': 'Integer Numbers',
                'content': '''# Integer Variables (int)

Integers store **whole numbers** - no decimals allowed!

```csharp
// Player stats
int playerLevel = 15;
int goldCoins = 250;
int healthPoints = 100;
int enemiesDefeated = 7;

Console.WriteLine("Level: " + playerLevel);
Console.WriteLine("Gold: " + goldCoins);
Console.WriteLine("Health: " + healthPoints);
```

## Common Uses in Games
- Player health and mana
- Score and currency
- Level and experience
- Inventory counts'''
            },
            {
                'title': 'Decimal Numbers',
                'content': '''# Decimal Numbers

## double - High Precision
```csharp
double accuracy = 0.875;
double criticalChance = 0.225;
double experienceMultiplier = 1.5;

Console.WriteLine("Accuracy: " + (accuracy * 100) + "%");
```

## float - Less Precision (needs 'f')
```csharp
float attackSpeed = 1.5f;    // Note the 'f'!
float moveSpeed = 5.25f;
float damageMultiplier = 2.0f;
```

## When to Use Each
| Type | Precision | Memory | Use Case |
|------|-----------|--------|----------|
| `int` | Exact | 4 bytes | Whole numbers |
| `float` | ~7 digits | 4 bytes | 3D graphics, physics |
| `double` | ~15 digits | 8 bytes | Financial calculations |'''
            },
            {
                'title': 'Constants',
                'content': '''# Constants (const)

Constants are values that **never change** during program execution.

```csharp
const int MAX_LEVEL = 99;
const int MAX_INVENTORY = 50;
const double BASE_CRIT_MULTIPLIER = 2.0;

// Using constants
int currentLevel = 15;
int levelsToMax = MAX_LEVEL - currentLevel;
Console.WriteLine("Levels until max: " + levelsToMax);
```

## Why Use Constants?
1. **Self-documenting**: `MAX_LEVEL` is clearer than `99`
2. **Easy updates**: Change one value, affects everywhere
3. **Prevents errors**: Can't accidentally change the value
4. **Performance**: Compiler optimizes constants'''
            }
        ])
        self._create_lesson_questions(lesson1, [
            {
                'text': 'Which data type stores whole numbers without decimals?',
                'choices': [('int', True), ('float', False), ('double', False), ('string', False)]
            },
            {
                'text': 'What suffix is required for float literals?',
                'choices': [('f', True), ('d', False), ('l', False), ('i', False)]
            },
            {
                'text': 'Which number type has the highest precision for decimals?',
                'choices': [('double', True), ('float', False), ('int', False), ('char', False)]
            },
            {
                'text': 'What keyword makes a variable value unchangeable?',
                'choices': [('const', True), ('static', False), ('final', False), ('fixed', False)]
            },
            {
                'text': 'What is the result of 10 / 3 when both numbers are integers?',
                'choices': [('3 (integer division drops decimals)', True), ('3.33', False), ('3.0', False), ('Error', False)]
            }
        ])

        # Lesson 2: Text and Boolean Types
        lesson2 = Lesson.objects.create(
            unit=unit, title='Text and Boolean Types', order=1, max_quiz_attempts=3
        )
        self._create_sections(lesson2, [
            {
                'title': 'Overview',
                'content': '''# Text and Boolean Types

Learn to work with text data and true/false values in C#.

## Learning Objectives

By the end of this lesson, you will be able to:
- Create and use `string` variables for text
- Concatenate (combine) strings together
- Use `bool` variables for true/false conditions
- Apply proper variable declaration patterns

## Why This Matters

Player names, dialogue, messages, and game states - strings and booleans are everywhere in games!'''
            },
            {
                'title': 'Video: Type Casting in C#',
                'content': '''# Video Lesson: Type Casting in C#

Watch this video from **Bro Code** to learn about converting between data types!

*After watching, continue to learn about strings and booleans.*''',
                'video_type': 'youtube',
                'video_id': 'uajWePMMs84'
            },
            {
                'title': 'String Variables',
                'content': '''# Strings - Text Data

Strings hold text and use double quotes:

```csharp
string playerName = "Hero";
string weaponName = "Sword of Destiny";
string greeting = "Welcome to the game!";

Console.WriteLine(playerName);
Console.WriteLine("Your weapon: " + weaponName);
```

## String Concatenation
Combine strings with `+`:
```csharp
string firstName = "Link";
string lastName = "Hero";
string fullName = firstName + " " + lastName;
// Result: "Link Hero"
```'''
            },
            {
                'title': 'Boolean Variables',
                'content': '''# Booleans - True or False

Booleans store only two values: `true` or `false`

```csharp
bool isAlive = true;
bool hasKey = false;
bool canJump = true;
bool isGameOver = false;

if (isAlive)
{
    Console.WriteLine("The player is alive!");
}

if (!hasKey)  // ! means "not"
{
    Console.WriteLine("You need a key!");
}
```

## Common Game Uses
- Player state (alive, dead, invincible)
- Game flags (paused, started, ended)
- Conditions (can attack, can move, has item)'''
            },
            {
                'title': 'Variable Declaration Patterns',
                'content': '''# Declaration Patterns

## Declare Then Assign
```csharp
int score;           // Declare
score = 100;         // Assign later
```

## Declare and Initialize
```csharp
int score = 100;     // Both at once (preferred)
```

## Multiple Variables
```csharp
// Same type on one line
int health = 100, mana = 50, stamina = 75;

// Or separately (clearer)
int health = 100;
int mana = 50;
int stamina = 75;
```

## Best Practice
Always initialize variables when you declare them to avoid bugs!'''
            },
            {
                'title': 'Type Casting',
                'content': '''# Type Casting (Converting Types)

Sometimes you need to convert between data types.

## Implicit Casting (Automatic)
Small to large types convert automatically:
```csharp
int myInt = 10;
double myDouble = myInt;  // OK! int → double
Console.WriteLine(myDouble);  // 10.0
```

## Explicit Casting (Manual)
Large to small types need explicit casting:
```csharp
double myDouble = 9.78;
int myInt = (int)myDouble;  // Cast with (int)
Console.WriteLine(myInt);  // 9 (decimals lost!)
```

## Convert Class
For converting strings to numbers:
```csharp
string numberText = "42";
int number = Convert.ToInt32(numberText);  // 42

string decimalText = "3.14";
double pi = Convert.ToDouble(decimalText);  // 3.14
```

## Common Conversions
| From | To | Method |
|------|-----|--------|
| string | int | `int.Parse(str)` or `Convert.ToInt32(str)` |
| string | double | `double.Parse(str)` or `Convert.ToDouble(str)` |
| int | string | `num.ToString()` |
| double | int | `(int)doubleValue` |

## Game Example
```csharp
// User enters score as text
string input = Console.ReadLine();
int score = int.Parse(input);

// Calculate percentage (need double for decimals)
int hits = 7;
int attempts = 10;
double accuracy = (double)hits / attempts;  // 0.7
Console.WriteLine($"Accuracy: {accuracy:P0}");  // 70%
```'''
            }
        ])
        self._create_lesson_questions(lesson2, [
            {
                'text': 'What are the only two values a bool can hold?',
                'choices': [('true and false', True), ('0 and 1', False), ('yes and no', False), ('on and off', False)]
            },
            {
                'text': 'What type of quotes does a string use?',
                'choices': [('Double quotes "text"', True), ('Single quotes \'text\'', False), ('Back ticks `text`', False), ('No quotes needed', False)]
            },
            {
                'text': 'What is the difference between string and char?',
                'choices': [('string holds multiple characters, char holds exactly one', True), ('They are the same thing', False), ('char holds numbers, string holds text', False), ('string is faster than char', False)]
            },
            {
                'text': 'Which is a valid bool variable declaration?',
                'choices': [('bool isAlive = true;', True), ('bool isAlive = "true";', False), ('bool isAlive = 1;', False), ('boolean isAlive = true;', False)]
            },
            {
                'text': 'How do you convert a double to an int?',
                'choices': [('Use explicit cast: (int)myDouble', True), ('It converts automatically', False), ('Use int.Parse()', False), ('It is not possible', False)]
            },
            {
                'text': 'What happens to decimals when casting double to int?',
                'choices': [('They are truncated (lost)', True), ('They are rounded up', False), ('They are kept as-is', False), ('An error occurs', False)]
            }
        ])

    def _create_unit2_quiz(self, unit):
        quiz = Quiz.objects.create(
            unit=unit,
            title='Variables & Operators Quiz',
            description='Test your knowledge of C# variables, data types, and operators.',
            passing_score=70,
            points=25,
            max_attempts=3,
            order=0
        )
        questions = [
            {
                'text': 'Which variable type would you use to store a player\'s name?',
                'choices': [('string', True), ('int', False), ('bool', False), ('float', False)]
            },
            {
                'text': 'What is the correct way to declare a constant in C#?',
                'choices': [('const int MAX = 100;', True), ('constant int MAX = 100;', False), ('final int MAX = 100;', False), ('int const MAX = 100;', False)]
            },
            {
                'text': 'Which type uses more memory: float or double?',
                'choices': [('double', True), ('float', False), ('They use the same', False), ('It depends', False)]
            },
            {
                'text': 'What is the result of 10 / 3 when both are integers?',
                'choices': [('3', True), ('3.33', False), ('3.0', False), ('4', False)]
            },
            {
                'text': 'What does `score++` do?',
                'choices': [('Adds 1 to score', True), ('Multiplies score by 2', False), ('Sets score to 1', False), ('Does nothing', False)]
            },
        ]
        self._create_quiz_questions(quiz, questions)

    # Operators lessons (part of Unit 2)
    def _create_unit2_operators_lessons(self, unit):
        lesson3 = Lesson.objects.create(
            unit=unit, title='Arithmetic Operators', order=2, max_quiz_attempts=3
        )
        self._create_sections(lesson3, [
            {
                'title': 'Overview',
                'content': '''# Arithmetic Operators

Learn how to perform calculations in C# using mathematical operators.

## Learning Objectives

By the end of this lesson, you will be able to:
- Use arithmetic operators: `+`, `-`, `*`, `/`, `%`
- Understand integer division behavior
- Apply the modulus operator for remainders
- Calculate game values like damage, healing, and currency

## Why This Matters

Every game needs math - damage calculations, score keeping, resource management. Mastering operators is essential!'''
            },
            {
                'title': 'Video: Arithmetic Operators',
                'content': '''# Video Lesson: Arithmetic Operators

Watch this video from **Bro Code** to see arithmetic operators in action!

*After watching, continue for game-specific examples.*''',
                'video_type': 'youtube',
                'video_id': 'k1ivOkhxxdw'
            },
            {
                'title': 'Video: Math Class',
                'content': '''# Video Lesson: Math Methods

Watch this video from **Bro Code** to learn about the Math class!

*Math.Max(), Math.Min(), Math.Abs(), Math.Pow() and more - essential for game calculations.*''',
                'video_type': 'youtube',
                'video_id': 'tzRK0QFEte0'
            },
            {
                'title': 'Basic Math Operators',
                'content': '''# Arithmetic Operators

C# supports all basic math operations:

| Operator | Name | Example |
|----------|------|---------|
| `+` | Addition | `5 + 3 = 8` |
| `-` | Subtraction | `5 - 3 = 2` |
| `*` | Multiplication | `5 * 3 = 15` |
| `/` | Division | `6 / 3 = 2` |
| `%` | Modulus (remainder) | `7 % 3 = 1` |

```csharp
int a = 10;
int b = 3;
Console.WriteLine(a + b);  // 13
Console.WriteLine(a - b);  // 7
Console.WriteLine(a * b);  // 30
Console.WriteLine(a / b);  // 3 (integer division!)
Console.WriteLine(a % b);  // 1
```'''
            },
            {
                'title': 'Game Math Examples',
                'content': '''# Operators in Game Context

## Addition: Healing
```csharp
int health = 50;
int potion = 30;
int newHealth = health + potion;
Console.WriteLine("Health restored: " + newHealth); // 80
```

## Subtraction: Taking Damage
```csharp
int gold = 100;
int itemCost = 35;
int remaining = gold - itemCost;
Console.WriteLine("Gold left: " + remaining); // 65
```

## Multiplication: Damage Calculation
```csharp
int baseDamage = 25;
int hits = 3;
int totalDamage = baseDamage * hits;
Console.WriteLine("Total damage: " + totalDamage); // 75
```

## Modulus: Inventory Rows
```csharp
int items = 17;
int itemsPerRow = 5;
int lastRowItems = items % itemsPerRow;
Console.WriteLine("Items in last row: " + lastRowItems); // 2
```'''
            }
        ])
        self._create_lesson_questions(lesson3, [
            {
                'text': 'What does the % (modulus) operator return?',
                'choices': [('The remainder of division', True), ('The percentage', False), ('The quotient', False), ('The product', False)]
            },
            {
                'text': 'What is the result of 17 % 5?',
                'choices': [('2 (remainder when 17 is divided by 5)', True), ('3', False), ('3.4', False), ('85', False)]
            },
            {
                'text': 'In the expression 2 + 3 * 4, what is calculated first?',
                'choices': [('3 * 4 (multiplication before addition)', True), ('2 + 3 (left to right)', False), ('They happen at the same time', False), ('2 + 3 (parentheses first)', False)]
            },
            {
                'text': 'What would (10 + 5) * 2 evaluate to?',
                'choices': [('30 (parentheses first: 15 * 2)', True), ('20', False), ('25', False), ('40', False)]
            }
        ])

        lesson4 = Lesson.objects.create(
            unit=unit, title='Assignment Operators', order=3, max_quiz_attempts=3
        )
        self._create_sections(lesson4, [
            {
                'title': 'Overview',
                'content': '''# Assignment Operators

Learn shorthand operators that make your code cleaner and more efficient.

## Learning Objectives

By the end of this lesson, you will be able to:
- Use compound assignment operators: `+=`, `-=`, `*=`, `/=`
- Use increment `++` and decrement `--` operators
- Understand the difference between prefix and postfix
- Write cleaner code with fewer repetitions

## Why This Matters

Assignment operators are used constantly in game loops for updating scores, health, and positions. They make your code shorter and clearer!'''
            },
            {
                'title': 'Compound Assignment',
                'content': '''# Assignment Operators

## Basic Assignment
```csharp
int score = 100;  // Assign 100 to score
```

## Compound Assignment Operators
Shorthand for common operations:

| Operator | Equivalent | Example |
|----------|------------|---------|
| `+=` | `x = x + y` | `score += 10;` |
| `-=` | `x = x - y` | `health -= 25;` |
| `*=` | `x = x * y` | `damage *= 2;` |
| `/=` | `x = x / y` | `gold /= 2;` |

```csharp
int score = 100;
score += 50;    // score is now 150
score -= 30;    // score is now 120
score *= 2;     // score is now 240
```'''
            },
            {
                'title': 'Increment and Decrement',
                'content': '''# Increment & Decrement

## Adding/Subtracting 1
```csharp
int level = 5;
level++;        // level is now 6 (same as level += 1)
level--;        // level is now 5 (same as level -= 1)
```

## Prefix vs Postfix
```csharp
int a = 5;
Console.WriteLine(a++);  // Prints 5, THEN a becomes 6
Console.WriteLine(++a);  // a becomes 7, THEN prints 7
```

## Common Use: Loops
```csharp
int count = 0;
count++;  // 1
count++;  // 2
count++;  // 3
```

Most of the time, `count++` and `++count` work the same. The difference only matters when used in expressions!'''
            }
        ])
        self._create_lesson_questions(lesson4, [
            {
                'text': 'What is `x += 5` equivalent to?',
                'choices': [('x = x + 5', True), ('x = 5', False), ('x = x * 5', False), ('x == 5', False)]
            },
            {
                'text': 'What does `score++` do?',
                'choices': [('Adds 1 to score', True), ('Multiplies score by 2', False), ('Sets score to 1', False), ('Subtracts 1 from score', False)]
            },
            {
                'text': 'If x = 5, what does `Console.WriteLine(x++)` print?',
                'choices': [('5 (prints first, then increments)', True), ('6', False), ('4', False), ('Error', False)]
            },
            {
                'text': 'If x = 5, what does `Console.WriteLine(++x)` print?',
                'choices': [('6 (increments first, then prints)', True), ('5', False), ('4', False), ('Error', False)]
            },
            {
                'text': 'What is `health -= 25` equivalent to?',
                'choices': [('health = health - 25', True), ('health = 25', False), ('health = health + 25', False), ('health == 25', False)]
            }
        ])

    # ================== UNIT 3: Strings & User Input ==================
    def _create_unit3_text_lessons(self, unit):
        lesson1 = Lesson.objects.create(
            unit=unit, title='String Interpolation', order=0, max_quiz_attempts=3
        )
        self._create_sections(lesson1, [
            {
                'title': 'Overview',
                'content': '''# String Interpolation

Learn the modern, clean way to combine text and variables in C#.

## Learning Objectives

By the end of this lesson, you will be able to:
- Use string interpolation with `$"text {variable}"`
- Format numbers with currency, percentages, and decimals
- Compare interpolation vs concatenation
- Create dynamic game messages efficiently

## Why This Matters

Every game displays text - scores, messages, dialogue. String interpolation makes creating dynamic text clean and readable!'''
            },
            {
                'title': 'Video: String Interpolation',
                'content': '''# Video Lesson: String Interpolation

Watch this video from **Bro Code** to see string interpolation in action!

*After watching, continue for more examples and formatting options.*''',
                'video_type': 'youtube',
                'video_id': 'taejaz9OwKY'
            },
            {
                'title': 'String Interpolation Basics',
                'content': '''# String Interpolation

String interpolation makes combining text and variables easy!

## The Old Way (Concatenation)
```csharp
string name = "Hero";
int level = 25;
Console.WriteLine("Player: " + name + " Level: " + level);
```

## The Better Way (Interpolation)
Use `$` before the string and `{variable}` inside:
```csharp
string name = "Hero";
int level = 25;
Console.WriteLine($"Player: {name} Level: {level}");
```

Both output: `Player: Hero Level: 25`

## Why Interpolation is Better
- Cleaner and easier to read
- Less error-prone (fewer `+` signs)
- Can include expressions: `$"Double: {level * 2}"`'''
            },
            {
                'title': 'Formatting Numbers',
                'content': '''# Number Formatting

## Currency
```csharp
double price = 19.99;
Console.WriteLine($"Price: {price:C}");  // $19.99
```

## Fixed Decimal Places
```csharp
double accuracy = 0.8567;
Console.WriteLine($"Accuracy: {accuracy:P1}");  // 85.7%
Console.WriteLine($"Value: {accuracy:F2}");     // 0.86
```

## Padding Numbers
```csharp
int score = 42;
Console.WriteLine($"Score: {score:D5}");  // 00042
```

## Common Format Specifiers
| Format | Description | Example |
|--------|-------------|---------|
| `:C` | Currency | $1,234.56 |
| `:P` | Percent | 85.00% |
| `:F2` | Fixed 2 decimals | 3.14 |
| `:D4` | Pad with zeros | 0042 |'''
            }
        ])
        self._create_lesson_questions(lesson1, [
            {
                'text': 'What character starts an interpolated string?',
                'choices': [('$', True), ('@', False), ('#', False), ('&', False)]
            },
            {
                'text': 'Given `int level = 5;`, what does `$"Level: {level}"` produce?',
                'choices': [('"Level: 5"', True), ('"Level: {level}"', False), ('"Level: $level"', False), ('Error', False)]
            },
            {
                'text': 'Can you do math inside string interpolation like `$"Double: {x * 2}"`?',
                'choices': [('Yes, expressions are evaluated inside { }', True), ('No, only variables allowed', False), ('Only addition is allowed', False), ('Only with parentheses', False)]
            },
            {
                'text': 'What does `{price:C}` do in string interpolation?',
                'choices': [('Formats the number as currency ($)', True), ('Converts to Celsius', False), ('Counts the characters', False), ('Makes it a constant', False)]
            }
        ])

        lesson2 = Lesson.objects.create(
            unit=unit, title='String Methods', order=1, max_quiz_attempts=3
        )
        self._create_sections(lesson2, [
            {
                'title': 'Overview',
                'content': '''# String Methods & User Input

Learn powerful string operations and how to get input from players.

## Learning Objectives

By the end of this lesson, you will be able to:
- Use string methods: `ToUpper()`, `ToLower()`, `Length`, `Contains()`
- Read user input with `Console.ReadLine()`
- Convert string input to numbers with `int.Parse()` and `TryParse()`
- Create interactive console programs

## Why This Matters

Interactive games need user input! Learning to read and process player choices is essential for any game.'''
            },
            {
                'title': 'Video: String Methods',
                'content': '''# Video Lesson: String Methods

Watch this video from **Bro Code** to learn about useful string methods!

*After watching, continue to see more examples.*''',
                'video_type': 'youtube',
                'video_id': 'BKYBiUAWZKM'
            },
            {
                'title': 'Common String Methods',
                'content': '''# String Methods

## Changing Case
```csharp
string name = "Hero";
Console.WriteLine(name.ToUpper());  // HERO
Console.WriteLine(name.ToLower());  // hero
```

## String Properties
```csharp
string message = "Hello World";
Console.WriteLine(message.Length);  // 11
```

## Finding Content
```csharp
string text = "Game Over";
Console.WriteLine(text.Contains("Over"));     // True
Console.WriteLine(text.StartsWith("Game"));   // True
Console.WriteLine(text.EndsWith("!"));        // False
```'''
            },
        ])
        self._create_lesson_questions(lesson2, [
            {
                'text': 'What does "Hello".Length return?',
                'choices': [('5', True), ('4', False), ('6', False), ('"Hello"', False)]
            },
            {
                'text': 'What does "hero".ToUpper() return?',
                'choices': [('"HERO"', True), ('"Hero"', False), ('"hero"', False), ('Error', False)]
            },
            {
                'text': 'What does "Game Over".Contains("Over") return?',
                'choices': [('true', True), ('false', False), ('"Over"', False), ('4', False)]
            }
        ])

        # Lesson 3: User Input
        lesson3 = Lesson.objects.create(
            unit=unit, title='User Input', order=2, max_quiz_attempts=3
        )
        self._create_sections(lesson3, [
            {
                'title': 'Overview',
                'content': '''# User Input

Learn how to make your programs interactive by reading input from users!

## Learning Objectives

By the end of this lesson, you will be able to:
- Use `Console.ReadLine()` to get text input
- Convert string input to numbers with `int.Parse()` and `double.Parse()`
- Handle invalid input safely with `TryParse()`
- Create interactive menu systems

## Why This Matters

Every game needs input! From entering player names to making menu choices, user input is what makes programs interactive and fun.'''
            },
            {
                'title': 'Video: User Input',
                'content': '''# Video Lesson: User Input

Watch this video from **Bro Code** to learn how to get input from users!

*User input is essential for interactive programs and games.*''',
                'video_type': 'youtube',
                'video_id': '_SXJyA605bI'
            },
            {
                'title': 'Console.ReadLine()',
                'content': '''# Reading Text Input

`Console.ReadLine()` waits for the user to type and press Enter:

```csharp
Console.Write("Enter your name: ");
string playerName = Console.ReadLine();
Console.WriteLine($"Hello, {playerName}!");
```

Output:
```
Enter your name: Alex
Hello, Alex!
```

## Write vs WriteLine
- `Console.Write()` - stays on same line (for prompts)
- `Console.WriteLine()` - moves to next line

```csharp
Console.Write("Name: ");      // Cursor stays after "Name: "
string name = Console.ReadLine();
Console.WriteLine("Done!");   // Moves to new line after
```'''
            },
            {
                'title': 'Converting Input to Numbers',
                'content': '''# Parsing Numbers

User input is ALWAYS a string - you must convert it:

```csharp
Console.Write("Enter your age: ");
string input = Console.ReadLine();
int age = int.Parse(input);  // Convert string to int

Console.Write("Enter price: ");
string priceText = Console.ReadLine();
double price = double.Parse(priceText);  // Convert to double
```

## Common Conversions
| Type | Method |
|------|--------|
| int | `int.Parse(str)` |
| double | `double.Parse(str)` |
| float | `float.Parse(str)` |
| bool | `bool.Parse(str)` |

## Warning!
`Parse()` crashes if input is invalid:
```csharp
int num = int.Parse("hello");  // CRASH! "hello" isn't a number
```'''
            },
            {
                'title': 'Safe Input with TryParse',
                'content': '''# Handling Invalid Input

Use `TryParse()` to safely handle bad input:

```csharp
Console.Write("Enter a number: ");
string input = Console.ReadLine();

if (int.TryParse(input, out int number))
{
    Console.WriteLine($"You entered: {number}");
}
else
{
    Console.WriteLine("That's not a valid number!");
}
```

## How TryParse Works
- Returns `true` if conversion succeeds
- Returns `false` if conversion fails (no crash!)
- `out int number` creates the variable and stores the result

## Game Example: Menu Selection
```csharp
Console.WriteLine("1. Start Game");
Console.WriteLine("2. Options");
Console.WriteLine("3. Exit");
Console.Write("Choose: ");

string choice = Console.ReadLine();

if (int.TryParse(choice, out int menuChoice))
{
    switch (menuChoice)
    {
        case 1: StartGame(); break;
        case 2: ShowOptions(); break;
        case 3: Exit(); break;
        default: Console.WriteLine("Invalid choice!"); break;
    }
}
else
{
    Console.WriteLine("Please enter a number!");
}
```'''
            },
            {
                'title': 'Game Input Examples',
                'content': '''# Interactive Game Examples

## Character Creation
```csharp
Console.WriteLine("=== CHARACTER CREATION ===");

Console.Write("Enter character name: ");
string name = Console.ReadLine();

Console.Write("Enter starting gold (0-100): ");
int gold = int.Parse(Console.ReadLine());

Console.Write("Enter difficulty (easy/medium/hard): ");
string difficulty = Console.ReadLine().ToLower();

Console.WriteLine($"\\nCreated {name} with {gold} gold on {difficulty} mode!");
```

## Number Guessing Setup
```csharp
Console.Write("Enter max number for guessing game: ");
if (int.TryParse(Console.ReadLine(), out int maxNum))
{
    Random rand = new Random();
    int secret = rand.Next(1, maxNum + 1);
    Console.WriteLine($"I'm thinking of a number 1-{maxNum}...");
}
```

## Yes/No Confirmation
```csharp
Console.Write("Are you sure? (y/n): ");
string answer = Console.ReadLine().ToLower();

if (answer == "y" || answer == "yes")
{
    Console.WriteLine("Confirmed!");
}
else
{
    Console.WriteLine("Cancelled.");
}
```'''
            }
        ])
        self._create_lesson_questions(lesson3, [
            {
                'text': 'Which method reads a line of text from the user?',
                'choices': [('Console.ReadLine()', True), ('Console.Read()', False), ('Console.GetInput()', False), ('Console.Input()', False)]
            },
            {
                'text': 'What type does Console.ReadLine() always return?',
                'choices': [('string', True), ('int', False), ('any type', False), ('void', False)]
            },
            {
                'text': 'How do you convert the string "42" to an integer?',
                'choices': [('int.Parse("42")', True), ('(int)"42"', False), ('"42".ToInt()', False), ('Convert("42")', False)]
            },
            {
                'text': 'What is the advantage of TryParse over Parse?',
                'choices': [("It doesn't crash on invalid input", True), ("It's faster", False), ("It works with more types", False), ('There is no difference', False)]
            },
            {
                'text': 'What does int.TryParse return?',
                'choices': [('true if conversion succeeded, false if it failed', True), ('The converted number', False), ('An error message', False), ('Nothing (void)', False)]
            }
        ])

    def _create_unit3_quiz(self, unit):
        quiz = Quiz.objects.create(
            unit=unit,
            title='Working with Text Quiz',
            description='Test your knowledge of strings and user input.',
            passing_score=70,
            points=20,
            max_attempts=3,
            order=0
        )
        questions = [
            {
                'text': 'What does "Hello".Length return?',
                'choices': [('5', True), ('4', False), ('6', False), ('"Hello"', False)]
            },
            {
                'text': 'How do you convert a string "42" to an integer?',
                'choices': [('int.Parse("42")', True), ('(int)"42"', False), ('"42".ToInt()', False), ('Convert("42")', False)]
            },
        ]
        self._create_quiz_questions(quiz, questions)

    # ================== UNIT 4: Control Flow ==================
    def _create_unit4_conditionals_lessons(self, unit):
        lesson1 = Lesson.objects.create(
            unit=unit, title='Comparison Operators', order=0, max_quiz_attempts=3
        )
        self._create_sections(lesson1, [
            {
                'title': 'Overview',
                'content': '''# Comparison Operators

Learn to compare values - the foundation of all game logic and decisions.

## Learning Objectives

By the end of this lesson, you will be able to:
- Use comparison operators: `==`, `!=`, `>`, `<`, `>=`, `<=`
- Understand that comparisons return boolean values
- Compare numbers, strings, and other values
- Build conditions for game logic

## Why This Matters

Every game decision requires comparisons - Is health below 0? Is the score high enough? Did the player win? Comparisons are everywhere!'''
            },
            {
                'title': 'Video: If Statements',
                'content': '''# Video Lesson: If Statements

Watch this video from **Bro Code** to learn about conditional logic!

*If statements are the foundation of all decision-making in programs.*''',
                'video_type': 'youtube',
                'video_id': 'pSPQnXleaS8'
            },
            {
                'title': 'Comparison Operators',
                'content': '''# Comparison Operators

Comparisons return `true` or `false`:

| Operator | Meaning | Example |
|----------|---------|---------|
| `==` | Equal to | `5 == 5` → true |
| `!=` | Not equal | `5 != 3` → true |
| `>` | Greater than | `5 > 3` → true |
| `<` | Less than | `5 < 3` → false |
| `>=` | Greater or equal | `5 >= 5` → true |
| `<=` | Less or equal | `5 <= 3` → false |

```csharp
int health = 25;
int maxHealth = 100;

Console.WriteLine(health < 30);      // true
Console.WriteLine(health == 25);     // true
Console.WriteLine(health >= maxHealth); // false
```'''
            }
        ])
        self._create_lesson_questions(lesson1, [
            {
                'text': 'What does == check for?',
                'choices': [('Equality (are two values the same)', True), ('Assignment (set a value)', False), ('Greater than', False), ('Not equal', False)]
            },
            {
                'text': 'What is the difference between = and ==?',
                'choices': [('= assigns a value, == compares values', True), ('They are the same', False), ('= compares, == assigns', False), ('== is for strings only', False)]
            },
            {
                'text': 'What does != mean?',
                'choices': [('Not equal to', True), ('Equal to', False), ('Greater than', False), ('Less than', False)]
            },
            {
                'text': 'What does the expression (5 > 3) evaluate to?',
                'choices': [('true', True), ('false', False), ('5', False), ('3', False)]
            }
        ])

        lesson2 = Lesson.objects.create(
            unit=unit, title='If Statements', order=1, max_quiz_attempts=3
        )
        self._create_sections(lesson2, [
            {
                'title': 'Overview',
                'content': '''# If Statements

Learn to make your programs smart by making decisions based on conditions.

## Learning Objectives

By the end of this lesson, you will be able to:
- Write `if` statements to execute conditional code
- Use `if-else` for two-way decisions
- Chain multiple conditions with `else if`
- Combine conditions using `&&` (AND), `||` (OR), and `!` (NOT)

## Why This Matters

Conditionals are the brain of your game! Every enemy AI decision, every player action check, every game rule uses if statements.'''
            },
            {
                'title': 'Video: Logical Operators',
                'content': '''# Video Lesson: Logical Operators

Watch this video from **Bro Code** to learn about combining conditions with AND, OR, and NOT!

*Logical operators let you create complex conditions for game logic.*''',
                'video_type': 'youtube',
                'video_id': 'uxS_0S0dNs8'
            },
            {
                'title': 'Basic If Statements',
                'content': '''# If Statements

Execute code only when a condition is true:

```csharp
int gold = 50;
bool foundTreasure = true;

if (foundTreasure)
{
    gold = gold + 100;
    Console.WriteLine("You found treasure! +100 gold!");
}
Console.WriteLine($"Total gold: {gold}");
```

## Game Example: Low Health Warning
```csharp
int playerHealth = 20;

if (playerHealth < 30)
{
    Console.WriteLine("WARNING: Low health!");
}
```'''
            },
            {
                'title': 'If-Else Statements',
                'content': '''# If-Else

Choose between two options:

```csharp
int score = 75;

if (score >= 60)
{
    Console.WriteLine("You passed!");
}
else
{
    Console.WriteLine("Try again.");
}
```

## Game Example: Attack or Defend
```csharp
int enemyDistance = 5;

if (enemyDistance < 10)
{
    Console.WriteLine("Attack the enemy!");
}
else
{
    Console.WriteLine("Move closer first.");
}
```'''
            },
            {
                'title': 'Else-If Chains',
                'content': '''# Else-If Chains

Handle multiple conditions:

```csharp
int score = 85;

if (score >= 90)
{
    Console.WriteLine("Grade: A");
}
else if (score >= 80)
{
    Console.WriteLine("Grade: B");
}
else if (score >= 70)
{
    Console.WriteLine("Grade: C");
}
else
{
    Console.WriteLine("Grade: F");
}
```

Only **one** block runs - the first true condition!'''
            },
            {
                'title': 'Logical Operators',
                'content': '''# Logical Operators

Combine multiple conditions:

| Operator | Name | True When |
|----------|------|-----------|
| `&&` | AND | Both true |
| `\\|\\|` | OR | Either true |
| `!` | NOT | Reverses value |

```csharp
int mana = 50;
bool hasSpellbook = true;

// AND - both must be true
if (mana >= 20 && hasSpellbook)
{
    Console.WriteLine("You can cast spells!");
}

// OR - either can be true
if (health <= 0 || isStunned)
{
    Console.WriteLine("Cannot move!");
}

// NOT - reverses the condition
if (!hasKey)
{
    Console.WriteLine("You need a key!");
}
```'''
            }
        ])
        self._create_lesson_questions(lesson2, [
            {
                'text': 'What does && (AND) require for the condition to be true?',
                'choices': [('Both conditions must be true', True), ('Either condition must be true', False), ('Neither condition must be true', False), ('Only the first condition', False)]
            },
            {
                'text': 'What does || (OR) require for the condition to be true?',
                'choices': [('At least one condition must be true', True), ('Both conditions must be true', False), ('Neither condition must be true', False), ('Exactly one must be true', False)]
            },
            {
                'text': 'When does the else block run?',
                'choices': [('When all if/else-if conditions are false', True), ('When the if condition is true', False), ('Always', False), ('Never', False)]
            },
            {
                'text': 'In an else-if chain, how many blocks can execute?',
                'choices': [('Only one (the first true condition)', True), ('All true conditions', False), ('Always two', False), ('None', False)]
            },
            {
                'text': 'What does the ! (NOT) operator do?',
                'choices': [('Reverses a boolean (true becomes false)', True), ('Checks if not equal', False), ('Multiplies by -1', False), ('Ends the program', False)]
            }
        ])

        # Lesson 3: Switch Statements
        lesson3 = Lesson.objects.create(
            unit=unit, title='Switch Statements', order=2, max_quiz_attempts=3
        )
        self._create_sections(lesson3, [
            {
                'title': 'Overview',
                'content': '''# Switch Statements

Learn a cleaner way to handle multiple conditions - perfect for menus and game states!

## Learning Objectives

By the end of this lesson, you will be able to:
- Use `switch` statements for multi-way branching
- Write `case` labels and `default` handlers
- Understand when switch is better than if-else chains
- Create game menus and state machines

## Why This Matters

Game menus, character classes, inventory items, enemy types - switch statements handle these choices elegantly without messy if-else chains!'''
            },
            {
                'title': 'Video: Switch Statements',
                'content': '''# Video Lesson: Switch Statements

Watch this video from **Bro Code** to learn about switch statements in C#!

*Switch is perfect for handling multiple specific values cleanly.*''',
                'video_type': 'youtube',
                'video_id': 'Qu93CRt-FGc'
            },
            {
                'title': 'Switch Syntax',
                'content': '''# Switch Statement

Compare one value against many cases:

```csharp
int dayNumber = 3;

switch (dayNumber)
{
    case 1:
        Console.WriteLine("Monday");
        break;
    case 2:
        Console.WriteLine("Tuesday");
        break;
    case 3:
        Console.WriteLine("Wednesday");
        break;
    default:
        Console.WriteLine("Unknown day");
        break;
}
```

## Key Parts
- `switch (variable)` - The value to check
- `case value:` - A possible match
- `break;` - Exit the switch (required!)
- `default:` - Runs if no case matches'''
            },
            {
                'title': 'Switch vs If-Else',
                'content': '''# When to Use Switch

## Switch is Better When:
- Comparing ONE variable to MANY specific values
- Each case has distinct, fixed values
- Creating menus or state machines

## If-Else is Better When:
- Checking ranges (`x > 10`)
- Complex conditions (`x > 5 && y < 10`)
- Comparing multiple variables

## Comparison
```csharp
// If-else chain (harder to read)
if (choice == 1) { Attack(); }
else if (choice == 2) { Defend(); }
else if (choice == 3) { UseItem(); }
else if (choice == 4) { RunAway(); }
else { Console.WriteLine("Invalid"); }

// Switch (cleaner!)
switch (choice)
{
    case 1: Attack(); break;
    case 2: Defend(); break;
    case 3: UseItem(); break;
    case 4: RunAway(); break;
    default: Console.WriteLine("Invalid"); break;
}
```'''
            },
            {
                'title': 'Game Examples',
                'content': '''# Switch in Games

## Character Class Selection
```csharp
Console.WriteLine("Choose your class:");
Console.WriteLine("1. Warrior  2. Mage  3. Rogue");
int classChoice = int.Parse(Console.ReadLine());

switch (classChoice)
{
    case 1:
        Console.WriteLine("You chose Warrior!");
        Console.WriteLine("High health, melee attacks");
        break;
    case 2:
        Console.WriteLine("You chose Mage!");
        Console.WriteLine("Powerful spells, low health");
        break;
    case 3:
        Console.WriteLine("You chose Rogue!");
        Console.WriteLine("Fast attacks, stealth abilities");
        break;
    default:
        Console.WriteLine("Invalid choice!");
        break;
}
```

## Game State Machine
```csharp
string gameState = "playing";

switch (gameState)
{
    case "menu":
        ShowMainMenu();
        break;
    case "playing":
        UpdateGame();
        break;
    case "paused":
        ShowPauseMenu();
        break;
    case "gameover":
        ShowGameOver();
        break;
}
```

## Grade Calculator
```csharp
char grade = 'B';

switch (grade)
{
    case 'A':
        Console.WriteLine("Excellent!");
        break;
    case 'B':
        Console.WriteLine("Good job!");
        break;
    case 'C':
        Console.WriteLine("You passed.");
        break;
    case 'D':
    case 'F':
        Console.WriteLine("Need improvement.");
        break;
}
```'''
            }
        ])
        self._create_lesson_questions(lesson3, [
            {
                'text': 'What keyword ends each case in a switch statement?',
                'choices': [
                    ('break', True),
                    ('end', False),
                    ('stop', False),
                    ('return', False)
                ]
            },
            {
                'text': 'What does the "default" case do?',
                'choices': [
                    ('Runs when no other case matches', True),
                    ('Runs first before any cases', False),
                    ('Runs after every case', False),
                    ('Is required in every switch', False)
                ]
            },
            {
                'text': 'When is switch better than if-else?',
                'choices': [
                    ('When comparing one variable to many specific values', True),
                    ('When checking ranges like x > 10', False),
                    ('When you have complex conditions', False),
                    ('Switch is always better', False)
                ]
            },
            {
                'text': 'What happens if you forget the break statement?',
                'choices': [
                    ('Code "falls through" to the next case (usually a bug)', True),
                    ('Compile error', False),
                    ('Nothing - it is optional', False),
                    ('The program crashes', False)
                ]
            }
        ])

    def _create_unit4_quiz(self, unit):
        quiz = Quiz.objects.create(
            unit=unit,
            title='Control Flow Quiz',
            description='Test your understanding of conditionals and loops.',
            passing_score=70,
            points=30,
            max_attempts=3,
            order=0
        )
        questions = [
            {
                'text': 'What is the difference between = and ==?',
                'choices': [('= assigns, == compares', True), ('They are the same', False), ('= compares, == assigns', False), ('== is for strings only', False)]
            },
            {
                'text': 'When does an else block run?',
                'choices': [('When the if condition is false', True), ('When the if condition is true', False), ('Always', False), ('Never', False)]
            },
            {
                'text': 'When is a switch statement better than if-else?',
                'choices': [('When comparing one variable to many specific values', True), ('When checking ranges', False), ('When you have complex conditions', False), ('Never - always use if-else', False)]
            },
            {
                'text': 'Which loop is best when you don\'t know how many iterations you need?',
                'choices': [('while loop', True), ('for loop', False), ('foreach loop', False), ('None of these', False)]
            },
            {
                'text': 'What does "break" do inside a loop?',
                'choices': [('Exits the loop immediately', True), ('Skips one iteration', False), ('Pauses the loop', False), ('Restarts the loop', False)]
            },
            {
                'text': 'Which loop automatically handles indexing through a collection?',
                'choices': [('foreach', True), ('while', False), ('for', False), ('do-while', False)]
            },
        ]
        self._create_quiz_questions(quiz, questions)

    # Loops lessons (part of Unit 4: Control Flow)
    def _create_unit4_loops_lessons(self, unit):
        # Lesson 4: While Loops
        lesson4 = Lesson.objects.create(
            unit=unit, title='While Loops', order=3, max_quiz_attempts=3
        )
        self._create_sections(lesson4, [
            {
                'title': 'Overview',
                'content': '''# While Loops

Learn to repeat code as long as a condition is true - essential for game loops!

## Learning Objectives

By the end of this lesson, you will be able to:
- Create `while` loops that repeat based on a condition
- Avoid infinite loops with proper exit conditions
- Use loop control statements: `break` and `continue`
- Implement countdown timers and input validation

## Why This Matters

Every game has loops - game loops, animation loops, spawn loops. Understanding while loops is crucial for creating dynamic, interactive programs!'''
            },
            {
                'title': 'Video: While Loops',
                'content': '''# Video Lesson: While Loops

Watch this video from **Bro Code** to learn about while loops in C#!

*While loops repeat code as long as a condition remains true.*''',
                'video_type': 'youtube',
                'video_id': 'EyghyKO4BlA'
            },
            {
                'title': 'Basic While Loop',
                'content': '''# While Loop Syntax

A while loop repeats code **while** a condition is true:

```csharp
int count = 0;

while (count < 5)
{
    Console.WriteLine($"Count: {count}");
    count++;  // Don't forget to update!
}
```

Output:
```
Count: 0
Count: 1
Count: 2
Count: 3
Count: 4
```

## Key Parts
1. **Condition**: Checked before each iteration
2. **Body**: Code that repeats
3. **Update**: Something must change to eventually exit!'''
            },
            {
                'title': 'Game Examples',
                'content': '''# While Loops in Games

## Countdown Timer
```csharp
int countdown = 10;

while (countdown > 0)
{
    Console.WriteLine($"Starting in {countdown}...");
    countdown--;
}
Console.WriteLine("GO!");
```

## Player Health Regeneration
```csharp
int health = 50;
int maxHealth = 100;

while (health < maxHealth)
{
    health += 5;  // Regen 5 HP
    Console.WriteLine($"Health: {health}/{maxHealth}");
}
Console.WriteLine("Fully healed!");
```

## Input Validation (Keep Asking Until Valid)
```csharp
string password = "";

while (password != "secret123")
{
    Console.Write("Enter password: ");
    password = Console.ReadLine();
}
Console.WriteLine("Access granted!");
```'''
            },
            {
                'title': 'Break and Continue',
                'content': '''# Loop Control

## break - Exit the loop immediately
```csharp
int health = 100;

while (true)  // Infinite loop!
{
    health -= 10;
    Console.WriteLine($"Health: {health}");

    if (health <= 0)
    {
        Console.WriteLine("Game Over!");
        break;  // Exit the loop
    }
}
```

## continue - Skip to next iteration
```csharp
int i = 0;

while (i < 10)
{
    i++;

    if (i % 2 == 0)
    {
        continue;  // Skip even numbers
    }

    Console.WriteLine(i);  // Only prints odd: 1, 3, 5, 7, 9
}
```

## Warning: Infinite Loops!
```csharp
// DANGER - This never ends!
while (true)
{
    Console.WriteLine("Forever...");
}
// Make sure you have a way to exit!
```'''
            }
        ])
        self._create_lesson_questions(lesson4, [
            {
                'text': 'When does a while loop stop executing?',
                'choices': [
                    ('When the condition becomes false', True),
                    ('After running once', False),
                    ('When it reaches the end of the file', False),
                    ('It never stops', False)
                ]
            },
            {
                'text': 'What does the "break" statement do?',
                'choices': [
                    ('Exits the loop immediately', True),
                    ('Pauses the loop', False),
                    ('Skips to the next iteration', False),
                    ('Breaks the computer', False)
                ]
            },
            {
                'text': 'What does the "continue" statement do?',
                'choices': [
                    ('Skips to the next iteration of the loop', True),
                    ('Exits the loop', False),
                    ('Continues to the next line', False),
                    ('Restarts the loop from the beginning', False)
                ]
            },
            {
                'text': 'What happens if the condition is never false?',
                'choices': [
                    ('An infinite loop (runs forever)', True),
                    ('The loop runs once', False),
                    ('A compile error', False),
                    ('The loop is skipped', False)
                ]
            }
        ])

        # Lesson 5: For Loops
        lesson5 = Lesson.objects.create(
            unit=unit, title='For Loops', order=4, max_quiz_attempts=3
        )
        self._create_sections(lesson5, [
            {
                'title': 'Overview',
                'content': '''# For Loops

Master the most common loop type - perfect when you know how many times to repeat!

## Learning Objectives

By the end of this lesson, you will be able to:
- Create `for` loops with initialization, condition, and increment
- Use for loops to iterate a specific number of times
- Count up, count down, and count by different amounts
- Choose between for and while loops appropriately

## Why This Matters

For loops are the workhorses of programming. Spawning enemies, processing inventory items, creating level tiles - for loops handle it all!'''
            },
            {
                'title': 'Video: For Loops',
                'content': '''# Video Lesson: For Loops

Watch this video from **Bro Code** to learn about for loops in C#!

*For loops are perfect when you know exactly how many iterations you need.*''',
                'video_type': 'youtube',
                'video_id': 'h4hY2hho73Q'
            },
            {
                'title': 'For Loop Syntax',
                'content': '''# For Loop Structure

```csharp
for (int i = 0; i < 5; i++)
{
    Console.WriteLine($"Iteration {i}");
}
```

## The Three Parts
```
for (initialization; condition; update)
```

| Part | Purpose | Example |
|------|---------|---------|
| Initialization | Create counter variable | `int i = 0` |
| Condition | Check before each loop | `i < 5` |
| Update | Run after each iteration | `i++` |

## Step by Step:
1. `int i = 0` - Start at 0
2. `i < 5?` - Yes! Run the body
3. Print "Iteration 0"
4. `i++` - Now i = 1
5. `i < 5?` - Yes! Continue...
6. Repeats until i = 5, then stops'''
            },
            {
                'title': 'Counting Variations',
                'content': '''# Different Counting Patterns

## Count Up (0 to 9)
```csharp
for (int i = 0; i < 10; i++)
{
    Console.WriteLine(i);
}
```

## Count Down (10 to 1)
```csharp
for (int i = 10; i > 0; i--)
{
    Console.WriteLine(i);
}
Console.WriteLine("Blast off!");
```

## Count by 2s (Even Numbers)
```csharp
for (int i = 0; i <= 10; i += 2)
{
    Console.WriteLine(i);  // 0, 2, 4, 6, 8, 10
}
```

## Start at Different Number
```csharp
for (int i = 5; i <= 15; i++)
{
    Console.WriteLine(i);  // 5, 6, 7... 15
}
```'''
            },
            {
                'title': 'Game Examples',
                'content': '''# For Loops in Games

## Spawn 5 Enemies
```csharp
for (int i = 0; i < 5; i++)
{
    Console.WriteLine($"Spawning enemy #{i + 1}");
}
```

## Display Inventory
```csharp
string[] items = {"Sword", "Shield", "Potion"};

for (int i = 0; i < items.Length; i++)
{
    Console.WriteLine($"{i + 1}. {items[i]}");
}
```

## Draw Health Bar
```csharp
int health = 7;
int maxHealth = 10;

Console.Write("HP: [");
for (int i = 0; i < maxHealth; i++)
{
    if (i < health)
        Console.Write("█");
    else
        Console.Write("░");
}
Console.WriteLine("]");
// Output: HP: [███████░░░]
```'''
            }
        ])
        self._create_lesson_questions(lesson5, [
            {
                'text': 'What are the three parts of a for loop?',
                'choices': [
                    ('Initialization, condition, update', True),
                    ('Start, middle, end', False),
                    ('Input, process, output', False),
                    ('Begin, loop, finish', False)
                ]
            },
            {
                'text': 'In `for (int i = 0; i < 5; i++)`, how many times does the loop run?',
                'choices': [
                    ('5 times (0, 1, 2, 3, 4)', True),
                    ('6 times', False),
                    ('4 times', False),
                    ('Infinite times', False)
                ]
            },
            {
                'text': 'Which loop is best when you know exactly how many iterations?',
                'choices': [
                    ('for loop', True),
                    ('while loop', False),
                    ('if statement', False),
                    ('switch statement', False)
                ]
            },
            {
                'text': 'What does `i += 2` do in a for loop update?',
                'choices': [
                    ('Increases i by 2 each iteration', True),
                    ('Multiplies i by 2', False),
                    ('Sets i to 2', False),
                    ('Divides i by 2', False)
                ]
            }
        ])

        # Lesson 6: Nested Loops
        lesson6 = Lesson.objects.create(
            unit=unit, title='Nested Loops', order=5, max_quiz_attempts=3
        )
        self._create_sections(lesson6, [
            {
                'title': 'Overview',
                'content': '''# Nested Loops

Learn to put loops inside loops - essential for 2D patterns, grids, and tables!

## Learning Objectives

By the end of this lesson, you will be able to:
- Create loops inside other loops (nesting)
- Understand how nested loop iterations multiply
- Generate 2D patterns and grids
- Create game boards and tile maps

## Why This Matters

Game worlds are 2D grids! Tile maps, chess boards, inventory grids - nested loops create all of these structures.'''
            },
            {
                'title': 'Video: Nested Loops',
                'content': '''# Video Lesson: Nested Loops

Watch this video from **Bro Code** to learn about putting loops inside loops!

*Nested loops are essential for working with 2D data like game boards.*''',
                'video_type': 'youtube',
                'video_id': 'WFzLcZk137s'
            },
            {
                'title': 'Understanding Nested Loops',
                'content': '''# Loops Inside Loops

The inner loop runs completely for EACH iteration of the outer loop:

```csharp
for (int i = 0; i < 3; i++)       // Outer: rows
{
    for (int j = 0; j < 4; j++)   // Inner: columns
    {
        Console.Write("* ");
    }
    Console.WriteLine();  // New line after each row
}
```

Output:
```
* * * *
* * * *
* * * *
```

## Iteration Count
- Outer loop: 3 iterations
- Inner loop: 4 iterations **per outer**
- Total: 3 × 4 = **12 prints**'''
            },
            {
                'title': 'Grid and Pattern Examples',
                'content': '''# Practical Patterns

## Multiplication Table
```csharp
for (int i = 1; i <= 5; i++)
{
    for (int j = 1; j <= 5; j++)
    {
        Console.Write($"{i * j,4}");
    }
    Console.WriteLine();
}
```
Output:
```
   1   2   3   4   5
   2   4   6   8  10
   3   6   9  12  15
   4   8  12  16  20
   5  10  15  20  25
```

## Game Board (Checkerboard)
```csharp
for (int row = 0; row < 8; row++)
{
    for (int col = 0; col < 8; col++)
    {
        if ((row + col) % 2 == 0)
            Console.Write("□ ");
        else
            Console.Write("■ ");
    }
    Console.WriteLine();
}
```

## Coordinate Grid
```csharp
for (int y = 0; y < 3; y++)
{
    for (int x = 0; x < 3; x++)
    {
        Console.Write($"({x},{y}) ");
    }
    Console.WriteLine();
}
```'''
            }
        ])
        self._create_lesson_questions(lesson6, [
            {
                'text': 'In nested loops, how many times does the inner loop run in total?',
                'choices': [
                    ('Outer iterations × Inner iterations', True),
                    ('Outer + Inner iterations', False),
                    ('Just the inner loop count', False),
                    ('Just the outer loop count', False)
                ]
            },
            {
                'text': 'What are nested loops commonly used for?',
                'choices': [
                    ('Creating 2D grids and patterns', True),
                    ('Making code run faster', False),
                    ('Avoiding while loops', False),
                    ('Creating variables', False)
                ]
            },
            {
                'text': 'If outer loop runs 5 times and inner runs 3 times, how many total iterations?',
                'choices': [
                    ('15 (5 × 3)', True),
                    ('8 (5 + 3)', False),
                    ('5', False),
                    ('3', False)
                ]
            }
        ])

        # Lesson 7: ForEach Loops
        lesson7 = Lesson.objects.create(
            unit=unit, title='ForEach Loops', order=6, max_quiz_attempts=3
        )
        self._create_sections(lesson7, [
            {
                'title': 'Overview',
                'content': '''# ForEach Loops

Discover the cleanest way to loop through collections - no index needed!

## Learning Objectives

By the end of this lesson, you will be able to:
- Use `foreach` to iterate through arrays and collections
- Understand when foreach is better than for
- Process each item without managing an index
- Work with different collection types

## Why This Matters

Most game data lives in collections - inventories, enemy lists, high scores. ForEach makes processing these collections simple and readable!'''
            },
            {
                'title': 'Video: ForEach Loops',
                'content': '''# Video Lesson: ForEach Loops

Watch this video from **Bro Code** to learn about the foreach loop!

*ForEach is the cleanest way to process every item in a collection.*''',
                'video_type': 'youtube',
                'video_id': 'WhACXlObR8s'
            },
            {
                'title': 'ForEach Syntax',
                'content': '''# ForEach Loop

Process each item without managing an index:

```csharp
string[] weapons = {"Sword", "Bow", "Staff", "Axe"};

foreach (string weapon in weapons)
{
    Console.WriteLine($"You have a {weapon}");
}
```

Output:
```
You have a Sword
You have a Bow
You have a Staff
You have a Axe
```

## Syntax Breakdown
```csharp
foreach (type variableName in collection)
{
    // Use variableName
}
```

- `type` - The type of items in the collection
- `variableName` - Name for current item
- `collection` - The array/list to loop through'''
            },
            {
                'title': 'ForEach vs For',
                'content': '''# When to Use Each

## Use foreach when:
- You need every item
- You don't need the index
- You want cleaner code

```csharp
// Clean and simple
foreach (string item in inventory)
{
    Console.WriteLine(item);
}
```

## Use for when:
- You need the index
- You need to modify the array
- You need to skip/select certain indices

```csharp
// Need index for numbering
for (int i = 0; i < inventory.Length; i++)
{
    Console.WriteLine($"{i + 1}. {inventory[i]}");
}
```

## Game Examples
```csharp
// Calculate total damage from all weapons
int totalDamage = 0;
int[] weaponDamages = {10, 25, 15, 30};

foreach (int damage in weaponDamages)
{
    totalDamage += damage;
}
Console.WriteLine($"Total damage: {totalDamage}");

// Find all alive enemies
string[] enemies = {"Goblin", "Dead", "Orc", "Dead", "Dragon"};

foreach (string enemy in enemies)
{
    if (enemy != "Dead")
    {
        Console.WriteLine($"{enemy} is still alive!");
    }
}
```'''
            }
        ])
        self._create_lesson_questions(lesson7, [
            {
                'text': 'What is the main advantage of foreach over for?',
                'choices': [
                    ('Cleaner syntax - no index management needed', True),
                    ('Runs faster', False),
                    ('Can modify the array', False),
                    ('Works with more data types', False)
                ]
            },
            {
                'text': 'When should you use a for loop instead of foreach?',
                'choices': [
                    ('When you need the index or need to modify items', True),
                    ('When you have a string array', False),
                    ('When you want cleaner code', False),
                    ('Always - for is always better', False)
                ]
            },
            {
                'text': 'In `foreach (int num in numbers)`, what does `num` represent?',
                'choices': [
                    ('The current item being processed', True),
                    ('The index of the current item', False),
                    ('The total count of items', False),
                    ('The name of the array', False)
                ]
            }
        ])

    # ================== UNIT 5: Methods & Functions ==================
    def _create_unit5_methods_lessons(self, unit):
        lesson1 = Lesson.objects.create(
            unit=unit, title='Built-in Methods', order=0, max_quiz_attempts=3
        )
        self._create_sections(lesson1, [
            {
                'title': 'Overview',
                'content': '''# Built-in Methods

Discover powerful pre-built methods that C# provides for math and randomness.

## Learning Objectives

By the end of this lesson, you will be able to:
- Use `Math` methods: `Max()`, `Min()`, `Abs()`, `Pow()`, `Sqrt()`, `Round()`
- Generate random numbers with the `Random` class
- Apply random values for game mechanics like damage and dice rolls
- Understand how built-in methods save you time

## Why This Matters

Don't reinvent the wheel! C# provides hundreds of useful methods. Learning to use them makes you a more efficient programmer.'''
            },
            {
                'title': 'Math Methods',
                'content': '''# Built-in Math Methods

C# includes many useful methods:

```csharp
// Find the larger/smaller value
int max = Math.Max(10, 20);    // 20
int min = Math.Min(10, 20);    // 10

// Absolute value (removes negative)
int abs = Math.Abs(-15);       // 15

// Power (exponent)
double power = Math.Pow(2, 3); // 8.0

// Square root
double sqrt = Math.Sqrt(16);   // 4.0

// Round numbers
double rounded = Math.Round(3.7);  // 4.0
int floor = (int)Math.Floor(3.9);  // 3
int ceiling = (int)Math.Ceiling(3.1); // 4
```'''
            },
            {
                'title': 'Random Numbers',
                'content': '''# Generating Random Numbers

Games need randomness for variety!

```csharp
Random rand = new Random();

// Random int from 1 to 10
int roll = rand.Next(1, 11);  // Max is exclusive!

// Random int from 0 to 99
int percent = rand.Next(100);

// Random double from 0.0 to 1.0
double chance = rand.NextDouble();
```

## Game Examples
```csharp
Random rand = new Random();

// Dice roll (1-6)
int dice = rand.Next(1, 7);

// Critical hit chance (25%)
if (rand.NextDouble() < 0.25)
{
    Console.WriteLine("Critical hit!");
}

// Random damage (10-20)
int damage = rand.Next(10, 21);
```'''
            }
        ])
        self._create_lesson_questions(lesson1, [
            {
                'text': 'What does Math.Max(5, 10) return?',
                'choices': [('10 (the larger value)', True), ('5', False), ('15', False), ('50', False)]
            },
            {
                'text': 'What does Math.Min(5, 10) return?',
                'choices': [('5 (the smaller value)', True), ('10', False), ('15', False), ('-5', False)]
            },
            {
                'text': 'What does Math.Abs(-15) return?',
                'choices': [('15 (absolute value removes negative)', True), ('-15', False), ('0', False), ('Error', False)]
            },
            {
                'text': 'How do you generate a random number from 1 to 6 (like a dice)?',
                'choices': [('rand.Next(1, 7) - max is exclusive', True), ('rand.Next(1, 6)', False), ('rand.Next(6)', False), ('Random(1, 6)', False)]
            }
        ])

        lesson2 = Lesson.objects.create(
            unit=unit, title='Creating Your Own Methods', order=1, max_quiz_attempts=3
        )
        self._create_sections(lesson2, [
            {
                'title': 'Overview',
                'content': '''# Creating Your Own Methods

Learn to write reusable code blocks that organize your programs like a pro.

## Learning Objectives

By the end of this lesson, you will be able to:
- Create methods with `void` that perform actions
- Create methods with parameters to accept input
- Create methods with return values to send data back
- Organize code into logical, reusable pieces

## Why This Matters

Methods are the building blocks of professional software. Every game system - combat, inventory, AI - is built from well-organized methods!'''
            },
            {
                'title': 'Video: Methods',
                'content': '''# Video Lesson: Methods

Watch this video from **Bro Code** to learn about creating and using methods!

*Methods help you organize code into reusable pieces.*''',
                'video_type': 'youtube',
                'video_id': 'IPpEefuFiVM'
            },
            {
                'title': 'Video: Return Keyword',
                'content': '''# Video Lesson: Return Values

Watch this video from **Bro Code** to learn about returning values from methods!

*Return values let methods send data back to the caller.*''',
                'video_type': 'youtube',
                'video_id': 'FaK5Nh20gVA'
            },
            {
                'title': 'Basic Methods',
                'content': '''# Creating Methods

Methods are reusable blocks of code:

```csharp
class Program
{
    static void Main()
    {
        Greet();  // Call the method
        Greet();  // Call it again!
    }

    static void Greet()
    {
        Console.WriteLine("Hello, adventurer!");
    }
}
```

## Anatomy of a Method
```csharp
static void MethodName()
{
    // Code goes here
}
```
- `static` - belongs to the class
- `void` - returns nothing
- `MethodName` - use PascalCase!'''
            },
            {
                'title': 'Methods with Parameters',
                'content': '''# Parameters

Pass data into methods:

```csharp
static void Main()
{
    Greet("Link");
    Greet("Zelda");
    Attack("Slime", 25);
}

static void Greet(string name)
{
    Console.WriteLine($"Hello, {name}!");
}

static void Attack(string enemy, int damage)
{
    Console.WriteLine($"You deal {damage} damage to {enemy}!");
}
```

Output:
```
Hello, Link!
Hello, Zelda!
You deal 25 damage to Slime!
```'''
            },
            {
                'title': 'Return Values',
                'content': '''# Methods with Return Values

Methods can send data back:

```csharp
static void Main()
{
    int total = Add(5, 3);
    Console.WriteLine(total);  // 8

    int damage = CalculateDamage(10, 1.5);
    Console.WriteLine($"Damage: {damage}");
}

static int Add(int a, int b)
{
    return a + b;
}

static int CalculateDamage(int baseDamage, double multiplier)
{
    return (int)(baseDamage * multiplier);
}
```

## Key Points
- Replace `void` with the return type (`int`, `string`, etc.)
- Use `return` to send the value back
- The method call becomes that value'''
            },
            {
                'title': 'Putting It All Together',
                'content': '''# Complete Example: Combat System

```csharp
class CombatGame
{
    static Random rand = new Random();

    static void Main()
    {
        int playerHealth = 100;
        int enemyHealth = 50;

        while (playerHealth > 0 && enemyHealth > 0)
        {
            // Player attacks
            int damage = CalculateDamage(10, 20);
            enemyHealth = TakeDamage(enemyHealth, damage);
            Console.WriteLine($"You deal {damage} damage!");

            if (enemyHealth <= 0) break;

            // Enemy attacks
            int enemyDamage = CalculateDamage(5, 15);
            playerHealth = TakeDamage(playerHealth, enemyDamage);
            Console.WriteLine($"Enemy deals {enemyDamage} damage!");
        }

        DisplayResult(playerHealth, enemyHealth);
    }

    static int CalculateDamage(int min, int max)
    {
        return rand.Next(min, max + 1);
    }

    static int TakeDamage(int health, int damage)
    {
        return Math.Max(0, health - damage);
    }

    static void DisplayResult(int player, int enemy)
    {
        if (player > 0)
            Console.WriteLine("Victory!");
        else
            Console.WriteLine("Defeat...");
    }
}
```'''
            }
        ])
        self._create_lesson_questions(lesson2, [
            {
                'text': 'What keyword is used to send a value back from a method?',
                'choices': [('return', True), ('send', False), ('give', False), ('output', False)]
            },
            {
                'text': 'What does "void" mean for a method?',
                'choices': [('The method returns nothing', True), ('The method is empty', False), ('The method is invalid', False), ('The method has no parameters', False)]
            },
            {
                'text': 'What naming convention should methods use?',
                'choices': [('PascalCase (e.g., CalculateDamage)', True), ('camelCase', False), ('UPPER_CASE', False), ('snake_case', False)]
            },
            {
                'text': 'What is a parameter?',
                'choices': [('Data passed INTO a method when calling it', True), ('Data returned FROM a method', False), ('The name of the method', False), ('A type of variable', False)]
            },
            {
                'text': 'If a method has return type `int`, what must it return?',
                'choices': [('An integer value using the return keyword', True), ('Nothing (void)', False), ('A string', False), ('Any type of value', False)]
            }
        ])

    def _create_unit5_quiz(self, unit):
        quiz = Quiz.objects.create(
            unit=unit,
            title='Methods Quiz',
            description='Test your understanding of methods and functions.',
            passing_score=70,
            points=25,
            max_attempts=3,
            order=0
        )
        questions = [
            {
                'text': 'What is the purpose of methods?',
                'choices': [('To organize and reuse code', True), ('To store data', False), ('To create variables', False), ('To import libraries', False)]
            },
            {
                'text': 'What naming convention should methods use?',
                'choices': [('PascalCase', True), ('camelCase', False), ('UPPER_CASE', False), ('snake_case', False)]
            },
            {
                'text': 'What happens if a method has return type int but no return statement?',
                'choices': [('Compile error', True), ('Returns 0', False), ('Returns null', False), ('Runtime error', False)]
            },
        ]
        self._create_quiz_questions(quiz, questions)

    # ================== Helper Methods ==================
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
        """Create comprehension questions for a lesson."""
        for i, q in enumerate(questions_data):
            question = LessonQuestion.objects.create(
                lesson=lesson,
                text=q['text'],
                order=i
            )
            for j, (choice_text, is_correct) in enumerate(q['choices']):
                LessonQuestionChoice.objects.create(
                    question=question,
                    text=choice_text,
                    is_correct=is_correct,
                    order=j
                )

    def _create_quiz_questions(self, quiz, questions_data):
        """Create quiz questions."""
        for i, q in enumerate(questions_data):
            question = Question.objects.create(
                quiz=quiz,
                text=q['text'],
                order=i
            )
            for j, (choice_text, is_correct) in enumerate(q['choices']):
                Choice.objects.create(
                    question=question,
                    text=choice_text,
                    is_correct=is_correct,
                    order=j
                )

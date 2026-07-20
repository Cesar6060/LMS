"""
Management command to create/refresh the JAVA101 course
("Introduction to Programming with Java") with the full Java computer-science
fundamentals curriculum.

This command is NON-DESTRUCTIVE:
1. Does NOT delete or create any users
2. Does NOT touch any other course
3. Creates (or idempotently refreshes) only the JAVA101 course and its content
   (units -> lessons -> paginated sections + comprehension quizzes, plus a unit
   quiz per unit)
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from courses.models import (
    Course, Unit, Lesson, LessonSection, LessonQuestion, LessonQuestionChoice
)
from quizzes.models import Quiz, Question, Choice

User = get_user_model()


class Command(BaseCommand):
    help = 'Create or refresh the JAVA101 Java course (non-destructive; no user or other-course changes)'

    def handle(self, *args, **options):
        self.stdout.write('Populating JAVA101 course...\n')

        # Find the instructor (never modifies users)
        instructor = self._get_instructor()
        if not instructor:
            return

        # Get or create JAVA101 (touches no other course)
        course = self._get_or_update_course(instructor)

        # Clear only this course's content, then rebuild it
        self._clear_course_content(course)
        self._create_course_content(course)

        self.stdout.write(self.style.SUCCESS('\nJAVA101 population complete (non-destructive).'))

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
        """Get or create the JAVA101 course (non-destructive; no other course touched)."""
        title = 'Introduction to Programming with Java'
        description = (
            'Learn the fundamental principles of computer science in Java - '
            'variables, data types, operators, conditionals, loops, and methods. '
            'A hands-on introductory course where you write and run real code from day one.'
        )
        course, created = Course.objects.get_or_create(
            code='JAVA101',
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

Welcome to your first Java lesson! In this lesson, you'll write and run your very first program.

## Learning Objectives

By the end of this lesson, you will be able to:
- Understand the basic structure of a Java program
- Write and run a "Hello World" program
- Use `System.out.println()` and `System.out.print()` to display output
- Identify the `main` method as the program entry point

## Why This Matters

Every programmer starts with "Hello World" - it's a rite of passage! This simple program teaches you the fundamental structure that every Java program follows.'''
            },
            {
                'title': 'Introduction to Java',
                'content': '''# Welcome to Java Programming!

Java is one of the world's most widely used programming languages. It runs on billions of devices thanks to the Java Virtual Machine (JVM) - from Android phones to enterprise servers - and is a common first language for learning computer science.

## Why Learn Java?

- **Runs Everywhere**: "Write once, run anywhere" on the JVM
- **Widely Used**: Android apps, web and enterprise back-ends, and data processing
- **Job Market**: Consistently high demand for Java developers
- **Beginner Friendly**: Clear, structured syntax that's easy to read

By the end of this course, you'll be writing your own interactive programs!'''
            },
            {
                'title': 'Your First Program',
                'content': '''# Your First Java Program

Let's write the classic "Hello, World!" program:

```java
class HelloWorld
{
    public static void main(String[] args)
    {
        System.out.println("Hello, World!");
        System.out.println("This is my first Java program.");
    }
}
```

## Breaking It Down

| Code | Purpose |
|------|---------|
| `class HelloWorld` | Container for our code |
| `public static void main(String[] args)` | Entry point - where program starts |
| `System.out.println()` | Prints text to the screen |

Every Java program needs a `main` method - this is where the computer starts reading your code!'''
            },
            {
                'title': 'Console Output',
                'content': '''# Printing to the Console

There are two main ways to output text:

## System.out.println()
Prints text and moves to a **new line**:
```java
System.out.println("Line 1");
System.out.println("Line 2");
```
Output:
```
Line 1
Line 2
```

## System.out.print()
Prints text but stays on the **same line**:
```java
System.out.print("Hello ");
System.out.print("World!");
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
                'text': 'Which method is the entry point of a Java program?',
                'choices': [
                    ('main()', True),
                    ('start()', False),
                    ('begin()', False),
                    ('run()', False),
                ]
            },
            {
                'text': 'What does System.out.println() do?',
                'choices': [
                    ('Prints text and moves to a new line', True),
                    ('Prints text and stays on the same line', False),
                    ('Reads input from the user', False),
                    ('Clears the console screen', False),
                ]
            },
            {
                'text': 'What is the correct signature for the main method in Java?',
                'choices': [
                    ('public static void main(String[] args)', True),
                    ('public static void main(String args)', False),
                    ('public void main()', False),
                    ('void start(String[] args)', False),
                ]
            },
            {
                'text': 'What is the difference between System.out.println() and System.out.print()?',
                'choices': [
                    ('println adds a new line after, print stays on the same line', True),
                    ('println is faster than print', False),
                    ('print can only display numbers', False),
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
                'content': '''# Comments in Java

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
```java
// This is a single-line comment
int counter = 100;  // You can put comments at the end of lines too
```

## Multi-Line Comments
Use `/* */` for longer explanations:
```java
/*
 * This is a multi-line comment.
 * Use it for longer explanations
 * that span multiple lines.
 */
```

## Documentation Comments
Use `/** */` for documentation (advanced):
```java
/**
 * Calculates the total price.
 */
int calculateTotal() { ... }
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
```java
// BAD: Adds 1 to counter
counter = counter + 1;

// GOOD: Advance to the next page of results
counter = counter + 1;
```

Remember: Good code with good variable names often needs fewer comments!'''
            }
        ])
        self._create_lesson_questions(lesson2, [
            {
                'text': 'Which symbol starts a single-line comment in Java?',
                'choices': [
                    ('//', True),
                    ('/*', False),
                    ('#', False),
                    ('--', False),
                ]
            },
            {
                'text': 'How do you write a multi-line comment in Java?',
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

Learn how Java uses curly braces to organize code into logical sections.

## Learning Objectives

By the end of this lesson, you will be able to:
- Understand the purpose of curly braces `{ }` in Java
- Create properly nested code blocks
- Apply consistent indentation for readable code
- Recognize common bracket-related errors

## Why This Matters

Clean code organization makes programs easier to read, debug, and maintain. Proper indentation is a mark of a professional developer!'''
            },
            {
                'title': 'Understanding Code Blocks',
                'content': '''# Brackets and Code Blocks

In Java, curly braces `{ }` create **code blocks** - sections of code that belong together.

```java
class Program
{                           // Block starts
    public static void main(String[] args)
    {                       // Nested block starts
        System.out.println("Hello!");
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
```java
class Program
{
    public static void main(String[] args)
    {
        if (balance > 0)
        {
            System.out.println("Account is in credit!");
        }
    }
}
```

## Bad Indentation (Don't Do This!)
```java
class Program{
public static void main(String[] args){
if(balance>0){
System.out.println("Account is in credit!");
}}}
```

Both compile, but which would you rather debug at 2 AM?'''
            }
        ])
        self._create_lesson_questions(lesson3, [
            {
                'text': 'What do curly braces { } define in Java?',
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

Learn the standard naming rules that make Java code readable and professional.

## Learning Objectives

By the end of this lesson, you will be able to:
- Apply camelCase for variables and methods
- Apply PascalCase for classes
- Use UPPER_SNAKE_CASE for constants
- Write self-documenting code with descriptive names

## Why This Matters

Following naming conventions makes your code readable by any Java developer. It's the difference between amateur and professional code!'''
            },
            {
                'title': 'Why Naming Matters',
                'content': '''# Naming Conventions

Good names make code self-documenting. Compare:

```java
// BAD
int x = 100;
int y = 25;
int z = x - y;

// GOOD
int bankBalance = 100;
int withdrawal = 25;
int remainingBalance = bankBalance - withdrawal;
```

Which would you rather maintain?'''
            },
            {
                'title': 'Java Naming Rules',
                'content': '''# Java Naming Conventions

Java conventions are different from some other languages: methods use **camelCase**, not PascalCase.

## camelCase
For variables **and methods**:
```java
int itemCount = 0;
String userName = "Ada";
double calculateTotal() { ... }
```

## PascalCase
For class names:
```java
class BankAccount { }
class TemperatureSensor { }
```

## UPPER_SNAKE_CASE
For constants:
```java
final int MAX_SIZE = 99;
final double PI = 3.14159;
```

## Quick Reference
| Type | Convention | Example |
|------|------------|---------|
| Variable | camelCase | `userAge` |
| Method | camelCase | `calculateTotal()` |
| Class | PascalCase | `BankAccount` |
| Constant | UPPER_SNAKE_CASE | `MAX_SIZE` |'''
            }
        ])
        self._create_lesson_questions(lesson4, [
            {
                'text': 'Which naming convention should be used for variables in Java?',
                'choices': [
                    ('camelCase', True),
                    ('PascalCase', False),
                    ('UPPER_SNAKE_CASE', False),
                    ('snake_case', False),
                ]
            },
            {
                'text': 'Which naming convention should be used for methods in Java?',
                'choices': [
                    ('camelCase', True),
                    ('PascalCase', False),
                    ('UPPER_SNAKE_CASE', False),
                    ('lowercase', False),
                ]
            },
            {
                'text': 'Which naming convention should be used for class names in Java?',
                'choices': [
                    ('PascalCase', True),
                    ('camelCase', False),
                    ('UPPER_SNAKE_CASE', False),
                    ('snake_case', False),
                ]
            },
            {
                'text': 'Which variable name is INVALID in Java?',
                'choices': [
                    ('2count', True),
                    ('itemCount', False),
                    ('_balance', False),
                    ('maxSize', False),
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
            title='Program Structure Quiz',
            description='Test your knowledge of Java basics, comments, and code organization.',
            passing_score=70,
            points=20,
            max_attempts=3,
            order=0
        )
        questions = [
            {
                'text': 'What is the correct file extension for Java source files?',
                'choices': [('.java', True), ('.jv', False), ('.class', False), ('.js', False)]
            },
            {
                'text': 'Which method prints a line of text to the console in Java?',
                'choices': [('System.out.println', True), ('System.out.printLine', False), ('print()', False), ('echo', False)]
            },
            {
                'text': 'What must every Java program have as its entry point?',
                'choices': [('A public static void main(String[] args) method', True), ('A start method', False), ('A run method', False), ('A begin method', False)]
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

Learn about the different ways Java stores numbers.

## Learning Objectives

By the end of this lesson, you will be able to:
- Declare and use `int` variables for whole numbers
- Declare and use `float` and `double` for decimal numbers
- Understand when to use each number type
- Create constants using the `final` keyword

## Why This Matters

Programs are full of numbers - prices, quantities, measurements, totals. Choosing the right number type is crucial for both accuracy and performance!'''
            },
            {
                'title': 'Integer Numbers',
                'content': '''# Integer Variables (int)

Integers store **whole numbers** - no decimals allowed!

```java
// Store counts
int userAge = 15;
int quantity = 250;
int itemCount = 100;
int daysRemaining = 7;

System.out.println("Age: " + userAge);
System.out.println("Quantity: " + quantity);
System.out.println("Items: " + itemCount);
```

## Common Uses
- Counts and quantities
- Ages and years
- Index positions
- Whole-number totals

For very large whole numbers, use `long` instead of `int`.'''
            },
            {
                'title': 'Decimal Numbers',
                'content': '''# Decimal Numbers

## double - Default for Decimals
In Java, a decimal literal like `19.99` is a `double` by default.
```java
double price = 19.99;
double taxRate = 0.225;
double average = 1.5;

System.out.println("Total: " + (price * 100) + " cents");
```

## float - Less Precision (needs 'f')
A `float` literal must end with `f`, or Java treats it as a `double`.
```java
float pi = 3.14f;        // Note the 'f'!
float distance = 5.25f;
float multiplier = 2.0f;
```

## When to Use Each
| Type | Precision | Memory | Use Case |
|------|-----------|--------|----------|
| `int` | Exact | 4 bytes | Whole numbers |
| `float` | ~7 digits | 4 bytes | Memory-limited decimals |
| `double` | ~15 digits | 8 bytes | Default decimal calculations |'''
            },
            {
                'title': 'Constants',
                'content': '''# Constants (final)

Constants are values that **never change** during program execution. In Java, use the `final` keyword.

```java
final int MAX_USERS = 99;
final int MAX_ITEMS = 50;
final double TAX_RATE = 0.2;

// Using constants
int currentUsers = 15;
int usersRemaining = MAX_USERS - currentUsers;
System.out.println("Slots remaining: " + usersRemaining);
```

## Why Use Constants?
1. **Self-documenting**: `MAX_USERS` is clearer than `99`
2. **Easy updates**: Change one value, affects everywhere
3. **Prevents errors**: Can't accidentally change the value
4. **Convention**: Constant names are usually written in UPPER_CASE'''
            }
        ])
        self._create_lesson_questions(lesson1, [
            {
                'text': 'Which data type stores whole numbers without decimals?',
                'choices': [('int', True), ('float', False), ('double', False), ('String', False)]
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
                'text': 'What keyword makes a variable value unchangeable in Java?',
                'choices': [('final', True), ('static', False), ('const', False), ('fixed', False)]
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

Learn to work with text data and true/false values in Java.

## Learning Objectives

By the end of this lesson, you will be able to:
- Create and use `String` variables for text
- Concatenate (combine) strings together
- Use `boolean` variables for true/false conditions
- Apply proper variable declaration patterns

## Why This Matters

Names, messages, labels, and yes/no states - strings and booleans are everywhere in programs!'''
            },
            {
                'title': 'String Variables',
                'content': '''# Strings - Text Data

`String` (capital S) is a class, and its values use double quotes:

```java
String userName = "Alex";
String city = "Springfield";
String greeting = "Welcome to the program!";

System.out.println(userName);
System.out.println("Your city: " + city);
```

## String Concatenation
Combine strings with `+`:
```java
String firstName = "Alex";
String lastName = "Smith";
String fullName = firstName + " " + lastName;
// Result: "Alex Smith"
```

## Characters
A single character uses `char` with single quotes:
```java
char grade = 'A';
```'''
            },
            {
                'title': 'Boolean Variables',
                'content': '''# Booleans - True or False

Booleans store only two values: `true` or `false`

```java
boolean isActive = true;
boolean hasAccess = false;
boolean isValid = true;
boolean isComplete = false;

if (isActive)
{
    System.out.println("The account is active!");
}

if (!hasAccess)  // ! means "not"
{
    System.out.println("Access denied!");
}
```

## Common Uses
- Status flags (active, complete, valid)
- Feature toggles (enabled, disabled)
- Conditions (isEmpty, hasNext, isPositive)'''
            },
            {
                'title': 'Variable Declaration Patterns',
                'content': '''# Declaration Patterns

## Declare Then Assign
```java
int total;           // Declare
total = 100;         // Assign later
```

## Declare and Initialize
```java
int total = 100;     // Both at once (preferred)
```

## Multiple Variables
```java
// Same type on one line
int width = 100, height = 50, depth = 75;

// Or separately (clearer)
int width = 100;
int height = 50;
int depth = 75;
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
```java
int myInt = 10;
double myDouble = myInt;  // OK! int -> double
System.out.println(myDouble);  // 10.0
```

## Explicit Casting (Manual)
Large to small types need an explicit cast:
```java
double myDouble = 9.78;
int myInt = (int)myDouble;  // Cast with (int)
System.out.println(myInt);  // 9 (decimals lost!)
```

## Parsing Strings to Numbers
To turn text into a number, use the wrapper-class parse methods:
```java
String numberText = "42";
int number = Integer.parseInt(numberText);  // 42

String decimalText = "3.14";
double pi = Double.parseDouble(decimalText);  // 3.14
```

## Common Conversions
| From | To | Method |
|------|-----|--------|
| String | int | `Integer.parseInt(str)` |
| String | double | `Double.parseDouble(str)` |
| int | String | `String.valueOf(num)` or `Integer.toString(num)` |
| double | int | `(int)doubleValue` |

## Example
```java
// Input arrives as text
String input = "7";
int hits = Integer.parseInt(input);

// Calculate a ratio (need double for decimals)
int attempts = 10;
double accuracy = (double)hits / attempts;  // 0.7
System.out.println("Accuracy: " + (accuracy * 100) + "%");  // 70.0%
```'''
            }
        ])
        self._create_lesson_questions(lesson2, [
            {
                'text': 'What are the only two values a boolean can hold?',
                'choices': [('true and false', True), ('0 and 1', False), ('yes and no', False), ('on and off', False)]
            },
            {
                'text': 'What type of quotes does a String use?',
                'choices': [('Double quotes "text"', True), ('Single quotes \'text\'', False), ('Back ticks `text`', False), ('No quotes needed', False)]
            },
            {
                'text': 'What is the difference between String and char?',
                'choices': [('String holds multiple characters, char holds exactly one', True), ('They are the same thing', False), ('char holds numbers, String holds text', False), ('String is faster than char', False)]
            },
            {
                'text': 'Which is a valid boolean variable declaration?',
                'choices': [('boolean isActive = true;', True), ('boolean isActive = "true";', False), ('boolean isActive = 1;', False), ('Boolean isActive = True;', False)]
            },
            {
                'text': 'How do you convert a double to an int?',
                'choices': [('Use explicit cast: (int)myDouble', True), ('It converts automatically', False), ('Use Integer.parseInt()', False), ('It is not possible', False)]
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
            description='Test your knowledge of Java variables, data types, and operators.',
            passing_score=70,
            points=25,
            max_attempts=3,
            order=0
        )
        questions = [
            {
                'text': 'Which variable type would you use to store a user\'s name?',
                'choices': [('String', True), ('int', False), ('boolean', False), ('float', False)]
            },
            {
                'text': 'What is the correct way to declare a constant in Java?',
                'choices': [('final int MAX = 100;', True), ('constant int MAX = 100;', False), ('int final MAX = 100;', False), ('finalize int MAX = 100;', False)]
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
                'text': 'What does `count++` do?',
                'choices': [('Adds 1 to count', True), ('Multiplies count by 2', False), ('Sets count to 1', False), ('Does nothing', False)]
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

Learn how to perform calculations in Java using mathematical operators.

## Learning Objectives

By the end of this lesson, you will be able to:
- Use arithmetic operators: `+`, `-`, `*`, `/`, `%`
- Understand integer division behavior
- Apply the modulus operator for remainders
- Calculate values like totals, costs, and averages

## Why This Matters

Every program needs math - totals, pricing, statistics, resource management. Mastering operators is essential!'''
            },
            {
                'title': 'Basic Math Operators',
                'content': '''# Arithmetic Operators

Java supports all basic math operations:

| Operator | Name | Example |
|----------|------|---------|
| `+` | Addition | `5 + 3 = 8` |
| `-` | Subtraction | `5 - 3 = 2` |
| `*` | Multiplication | `5 * 3 = 15` |
| `/` | Division | `6 / 3 = 2` |
| `%` | Modulus (remainder) | `7 % 3 = 1` |

```java
int a = 10;
int b = 3;
System.out.println(a + b);  // 13
System.out.println(a - b);  // 7
System.out.println(a * b);  // 30
System.out.println(a / b);  // 3 (integer division!)
System.out.println(a % b);  // 1
```

## The Math Class
Java's built-in `Math` class provides helpful methods:
```java
System.out.println(Math.max(8, 3));  // 8
System.out.println(Math.abs(-5));    // 5
System.out.println(Math.pow(2, 3));  // 8.0
```'''
            },
            {
                'title': 'Practical Math Examples',
                'content': '''# Operators in Context

## Addition: Adding to a Balance
```java
int bankBalance = 50;
int deposit = 30;
int newBalance = bankBalance + deposit;
System.out.println("New balance: " + newBalance); // 80
```

## Subtraction: Applying a Cost
```java
int budget = 100;
int itemCost = 35;
int remaining = budget - itemCost;
System.out.println("Budget left: " + remaining); // 65
```

## Multiplication: Line Total
```java
int price = 25;
int quantity = 3;
int total = price * quantity;
System.out.println("Total cost: " + total); // 75
```

## Modulus: Items in the Last Row
```java
int itemCount = 17;
int itemsPerRow = 5;
int lastRowItems = itemCount % itemsPerRow;
System.out.println("Items in last row: " + lastRowItems); // 2
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

Assignment operators are used constantly in loops for updating totals, counters, and running values. They make your code shorter and clearer!'''
            },
            {
                'title': 'Compound Assignment',
                'content': '''# Assignment Operators

## Basic Assignment
```java
int total = 100;  // Assign 100 to total
```

## Compound Assignment Operators
Shorthand for common operations:

| Operator | Equivalent | Example |
|----------|------------|---------|
| `+=` | `x = x + y` | `total += 10;` |
| `-=` | `x = x - y` | `balance -= 25;` |
| `*=` | `x = x * y` | `amount *= 2;` |
| `/=` | `x = x / y` | `price /= 2;` |

```java
int total = 100;
total += 50;    // total is now 150
total -= 30;    // total is now 120
total *= 2;     // total is now 240
```'''
            },
            {
                'title': 'Increment and Decrement',
                'content': '''# Increment & Decrement

## Adding/Subtracting 1
```java
int userAge = 5;
userAge++;      // userAge is now 6 (same as userAge += 1)
userAge--;      // userAge is now 5 (same as userAge -= 1)
```

## Prefix vs Postfix
```java
int a = 5;
System.out.println(a++);  // Prints 5, THEN a becomes 6
System.out.println(++a);  // a becomes 7, THEN prints 7
```

## Common Use: Loops
```java
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
                'text': 'What does `count++` do?',
                'choices': [('Adds 1 to count', True), ('Multiplies count by 2', False), ('Sets count to 1', False), ('Subtracts 1 from count', False)]
            },
            {
                'text': 'If x = 5, what does `System.out.println(x++)` print?',
                'choices': [('5 (prints first, then increments)', True), ('6', False), ('4', False), ('Error', False)]
            },
            {
                'text': 'If x = 5, what does `System.out.println(++x)` print?',
                'choices': [('6 (increments first, then prints)', True), ('5', False), ('4', False), ('Error', False)]
            },
            {
                'text': 'What is `balance -= 25` equivalent to?',
                'choices': [('balance = balance - 25', True), ('balance = 25', False), ('balance = balance + 25', False), ('balance == 25', False)]
            }
        ])

    # ================== UNIT 3: Strings & User Input ==================
    def _create_unit3_text_lessons(self, unit):
        lesson1 = Lesson.objects.create(
            unit=unit, title='Formatting Text', order=0, max_quiz_attempts=3
        )
        self._create_sections(lesson1, [
            {
                'title': 'Overview',
                'content': '''# Formatting Text

Learn how to combine variables with text and format your output cleanly in Java.

## Learning Objectives

By the end of this lesson, you will be able to:
- Combine text and variables with concatenation (`+`)
- Build formatted strings with `String.format`
- Print formatted output with `System.out.printf`
- Format numbers with a fixed number of decimal places

## Why This Matters

Programs constantly display text built from data - totals, messages, reports. Java has no special syntax for embedding variables inside a string, so knowing concatenation and `String.format` is essential.'''
            },
            {
                'title': 'Combining Text with Concatenation',
                'content': '''# Concatenation

The simplest way to combine text and variables in Java is the `+` operator.

## Basic Concatenation
```java
String name = "Ada";
int age = 25;
System.out.println("Name: " + name + " Age: " + age);
```

Output: `Name: Ada Age: 25`

## Watch the Spacing
You are responsible for the spaces inside the quotes:
```java
String city = "Paris";
System.out.println("City: " + city);  // City: Paris
```

## You Can Include Expressions
```java
int total = 20;
System.out.println("Double: " + (total * 2));  // Double: 40
```

Wrap math in parentheses so Java does the arithmetic before joining the text.'''
            },
            {
                'title': 'Formatting with String.format and printf',
                'content': '''# String.format and printf

When you need cleaner output or number formatting, use `String.format` or `System.out.printf`. Both use **placeholders** in the text.

## String.format
Builds a `String` you can store or print:
```java
String name = "Ada";
int age = 25;
String message = String.format("Name: %s, Age: %d", name, age);
System.out.println(message);  // Name: Ada, Age: 25
```

## System.out.printf
Prints directly. Use `%n` for a new line:
```java
String name = "Ada";
System.out.printf("Hello %s%n", name);  // Hello Ada
```

## Decimal Places
`%.2f` prints a decimal rounded to 2 places:
```java
double price = 19.999;
System.out.printf("Price: %.2f%n", price);  // Price: 20.00
```

## Common Format Specifiers
| Specifier | Use For | Example |
|-----------|---------|---------|
| `%s` | String | `"Ada"` |
| `%d` | Whole number (int) | `25` |
| `%.2f` | Decimal, 2 places | `3.14` |
| `%n` | New line | (line break) |'''
            }
        ])
        self._create_lesson_questions(lesson1, [
            {
                'text': 'Which operator combines text and variables directly in Java?',
                'choices': [('+', True), ('%', False), ('&', False), ('.', False)]
            },
            {
                'text': 'Given `String name = "Ada";`, what does `String.format("Hi %s", name)` produce?',
                'choices': [('"Hi Ada"', True), ('"Hi %s"', False), ('"Hi {name}"', False), ('Error', False)]
            },
            {
                'text': 'In `String.format`, which specifier inserts a whole number (int)?',
                'choices': [('%d', True), ('%s', False), ('%i', False), ('%n', False)]
            },
            {
                'text': 'What does `System.out.printf("Price: %.2f%n", 3.14159)` print?',
                'choices': [('Price: 3.14', True), ('Price: 3.14159', False), ('Price: 3', False), ('Price: %.2f', False)]
            }
        ])

        lesson2 = Lesson.objects.create(
            unit=unit, title='String Methods', order=1, max_quiz_attempts=3
        )
        self._create_sections(lesson2, [
            {
                'title': 'Overview',
                'content': '''# String Methods

Learn powerful built-in operations for inspecting and transforming text.

## Learning Objectives

By the end of this lesson, you will be able to:
- Use String methods: `toUpperCase()`, `toLowerCase()`, `length()`, `contains()`
- Get a string's length with the `length()` method (note the parentheses)
- Compare strings correctly with `equals()`
- Search and transform text

## Why This Matters

Real programs constantly process text - names, emails, messages. Java's `String` class provides methods for almost anything you need to do with text.'''
            },
            {
                'title': 'Common String Methods',
                'content': '''# String Methods

## Changing Case
```java
String name = "Ada";
System.out.println(name.toUpperCase());  // ADA
System.out.println(name.toLowerCase());  // ada
```

## Length is a METHOD in Java
In Java, `length()` is a method - you must use parentheses:
```java
String message = "Hello World";
System.out.println(message.length());  // 11
```

## Finding Content
```java
String text = "Welcome Back";
System.out.println(text.contains("Back"));       // true
System.out.println(text.startsWith("Welcome"));  // true
System.out.println(text.endsWith("!"));          // false
```

## Transforming Text
```java
String raw = "  hello  ";
System.out.println(raw.trim());                  // "hello"
System.out.println("cat".replace("c", "b"));     // "bat"
System.out.println("Hello".substring(0, 3));     // "Hel"
```'''
            },
            {
                'title': 'Comparing Strings',
                'content': '''# Comparing Strings

To check if two strings have the same text, use `.equals()` - NOT `==`.

## Use equals()
```java
String input = "yes";
System.out.println(input.equals("yes"));  // true
```

## Why Not ==
In Java, `==` compares whether two variables point to the same object in memory, not whether the text matches. For text equality, always use `.equals()`:
```java
String a = "hello";
String b = "hello";
System.out.println(a.equals(b));  // true - compares the text
```

## Ignoring Case
```java
String answer = "YES";
System.out.println(answer.equalsIgnoreCase("yes"));  // true
```'''
            },
        ])
        self._create_lesson_questions(lesson2, [
            {
                'text': 'In Java, how do you get the number of characters in a String named text?',
                'choices': [('text.length()', True), ('text.length', False), ('text.size()', False), ('length(text)', False)]
            },
            {
                'text': 'What does "ada".toUpperCase() return?',
                'choices': [('"ADA"', True), ('"Ada"', False), ('"ada"', False), ('Error', False)]
            },
            {
                'text': 'What does "Welcome Back".contains("Back") return?',
                'choices': [('true', True), ('false', False), ('"Back"', False), ('8', False)]
            },
            {
                'text': 'Which is the correct way to check if two Strings have the same text?',
                'choices': [('a.equals(b)', True), ('a == b', False), ('a.compare(b)', False), ('a.same(b)', False)]
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

Learn how to make your programs interactive by reading input from users with `Scanner`.

## Learning Objectives

By the end of this lesson, you will be able to:
- Import and create a `Scanner` to read input
- Read text with `nextLine()` and numbers with `nextInt()` / `nextDouble()`
- Convert text to numbers with `Integer.parseInt()`
- Build simple interactive programs

## Why This Matters

Interactive programs need input! From entering a user name to making menu choices, reading input is what makes a program respond to the person using it.'''
            },
            {
                'title': 'Reading Input with Scanner',
                'content': '''# Reading Text Input

Java reads console input with a `Scanner`. First, import it at the top of your file:

```java
import java.util.Scanner;
```

Then create a `Scanner` connected to `System.in` and call `nextLine()`:

```java
Scanner scanner = new Scanner(System.in);

System.out.print("Enter your name: ");
String userName = scanner.nextLine();
System.out.println("Hello, " + userName + "!");
```

Output:
```
Enter your name: Alex
Hello, Alex!
```

## print vs println
- `System.out.print()` - stays on the same line (great for prompts)
- `System.out.println()` - moves to the next line

```java
System.out.print("Name: ");        // Cursor stays after "Name: "
String name = scanner.nextLine();
System.out.println("Done!");       // Moves to a new line
```'''
            },
            {
                'title': 'Reading Numbers',
                'content': '''# Reading Numbers

A `Scanner` can read numbers directly, or you can convert text yourself.

## Reading Numbers Directly
```java
Scanner scanner = new Scanner(System.in);

System.out.print("Enter your age: ");
int age = scanner.nextInt();

System.out.print("Enter a price: ");
double price = scanner.nextDouble();
```

## Common Scanner Methods
| Method | Reads |
|--------|-------|
| `nextLine()` | A full line of text (String) |
| `nextInt()` | A whole number (int) |
| `nextDouble()` | A decimal number (double) |

## Converting Text to Numbers
If you read a line as text, convert it with `Integer.parseInt`:
```java
System.out.print("Enter your age: ");
String input = scanner.nextLine();
int age = Integer.parseInt(input);  // Convert "25" to 25
```

`Double.parseDouble` works the same way for decimals.'''
            },
            {
                'title': 'Handling Invalid Input',
                'content': '''# Handling Invalid Input

`Integer.parseInt` throws an error if the text is not a valid number:
```java
int num = Integer.parseInt("hello");  // Error! "hello" isn't a number
```

## Checking Before You Read
Use `hasNextInt()` to check whether the next value is a valid integer before reading it:
```java
Scanner scanner = new Scanner(System.in);
System.out.print("Enter a number: ");

if (scanner.hasNextInt()) {
    int number = scanner.nextInt();
    System.out.println("You entered: " + number);
} else {
    System.out.println("That's not a valid number!");
}
```

## How hasNextInt Works
- Returns `true` if the next input is a valid integer
- Returns `false` otherwise (so you can handle it without crashing)
- Only reads the value after you confirm it is safe'''
            },
            {
                'title': 'Interactive Examples',
                'content': '''# Interactive Examples

## Registration Form
```java
import java.util.Scanner;

Scanner scanner = new Scanner(System.in);
System.out.println("=== REGISTRATION ===");

System.out.print("Enter your name: ");
String name = scanner.nextLine();

System.out.print("Enter your age: ");
int age = Integer.parseInt(scanner.nextLine());

System.out.print("Enter your city: ");
String city = scanner.nextLine().toLowerCase();

System.out.printf("Welcome %s, age %d, from %s!%n", name, age, city);
```

## Menu Selection
```java
Scanner scanner = new Scanner(System.in);
System.out.println("1. View Profile");
System.out.println("2. Settings");
System.out.println("3. Exit");
System.out.print("Choose: ");

if (scanner.hasNextInt()) {
    int menuChoice = scanner.nextInt();
    switch (menuChoice) {
        case 1: System.out.println("Opening profile..."); break;
        case 2: System.out.println("Opening settings..."); break;
        case 3: System.out.println("Goodbye!"); break;
        default: System.out.println("Invalid choice!"); break;
    }
} else {
    System.out.println("Please enter a number!");
}
```

## Yes/No Confirmation
```java
Scanner scanner = new Scanner(System.in);
System.out.print("Are you sure? (y/n): ");
String answer = scanner.nextLine().toLowerCase();

if (answer.equals("y") || answer.equals("yes")) {
    System.out.println("Confirmed!");
} else {
    System.out.println("Cancelled.");
}
```'''
            }
        ])
        self._create_lesson_questions(lesson3, [
            {
                'text': 'Which class does Java use to read input from the console?',
                'choices': [('Scanner', True), ('Reader', False), ('Input', False), ('Console', False)]
            },
            {
                'text': 'Which import is needed to use Scanner?',
                'choices': [('import java.util.Scanner;', True), ('import java.io.Scanner;', False), ('import java.lang.Scanner;', False), ('No import is needed', False)]
            },
            {
                'text': 'Which Scanner method reads a full line of text?',
                'choices': [('nextLine()', True), ('readLine()', False), ('getLine()', False), ('nextText()', False)]
            },
            {
                'text': 'How do you convert the String "42" to an integer in Java?',
                'choices': [('Integer.parseInt("42")', True), ('(int)"42"', False), ('"42".toInt()', False), ('int.parse("42")', False)]
            },
            {
                'text': 'How can you check if the next input is a valid integer before reading it?',
                'choices': [('scanner.hasNextInt()', True), ('scanner.isInt()', False), ('scanner.checkInt()', False), ('scanner.nextInt()', False)]
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
                'text': 'In Java, what does "Hello".length() return?',
                'choices': [('5', True), ('4', False), ('6', False), ('"Hello"', False)]
            },
            {
                'text': 'How do you convert the String "42" to an integer in Java?',
                'choices': [('Integer.parseInt("42")', True), ('(int)"42"', False), ('"42".toInt()', False), ('int.parse("42")', False)]
            },
            {
                'text': 'Which expression builds a formatted String in Java?',
                'choices': [('String.format("Hi %s", name)', True), ('format("Hi %s", name)', False), ('"Hi " % name', False), ('"Hi " . name', False)]
            },
            {
                'text': 'Which class reads user input from the console in Java?',
                'choices': [('Scanner', True), ('Reader', False), ('Console', False), ('Input', False)]
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

Learn to compare values - the foundation of all program logic and decisions.

## Learning Objectives

By the end of this lesson, you will be able to:
- Use comparison operators: `==`, `!=`, `>`, `<`, `>=`, `<=`
- Understand that comparisons return boolean values
- Compare numbers, strings, and other values
- Build conditions for program logic

## Why This Matters

Every decision a program makes requires comparisons - Is the temperature below freezing? Is the grade high enough to pass? Comparisons are everywhere!'''
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

```java
int temperature = 25;
int maxTemperature = 100;

System.out.println(temperature < 30);            // true
System.out.println(temperature == 25);           // true
System.out.println(temperature >= maxTemperature); // false
```

## Comparing Strings

For numbers use `==`, but to compare `String` values use `.equals()`:

```java
String name = "Alice";
System.out.println(name.equals("Alice"));  // true
System.out.println(name == "Alice");       // avoid - compares references, not the text
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

Conditionals are the brain of your program! Every input check, every rule, every automated decision uses if statements.'''
            },
            {
                'title': 'Basic If Statements',
                'content': '''# If Statements

Execute code only when a condition is true:

```java
int total = 50;
boolean isMember = true;

if (isMember)
{
    total = total + 100;
    System.out.println("Member bonus! +100 points!");
}
System.out.println("Total points: " + total);
```

## Example: Low Temperature Warning
```java
int temperature = 20;

if (temperature < 30)
{
    System.out.println("WARNING: Low temperature!");
}
```'''
            },
            {
                'title': 'If-Else Statements',
                'content': '''# If-Else

Choose between two options:

```java
int grade = 75;

if (grade >= 60)
{
    System.out.println("You passed!");
}
else
{
    System.out.println("Try again.");
}
```

## Example: Check a Limit
```java
int count = 5;

if (count < 10)
{
    System.out.println("Below the limit.");
}
else
{
    System.out.println("Limit reached.");
}
```'''
            },
            {
                'title': 'Else-If Chains',
                'content': '''# Else-If Chains

Handle multiple conditions:

```java
int grade = 85;

if (grade >= 90)
{
    System.out.println("Grade: A");
}
else if (grade >= 80)
{
    System.out.println("Grade: B");
}
else if (grade >= 70)
{
    System.out.println("Grade: C");
}
else
{
    System.out.println("Grade: F");
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

```java
int balance = 50;
boolean hasAccount = true;
boolean isFrozen = false;
boolean hasKey = false;

// AND - both must be true
if (balance >= 20 && hasAccount)
{
    System.out.println("You can make a purchase!");
}

// OR - either can be true
if (balance <= 0 || isFrozen)
{
    System.out.println("Cannot withdraw!");
}

// NOT - reverses the condition
if (!hasKey)
{
    System.out.println("You need a key!");
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

Learn a cleaner way to handle multiple conditions - perfect for menus and program states!

## Learning Objectives

By the end of this lesson, you will be able to:
- Use `switch` statements for multi-way branching
- Write `case` labels and `default` handlers
- Understand when switch is better than if-else chains
- Create menus and state machines

## Why This Matters

Menu selections, command handling, category lookups - switch statements handle these choices elegantly without messy if-else chains!'''
            },
            {
                'title': 'Switch Syntax',
                'content': '''# Switch Statement

Compare one value against many cases:

```java
int dayNumber = 3;

switch (dayNumber)
{
    case 1:
        System.out.println("Monday");
        break;
    case 2:
        System.out.println("Tuesday");
        break;
    case 3:
        System.out.println("Wednesday");
        break;
    default:
        System.out.println("Unknown day");
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
```java
// If-else chain (harder to read)
if (choice == 1) { showProfile(); }
else if (choice == 2) { showSettings(); }
else if (choice == 3) { showHelp(); }
else if (choice == 4) { logOut(); }
else { System.out.println("Invalid"); }

// Switch (cleaner!)
switch (choice)
{
    case 1: showProfile(); break;
    case 2: showSettings(); break;
    case 3: showHelp(); break;
    case 4: logOut(); break;
    default: System.out.println("Invalid"); break;
}
```'''
            },
            {
                'title': 'Switch Examples',
                'content': '''# Switch in Action

## Menu Selection
```java
import java.util.Scanner;

Scanner scanner = new Scanner(System.in);
System.out.println("Choose an option:");
System.out.println("1. New  2. Open  3. Save");
int menuChoice = scanner.nextInt();

switch (menuChoice)
{
    case 1:
        System.out.println("Creating a new file...");
        System.out.println("Starting from scratch");
        break;
    case 2:
        System.out.println("Opening a file...");
        System.out.println("Choose from recent files");
        break;
    case 3:
        System.out.println("Saving your work...");
        System.out.println("File saved");
        break;
    default:
        System.out.println("Invalid choice!");
        break;
}
```

## Program State Machine
```java
String programState = "running";

switch (programState)
{
    case "menu":
        showMainMenu();
        break;
    case "running":
        updateProgram();
        break;
    case "paused":
        showPauseMenu();
        break;
    case "stopped":
        showSummary();
        break;
}
```

## Grade Message
```java
char grade = 'B';

switch (grade)
{
    case 'A':
        System.out.println("Excellent!");
        break;
    case 'B':
        System.out.println("Good job!");
        break;
    case 'C':
        System.out.println("You passed.");
        break;
    case 'D':
    case 'F':
        System.out.println("Need improvement.");
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
                'choices': [('while loop', True), ('for loop', False), ('for-each loop', False), ('None of these', False)]
            },
            {
                'text': 'What does "break" do inside a loop?',
                'choices': [('Exits the loop immediately', True), ('Skips one iteration', False), ('Pauses the loop', False), ('Restarts the loop', False)]
            },
            {
                'text': 'Which loop automatically handles indexing through a collection?',
                'choices': [('the for-each (enhanced for) loop', True), ('while', False), ('a counting for loop', False), ('do-while', False)]
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

Learn to repeat code as long as a condition is true - a fundamental building block!

## Learning Objectives

By the end of this lesson, you will be able to:
- Create `while` loops that repeat based on a condition
- Avoid infinite loops with proper exit conditions
- Use loop control statements: `break` and `continue`
- Implement countdown timers and input validation

## Why This Matters

Many programs repeat work - reading input until it is valid, processing data until it is done, counting down a timer. Understanding while loops is crucial for creating dynamic programs!'''
            },
            {
                'title': 'Basic While Loop',
                'content': '''# While Loop Syntax

A while loop repeats code **while** a condition is true:

```java
int count = 0;

while (count < 5)
{
    System.out.println("Count: " + count);
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
                'title': 'While Loop Examples',
                'content': '''# While Loops in Action

## Countdown Timer
```java
int countdown = 10;

while (countdown > 0)
{
    System.out.println("Starting in " + countdown + "...");
    countdown--;
}
System.out.println("GO!");
```

## Filling a Balance
```java
int balance = 50;
int target = 100;

while (balance < target)
{
    balance += 5;  // Add 5 each step
    System.out.println("Balance: " + balance + "/" + target);
}
System.out.println("Target reached!");
```

## Input Validation (Keep Asking Until Valid)
```java
import java.util.Scanner;

Scanner scanner = new Scanner(System.in);
String password = "";

while (!password.equals("secret123"))
{
    System.out.print("Enter password: ");
    password = scanner.nextLine();
}
System.out.println("Access granted!");
```'''
            },
            {
                'title': 'Break and Continue',
                'content': '''# Loop Control

## break - Exit the loop immediately
```java
int number = 100;

while (true)  // Infinite loop!
{
    number -= 10;
    System.out.println("Number: " + number);

    if (number <= 0)
    {
        System.out.println("Done!");
        break;  // Exit the loop
    }
}
```

## continue - Skip to next iteration
```java
int i = 0;

while (i < 10)
{
    i++;

    if (i % 2 == 0)
    {
        continue;  // Skip even numbers
    }

    System.out.println(i);  // Only prints odd: 1, 3, 5, 7, 9
}
```

## Warning: Infinite Loops!
```java
// DANGER - This never ends!
while (true)
{
    System.out.println("Forever...");
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

For loops are the workhorses of programming. Processing lists of data, repeating a task a set number of times, building tables - for loops handle it all!'''
            },
            {
                'title': 'For Loop Syntax',
                'content': '''# For Loop Structure

```java
for (int i = 0; i < 5; i++)
{
    System.out.println("Iteration " + i);
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
```java
for (int i = 0; i < 10; i++)
{
    System.out.println(i);
}
```

## Count Down (10 to 1)
```java
for (int i = 10; i > 0; i--)
{
    System.out.println(i);
}
System.out.println("Blast off!");
```

## Count by 2s (Even Numbers)
```java
for (int i = 0; i <= 10; i += 2)
{
    System.out.println(i);  // 0, 2, 4, 6, 8, 10
}
```

## Start at Different Number
```java
for (int i = 5; i <= 15; i++)
{
    System.out.println(i);  // 5, 6, 7... 15
}
```'''
            },
            {
                'title': 'For Loop Examples',
                'content': '''# For Loops in Action

## Repeat a Task 5 Times
```java
for (int i = 0; i < 5; i++)
{
    System.out.println("Processing item #" + (i + 1));
}
```

## Display a List
```java
String[] items = {"Pen", "Notebook", "Eraser"};

for (int i = 0; i < items.length; i++)
{
    System.out.println((i + 1) + ". " + items[i]);
}
```

## Draw a Progress Bar
```java
int progress = 7;
int total = 10;

System.out.print("Progress: [");
for (int i = 0; i < total; i++)
{
    if (i < progress)
        System.out.print("#");
    else
        System.out.print("-");
}
System.out.println("]");
// Output: Progress: [#######---]
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
- Create tables and grids

## Why This Matters

Grids are everywhere in programming! Spreadsheets, image pixels, tables of data - nested loops create all of these structures.'''
            },
            {
                'title': 'Understanding Nested Loops',
                'content': '''# Loops Inside Loops

The inner loop runs completely for EACH iteration of the outer loop:

```java
for (int i = 0; i < 3; i++)       // Outer: rows
{
    for (int j = 0; j < 4; j++)   // Inner: columns
    {
        System.out.print("* ");
    }
    System.out.println();  // New line after each row
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
```java
for (int i = 1; i <= 5; i++)
{
    for (int j = 1; j <= 5; j++)
    {
        System.out.printf("%4d", i * j);
    }
    System.out.println();
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

## Checkerboard Pattern
```java
for (int row = 0; row < 8; row++)
{
    for (int col = 0; col < 8; col++)
    {
        if ((row + col) % 2 == 0)
            System.out.print("[] ");
        else
            System.out.print("## ");
    }
    System.out.println();
}
```

## Coordinate Grid
```java
for (int y = 0; y < 3; y++)
{
    for (int x = 0; x < 3; x++)
    {
        System.out.print("(" + x + "," + y + ") ");
    }
    System.out.println();
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

        # Lesson 7: For-Each Loops (Enhanced For)
        lesson7 = Lesson.objects.create(
            unit=unit, title='For-Each Loops (Enhanced For)', order=6, max_quiz_attempts=3
        )
        self._create_sections(lesson7, [
            {
                'title': 'Overview',
                'content': '''# For-Each Loops (Enhanced For)

Discover the cleanest way to loop through collections - no index needed!

## Learning Objectives

By the end of this lesson, you will be able to:
- Use the enhanced `for` loop to iterate through arrays and collections
- Understand when for-each is better than a counting for loop
- Process each item without managing an index
- Work with different collection types

## Why This Matters

Most data lives in collections - lists of names, sets of numbers, records. The for-each loop makes processing these collections simple and readable!'''
            },
            {
                'title': 'For-Each Syntax',
                'content': '''# For-Each Loop (Enhanced For)

Process each item without managing an index:

```java
String[] fruits = {"Apple", "Banana", "Cherry", "Date"};

for (String fruit : fruits)
{
    System.out.println("Item: " + fruit);
}
```

Output:
```
Item: Apple
Item: Banana
Item: Cherry
Item: Date
```

## Syntax Breakdown
```java
for (type variableName : collection)
{
    // Use variableName
}
```

- `type` - The type of items in the collection
- `variableName` - Name for current item
- `collection` - The array/list to loop through
- The colon `:` reads as "in" - "for each item in the collection"'''
            },
            {
                'title': 'For-Each vs Counting For',
                'content': '''# When to Use Each

## Use the for-each loop when:
- You need every item
- You don't need the index
- You want cleaner code

```java
// Clean and simple
for (String item : inventory)
{
    System.out.println(item);
}
```

## Use a counting for loop when:
- You need the index
- You need to modify the array
- You need to skip/select certain indices

```java
// Need index for numbering
for (int i = 0; i < inventory.length; i++)
{
    System.out.println((i + 1) + ". " + inventory[i]);
}
```

## Examples
```java
// Add up all the numbers
int total = 0;
int[] numbers = {10, 25, 15, 30};

for (int number : numbers)
{
    total += number;
}
System.out.println("Total: " + total);

// Print all valid names
String[] names = {"Alice", "N/A", "Bob", "N/A", "Carol"};

for (String name : names)
{
    if (!name.equals("N/A"))
    {
        System.out.println(name + " is valid!");
    }
}
```'''
            }
        ])
        self._create_lesson_questions(lesson7, [
            {
                'text': 'What is the main advantage of the for-each loop over a counting for loop?',
                'choices': [
                    ('Cleaner syntax - no index management needed', True),
                    ('Runs faster', False),
                    ('Can modify the array', False),
                    ('Works with more data types', False)
                ]
            },
            {
                'text': 'When should you use a counting for loop instead of a for-each loop?',
                'choices': [
                    ('When you need the index or need to modify items', True),
                    ('When you have a string array', False),
                    ('When you want cleaner code', False),
                    ('Always - the counting for loop is always better', False)
                ]
            },
            {
                'text': 'In `for (int num : numbers)`, what does `num` represent?',
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

Discover powerful pre-built methods that Java provides for math, text, and randomness.

## Learning Objectives

By the end of this lesson, you will be able to:
- Use `Math` methods: `max()`, `min()`, `abs()`, `pow()`, `sqrt()`, `round()`
- Use common `String` methods like `toUpperCase()`, `length()`, and `substring()`
- Generate random numbers with `Math.random()`
- Understand how built-in methods save you time

## Why This Matters

Don't reinvent the wheel! Java provides hundreds of useful methods. Learning to use them makes you a more efficient programmer.'''
            },
            {
                'title': 'Math Methods',
                'content': '''# Built-in Math Methods

Java's `Math` class includes many useful methods (note the lowercase method names):

```java
// Find the larger/smaller value
int max = Math.max(10, 20);    // 20
int min = Math.min(10, 20);    // 10

// Absolute value (removes negative)
int abs = Math.abs(-15);       // 15

// Power (exponent)
double power = Math.pow(2, 3); // 8.0

// Square root
double sqrt = Math.sqrt(16);   // 4.0

// Round numbers
long rounded = Math.round(3.7);   // 4
int floor = (int) Math.floor(3.9);   // 3
int ceiling = (int) Math.ceil(3.1);  // 4
```'''
            },
            {
                'title': 'String Methods',
                'content': '''# Built-in String Methods

Java `String` objects come with handy built-in methods:

```java
String name = "Ada Lovelace";

// Number of characters
int length = name.length();          // 12

// Change case
String upper = name.toUpperCase();   // "ADA LOVELACE"
String lower = name.toLowerCase();   // "ada lovelace"

// Extract part of the text
String first = name.substring(0, 3); // "Ada"

// Convert text to a number
int count = Integer.parseInt("42");        // 42
double price = Double.parseDouble("9.99"); // 9.99
```'''
            },
            {
                'title': 'Random Numbers',
                'content': '''# Generating Random Numbers

`Math.random()` returns a `double` from 0.0 (inclusive) to 1.0 (exclusive):

```java
// Random double from 0.0 to 1.0
double chance = Math.random();

// Random int from 1 to 10
int roll = (int) (Math.random() * 10) + 1;

// Random int from 0 to 99
int percent = (int) (Math.random() * 100);
```

## Common Examples
```java
// Simulate a coin flip
if (Math.random() < 0.5) {
    System.out.println("Heads");
} else {
    System.out.println("Tails");
}

// Random number between 10 and 20 (inclusive)
int value = (int) (Math.random() * 11) + 10;
```'''
            }
        ])
        self._create_lesson_questions(lesson1, [
            {
                'text': 'What does Math.max(5, 10) return?',
                'choices': [('10 (the larger value)', True), ('5', False), ('15', False), ('50', False)]
            },
            {
                'text': 'What does Math.min(5, 10) return?',
                'choices': [('5 (the smaller value)', True), ('10', False), ('15', False), ('-5', False)]
            },
            {
                'text': 'What does Math.abs(-15) return?',
                'choices': [('15 (absolute value removes negative)', True), ('-15', False), ('0', False), ('Error', False)]
            },
            {
                'text': 'What does "Java".length() return?',
                'choices': [('4', True), ('3', False), ('5', False), ('"Java"', False)]
            },
            {
                'text': 'What does Math.random() return?',
                'choices': [('A double from 0.0 (inclusive) to 1.0 (exclusive)', True), ('An integer from 0 to 100', False), ('A double from 1.0 to 10.0', False), ('A random whole number of any size', False)]
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

Methods are the building blocks of professional software. Every program feature - calculations, formatting, validation - is built from well-organized methods!'''
            },
            {
                'title': 'Basic Methods',
                'content': '''# Creating Methods

Methods are reusable blocks of code. In Java they live inside a class:

```java
public class Program {
    public static void main(String[] args) {
        printGreeting();  // Call the method
        printGreeting();  // Call it again!
    }

    public static void printGreeting() {
        System.out.println("Hello, world!");
    }
}
```

## Anatomy of a Method
```java
public static void methodName() {
    // Code goes here
}
```
- `public static` - beginner methods belong to the class
- `void` - returns nothing
- `methodName` - use camelCase!'''
            },
            {
                'title': 'Methods with Parameters',
                'content': '''# Parameters

Pass data into methods:

```java
public static void main(String[] args) {
    printGreeting("Ada");
    printGreeting("Grace");
    printLabel("Total", 25);
}

public static void printGreeting(String name) {
    System.out.println("Hello, " + name + "!");
}

public static void printLabel(String label, int value) {
    System.out.println(label + ": " + value);
}
```

Output:
```
Hello, Ada!
Hello, Grace!
Total: 25
```

The values you pass in (`"Ada"`, `25`) are called **arguments**. The variables that receive them (`name`, `value`) are the method's **parameters**.'''
            },
            {
                'title': 'Return Values',
                'content': '''# Methods with Return Values

Methods can send data back:

```java
public static void main(String[] args) {
    int total = addNumbers(5, 3);
    System.out.println(total);  // 8

    int price = applyDiscount(100, 0.25);
    System.out.println("Price: " + price);
}

public static int addNumbers(int a, int b) {
    return a + b;
}

public static int applyDiscount(int amount, double rate) {
    return (int) (amount * (1 - rate));
}
```

## Key Points
- Replace `void` with the return type (`int`, `String`, etc.)
- Use `return` to send the value back
- The method call becomes that value'''
            },
            {
                'title': 'Putting It All Together',
                'content': '''# Complete Example: Receipt Calculator

```java
public class ReceiptCalculator {
    public static void main(String[] args) {
        int subtotal = addNumbers(1200, 850);
        int tax = calculateTax(subtotal, 0.08);
        int total = addNumbers(subtotal, tax);

        printReceipt(subtotal, tax, total);
    }

    public static int addNumbers(int a, int b) {
        return a + b;
    }

    public static int calculateTax(int amount, double rate) {
        return (int) (amount * rate);
    }

    public static void printReceipt(int subtotal, int tax, int total) {
        System.out.println("Subtotal: " + subtotal);
        System.out.println("Tax:      " + tax);
        System.out.println("Total:    " + total);
    }
}
```

Each method does one job: `addNumbers` and `calculateTax` return values, while `printReceipt` performs an action and returns nothing (`void`).'''
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
                'text': 'What naming convention should Java methods use?',
                'choices': [('camelCase (e.g., calculateTax)', True), ('PascalCase', False), ('UPPER_CASE', False), ('snake_case', False)]
            },
            {
                'text': 'What is a parameter?',
                'choices': [('Data passed INTO a method when calling it', True), ('Data returned FROM a method', False), ('The name of the method', False), ('A type of variable', False)]
            },
            {
                'text': 'If a method has return type `int`, what must it return?',
                'choices': [('An integer value using the return keyword', True), ('Nothing (void)', False), ('A String', False), ('Any type of value', False)]
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
                'text': 'What naming convention should Java methods use?',
                'choices': [('camelCase', True), ('PascalCase', False), ('UPPER_CASE', False), ('snake_case', False)]
            },
            {
                'text': 'Which is a correct method declaration in Java?',
                'choices': [('public static int addNumbers(int a, int b)', True), ('public static addNumbers(int a, int b) int', False), ('static void addNumbers[int a, int b]', False), ('function addNumbers(int a, int b)', False)]
            },
            {
                'text': 'What is the difference between a parameter and an argument?',
                'choices': [('A parameter is the variable in the method definition; an argument is the value passed in when calling it', True), ('They are two words for exactly the same thing', False), ('A parameter is passed in; an argument is the return value', False), ('An argument must always be an int, a parameter can be any type', False)]
            },
            {
                'text': 'What does the return type void mean?',
                'choices': [('The method does not return any value', True), ('The method returns an empty String', False), ('The method returns 0', False), ('The method cannot take parameters', False)]
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

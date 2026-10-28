"""SQLite schema and migration helpers for the LearnHub browser application."""
from __future__ import annotations

import re
import math
import secrets
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB_FILE = ROOT / "learnhub.db"
LEGACY_DB_FILE = ROOT / "learnsphere.db"
SCHEMA_FILE = ROOT / "schema.sql"


def connect():
    db = sqlite3.connect(DB_FILE)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


def grade_assignment_submission(instructor_id: int, submission_id: int, score: float, feedback: str):
    """Save a grade only when the assignment belongs to this instructor's course."""
    feedback = (feedback or "").strip()
    if not feedback:
        raise ValueError("Enter feedback before saving the grade.")
    if len(feedback) > 2000:
        raise ValueError("Feedback must be 2,000 characters or fewer.")
    if not math.isfinite(score):
        raise ValueError("Enter a finite mark.")
    with connect() as db:
        submission = db.execute("""SELECT s.submission_id,a.max_marks
            FROM Submission s JOIN Assignment a ON a.assignment_id=s.assignment_id
            JOIN Course c ON c.course_id=a.course_id
            WHERE s.submission_id=? AND c.instructor_id=?""",
                                (submission_id,instructor_id)).fetchone()
        if not submission:
            raise LookupError("Assignment submission not found for your courses.")
        if score < 0 or score > submission["max_marks"]:
            raise ValueError(f"Enter a mark between 0 and {submission['max_marks']}.")
        db.execute("""UPDATE Submission
            SET score=?,feedback=?,graded_at=DATE('now') WHERE submission_id=?""",
                   (score,feedback,submission_id))
    return score


def _weeks(duration: str) -> int:
    match = re.search(r"\d+", duration or "")
    return max(1, int(match.group()) if match else 4)


def _migrate_quiz_questions(db):
    """Apply a follow-up migration for quiz banks added after the first schema migration."""
    if db.execute("SELECT 1 FROM web_migrations WHERE name='chapter3_quiz_questions_v1'").fetchone():
        return
    if LEGACY_DB_FILE.exists():
        source = sqlite3.connect(LEGACY_DB_FILE)
        source.row_factory = sqlite3.Row
        try:
            if source.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='questions'").fetchone():
                for row in source.execute("SELECT * FROM questions ORDER BY id"):
                    if db.execute("SELECT 1 FROM Quiz WHERE quiz_id=?", (row['quiz_id'],)).fetchone():
                        db.execute("""INSERT OR IGNORE INTO QuizQuestion
                            (question_id,quiz_id,prompt,option_a,option_b,option_c,option_d,correct_option,question_order)
                            VALUES(?,?,?,?,?,?,?,?,?)""",
                            (row['id'],row['quiz_id'],row['prompt'],row['option_a'],row['option_b'],
                             row['option_c'],row['option_d'],row['answer'],row['position']))
        finally:
            source.close()
    db.execute("INSERT INTO web_migrations(name) VALUES('chapter3_quiz_questions_v1')")


def _fill_demo_lesson_content(db):
    if db.execute("SELECT 1 FROM web_migrations WHERE name='expanded_lesson_reading_v2'").fetchone():
        return
    content_by_course = {
        "Database Design with SQL": [
            "A relational database organizes information into tables. Each table represents an entity, such as Student or Course; each row is one record and each column is an attribute. A Student row might contain a student ID, name, email, and join date. Choose a primary key that identifies every row and does not change when a person's name changes. A foreign key stores the key of a related row, which connects records without repeating all their details.\n\nStudents can take many courses, and a course can contain many students. Model that many-to-many relationship with an Enrollment table containing student_id and course_id. Each Enrollment row links one student to one course and can also store enrollment_date and progress_status. This design avoids repeating course and student details in every enrollment.\n\nPractice: draw Student, Course, and Enrollment as three boxes. Mark each primary key, draw arrows from Enrollment's foreign keys to the two parent tables, then write one example row for each table.",
            "SQL defines tables and protects their data. CREATE TABLE creates a table; INTEGER, TEXT, and REAL describe common SQLite values. NOT NULL requires a value, UNIQUE prevents duplicate values, and CHECK restricts values to a valid range or list. A foreign key verifies that a referenced parent row exists. SQLite connections must enable enforcement with PRAGMA foreign_keys = ON.\n\nUse JOIN to combine related rows. For example, join Enrollment to Student and Course to display a student's name beside the course title. Use LEFT JOIN when you want every course in a report, including courses with no enrollments. WHERE filters rows, ORDER BY sorts them, and GROUP BY combines rows for summaries. COUNT(*) counts rows; COUNT(column) ignores NULL values.\n\nPractice: write a query that lists each student's name, course title, and progress_status. Then change the query to include courses with zero students and explain why LEFT JOIN is needed.",
            "A useful course report groups Enrollment records by course. Join Course to Enrollment, group by the course key and title, and count enrollment IDs. This produces one row per course, including courses with no students when LEFT JOIN is used. The same pattern can count completed enrollments by summing a CASE expression that returns one for Completed and zero otherwise.\n\nA transaction treats related database changes as one unit. For enrollment, begin a transaction, verify the student and course, insert the Enrollment row, and commit. If a required check or insert fails, roll back so the database is not left half-updated. The UNIQUE rule on student_id and course_id prevents duplicate enrollment; foreign keys reject references to missing records.\n\nPractice: insert one valid enrollment, then try the same student/course pair again. Try an unknown student ID and a progress_status outside the allowed list. Record which constraints reject each attempt and why preserving these rules matters for reports.",
        ],
        "Python Programming Essentials": [
            "Python programs work with values stored under names. A string stores text, an integer stores a whole number, a float stores a decimal, and a Boolean stores True or False. Assign a value with the equals sign: learner = 'Mina'. Use print() to show a value and input() to read text from a person. Input arrives as a string, so convert it with int() or float() before arithmetic. Expressions combine values: 8 + 3 adds, name + ' Lee' joins strings, and score >= 50 produces a Boolean.\n\nUse descriptive variable names so another reader can understand what a value means. Comments beginning with # can explain a decision, but clear names and small functions are usually better documentation. Values have types, and choosing the right type makes operations easier to reason about.\n\nPractice: ask for a learner's name and three quiz scores. Convert the scores to numbers, calculate their average, and print a friendly summary. Try entering a blank or nonnumeric value and consider how the program should respond instead of crashing.",
            "Conditions let a program choose what to do. Use if for the first case, elif for another case, and else for the fallback. A for loop visits each item in a sequence; a while loop repeats while a condition remains true. Indentation defines which lines belong to a condition, loop, or function, so keep it consistent.\n\nFunctions package a task so it can be reused. Define one with def, pass information through parameters, and use return to send a result back. For example, an average function can accept a list of scores and return their mean. Check for an empty list before dividing, since division by zero is an error.\n\nPractice: write a function that receives a score and returns 'Pass' when it is at least 60, otherwise 'Try again'. Test values below, exactly at, and above 60. Then loop through several scores and print each result. These boundary tests help catch mistakes that a single example might miss.",
            "Lists store ordered collections and can be changed; dictionaries map keys to values. A study tracker could use a dictionary whose keys are course titles and whose values are completion percentages. Use append() to add an item to a list, items() to loop over a dictionary, and len() to count entries. Choose a list when order matters and a dictionary when you need quick lookup by a meaningful key.\n\nYou can combine these structures: a list of dictionaries can represent multiple students, with each dictionary holding a name and score. A loop can calculate totals or select records that meet a condition. Keep calculations in functions so they can be tested independently from input and display code.\n\nPractice: create a dictionary for three courses and their completion percentages. Print each course below 100%, then calculate the average progress. Add a function that returns the unfinished course names. Test the function with an empty dictionary and decide what an average should mean when there are no courses.",
        ],
        "UI/UX Design Fundamentals": [
            "User-centered design begins by understanding the people who will use a product, their goals, and the situation in which they work. Gather evidence through interviews, observation, or existing support requests. Summarize a user group with a short persona based on those findings; avoid inventing details that do not affect the task. Describe the user's goal in plain language, such as finding when an assignment is due.\n\nMap the steps the user takes today. Note where they wait, repeat work, make an error, or need help. These points reveal opportunities to improve the experience. A problem statement should describe the need without prescribing a screen too early.\n\nPractice: ask a student how they currently find an assignment deadline. Write the steps in order, identify the most confusing step, and turn it into a clear design question. For example: how might the course page make the next deadline visible without requiring the student to open every assignment?",
            "A wireframe shows the structure of a screen before color, imagery, and visual polish are chosen. Place related information together and create a hierarchy so the title, current status, and next action are easy to find. Navigation labels should use words users recognize. Buttons should describe their outcome, such as 'Submit assignment', rather than a vague label such as 'Go'.\n\nAccessibility is part of the structure. Use readable text, sufficient contrast, keyboard access, and clear focus indicators. Do not use color alone to signal a status; pair it with a label or icon. Forms need visible labels and useful error messages. A page should remain understandable when zoomed or used with assistive technology.\n\nPractice: sketch a course page with its title, instructor, lesson list, completion status, and next due assignment. Mark the tab order for keyboard use. Check whether a person can tell which lesson is complete without relying only on color.",
            "A prototype makes an idea concrete enough for someone to try. It can be a clickable wireframe or a simple sequence of screens. Test one realistic task at a time, such as locating a lesson and finding its completion control. Give the participant the goal, then observe without explaining where to click. Hesitation, backtracking, and errors are useful evidence.\n\nRecord what the participant did and said separately from your interpretation. After several sessions, look for repeated problems. Prioritize changes that block task completion or cause misunderstanding. Update the prototype and test again to see whether the change helped. A usability test does not prove that every user will succeed, but it reveals issues that a design team can address.\n\nPractice: ask someone to find a lesson and mark it complete in your wireframe. Note where they pause. Make one specific change, then repeat the task with another person and compare what happened.",
        ],
    }
    extra_practice = {
        "Database Design with SQL": [
            "Check your model: can a student enroll twice in the same course? Which key or constraint would prevent that? Explain why storing instructor or course details repeatedly in Enrollment would make later corrections difficult.",
            "Read your query from its first table outward. Identify the key used by each join, then predict what would happen if an Enrollment row referenced a Course that did not exist. Explain how a foreign key protects this query's results.",
            "Finish by listing the statements that belong in one transaction. Describe what the application should roll back if the enrollment insert fails, and name the constraints that protect the database from duplicate or invalid records.",
        ],
        "Python Programming Essentials": [
            "Trace the program with sample values and write down each variable's type after conversion. Try a blank value and text where a number is expected. Decide what helpful message the program should show instead of stopping unexpectedly.",
            "Refactor repeated logic into a second function. Write down what each function receives and returns, then test the boundary values again. This helps separate calculation from display and makes the code easier to reuse.",
            "Add a fourth course, change its completion value, and verify the output reflects the update. Explain why a dictionary is convenient when the course title is the lookup key, and consider how you would reject a percentage below zero or above 100.",
        ],
        "UI/UX Design Fundamentals": [
            "Check that your design question describes a real user need without assuming a specific interface solution. Ask one more student whether the problem also affects them, and note which parts of your understanding are supported by evidence.",
            "Ask a peer to find the next lesson using only the labels and visual hierarchy in your sketch. Note any hesitation, then check whether the design communicates completion with text or an icon as well as color.",
            "Keep the task and instructions consistent between usability sessions. Compare where each participant pauses, and explain whether your interface change reduced confusion rather than simply changing the test instructions.",
        ],
    }
    for course_title, lessons in content_by_course.items():
        course = db.execute("SELECT course_id FROM Course WHERE title=?", (course_title,)).fetchone()
        if not course:
            continue
        rows = db.execute("SELECT lesson_id,lesson_order,content FROM Lesson WHERE course_id=?", (course['course_id'],)).fetchall()
        for row in rows:
            position = row['lesson_order'] - 1
            if 0 <= position < len(lessons):
                content = lessons[position] + "\n\n" + extra_practice[course_title][position]
                db.execute("UPDATE Lesson SET content=?,duration_minutes=15 WHERE lesson_id=?", (content,row['lesson_id']))
    db.execute("INSERT INTO web_migrations(name) VALUES('expanded_lesson_reading_v2')")


def _issue_missing_certificates(db):
    completed = db.execute("""SELECT e.enrollment_id FROM Enrollment e
        LEFT JOIN Certificate c ON c.enrollment_id=e.enrollment_id
        WHERE e.progress_status='Completed' AND c.certificate_id IS NULL""").fetchall()
    for row in completed:
        db.execute("INSERT INTO Certificate(enrollment_id,certificate_code) VALUES(?,?)",
                   (row['enrollment_id'],f"LH-{secrets.token_hex(5).upper()}"))


def initialize_database():
    """Create the Chapter 3 schema and migrate existing desktop data once."""
    with connect() as db:
        db.executescript(SCHEMA_FILE.read_text(encoding="utf-8-sig"))
        # Additive columns keep previously-created local databases usable.
        instructor_columns = {row[1] for row in db.execute("PRAGMA table_info(Instructor)")}
        if "password_hash" not in instructor_columns:
            db.execute("ALTER TABLE Instructor ADD COLUMN password_hash TEXT")
        submission_columns = {row[1] for row in db.execute("PRAGMA table_info(Submission)")}
        if "feedback" not in submission_columns:
            db.execute("ALTER TABLE Submission ADD COLUMN feedback TEXT NOT NULL DEFAULT ''")
        if "graded_at" not in submission_columns:
            db.execute("ALTER TABLE Submission ADD COLUMN graded_at TEXT")
        if "file_name" not in submission_columns:
            db.execute("ALTER TABLE Submission ADD COLUMN file_name TEXT")
        if "file_path" not in submission_columns:
            db.execute("ALTER TABLE Submission ADD COLUMN file_path TEXT")
        if "file_size" not in submission_columns:
            db.execute("ALTER TABLE Submission ADD COLUMN file_size INTEGER CHECK (file_size IS NULL OR file_size >= 0)")
        if "file_mime_type" not in submission_columns:
            db.execute("ALTER TABLE Submission ADD COLUMN file_mime_type TEXT")
        db.execute("CREATE TABLE IF NOT EXISTS web_migrations (name TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
        if db.execute("SELECT 1 FROM web_migrations WHERE name='chapter3_nine_entities_v1'").fetchone():
            _migrate_quiz_questions(db)
            _fill_demo_lesson_content(db)
            _issue_missing_certificates(db)
            return

        if LEGACY_DB_FILE.exists():
            source = sqlite3.connect(LEGACY_DB_FILE)
            source.row_factory = sqlite3.Row
            try:
                tables = {row[0] for row in source.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                if {'users','courses'}.issubset(tables):
                    for user in source.execute("SELECT * FROM users ORDER BY id"):
                        if user['role'] == 'student':
                            db.execute("INSERT OR IGNORE INTO Student(student_id,name,email,join_date,password_hash) VALUES(?,?,?,?,?)",
                                       (user['id'],user['full_name'],user['email'],user['created_at'][:10],user['password_hash']))
                        elif user['role'] == 'instructor':
                            db.execute("INSERT OR IGNORE INTO Instructor(instructor_id,name,email,expertise) VALUES(?,?,?,?)",
                                       (user['id'],user['full_name'],user['email'],None))
                    if not db.execute("SELECT 1 FROM Instructor LIMIT 1").fetchone():
                        db.execute("INSERT INTO Instructor(name,email,expertise) VALUES('Course Instructor','instructor@learnhub.local','General')")
                    fallback_instructor = db.execute("SELECT instructor_id FROM Instructor ORDER BY instructor_id LIMIT 1").fetchone()[0]
                    for course in source.execute("SELECT * FROM courses ORDER BY id"):
                        instructor_id = course['instructor_id'] if course['instructor_id'] and db.execute("SELECT 1 FROM Instructor WHERE instructor_id=?",(course['instructor_id'],)).fetchone() else fallback_instructor
                        enrollment_count = source.execute("SELECT COUNT(*) FROM enrollments WHERE course_id=?",(course['id'],)).fetchone()[0] if 'enrollments' in tables else 0
                        db.execute("INSERT OR IGNORE INTO Course(course_id,instructor_id,title,description,duration_weeks,capacity) VALUES(?,?,?,?,?,?)",
                                   (course['id'],instructor_id,course['title'],course['description'],_weeks(course['duration']),max(100,enrollment_count)))
                    if 'enrollments' in tables:
                        for row in source.execute("SELECT * FROM enrollments ORDER BY id"):
                            if db.execute("SELECT 1 FROM Student WHERE student_id=?",(row['student_id'],)).fetchone() and db.execute("SELECT 1 FROM Course WHERE course_id=?",(row['course_id'],)).fetchone():
                                db.execute("INSERT OR IGNORE INTO Enrollment(enrollment_id,student_id,course_id,enrollment_date) VALUES(?,?,?,?)",
                                           (row['id'],row['student_id'],row['course_id'],row['enrolled_at'][:10]))
                    if 'lessons' in tables:
                        for row in source.execute("SELECT * FROM lessons ORDER BY id"):
                            db.execute("INSERT OR IGNORE INTO Lesson(lesson_id,course_id,lesson_title,lesson_order,content) VALUES(?,?,?,?,?)",
                                       (row['id'],row['course_id'],row['title'],row['position'],row['content']))
                    if 'assignments' in tables:
                        for row in source.execute("SELECT * FROM assignments ORDER BY id"):
                            db.execute("INSERT OR IGNORE INTO Assignment(assignment_id,course_id,title,due_date,max_marks,description) VALUES(?,?,?,?,?,?)",
                                       (row['id'],row['course_id'],row['title'],row['due_date'] or '2099-12-31',row['points'],row['instructions']))
                    if 'quizzes' in tables:
                        for row in source.execute("SELECT * FROM quizzes ORDER BY id"):
                            db.execute("INSERT OR IGNORE INTO Quiz(quiz_id,course_id,title,total_marks) VALUES(?,?,?,100)",
                                       (row['id'],row['course_id'],row['title']))
                    if 'submissions' in tables:
                        for row in source.execute("SELECT * FROM submissions ORDER BY id"):
                            db.execute("INSERT OR IGNORE INTO Submission(submission_id,student_id,assignment_id,submission_date,score,content,status) VALUES(?,?,?,?,?,?,?)",
                                       (row['id'],row['student_id'],row['assignment_id'],row['submitted_at'][:10],row['grade'],row['content'],'Late' if row['status']=='late' else 'Submitted'))
                    if 'quiz_attempts' in tables:
                        for row in source.execute("SELECT * FROM quiz_attempts ORDER BY id"):
                            db.execute("INSERT OR IGNORE INTO Submission(submission_id,student_id,quiz_id,submission_date,score) VALUES(?,?,?,?,?)",
                                       (1_000_000+row['id'],row['student_id'],row['quiz_id'],row['attempted_at'][:10],row['score']))
                    if 'lesson_progress' in tables:
                        for row in source.execute("SELECT p.student_id,p.lesson_id,p.completed_at FROM lesson_progress p"):
                            if db.execute("SELECT 1 FROM Student WHERE student_id=?",(row['student_id'],)).fetchone() and db.execute("SELECT 1 FROM Lesson WHERE lesson_id=?",(row['lesson_id'],)).fetchone():
                                db.execute("INSERT OR IGNORE INTO LessonProgress(student_id,lesson_id,completed_at) VALUES(?,?,?)",
                                           (row['student_id'],row['lesson_id'],row['completed_at']))
                        for row in source.execute("SELECT DISTINCT p.student_id,l.course_id FROM lesson_progress p JOIN lessons l ON l.id=p.lesson_id"):
                            total=db.execute("SELECT COUNT(*) FROM Lesson WHERE course_id=?",(row['course_id'],)).fetchone()[0]
                            done=db.execute("SELECT COUNT(*) FROM LessonProgress p JOIN Lesson l ON l.lesson_id=p.lesson_id WHERE p.student_id=? AND l.course_id=?",(row['student_id'],row['course_id'])).fetchone()[0]
                            if total and done==total:
                                db.execute("UPDATE Enrollment SET progress_status='Completed' WHERE student_id=? AND course_id=?",(row['student_id'],row['course_id']))
                            elif done:
                                db.execute("UPDATE Enrollment SET progress_status='In Progress' WHERE student_id=? AND course_id=? AND progress_status='Enrolled'",(row['student_id'],row['course_id']))
                    if 'course_completions' in tables:
                        for row in source.execute("SELECT * FROM course_completions"):
                            enrollment=db.execute("SELECT enrollment_id FROM Enrollment WHERE student_id=? AND course_id=?",(row['student_id'],row['course_id'])).fetchone()
                            if enrollment: db.execute("UPDATE Enrollment SET progress_status='Completed' WHERE enrollment_id=?",(enrollment['enrollment_id'],))
                    if 'certificates' in tables:
                        for row in source.execute("SELECT * FROM certificates"):
                            enrollment=db.execute("SELECT enrollment_id FROM Enrollment WHERE student_id=? AND course_id=?",(row['student_id'],row['course_id'])).fetchone()
                            if enrollment:
                                db.execute("INSERT OR IGNORE INTO Certificate(certificate_id,enrollment_id,certificate_code,issue_date) VALUES(?,?,?,?)",
                                           (row['id'],enrollment['enrollment_id'],row['certificate_code'],row['issued_at'][:10]))
            finally:
                source.close()
        db.execute("INSERT INTO web_migrations(name) VALUES('chapter3_nine_entities_v1')")
        _migrate_quiz_questions(db)
        _fill_demo_lesson_content(db)
        _issue_missing_certificates(db)


if __name__ == "__main__":
    initialize_database()
    print(f"LearnHub database initialized: {DB_FILE}")

# LearnHub — E-Learning Management System

LearnHub is a browser-based e-learning system with separate student and instructor accounts. Students enroll in courses, read lessons, complete quizzes, submit assignment text or documents, view results, and track certificates. Instructors review assignment submissions, download attached documents, enter marks, and provide feedback.

## Technologies

- **Frontend:** HTML, CSS, and JavaScript
- **Backend:** Python standard library (`http.server`, `json`, `sqlite3`, `hashlib`, `secrets`, and related modules)
- **Database:** SQLite with relational tables, primary and foreign keys, constraints, indexes, and triggers

## Run the website

From the project folder, start the local server:

```powershell
python web_backend.py
```

Then open <http://127.0.0.1:8000>. Stop the server with `Ctrl+C`. Restart it after updating the project.

## Student sign-in

Use the demo student account:

- Email: `jordan@learnsphere.local`
- Password: `learn123`

Students can also create a new student account from the sign-in page.

## Instructor sign-in and grading

Instructor sign-in is tied to an instructor profile already associated with courses. For the current project database, the instructor profile email is `alex@learnsphere.local`.

1. On the sign-in page, choose **Instructor**.
2. The first time, choose **Create instructor account**, enter the existing instructor email, the instructor's name, and a password of at least eight characters. This activates the existing instructor profile. On later visits, choose **Sign in** with that email and password.
3. The **Grading** page lists assignment submissions for courses assigned to that instructor, shows student text and attached documents, and provides each assignment's maximum marks.
4. Enter a mark from zero through the maximum, add feedback, and select **Save grade**. The pending-grading and graded totals update.
5. The student can see the mark and feedback on the Assignments and Results & Progress pages after refreshing the page.

Students can type a response, attach one PDF, DOC, DOCX, or TXT file (maximum 10 MB), or do both. Uploaded files are kept in the local assignment-upload storage and appear as download links for the submitting student and the assigned instructor. Only submitted assignments appear in the grading list. If it is empty, sign in as a student, enroll in one of the instructor's courses, and submit its assignment first.

Quiz attempts are automatically scored by the system. Instructor grading applies to assignment submissions. The grade endpoint verifies that the instructor owns the course and rejects marks outside the assignment's allowed range.

## Database design

The nine main entities are Student, Instructor, Course, Enrollment, Lesson, Assignment, Quiz, Submission, and Certificate. LessonProgress records each student's lesson completion, and QuizQuestion stores quiz questions and options. Submission stores assignment or quiz work, a nullable score, instructor feedback, grading date, and optional assignment-file metadata. Existing local databases are updated at startup to support instructor sign-in, feedback, and file submissions.

The browser database uses foreign keys, unique and check constraints, indexes, and triggers for course capacity and assessment score limits. Student passwords are stored as salted PBKDF2-HMAC-SHA256 hashes.

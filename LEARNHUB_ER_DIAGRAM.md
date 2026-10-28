# LearnHub ER Diagram

This diagram follows the current SQLite tables used by the LearnHub browser application. `phone_no` is optional for students. A submission is linked to exactly one assignment or one quiz, as enforced by the database check constraint.

```mermaid
erDiagram
    Student ||--o{ Enrollment : makes
    Course ||--o{ Enrollment : includes
    Instructor ||--o{ Course : teaches
    Course ||--o{ Lesson : contains
    Student ||--o{ LessonProgress : records
    Lesson ||--o{ LessonProgress : tracks
    Course ||--o{ Assignment : has
    Course ||--o{ Quiz : has
    Quiz ||--o{ QuizQuestion : contains
    Student ||--o{ Submission : submits
    Assignment ||--o{ Submission : receives_assignment_work
    Quiz ||--o{ Submission : receives_quiz_attempts
    Enrollment ||--o| Certificate : earns

    Student {
        INTEGER student_id PK
        TEXT name
        TEXT email UK
        TEXT phone_no
        TEXT join_date
        TEXT password_hash
    }
    Instructor {
        INTEGER instructor_id PK
        TEXT name
        TEXT email UK
        TEXT expertise
        TEXT password_hash
    }
    Course {
        INTEGER course_id PK
        INTEGER instructor_id FK
        TEXT title UK
        TEXT description
        INTEGER duration_weeks
        INTEGER capacity
    }
    Enrollment {
        INTEGER enrollment_id PK
        INTEGER student_id FK
        INTEGER course_id FK
        TEXT enrollment_date
        TEXT progress_status
    }
    Lesson {
        INTEGER lesson_id PK
        INTEGER course_id FK
        TEXT lesson_title
        INTEGER lesson_order
        INTEGER duration_minutes
        TEXT content
    }
    LessonProgress {
        INTEGER student_id PK, FK
        INTEGER lesson_id PK, FK
        TEXT completed_at
    }
    Assignment {
        INTEGER assignment_id PK
        INTEGER course_id FK
        TEXT title
        TEXT due_date
        INTEGER max_marks
        TEXT description
    }
    Quiz {
        INTEGER quiz_id PK
        INTEGER course_id FK
        TEXT title
        INTEGER total_marks
    }
    QuizQuestion {
        INTEGER question_id PK
        INTEGER quiz_id FK
        TEXT prompt
        TEXT option_a
        TEXT option_b
        TEXT option_c
        TEXT option_d
        TEXT correct_option
        INTEGER question_order
    }
    Submission {
        INTEGER submission_id PK
        INTEGER student_id FK
        INTEGER assignment_id FK
        INTEGER quiz_id FK
        TEXT submission_date
        REAL score
        TEXT content
        TEXT feedback
        TEXT graded_at
        TEXT file_name
        TEXT file_path
        INTEGER file_size
        TEXT file_mime_type
        TEXT status
    }
    Certificate {
        INTEGER certificate_id PK
        INTEGER enrollment_id FK, UK
        TEXT certificate_code UK
        TEXT issue_date
    }
    web_migrations {
        TEXT name PK
        TEXT applied_at
    }
```

`Enrollment` also enforces one row per student and course. `LessonProgress` uses the student and lesson identifiers together as its primary key, so a student's completion for a lesson is recorded once. `Submission` permits only one of `assignment_id` or `quiz_id` for each row. The database also limits a student to one assignment submission per assignment. `web_migrations` is the backend's startup migration-tracking table; it is not connected to the learning records.

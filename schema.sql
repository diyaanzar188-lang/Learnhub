PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS Student (
    student_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
    phone_no TEXT,
    join_date TEXT NOT NULL DEFAULT (DATE('now')),
    password_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS Instructor (
    instructor_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
    expertise TEXT,
    password_hash TEXT
);

CREATE TABLE IF NOT EXISTS Course (
    course_id INTEGER PRIMARY KEY AUTOINCREMENT,
    instructor_id INTEGER NOT NULL,
    title TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL DEFAULT '',
    duration_weeks INTEGER NOT NULL CHECK (duration_weeks > 0),
    capacity INTEGER NOT NULL DEFAULT 100 CHECK (capacity > 0),
    FOREIGN KEY (instructor_id) REFERENCES Instructor(instructor_id)
);

CREATE TABLE IF NOT EXISTS Enrollment (
    enrollment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    course_id INTEGER NOT NULL,
    enrollment_date TEXT NOT NULL DEFAULT (DATE('now')),
    progress_status TEXT NOT NULL DEFAULT 'Enrolled'
        CHECK (progress_status IN ('Enrolled','In Progress','Completed')),
    UNIQUE (student_id, course_id),
    FOREIGN KEY (student_id) REFERENCES Student(student_id) ON DELETE CASCADE,
    FOREIGN KEY (course_id) REFERENCES Course(course_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS Lesson (
    lesson_id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id INTEGER NOT NULL,
    lesson_title TEXT NOT NULL,
    lesson_order INTEGER NOT NULL,
    duration_minutes INTEGER NOT NULL DEFAULT 15 CHECK (duration_minutes > 0),
    content TEXT NOT NULL DEFAULT '',
    UNIQUE (course_id, lesson_order),
    FOREIGN KEY (course_id) REFERENCES Course(course_id) ON DELETE CASCADE
);

-- Supporting relation for per-student lesson completion; this enables the
-- Enrollment.progress_status summary while keeping lesson catalog data shared.
CREATE TABLE IF NOT EXISTS LessonProgress (
    student_id INTEGER NOT NULL,
    lesson_id INTEGER NOT NULL,
    completed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (student_id, lesson_id),
    FOREIGN KEY (student_id) REFERENCES Student(student_id) ON DELETE CASCADE,
    FOREIGN KEY (lesson_id) REFERENCES Lesson(lesson_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS Assignment (
    assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    due_date TEXT NOT NULL,
    max_marks INTEGER NOT NULL CHECK (max_marks > 0),
    description TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (course_id) REFERENCES Course(course_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS Quiz (
    quiz_id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    total_marks INTEGER NOT NULL CHECK (total_marks > 0),
    FOREIGN KEY (course_id) REFERENCES Course(course_id) ON DELETE CASCADE
);

-- Supporting assessment items; Quiz remains the Chapter 3 assessment entity.
CREATE TABLE IF NOT EXISTS QuizQuestion (
    question_id INTEGER PRIMARY KEY AUTOINCREMENT,
    quiz_id INTEGER NOT NULL,
    prompt TEXT NOT NULL,
    option_a TEXT NOT NULL,
    option_b TEXT NOT NULL,
    option_c TEXT NOT NULL,
    option_d TEXT NOT NULL,
    correct_option TEXT NOT NULL CHECK (correct_option IN ('A','B','C','D')),
    question_order INTEGER NOT NULL,
    UNIQUE (quiz_id, question_order),
    FOREIGN KEY (quiz_id) REFERENCES Quiz(quiz_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS Submission (
    submission_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    assignment_id INTEGER,
    quiz_id INTEGER,
    submission_date TEXT NOT NULL DEFAULT (DATE('now')),
    score REAL CHECK (score IS NULL OR score >= 0),
    content TEXT NOT NULL DEFAULT '',
    feedback TEXT NOT NULL DEFAULT '',
    graded_at TEXT,
    file_name TEXT,
    file_path TEXT,
    file_size INTEGER CHECK (file_size IS NULL OR file_size >= 0),
    file_mime_type TEXT,
    status TEXT NOT NULL DEFAULT 'Submitted' CHECK (status IN ('Submitted','Late')),
    CHECK ((assignment_id IS NOT NULL AND quiz_id IS NULL) OR
           (assignment_id IS NULL AND quiz_id IS NOT NULL)),
    FOREIGN KEY (student_id) REFERENCES Student(student_id) ON DELETE CASCADE,
    FOREIGN KEY (assignment_id) REFERENCES Assignment(assignment_id) ON DELETE CASCADE,
    FOREIGN KEY (quiz_id) REFERENCES Quiz(quiz_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS Certificate (
    certificate_id INTEGER PRIMARY KEY AUTOINCREMENT,
    enrollment_id INTEGER NOT NULL UNIQUE,
    certificate_code TEXT NOT NULL UNIQUE,
    issue_date TEXT NOT NULL DEFAULT (DATE('now')),
    FOREIGN KEY (enrollment_id) REFERENCES Enrollment(enrollment_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_enrollment_course ON Enrollment(course_id);
CREATE INDEX IF NOT EXISTS idx_lesson_course ON Lesson(course_id, lesson_order);
CREATE INDEX IF NOT EXISTS idx_assignment_course ON Assignment(course_id);
CREATE INDEX IF NOT EXISTS idx_quiz_course ON Quiz(course_id);
CREATE INDEX IF NOT EXISTS idx_question_quiz ON QuizQuestion(quiz_id, question_order);
CREATE INDEX IF NOT EXISTS idx_submission_student ON Submission(student_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_one_assignment_submission_per_student
    ON Submission(student_id, assignment_id) WHERE assignment_id IS NOT NULL;

CREATE TRIGGER IF NOT EXISTS trg_enrollment_capacity
BEFORE INSERT ON Enrollment
WHEN (SELECT COUNT(*) FROM Enrollment WHERE course_id=NEW.course_id) >=
     (SELECT capacity FROM Course WHERE course_id=NEW.course_id)
BEGIN
    SELECT RAISE(ABORT, 'course capacity reached');
END;

CREATE TRIGGER IF NOT EXISTS trg_submission_score_limit_insert
BEFORE INSERT ON Submission
WHEN NEW.score IS NOT NULL AND (
    (NEW.assignment_id IS NOT NULL AND NEW.score > (SELECT max_marks FROM Assignment WHERE assignment_id=NEW.assignment_id)) OR
    (NEW.quiz_id IS NOT NULL AND NEW.score > (SELECT total_marks FROM Quiz WHERE quiz_id=NEW.quiz_id))
)
BEGIN
    SELECT RAISE(ABORT, 'score exceeds assessment maximum');
END;

CREATE TRIGGER IF NOT EXISTS trg_submission_score_limit_update
BEFORE UPDATE OF score, assignment_id, quiz_id ON Submission
WHEN NEW.score IS NOT NULL AND (
    (NEW.assignment_id IS NOT NULL AND NEW.score > (SELECT max_marks FROM Assignment WHERE assignment_id=NEW.assignment_id)) OR
    (NEW.quiz_id IS NOT NULL AND NEW.score > (SELECT total_marks FROM Quiz WHERE quiz_id=NEW.quiz_id))
)
BEGIN
    SELECT RAISE(ABORT, 'score exceeds assessment maximum');
END;

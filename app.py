"""LearnSphere — a self-contained Tkinter and SQLite e-learning system."""
from __future__ import annotations

import hashlib
import html
import os
import secrets
import sqlite3
import tkinter as tk
import webbrowser
import csv
from datetime import datetime, timedelta
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

APP_NAME = "LearnSphere"
DB_FILE = Path(__file__).with_name("learnsphere.db")
BG = "#f4f7fb"
INK = "#17253d"
MUTED = "#687891"
BLUE = "#315cf5"
TEAL = "#11a68a"
LINE = "#e4eaf2"
FONT = "Segoe UI"

# Ten course-specific, single-answer assessment questions for the bundled demo catalog.
DEMO_QUESTIONS = {
    "Python Programming Essentials": [
        ("Which Python type stores an ordered, changeable collection?", "tuple", "list", "set", "frozenset", "B"),
        ("What does `len([4, 8, 12])` return?", "2", "3", "4", "12", "B"),
        ("Which keyword starts a function definition?", "func", "define", "def", "function", "C"),
        ("What is the result of `7 // 2` in Python?", "3.5", "3", "4", "2", "B"),
        ("Which expression checks whether `x` is at least 10?", "x => 10", "x >= 10", "x = 10", "x <> 10", "B"),
        ("Which loop is commonly used to visit every item in a list?", "for loop", "switch statement", "try block", "class block", "A"),
        ("What does a dictionary store?", "Only numeric indexes", "Key-value pairs", "Unique characters only", "A sequence of files", "B"),
        ("Which value represents the absence of a value in Python?", "empty", "void", "None", "null", "C"),
        ("What does `return` do inside a function?", "Repeats the function", "Sends a value back to the caller", "Prints every variable", "Stops the Python interpreter", "B"),
        ("Which block handles an exception raised in a `try` block?", "except", "finally only", "rescue", "catch", "A"),
    ],
    "Database Design with SQL": [
        ("What uniquely identifies each row in a relational table?", "Foreign key", "Primary key", "View", "Index name", "B"),
        ("What is the purpose of a foreign key?", "To link rows between related tables", "To encrypt a column", "To sort query results", "To rename a database", "A"),
        ("Which SQL statement retrieves rows?", "GET", "SELECT", "FETCH TABLE", "OPEN", "B"),
        ("Which clause filters rows before grouping?", "ORDER BY", "HAVING", "WHERE", "LIMIT", "C"),
        ("Which join returns rows with matching values in both tables?", "INNER JOIN", "CROSS JOIN", "FULL TEXT JOIN", "UNION", "A"),
        ("What does `COUNT(*)` return?", "The sum of numeric values", "The number of rows", "The number of columns", "The first row", "B"),
        ("Which command adds a new row to a table?", "UPDATE", "ALTER", "INSERT", "CREATE INDEX", "C"),
        ("What does a database transaction help ensure?", "A group of changes succeeds or rolls back together", "Every query creates a new table", "All columns become unique", "Queries run without constraints", "A"),
        ("Which constraint prevents duplicate values in a column or column set?", "DEFAULT", "UNIQUE", "CHECK", "NOT NULL", "B"),
        ("Which clause sorts query results?", "GROUP BY", "ORDER BY", "SORT", "ARRANGE", "B"),
    ],
    "UI/UX Design Fundamentals": [
        ("What is the primary goal of user-centered design?", "Make the interface as decorative as possible", "Meet users' needs and support their tasks", "Use the newest visual trend", "Reduce the number of research sessions", "B"),
        ("What is a wireframe mainly used to communicate?", "The structure and layout of a screen", "Final production code", "The complete brand strategy", "Database relationships", "A"),
        ("Which activity is most useful before designing a solution?", "Assume users behave like the designer", "Understand users and their context", "Choose animation effects", "Write the release notes", "B"),
        ("What does visual hierarchy help users do?", "Find the most important information first", "Avoid all text", "Use every color equally", "Open multiple screens at once", "A"),
        ("What is a prototype useful for?", "Testing and communicating an interaction idea", "Replacing all user research", "Storing customer passwords", "Guaranteeing a design has no issues", "A"),
        ("What does usability testing observe?", "How people complete tasks with a design", "How fast a computer starts", "How many colors are in a brand", "How developers name variables", "A"),
        ("Why should interfaces provide feedback after an action?", "To confirm the action's result to the user", "To make every screen busier", "To hide system status", "To prevent users from navigating", "A"),
        ("Which choice usually improves accessibility?", "Rely on color alone to convey meaning", "Use clear labels and sufficient contrast", "Make all text very small", "Remove keyboard navigation", "B"),
        ("What is an affordance in interface design?", "A clue about how an element can be used", "A database backup", "A type of color palette", "A screen resolution", "A"),
        ("Why iterate on a design after testing?", "To refine it using observed issues and feedback", "To avoid documenting changes", "To keep the first draft unchanged", "To remove all user input", "A"),
    ],
}


def connect():
    db = sqlite3.connect(DB_FILE)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


def password_hash(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310_000)
    return f"{salt.hex()}${digest.hex()}"


def password_ok(password: str, stored: str) -> bool:
    try:
        salt, digest = stored.split("$")
        return secrets.compare_digest(hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 310_000).hex(), digest)
    except (ValueError, TypeError):
        return False


def record_activity(user_id, event_type, summary, course_id=None, actor_id=None):
    """Append a permanent learner/account event to the activity history."""
    if user_id is None:
        return
    with connect() as db:
        db.execute("""INSERT INTO activity_history(user_id,actor_id,course_id,event_type,summary)
            VALUES(?,?,?,?,?)""", (user_id, actor_id if actor_id is not None else user_id,
                                     course_id, event_type, summary))


def record_course_completion(student_id, course_id):
    """Record the completion milestone once lessons and a passing quiz are both done."""
    with connect() as db:
        total = db.execute("SELECT COUNT(*) FROM lessons WHERE course_id=?", (course_id,)).fetchone()[0]
        done = db.execute("""SELECT COUNT(*) FROM lesson_progress p JOIN lessons l ON l.id=p.lesson_id
            WHERE p.student_id=? AND l.course_id=?""", (student_id, course_id)).fetchone()[0]
        score = db.execute("""SELECT MAX(a.score) FROM quiz_attempts a JOIN quizzes q ON q.id=a.quiz_id
            WHERE a.student_id=? AND q.course_id=? AND a.passed=1""", (student_id, course_id)).fetchone()[0]
        if not total or done < total or score is None:
            return False
        inserted = db.execute("""INSERT OR IGNORE INTO course_completions(student_id,course_id,final_score)
            VALUES(?,?,?)""", (student_id, course_id, score)).rowcount
    if inserted:
        record_activity(student_id, "course_completed", f"Completed all lessons and passed the assessment ({score}%).", course_id)
    return bool(inserted)


def initialize():
    with connect() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS users(
          id INTEGER PRIMARY KEY, full_name TEXT NOT NULL, email TEXT NOT NULL UNIQUE COLLATE NOCASE,
          password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('student','instructor','admin')),
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS courses(
          id INTEGER PRIMARY KEY, title TEXT NOT NULL, category TEXT NOT NULL DEFAULT 'General',
          description TEXT NOT NULL DEFAULT '', instructor_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
          duration TEXT NOT NULL DEFAULT '4 weeks', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS enrollments(
          id INTEGER PRIMARY KEY, student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
          enrolled_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE(student_id,course_id));
        CREATE TABLE IF NOT EXISTS lessons(
          id INTEGER PRIMARY KEY, course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
          title TEXT NOT NULL, content TEXT NOT NULL DEFAULT '', position INTEGER NOT NULL DEFAULT 1,
          UNIQUE(course_id,position));
        CREATE TABLE IF NOT EXISTS learning_materials(
          id INTEGER PRIMARY KEY, course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
          title TEXT NOT NULL, material_type TEXT NOT NULL CHECK(material_type IN ('PDF','Video','Link')),
          material_url TEXT, uploaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS lesson_progress(
          student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          lesson_id INTEGER NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
          completed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(student_id,lesson_id));
        CREATE TABLE IF NOT EXISTS quizzes(
          id INTEGER PRIMARY KEY, course_id INTEGER NOT NULL UNIQUE REFERENCES courses(id) ON DELETE CASCADE,
          title TEXT NOT NULL DEFAULT 'Course assessment', pass_mark INTEGER NOT NULL DEFAULT 60);
        CREATE TABLE IF NOT EXISTS questions(
          id INTEGER PRIMARY KEY, quiz_id INTEGER NOT NULL REFERENCES quizzes(id) ON DELETE CASCADE,
          prompt TEXT NOT NULL, option_a TEXT NOT NULL, option_b TEXT NOT NULL,
          option_c TEXT NOT NULL, option_d TEXT NOT NULL, answer TEXT NOT NULL CHECK(answer IN ('A','B','C','D')),
          position INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS quiz_attempts(
          id INTEGER PRIMARY KEY, student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          quiz_id INTEGER NOT NULL REFERENCES quizzes(id) ON DELETE CASCADE, score INTEGER NOT NULL,
          passed INTEGER NOT NULL CHECK(passed IN (0,1)), attempted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS certificates(
          id INTEGER PRIMARY KEY, student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
          certificate_code TEXT NOT NULL UNIQUE, issued_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          UNIQUE(student_id,course_id));
        CREATE TABLE IF NOT EXISTS assignments(
          id INTEGER PRIMARY KEY, course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
          title TEXT NOT NULL, instructions TEXT NOT NULL DEFAULT '', due_date TEXT,
          points INTEGER NOT NULL DEFAULT 100 CHECK(points > 0),
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS submissions(
          id INTEGER PRIMARY KEY, assignment_id INTEGER NOT NULL REFERENCES assignments(id) ON DELETE CASCADE,
          student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          content TEXT NOT NULL, submitted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          grade INTEGER CHECK(grade IS NULL OR grade >= 0), feedback TEXT,
          status TEXT NOT NULL DEFAULT 'submitted' CHECK(status IN ('submitted','graded')),
          UNIQUE(assignment_id,student_id));
        CREATE TABLE IF NOT EXISTS course_completions(
          id INTEGER PRIMARY KEY, student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
          completed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, final_score INTEGER NOT NULL CHECK(final_score BETWEEN 0 AND 100),
          UNIQUE(student_id,course_id));
        CREATE TABLE IF NOT EXISTS activity_history(
          id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          actor_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
          course_id INTEGER REFERENCES courses(id) ON DELETE SET NULL,
          event_type TEXT NOT NULL, summary TEXT NOT NULL,
          occurred_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, source_key TEXT UNIQUE);
        CREATE TABLE IF NOT EXISTS app_meta(
          key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_enrollment_student ON enrollments(student_id);
        CREATE INDEX IF NOT EXISTS idx_lesson_course ON lessons(course_id);
        CREATE INDEX IF NOT EXISTS idx_material_course ON learning_materials(course_id);
        CREATE INDEX IF NOT EXISTS idx_attempt_student ON quiz_attempts(student_id);
        CREATE INDEX IF NOT EXISTS idx_assignment_course ON assignments(course_id);
        CREATE INDEX IF NOT EXISTS idx_submission_assignment ON submissions(assignment_id);
        CREATE INDEX IF NOT EXISTS idx_history_user ON activity_history(user_id,occurred_at DESC);
        CREATE INDEX IF NOT EXISTS idx_completion_student ON course_completions(student_id);
        """)
        if not db.execute("SELECT 1 FROM users LIMIT 1").fetchone():
            admin = db.execute("INSERT INTO users(full_name,email,password_hash,role) VALUES(?,?,?,?)",
                               ("LearnSphere Admin", "admin@learnsphere.local", password_hash("admin123"), "admin")).lastrowid
            instructor = db.execute("INSERT INTO users(full_name,email,password_hash,role) VALUES(?,?,?,?)",
                                    ("Alex Morgan", "alex@learnsphere.local", password_hash("learn123"), "instructor")).lastrowid
            student = db.execute("INSERT INTO users(full_name,email,password_hash,role) VALUES(?,?,?,?)",
                                 ("Jordan Lee", "jordan@learnsphere.local", password_hash("learn123"), "student")).lastrowid
            samples = [
              ("Python Programming Essentials", "Programming", "Build a solid foundation in Python, from data types and control flow to functions and practical projects.", "4 weeks"),
              ("Database Design with SQL", "Data & Analytics", "Learn relational modeling, SQL queries, constraints, and transaction fundamentals.", "3 weeks"),
              ("UI/UX Design Fundamentals", "Design", "Explore user-centered design, wireframing, visual hierarchy, and prototyping.", "5 weeks")]
            for title, category, desc, duration in samples:
                cid = db.execute("INSERT INTO courses(title,category,description,instructor_id,duration) VALUES(?,?,?,?,?)", (title,category,desc,instructor,duration)).lastrowid
                for n, lesson_title in enumerate(["Getting started", "Core concepts", "Practice and apply"], 1):
                    db.execute("INSERT INTO lessons(course_id,title,content,position) VALUES(?,?,?,?)", (cid, lesson_title, f"{lesson_title} — {desc}\n\nWork through the key ideas, take notes, and apply them in a small exercise.",n))
                qid = db.execute("INSERT INTO quizzes(course_id,title,pass_mark) VALUES(?,?,?)", (cid, f"{title} knowledge check",70)).lastrowid
                questions = DEMO_QUESTIONS[title]
                for pos, q in enumerate(questions, 1):
                    db.execute("INSERT INTO questions(quiz_id,prompt,option_a,option_b,option_c,option_d,answer,position) VALUES(?,?,?,?,?,?,?,?)", (qid,*q,pos))
            db.execute("INSERT INTO enrollments(student_id,course_id) VALUES(?,1)", (student,))
            db.execute("INSERT INTO lesson_progress(student_id,lesson_id) VALUES(?,1)", (student,))

        # One-time upgrade for databases created by earlier LearnSphere versions.
        # Preserve quiz attempts and any future instructor edits after this migration.
        if not db.execute("SELECT 1 FROM app_meta WHERE key='demo_assessments_v2'").fetchone():
            for course_title, questions in DEMO_QUESTIONS.items():
                course = db.execute("SELECT id FROM courses WHERE title=?", (course_title,)).fetchone()
                if not course:
                    continue
                quiz = db.execute("SELECT id FROM quizzes WHERE course_id=?", (course["id"],)).fetchone()
                if quiz:
                    quiz_id = quiz["id"]
                    db.execute("DELETE FROM questions WHERE quiz_id=?", (quiz_id,))
                else:
                    quiz_id = db.execute("INSERT INTO quizzes(course_id,title,pass_mark) VALUES(?,?,70)",
                                         (course["id"], f"{course_title} knowledge check")).lastrowid
                for pos, question in enumerate(questions, 1):
                    db.execute("INSERT INTO questions(quiz_id,prompt,option_a,option_b,option_c,option_d,answer,position) VALUES(?,?,?,?,?,?,?,?)",
                               (quiz_id, *question, pos))
            db.execute("INSERT INTO app_meta(key,value) VALUES('demo_assessments_v2','1')")

        if not db.execute("SELECT 1 FROM app_meta WHERE key='demo_assignments_v1'").fetchone():
            demo_assignment_text={
                "Python Programming Essentials":("Build a small Python program that accepts input, uses a function, and reports a useful result.","Create a command-line study planner. Use a list or dictionary to store tasks, write at least two functions, validate user input, and include a short example run."),
                "Database Design with SQL":("Design a small relational schema and demonstrate key SQL queries.","Create a normalized schema for a campus library with at least three related tables. Identify primary and foreign keys, then provide example INSERT, SELECT with JOIN, UPDATE, and DELETE statements."),
                "UI/UX Design Fundamentals":("Apply user-centered design to a focused screen or workflow.","Choose a common student task and describe the target user, task flow, and two wireframe screens. Explain one accessibility choice and one change you would make after usability feedback."),
            }
            for course_title,(title,instructions) in demo_assignment_text.items():
                course=db.execute("SELECT id FROM courses WHERE title=?",(course_title,)).fetchone()
                if course and not db.execute("SELECT 1 FROM assignments WHERE course_id=? LIMIT 1",(course["id"],)).fetchone():
                    due=(datetime.now().date()+timedelta(days=14)).isoformat()
                    db.execute("INSERT INTO assignments(course_id,title,instructions,due_date,points) VALUES(?,?,?,?,100)",
                               (course["id"],title,instructions,due))
            db.execute("INSERT INTO app_meta(key,value) VALUES('demo_assignments_v1','1')")

        if not db.execute("SELECT 1 FROM app_meta WHERE key='demo_materials_v1'").fetchone():
            demo_materials = {
                "Python Programming Essentials": [("Python Fundamentals", "PDF", "https://docs.python.org/3/tutorial/"), ("Python practice video", "Video", "https://www.youtube.com/results?search_query=python+programming+tutorial")],
                "Database Design with SQL": [("SQLite SQL Reference", "Link", "https://www.sqlite.org/lang.html"), ("Relational database notes", "PDF", "https://www.sqlite.org/about.html")],
                "UI/UX Design Fundamentals": [("Accessibility fundamentals", "Link", "https://www.w3.org/WAI/fundamentals/")],
            }
            for course_title, materials in demo_materials.items():
                course = db.execute("SELECT id FROM courses WHERE title=?", (course_title,)).fetchone()
                if course:
                    for title, kind, url in materials:
                        db.execute("INSERT INTO learning_materials(course_id,title,material_type,material_url) VALUES(?,?,?,?)", (course["id"], title, kind, url))
            db.execute("INSERT INTO app_meta(key,value) VALUES('demo_materials_v1','1')")

        # Backfill history for records made before activity tracking was introduced.
        if not db.execute("SELECT 1 FROM app_meta WHERE key='history_v1'").fetchone():
            db.execute("""INSERT OR IGNORE INTO course_completions(student_id,course_id,completed_at,final_score)
                SELECT cert.student_id,cert.course_id,cert.issued_at,
                    COALESCE((SELECT MAX(a.score) FROM quiz_attempts a JOIN quizzes q ON q.id=a.quiz_id
                              WHERE a.student_id=cert.student_id AND q.course_id=cert.course_id AND a.passed=1),100)
                FROM certificates cert""")
            db.execute("""INSERT OR IGNORE INTO activity_history(user_id,actor_id,event_type,summary,occurred_at,source_key)
                SELECT id,id,'account_created','Account created',created_at,'account:'||id FROM users""")
            db.execute("""INSERT OR IGNORE INTO activity_history(user_id,actor_id,course_id,event_type,summary,occurred_at,source_key)
                SELECT e.student_id,e.student_id,e.course_id,'enrolled','Enrolled in course',e.enrolled_at,'enrollment:'||e.id FROM enrollments e""")
            db.execute("""INSERT OR IGNORE INTO activity_history(user_id,actor_id,course_id,event_type,summary,occurred_at,source_key)
                SELECT p.student_id,p.student_id,l.course_id,'lesson_completed','Completed lesson: '||l.title,p.completed_at,
                    'lesson:'||p.student_id||':'||p.lesson_id FROM lesson_progress p JOIN lessons l ON l.id=p.lesson_id""")
            db.execute("""INSERT OR IGNORE INTO activity_history(user_id,actor_id,course_id,event_type,summary,occurred_at,source_key)
                SELECT a.student_id,a.student_id,q.course_id,'quiz_attempted',
                    'Assessment submitted: '||a.score||'% — '||CASE WHEN a.passed=1 THEN 'passed' ELSE 'not passed' END,
                    a.attempted_at,'quiz:'||a.id FROM quiz_attempts a JOIN quizzes q ON q.id=a.quiz_id""")
            db.execute("""INSERT OR IGNORE INTO activity_history(user_id,actor_id,course_id,event_type,summary,occurred_at,source_key)
                SELECT s.student_id,s.student_id,a.course_id,'assignment_submitted','Submitted assignment: '||a.title,
                    s.submitted_at,'submission:'||s.id FROM submissions s JOIN assignments a ON a.id=s.assignment_id""")
            db.execute("""INSERT OR IGNORE INTO activity_history(user_id,actor_id,course_id,event_type,summary,occurred_at,source_key)
                SELECT s.student_id,s.student_id,a.course_id,'assignment_graded',
                    'Assignment graded: '||a.title||' — '||s.grade||'/'||a.points,s.submitted_at,'grade:'||s.id
                FROM submissions s JOIN assignments a ON a.id=s.assignment_id WHERE s.status='graded'""")
            db.execute("""INSERT OR IGNORE INTO activity_history(user_id,actor_id,course_id,event_type,summary,occurred_at,source_key)
                SELECT c.student_id,c.student_id,c.course_id,'course_completed','Course certificate issued: '||c.certificate_code,
                    c.issued_at,'certificate:'||c.id FROM certificates c""")
            db.execute("INSERT INTO app_meta(key,value) VALUES('history_v1','1')")


class LearnSphere(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("LearnSphere | E-Learning Management System")
        self.geometry("1220x780")
        self.minsize(1000, 660)
        self.configure(bg=BG)
        self.user = None
        self._styles()
        self.protocol("WM_DELETE_WINDOW", self.close_application)
        self.show_login()

    def close_application(self):
        if self.user:
            record_activity(self.user["id"],"session_ended","Application closed")
        self.destroy()

    def _styles(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure("Treeview", background="white", foreground=INK, fieldbackground="white", rowheight=36, borderwidth=0, font=(FONT, 10))
        s.configure("Treeview.Heading", background="#eef2f8", foreground=MUTED, font=(FONT, 9, "bold"), relief="flat", padding=(10, 10))
        s.map("Treeview", background=[("selected", "#e8edff")], foreground=[("selected", INK)])
        s.configure("TCombobox", padding=7, font=(FONT, 10))
        s.configure("Horizontal.TProgressbar", troughcolor="#e8edf5", background=TEAL, bordercolor="#e8edf5", lightcolor=TEAL, darkcolor=TEAL)

    def clear(self):
        for child in self.winfo_children(): child.destroy()

    def show_login(self):
        self.clear()
        shell = tk.Frame(self, bg=BG); shell.pack(fill="both", expand=True)
        panel = tk.Frame(shell, bg="#17253d", width=430); panel.pack(side="left", fill="y"); panel.pack_propagate(False)
        tk.Label(panel, text="◈  LearnSphere", bg="#17253d", fg="white", font=(FONT, 24, "bold")).pack(anchor="w", padx=48, pady=(70, 18))
        tk.Label(panel, text="Learning that moves\nyou forward.", bg="#17253d", fg="white", font=(FONT, 24, "bold"), justify="left", anchor="w").pack(anchor="w", padx=40, pady=(50, 16))
        tk.Label(panel, text="A connected place to learn, practice,\nand celebrate your progress.", bg="#17253d", fg="#b6c5dc", font=(FONT, 12), justify="left").pack(anchor="w", padx=48)
        tk.Label(panel, text="E-LEARNING MANAGEMENT SYSTEM", bg="#17253d", fg="#7e91ad", font=(FONT, 9, "bold")).pack(side="bottom", anchor="w", padx=48, pady=38)
        right = tk.Frame(shell, bg=BG); right.pack(side="left", fill="both", expand=True)
        card = tk.Frame(right, bg="white", padx=42, pady=38); card.place(relx=.5, rely=.5, anchor="center")
        tk.Label(card, text="Welcome back", bg="white", fg=INK, font=(FONT, 24, "bold")).pack(anchor="w")
        tk.Label(card, text="Sign in to continue your learning journey.", bg="white", fg=MUTED, font=(FONT, 10)).pack(anchor="w", pady=(7, 26))
        tk.Label(card, text="EMAIL ADDRESS", bg="white", fg=MUTED, font=(FONT, 9, "bold")).pack(anchor="w")
        email = ttk.Entry(card, width=37, font=(FONT, 11)); email.pack(pady=(7, 18), ipady=7); email.insert(0, "jordan@learnsphere.local")
        tk.Label(card, text="PASSWORD", bg="white", fg=MUTED, font=(FONT, 9, "bold")).pack(anchor="w")
        pw = ttk.Entry(card, width=37, show="●", font=(FONT, 11)); pw.pack(pady=(7, 6), ipady=7); pw.insert(0, "learn123")
        show_password = tk.BooleanVar(value=False)
        tk.Checkbutton(card,text="Show password",variable=show_password,
                       command=lambda:pw.configure(show="" if show_password.get() else "●"),
                       bg="white",fg=MUTED,activebackground="white",font=(FONT,9)).pack(anchor="w",pady=(0,10))
        def login(event=None):
            with connect() as db: row = db.execute("SELECT * FROM users WHERE email=?", (email.get().strip(),)).fetchone()
            if row and password_ok(pw.get(), row["password_hash"]):
                self.user = dict(row)
                record_activity(row["id"], "signed_in", "Signed in")
                self.show_app()
            else: messagebox.showerror("Sign in failed", "The email or password is incorrect.", parent=self)
        tk.Button(card, text="Sign in  →", command=login, bg=BLUE, fg="white", activebackground="#244bd8", activeforeground="white", relief="flat", cursor="hand2", font=(FONT, 11, "bold"), padx=14, pady=11).pack(fill="x")
        tk.Button(card, text="Create a student account", command=self.register_dialog, bg="white", fg=BLUE, relief="flat", cursor="hand2", font=(FONT, 10, "bold")).pack(pady=(14, 0))
        tk.Label(card, text="Student: jordan@learnsphere.local / learn123\nInstructor: alex@learnsphere.local / learn123\nAdmin: admin@learnsphere.local / admin123", bg="white", fg="#8290a4", font=(FONT, 9), justify="left", anchor="w").pack(anchor="w", pady=(18, 0))
        pw.bind("<Return>", login); email.focus_set()

    def register_dialog(self):
        d = tk.Toplevel(self); d.title("Create student account"); d.configure(bg="white"); d.resizable(False, False)
        fields = {}
        for label in ("Full name", "Email", "Password", "Confirm password"):
            tk.Label(d, text=label, bg="white", fg=INK, font=(FONT, 10, "bold")).pack(anchor="w", padx=22, pady=(14, 0))
            ent = ttk.Entry(d, width=36, show="●" if "password" in label.lower() else ""); ent.pack(padx=22, pady=5, ipady=4); fields[label] = ent
        show_password = tk.BooleanVar(value=False)
        tk.Checkbutton(d,text="Show passwords",variable=show_password,
                       command=lambda:[fields[k].configure(show="" if show_password.get() else "●") for k in ("Password","Confirm password")],
                       bg="white",fg=MUTED,activebackground="white",font=(FONT,9)).pack(anchor="w",padx=22,pady=3)
        def create():
            name=fields["Full name"].get().strip()
            email=fields["Email"].get().strip()
            password=fields["Password"].get()
            confirmation=fields["Confirm password"].get()
            if not name or "@" not in email or len(password) < 8: return messagebox.showwarning("Check details", "Enter your name, a valid email, and a password of at least 8 characters.", parent=d)
            if password != confirmation:return messagebox.showwarning("Passwords do not match","Enter the same password in both password fields.",parent=d)
            try:
                with connect() as db:
                    user_id=db.execute("INSERT INTO users(full_name,email,password_hash,role) VALUES(?,?,?,'student')", (name,email,password_hash(password))).lastrowid
                record_activity(user_id,"account_created","Created a student account")
                messagebox.showinfo("Account created", "Your student account is ready. You can now sign in.", parent=d); d.destroy()
            except sqlite3.IntegrityError: messagebox.showerror("Email already registered", "Please use a different email address.", parent=d)
        tk.Button(d, text="Create account", command=create, bg=BLUE, fg="white", relief="flat", padx=20, pady=9).pack(pady=18)

    def show_app(self, page="Dashboard"):
        self.clear()
        root = tk.Frame(self, bg=BG); root.pack(fill="both", expand=True)
        side = tk.Frame(root, bg="#17253d", width=225); side.pack(side="left", fill="y"); side.pack_propagate(False)
        tk.Label(side, text="◈  LearnSphere", bg="#17253d", fg="white", font=(FONT, 17, "bold")).pack(anchor="w", padx=20, pady=(24, 3))
        tk.Label(side, text="LEARNING MANAGEMENT", bg="#17253d", fg="#8293ad", font=(FONT, 8, "bold")).pack(anchor="w", padx=22, pady=(2, 25))
        nav = ["Dashboard", "Course Catalog", "My Learning", "Learning Materials", "Learning History", "Assignments", "Assessments", "Certificates"]
        if self.user["role"] in ("admin", "instructor"): nav += ["Manage Courses", "Students", "Reports"]
        for item in nav:
            active = page == item
            tk.Button(side, text=("●  " if active else "○  ")+item, anchor="w", command=lambda p=item:self.show_app(p), bg="#29405e" if active else "#17253d", fg="white" if active else "#bfcbdb", relief="flat", font=(FONT, 10, "bold" if active else "normal"), padx=18, pady=11, cursor="hand2", activebackground="#29405e", activeforeground="white").pack(fill="x", padx=10, pady=2)
        tk.Label(side, text="DATABASE  •  SQLITE", bg="#17253d", fg="#7789a3", font=(FONT, 8, "bold")).pack(side="bottom", anchor="w", padx=20, pady=20)
        main = tk.Frame(root, bg=BG); main.pack(side="left", fill="both", expand=True)
        top = tk.Frame(main, bg="white", height=66); top.pack(fill="x"); top.pack_propagate(False)
        tk.Label(top, text="E-Learning Management System", bg="white", fg=MUTED, font=(FONT, 10)).pack(side="left", padx=26)
        tk.Label(top, text=f"{self.user['full_name']}  ·  {self.user['role'].title()}", bg="white", fg=INK, font=(FONT, 10, "bold")).pack(side="right", padx=(8,22))
        tk.Button(top, text="↪  Sign out", command=self.sign_out, bg="white", fg=BLUE, relief="flat", cursor="hand2", font=(FONT, 9, "bold")).pack(side="right")
        self.content = tk.Frame(main, bg=BG); self.content.pack(fill="both", expand=True, padx=26, pady=22)
        getattr(self, "page_"+page.lower().replace(" ","_"))()

    def sign_out(self):
        if self.user:
            record_activity(self.user["id"], "signed_out", "Signed out")
        self.user = None
        self.show_login()

    def heading(self, title, subtitle):
        tk.Label(self.content, text=title, bg=BG, fg=INK, font=(FONT, 23, "bold")).pack(anchor="w")
        tk.Label(self.content, text=subtitle, bg=BG, fg=MUTED, font=(FONT, 10)).pack(anchor="w", pady=(4, 18))

    def metric_cards(self, items):
        row=tk.Frame(self.content,bg=BG); row.pack(fill="x",pady=(0,18))
        for title,value,note in items:
            card=tk.Frame(row,bg="white",padx=18,pady=15); card.pack(side="left",fill="both",expand=True,padx=(0,12))
            tk.Label(card,text=title.upper(),bg="white",fg=MUTED,font=(FONT,8,"bold")).pack(anchor="w")
            tk.Label(card,text=str(value),bg="white",fg=INK,font=(FONT,23,"bold")).pack(anchor="w",pady=(4,0))
            tk.Label(card,text=note,bg="white",fg=TEAL,font=(FONT,9)).pack(anchor="w")

    def page_dashboard(self):
        self.heading(f"Good day, {self.user['full_name'].split()[0]} 👋", "Here’s your learning activity at a glance.")
        uid=self.user["id"]
        with connect() as db:
            courses=db.execute("SELECT COUNT(*) n FROM courses").fetchone()["n"]
            enrolled=db.execute("SELECT COUNT(*) n FROM enrollments WHERE student_id=?",(uid,)).fetchone()["n"]
            certs=db.execute("SELECT COUNT(*) n FROM certificates WHERE student_id=?",(uid,)).fetchone()["n"]
            attempts=db.execute("SELECT COUNT(*) n FROM quiz_attempts WHERE student_id=?",(uid,)).fetchone()["n"]
            completions=db.execute("SELECT COUNT(*) n FROM course_completions WHERE student_id=?",(uid,)).fetchone()["n"]
            if self.user["role"] in ("admin","instructor"):
                students=db.execute("SELECT COUNT(*) n FROM users WHERE role='student'").fetchone()["n"]
                instructors=db.execute("SELECT COUNT(*) n FROM users WHERE role='instructor'").fetchone()["n"]
                assignments=db.execute("SELECT COUNT(*) n FROM assignments").fetchone()["n"]
                submissions=db.execute("SELECT COUNT(*) n FROM submissions").fetchone()["n"]
                self.metric_cards([("Learners",students,"Registered students"),("Instructors",instructors,"Teaching staff"),("Courses",courses,"In the catalog"),("Enrollments",db.execute("SELECT COUNT(*) n FROM enrollments").fetchone()["n"],"Across all courses")])
                self.metric_cards([("Assignments",assignments,"Published coursework"),("Submissions",submissions,"Learner work received"),("Assessment attempts",db.execute("SELECT COUNT(*) n FROM quiz_attempts").fetchone()["n"],"Quiz records"),("Materials",db.execute("SELECT COUNT(*) n FROM learning_materials").fetchone()["n"],"Course resources")])
            else: self.metric_cards([("My courses",enrolled,"Courses enrolled"),("Assessments",attempts,"Attempts submitted"),("Completed",completions,"Courses completed"),("Certificates",certs,"Achievements earned")])
            rows=db.execute("SELECT c.id,c.title,c.category,(SELECT COUNT(*) FROM lessons l WHERE l.course_id=c.id) total,(SELECT COUNT(*) FROM lesson_progress p JOIN lessons l ON l.id=p.lesson_id WHERE p.student_id=? AND l.course_id=c.id) done FROM enrollments e JOIN courses c ON c.id=e.course_id WHERE e.student_id=? ORDER BY e.enrolled_at DESC LIMIT 5",(uid,uid)).fetchall()
        card=tk.Frame(self.content,bg="white",padx=20,pady=16); card.pack(fill="both",expand=True)
        tk.Label(card,text="Continue learning",bg="white",fg=INK,font=(FONT,14,"bold")).pack(anchor="w",pady=(0,10))
        if not rows:
            tk.Label(card,text="You’re all set to get started. Browse the catalog and enroll in a course.",bg="white",fg=MUTED,font=(FONT,10)).pack(anchor="w",pady=14)
            tk.Button(card,text="Explore course catalog →",command=lambda:self.show_app("Course Catalog"),bg=BLUE,fg="white",relief="flat",padx=12,pady=8).pack(anchor="w")
        for r in rows:
            line=tk.Frame(card,bg="white"); line.pack(fill="x",pady=8)
            tk.Label(line,text="◈",bg="white",fg=BLUE,font=(FONT,20)).pack(side="left",padx=(0,12))
            mid=tk.Frame(line,bg="white"); mid.pack(side="left",fill="x",expand=True)
            tk.Label(mid,text=r["title"],bg="white",fg=INK,font=(FONT,11,"bold")).pack(anchor="w")
            tk.Label(mid,text=f"{r['category']}  ·  {r['done']} of {r['total']} lessons complete",bg="white",fg=MUTED,font=(FONT,9)).pack(anchor="w")
            tk.Button(line,text="Open course",command=lambda cid=r["id"]:self.open_course(cid),bg="#eef2ff",fg=BLUE,relief="flat",padx=12,pady=7).pack(side="right")

    def table(self, parent, columns, headings, widths=None):
        frame=tk.Frame(parent,bg="white"); frame.pack(fill="both",expand=True)
        tree=ttk.Treeview(frame,columns=columns,show="headings",selectmode="browse")
        for i,(col,heading) in enumerate(zip(columns,headings)):
            tree.heading(col,text=heading); tree.column(col,width=(widths[i] if widths else 140),anchor="w")
        y=ttk.Scrollbar(frame,orient="vertical",command=tree.yview); tree.configure(yscrollcommand=y.set)
        tree.pack(side="left",fill="both",expand=True); y.pack(side="right",fill="y")
        return tree

    def page_course_catalog(self):
        self.heading("Course Catalog", "Discover practical courses and build skills at your own pace.")
        bar=tk.Frame(self.content,bg=BG); bar.pack(fill="x",pady=(0,12))
        search=ttk.Entry(bar,width=38); search.pack(side="left",ipady=6); search.insert(0,"Search courses by title or category")
        tree=self.table(self.content,("id","title","category","instructor","duration","lessons","enrolled"),("ID","COURSE","CATEGORY","INSTRUCTOR","DURATION","LESSONS","LEARNERS"),(45,230,140,145,90,75,75))
        def load(*_):
            tree.delete(*tree.get_children()); term=search.get().strip(); term="" if term.startswith("Search courses") else term
            with connect() as db: rows=db.execute("SELECT c.id,c.title,c.category,COALESCE(u.full_name,'LearnSphere'),c.duration,(SELECT COUNT(*) FROM lessons l WHERE l.course_id=c.id),(SELECT COUNT(*) FROM enrollments e WHERE e.course_id=c.id) FROM courses c LEFT JOIN users u ON u.id=c.instructor_id WHERE c.title LIKE ? OR c.category LIKE ? ORDER BY c.id DESC",(f"%{term}%",f"%{term}%")).fetchall()
            for r in rows: tree.insert("","end",values=tuple(r))
        search.bind("<KeyRelease>",load); load()
        buttons=tk.Frame(self.content,bg=BG); buttons.pack(fill="x",pady=12)
        tk.Button(buttons,text="View course",command=lambda:self.open_course(self.selected(tree)),bg=BLUE,fg="white",relief="flat",padx=14,pady=8).pack(side="left")
        tk.Button(buttons,text="Enroll in course",command=lambda:self.enroll(self.selected(tree)),bg=TEAL,fg="white",relief="flat",padx=14,pady=8).pack(side="left",padx=8)

    def selected(self, tree):
        sel=tree.selection()
        if not sel: messagebox.showinfo("Select a row","Please select an item first.",parent=self); return None
        return tree.item(sel[0],"values")[0]

    def enroll(self, course_id):
        if not course_id:return
        with connect() as db:
            if self.user["role"]!="student": return messagebox.showinfo("Student account required","Enrollments are available for student accounts.",parent=self)
            try: db.execute("INSERT INTO enrollments(student_id,course_id) VALUES(?,?)",(self.user["id"],course_id))
            except sqlite3.IntegrityError: return messagebox.showinfo("Already enrolled","You are already enrolled in this course.",parent=self)
        with connect() as db:course_title=db.execute("SELECT title FROM courses WHERE id=?",(course_id,)).fetchone()[0]
        record_activity(self.user["id"],"enrolled",f"Enrolled in {course_title}.",course_id)
        messagebox.showinfo("Enrolled","You’re enrolled. Your course is ready in My Learning.",parent=self); self.show_app("Course Catalog")

    def page_learning_materials(self):
        is_manager = self.user["role"] in ("admin", "instructor")
        self.heading("Learning Materials", "Browse course resources and open the material linked to each course.")
        tree = self.table(self.content, ("id", "course", "title", "type", "uploaded", "url"),
                          ("ID", "COURSE", "MATERIAL", "TYPE", "UPLOADED", "RESOURCE"), (45, 230, 230, 90, 120, 300))
        def load():
            tree.delete(*tree.get_children())
            with connect() as db:
                rows = db.execute("""SELECT m.id,c.title,m.title,m.material_type,date(m.uploaded_at),COALESCE(m.material_url,'')
                    FROM learning_materials m JOIN courses c ON c.id=m.course_id
                    ORDER BY c.title,m.id""").fetchall()
            for row in rows: tree.insert("", "end", values=tuple(row))
        load()
        bar = tk.Frame(self.content, bg=BG); bar.pack(fill="x", pady=12)
        tk.Button(bar, text="Open selected resource", command=lambda:self.open_material(self.selected(tree)), bg=BLUE, fg="white", relief="flat", padx=14, pady=8).pack(side="left")
        if is_manager:
            tk.Button(bar, text="＋  Add material", command=lambda:self.material_form(load), bg=TEAL, fg="white", relief="flat", padx=14, pady=8).pack(side="left", padx=8)
            tk.Button(bar, text="Remove material", command=lambda:self.remove_material(self.selected(tree), load), bg="white", fg="#c23939", relief="solid", padx=14, pady=8).pack(side="left")

    def open_material(self, material_id):
        if not material_id: return
        with connect() as db: row = db.execute("SELECT material_url FROM learning_materials WHERE id=?", (material_id,)).fetchone()
        url = row["material_url"] if row else ""
        if not url: return messagebox.showinfo("Resource link missing", "This material does not have a URL yet.", parent=self)
        if not url.startswith(("https://", "http://", "file://")):
            return messagebox.showwarning("Invalid resource link", "Only web links and local file URLs can be opened.", parent=self)
        webbrowser.open(url)

    def material_form(self, refresh):
        with connect() as db: courses = db.execute("SELECT id,title FROM courses ORDER BY title").fetchall()
        if not courses: return messagebox.showinfo("No courses", "Create a course before adding its materials.", parent=self)
        d = tk.Toplevel(self); d.title("Add learning material"); d.configure(bg="white"); d.resizable(False, False)
        tk.Label(d, text="Course", bg="white", fg=INK).pack(anchor="w", padx=20, pady=(16, 4))
        course = ttk.Combobox(d, state="readonly", width=50, values=[f"{r['id']} · {r['title']}" for r in courses]); course.current(0); course.pack(padx=20)
        fields = []
        for label in ("Material title", "Resource URL or local file URL"):
            tk.Label(d, text=label, bg="white", fg=INK).pack(anchor="w", padx=20, pady=(12, 4))
            entry = ttk.Entry(d, width=54); entry.pack(padx=20); fields.append(entry)
        tk.Label(d, text="Material type", bg="white", fg=INK).pack(anchor="w", padx=20, pady=(12, 4))
        kind = ttk.Combobox(d, state="readonly", values=("PDF", "Video", "Link"), width=18); kind.current(0); kind.pack(anchor="w", padx=20)
        def save():
            title, url = (field.get().strip() for field in fields)
            if not title: return messagebox.showwarning("Missing title", "Enter a material title.", parent=d)
            cid = int(course.get().split(" · ", 1)[0])
            try:
                with connect() as db: db.execute("INSERT INTO learning_materials(course_id,title,material_type,material_url) VALUES(?,?,?,?)", (cid,title,kind.get(),url or None))
            except sqlite3.IntegrityError as exc: return messagebox.showerror("Could not save", str(exc), parent=d)
            d.destroy(); refresh()
        tk.Button(d, text="Save material", command=save, bg=BLUE, fg="white", relief="flat", padx=14, pady=8).pack(pady=16)

    def remove_material(self, material_id, refresh):
        if not material_id: return
        with connect() as db: db.execute("DELETE FROM learning_materials WHERE id=?", (material_id,))
        refresh()

    def page_my_learning(self):
        self.heading("My Learning", "Your enrolled courses, lesson progress, and next steps.")
        tree=self.table(self.content,("id","title","category","progress","lessons","status","enrolled"),("ID","COURSE","CATEGORY","PROGRESS","LESSONS","STATUS","ENROLLED ON"),(45,210,125,90,75,150,130))
        with connect() as db: rows=db.execute("""SELECT c.id,c.title,c.category,COUNT(l.id) total,COUNT(p.lesson_id) done,
            e.enrolled_at,COALESCE(date(cc.completed_at),'In progress') status
            FROM enrollments e JOIN courses c ON c.id=e.course_id
            LEFT JOIN lessons l ON l.course_id=c.id
            LEFT JOIN lesson_progress p ON p.lesson_id=l.id AND p.student_id=e.student_id
            LEFT JOIN course_completions cc ON cc.student_id=e.student_id AND cc.course_id=c.id
            WHERE e.student_id=? GROUP BY c.id ORDER BY e.enrolled_at DESC""",(self.user["id"],)).fetchall()
        for r in rows: tree.insert("","end",values=(r["id"],r["title"],r["category"],f"{int(100*r['done']/r['total']) if r['total'] else 0}%",f"{r['done']}/{r['total']}",r["status"],r["enrolled_at"][:10]))
        tk.Button(self.content,text="Open selected course",command=lambda:self.open_course(self.selected(tree)),bg=BLUE,fg="white",relief="flat",padx=14,pady=8).pack(anchor="w",pady=12)

    def page_learning_history(self):
        is_student=self.user["role"]=="student"
        self.heading("My Learning History" if is_student else "Learning History",
                     "A dated record of your learning activity and achievements." if is_student else "Audit trail of account, course, assessment, and assignment activity.")
        if is_student:
            tree=self.table(self.content,("date","event","course","details"),("DATE / TIME","ACTIVITY","COURSE","DETAILS"),(175,160,235,450))
            with connect() as db:
                rows=db.execute("""SELECT h.occurred_at,h.event_type,COALESCE(c.title,'—'),h.summary
                    FROM activity_history h LEFT JOIN courses c ON c.id=h.course_id
                    WHERE h.user_id=? ORDER BY h.occurred_at DESC,h.id DESC""",(self.user["id"],)).fetchall()
            for r in rows:tree.insert("","end",values=(r[0],r[1].replace("_"," ").title(),r[2],r[3]))
        else:
            tree=self.table(self.content,("date","user","role","event","course","details"),("DATE / TIME","USER","ROLE","ACTIVITY","COURSE","DETAILS"),(160,170,90,150,200,330))
            with connect() as db:
                rows=db.execute("""SELECT h.occurred_at,u.full_name,u.role,h.event_type,COALESCE(c.title,'—'),h.summary
                    FROM activity_history h JOIN users u ON u.id=h.user_id LEFT JOIN courses c ON c.id=h.course_id
                    ORDER BY h.occurred_at DESC,h.id DESC LIMIT 1000""").fetchall()
            for r in rows:tree.insert("","end",values=(r[0],r[1],r[2].title(),r[3].replace("_"," ").title(),r[4],r[5]))
        if not rows:
            tk.Label(self.content,text="Your activity will appear here as you learn.",bg=BG,fg=MUTED,font=(FONT,10)).pack(anchor="w",pady=12)

    def page_assignments(self):
        is_student = self.user["role"] == "student"
        self.heading("Assignments", "Submit course work and follow grading feedback." if is_student else "Create course assignments and review learner submissions.")
        tree = self.table(self.content, ("id","course","assignment","due","points","submitted","grade"),
                          ("ID","COURSE","ASSIGNMENT","DUE DATE","POINTS","STATUS / SUBMISSIONS","GRADE"),
                          (45,190,210,110,75,150,85))
        if is_student:
            with connect() as db:
                rows = db.execute("""SELECT a.id,c.title,a.title,a.due_date,a.points,
                    COALESCE(s.status,'Not submitted'),
                    CASE WHEN s.grade IS NULL THEN '—' ELSE CAST(s.grade AS TEXT)||'/'||a.points END
                    FROM enrollments e JOIN assignments a ON a.course_id=e.course_id
                    JOIN courses c ON c.id=a.course_id
                    LEFT JOIN submissions s ON s.assignment_id=a.id AND s.student_id=e.student_id
                    WHERE e.student_id=? ORDER BY a.due_date IS NULL,a.due_date""", (self.user["id"],)).fetchall()
            for r in rows: tree.insert("","end",values=tuple(r))
            bar=tk.Frame(self.content,bg=BG);bar.pack(fill="x",pady=12)
            tk.Button(bar,text="View instructions",command=lambda:self.student_assignment(self.selected(tree),submit=False),bg="white",fg=INK,relief="solid",padx=12,pady=8).pack(side="left")
            tk.Button(bar,text="Submit / update work",command=lambda:self.student_assignment(self.selected(tree),submit=True),bg=BLUE,fg="white",relief="flat",padx=12,pady=8).pack(side="left",padx=8)
        else:
            with connect() as db:
                rows=db.execute("""SELECT a.id,c.title,a.title,COALESCE(a.due_date,'—'),a.points,
                    (SELECT COUNT(*) FROM submissions s WHERE s.assignment_id=a.id),
                    (SELECT COUNT(*) FROM submissions s WHERE s.assignment_id=a.id AND s.status='graded')
                    FROM assignments a JOIN courses c ON c.id=a.course_id ORDER BY a.id DESC""").fetchall()
            for r in rows: tree.insert("","end",values=(r[0],r[1],r[2],r[3],r[4],f"{r[5]} submitted",f"{r[6]} graded"))
            bar=tk.Frame(self.content,bg=BG);bar.pack(fill="x",pady=12)
            tk.Button(bar,text="＋  Add assignment",command=lambda:self.assignment_form(refresh=lambda:self.show_app("Assignments")),bg=BLUE,fg="white",relief="flat",padx=12,pady=8).pack(side="left")
            tk.Button(bar,text="Edit",command=lambda:self.assignment_form(self.selected(tree),lambda:self.show_app("Assignments")),bg="white",fg=INK,relief="solid",padx=12,pady=8).pack(side="left",padx=8)
            tk.Button(bar,text="Delete",command=lambda:self.delete_assignment(self.selected(tree)),bg="white",fg="#c23939",relief="solid",padx=12,pady=8).pack(side="left")
            tk.Button(bar,text="Review submissions",command=lambda:self.review_submissions(self.selected(tree)),bg=TEAL,fg="white",relief="flat",padx=12,pady=8).pack(side="right")

    def student_assignment(self, assignment_id, submit=False):
        if not assignment_id:return
        with connect() as db:
            a=db.execute("""SELECT a.*,c.title course FROM assignments a JOIN courses c ON c.id=a.course_id
                JOIN enrollments e ON e.course_id=a.course_id WHERE a.id=? AND e.student_id=?""",
                (assignment_id,self.user["id"])).fetchone()
            old=db.execute("SELECT * FROM submissions WHERE assignment_id=? AND student_id=?",(assignment_id,self.user["id"])).fetchone()
        if not a:return messagebox.showerror("Assignment unavailable","You are not enrolled in this assignment's course.",parent=self)
        d=tk.Toplevel(self);d.title(a["title"]);d.geometry("650x530");d.configure(bg="white")
        tk.Label(d,text=a["title"],bg="white",fg=INK,font=(FONT,18,"bold"),wraplength=600).pack(anchor="w",padx=22,pady=(20,4))
        tk.Label(d,text=f"{a['course']}  ·  Due {a['due_date'] or 'No due date'}  ·  {a['points']} points",bg="white",fg=MUTED,font=(FONT,10)).pack(anchor="w",padx=22,pady=(0,12))
        tk.Label(d,text="INSTRUCTIONS",bg="white",fg=MUTED,font=(FONT,9,"bold")).pack(anchor="w",padx=22)
        tk.Message(d,text=a["instructions"] or "No additional instructions.",bg="white",fg=INK,font=(FONT,10),width=600,justify="left").pack(anchor="w",padx=22,pady=8)
        if old:
            grade=f"{old['grade']}/{a['points']}" if old["grade"] is not None else "Not graded yet"
            tk.Label(d,text=f"Submission status: {old['status']}  ·  Grade: {grade}",bg="white",fg=TEAL,font=(FONT,10,"bold")).pack(anchor="w",padx=22,pady=5)
            if old["feedback"]:tk.Message(d,text=f"Instructor feedback: {old['feedback']}",bg="white",fg=INK,font=(FONT,10),width=600,justify="left").pack(anchor="w",padx=22,pady=4)
        if submit:
            tk.Label(d,text="YOUR SUBMISSION",bg="white",fg=MUTED,font=(FONT,9,"bold")).pack(anchor="w",padx=22,pady=(10,3))
            body=tk.Text(d,height=9,wrap="word",font=(FONT,10),relief="solid",borderwidth=1);body.pack(fill="both",expand=True,padx=22)
            if old:body.insert("1.0",old["content"])
            def save():
                content=body.get("1.0","end-1c").strip()
                if not content:return messagebox.showwarning("Submission required","Write your response before submitting.",parent=d)
                with connect() as db:
                    db.execute("""INSERT INTO submissions(assignment_id,student_id,content,submitted_at,grade,feedback,status)
                        VALUES(?,?,?,CURRENT_TIMESTAMP,NULL,NULL,'submitted') ON CONFLICT(assignment_id,student_id)
                        DO UPDATE SET content=excluded.content,submitted_at=CURRENT_TIMESTAMP,grade=NULL,feedback=NULL,status='submitted'""",
                        (assignment_id,self.user["id"],content))
                record_activity(self.user["id"],"assignment_submitted",f"Submitted assignment: {a['title']}.",a["course_id"])
                d.destroy();messagebox.showinfo("Submitted","Your assignment was submitted.",parent=self);self.show_app("Assignments")
            tk.Button(d,text="Submit assignment",command=save,bg=BLUE,fg="white",relief="flat",padx=14,pady=8).pack(anchor="e",padx=22,pady=12)

    def assignment_form(self, assignment_id=None, refresh=None):
        old=None
        with connect() as db:
            courses=db.execute("SELECT id,title FROM courses ORDER BY title").fetchall()
            if assignment_id:old=db.execute("SELECT * FROM assignments WHERE id=?",(assignment_id,)).fetchone()
        if not courses:return messagebox.showinfo("No courses","Create a course before adding an assignment.",parent=self)
        d=tk.Toplevel(self);d.title("Edit assignment" if old else "New assignment");d.geometry("560x590");d.configure(bg="white")
        tk.Label(d,text="Course",bg="white",fg=INK,font=(FONT,9,"bold")).pack(anchor="w",padx=20,pady=(16,3))
        course_combo=ttk.Combobox(d,state="readonly",width=55,values=[f"{c['id']} · {c['title']}" for c in courses]);course_combo.pack(padx=20,anchor="w")
        selected_course=next((i for i,c in enumerate(courses) if old and c["id"]==old["course_id"]),0);course_combo.current(selected_course)
        tk.Label(d,text="Assignment title",bg="white",fg=INK,font=(FONT,9,"bold")).pack(anchor="w",padx=20,pady=(12,3));title=ttk.Entry(d,width=58);title.pack(padx=20,anchor="w");title.insert(0,old["title"] if old else "")
        row=tk.Frame(d,bg="white");row.pack(fill="x",padx=20,pady=(12,3))
        tk.Label(row,text="Due date (YYYY-MM-DD)",bg="white",fg=INK,font=(FONT,9,"bold")).pack(side="left")
        tk.Label(row,text="Points",bg="white",fg=INK,font=(FONT,9,"bold")).pack(side="left",padx=(35,0))
        row2=tk.Frame(d,bg="white");row2.pack(fill="x",padx=20)
        due=ttk.Entry(row2,width=24);due.pack(side="left");due.insert(0,old["due_date"] if old and old["due_date"] else "")
        points=ttk.Entry(row2,width=10);points.pack(side="left",padx=(38,0));points.insert(0,str(old["points"] if old else 100))
        tk.Label(d,text="Instructions",bg="white",fg=INK,font=(FONT,9,"bold")).pack(anchor="w",padx=20,pady=(12,3))
        instructions=tk.Text(d,width=62,height=12,wrap="word",font=(FONT,10));instructions.pack(padx=20)
        if old:instructions.insert("1.0",old["instructions"])
        def save():
            name=title.get().strip();date=due.get().strip()
            if not name:return messagebox.showwarning("Title required","Enter an assignment title.",parent=d)
            if date:
                try:datetime.strptime(date,"%Y-%m-%d")
                except ValueError:return messagebox.showwarning("Invalid date","Use YYYY-MM-DD for the due date.",parent=d)
            try:score=int(points.get())
            except ValueError:return messagebox.showwarning("Invalid points","Points must be a positive whole number.",parent=d)
            if score<=0:return messagebox.showwarning("Invalid points","Points must be a positive whole number.",parent=d)
            course_id=int(course_combo.get().split(" · ",1)[0])
            with connect() as db:
                if old:db.execute("UPDATE assignments SET course_id=?,title=?,instructions=?,due_date=?,points=? WHERE id=?",(course_id,name,instructions.get("1.0","end-1c").strip(),date or None,score,assignment_id))
                else:db.execute("INSERT INTO assignments(course_id,title,instructions,due_date,points) VALUES(?,?,?,?,?)",(course_id,name,instructions.get("1.0","end-1c").strip(),date or None,score))
            d.destroy()
            if refresh:refresh()
        tk.Button(d,text="Save assignment",command=save,bg=BLUE,fg="white",relief="flat",padx=14,pady=8).pack(anchor="e",padx=20,pady=14)

    def delete_assignment(self, assignment_id):
        if not assignment_id:return
        if messagebox.askyesno("Delete assignment","Delete this assignment and all learner submissions?",parent=self):
            with connect() as db:db.execute("DELETE FROM assignments WHERE id=?",(assignment_id,))
            self.show_app("Assignments")

    def review_submissions(self, assignment_id):
        if not assignment_id:return
        with connect() as db:a=db.execute("SELECT * FROM assignments WHERE id=?",(assignment_id,)).fetchone()
        if not a:return
        d=tk.Toplevel(self);d.title(f"Submissions — {a['title']}");d.geometry("900x550");d.configure(bg=BG)
        tk.Label(d,text=a["title"],bg=BG,fg=INK,font=(FONT,18,"bold")).pack(anchor="w",padx=20,pady=15)
        tree=self.table(d,("id","student","email","submitted","status","grade"),("ID","STUDENT","EMAIL","SUBMITTED","STATUS","GRADE"),(45,180,230,160,100,100))
        def load():
            tree.delete(*tree.get_children())
            with connect() as db:rows=db.execute("SELECT s.id,u.full_name,u.email,s.submitted_at,s.status,COALESCE(CAST(s.grade AS TEXT)||'/'||?,'—') FROM submissions s JOIN users u ON u.id=s.student_id WHERE s.assignment_id=? ORDER BY s.submitted_at DESC",(a["points"],assignment_id)).fetchall()
            for r in rows:tree.insert("","end",values=tuple(r))
        load();bar=tk.Frame(d,bg=BG);bar.pack(fill="x",padx=20,pady=12)
        tk.Button(bar,text="Read submission",command=lambda:self.read_submission(self.selected(tree)),bg="white",fg=INK,relief="solid",padx=12,pady=8).pack(side="left")
        tk.Button(bar,text="Grade selected",command=lambda:self.grade_submission(self.selected(tree),a["points"],load),bg=TEAL,fg="white",relief="flat",padx=12,pady=8).pack(side="left",padx=8)

    def read_submission(self, submission_id):
        if not submission_id:return
        with connect() as db:r=db.execute("SELECT u.full_name,a.title,s.content FROM submissions s JOIN users u ON u.id=s.student_id JOIN assignments a ON a.id=s.assignment_id WHERE s.id=?",(submission_id,)).fetchone()
        d=tk.Toplevel(self);d.title(f"Submission — {r['full_name']}");d.geometry("650x480");d.configure(bg="white")
        tk.Label(d,text=r["title"],bg="white",fg=INK,font=(FONT,17,"bold"),wraplength=600).pack(anchor="w",padx=20,pady=(18,5))
        tk.Label(d,text=f"Submitted by {r['full_name']}",bg="white",fg=MUTED,font=(FONT,10)).pack(anchor="w",padx=20,pady=(0,12))
        body=tk.Text(d,wrap="word",font=(FONT,10),relief="flat",bg="#f4f7fb");body.pack(fill="both",expand=True,padx=20,pady=(0,20));body.insert("1.0",r["content"]);body.configure(state="disabled")

    def grade_submission(self, submission_id, max_points, refresh):
        if not submission_id:return
        with connect() as db:r=db.execute("SELECT * FROM submissions WHERE id=?",(submission_id,)).fetchone()
        d=tk.Toplevel(self);d.title("Grade submission");d.configure(bg="white");d.resizable(False,False)
        tk.Label(d,text=f"Grade (0–{max_points})",bg="white",fg=INK,font=(FONT,10,"bold")).pack(anchor="w",padx=20,pady=(16,3))
        grade=ttk.Entry(d,width=20);grade.pack(anchor="w",padx=20);grade.insert(0,str(r["grade"] if r["grade"] is not None else ""))
        tk.Label(d,text="Feedback for student",bg="white",fg=INK,font=(FONT,10,"bold")).pack(anchor="w",padx=20,pady=(12,3))
        feedback=tk.Text(d,width=48,height=6,wrap="word");feedback.pack(padx=20);feedback.insert("1.0",r["feedback"] or "")
        def save():
            try:value=int(grade.get())
            except ValueError:return messagebox.showwarning("Grade required","Enter a whole-number grade.",parent=d)
            if not 0<=value<=max_points:return messagebox.showwarning("Grade out of range",f"Grade must be between 0 and {max_points}.",parent=d)
            note=feedback.get("1.0","end-1c").strip()
            with connect() as db:db.execute("UPDATE submissions SET grade=?,feedback=?,status='graded' WHERE id=?",(value,note,submission_id))
            with connect() as db:
                info=db.execute("SELECT s.student_id,a.course_id,a.title FROM submissions s JOIN assignments a ON a.id=s.assignment_id WHERE s.id=?",(submission_id,)).fetchone()
            record_activity(info["student_id"],"assignment_graded",f"{info['title']} graded {value}/{max_points}."+(f" Feedback: {note}" if note else ""),info["course_id"],actor_id=self.user["id"])
            d.destroy();refresh()
        tk.Button(d,text="Save grade",command=save,bg=TEAL,fg="white",relief="flat",padx=14,pady=8).pack(anchor="e",padx=20,pady=14)

    def open_course(self, course_id):
        if not course_id:return
        with connect() as db:
            course=db.execute("SELECT * FROM courses WHERE id=?",(course_id,)).fetchone()
            lessons=db.execute("SELECT l.*,EXISTS(SELECT 1 FROM lesson_progress p WHERE p.lesson_id=l.id AND p.student_id=?) done FROM lessons l WHERE course_id=? ORDER BY position",(self.user["id"],course_id)).fetchall()
            enrolled=db.execute("SELECT 1 FROM enrollments WHERE student_id=? AND course_id=?",(self.user["id"],course_id)).fetchone()
        d=tk.Toplevel(self); d.title(course["title"]); d.geometry("660x570"); d.configure(bg=BG)
        tk.Label(d,text=course["title"],bg=BG,fg=INK,font=(FONT,20,"bold"),wraplength=600).pack(anchor="w",padx=24,pady=(22,4))
        tk.Label(d,text=f"{course['category']}  ·  {course['duration']}",bg=BG,fg=MUTED,font=(FONT,10)).pack(anchor="w",padx=24)
        tk.Label(d,text=course["description"],bg=BG,fg=INK,font=(FONT,10),wraplength=600,justify="left").pack(anchor="w",padx=24,pady=14)
        tk.Label(d,text="COURSE CONTENT",bg=BG,fg=MUTED,font=(FONT,9,"bold")).pack(anchor="w",padx=24,pady=(4,8))
        box=tk.Frame(d,bg="white",padx=14,pady=10); box.pack(fill="both",expand=True,padx=24)
        for l in lessons:
            row=tk.Frame(box,bg="white"); row.pack(fill="x",pady=5)
            tk.Label(row,text=("✓" if l["done"] else "○"),bg="white",fg=TEAL if l["done"] else MUTED,font=(FONT,15,"bold")).pack(side="left",padx=(0,10))
            tk.Label(row,text=f"{l['position']:02d}  {l['title']}",bg="white",fg=INK,font=(FONT,10,"bold")).pack(side="left")
            tk.Button(row,text="Open",command=lambda lesson=dict(l):self.lesson_dialog(lesson,d),bg="#eef2ff",fg=BLUE,relief="flat",padx=9).pack(side="right")
        bottom=tk.Frame(d,bg=BG); bottom.pack(fill="x",padx=24,pady=14)
        if self.user["role"]=="student" and not enrolled: tk.Button(bottom,text="Enroll now",command=lambda:(d.destroy(),self.enroll(course_id)),bg=TEAL,fg="white",relief="flat",padx=15,pady=8).pack(side="left")
        elif enrolled:
            tk.Button(bottom,text="Take assessment",command=lambda:self.take_quiz(course_id),bg=BLUE,fg="white",relief="flat",padx=14,pady=8).pack(side="left")
            tk.Button(bottom,text="Mark all lessons complete",command=lambda:self.complete_all(course_id,d),bg="white",fg=INK,relief="solid",padx=12,pady=8).pack(side="left",padx=8)

    def lesson_dialog(self, lesson, parent):
        with connect() as db: enrolled=db.execute("SELECT 1 FROM enrollments WHERE student_id=? AND course_id=?",(self.user["id"],lesson["course_id"])).fetchone()
        if not enrolled and self.user["role"]=="student": return messagebox.showinfo("Enroll first","Enroll in this course to access lessons.",parent=parent)
        d=tk.Toplevel(parent); d.title(lesson["title"]); d.geometry("540x390"); d.configure(bg="white")
        tk.Label(d,text=lesson["title"],bg="white",fg=INK,font=(FONT,18,"bold")).pack(anchor="w",padx=22,pady=(22,12))
        tk.Message(d,text=lesson["content"],bg="white",fg=INK,font=(FONT,11),width=490,justify="left").pack(anchor="w",padx=22,pady=10)
        if self.user["role"]=="student": tk.Button(d,text="✓  Mark lesson complete",command=lambda:(self.mark_lesson(lesson["id"]),d.destroy(),parent.destroy(),self.open_course(lesson["course_id"])),bg=TEAL,fg="white",relief="flat",padx=15,pady=9).pack(anchor="w",padx=22,pady=18)

    def mark_lesson(self, lesson_id):
        with connect() as db:
            cursor=db.execute("INSERT OR IGNORE INTO lesson_progress(student_id,lesson_id) VALUES(?,?)",(self.user["id"],lesson_id))
            lesson=db.execute("SELECT title,course_id FROM lessons WHERE id=?",(lesson_id,)).fetchone()
        if cursor.rowcount:
            record_activity(self.user["id"],"lesson_completed",f"Completed lesson: {lesson['title']}.",lesson["course_id"])

    def complete_all(self, course_id, parent):
        with connect() as db:
            pending=db.execute("""SELECT l.id,l.title FROM lessons l LEFT JOIN lesson_progress p
                ON p.lesson_id=l.id AND p.student_id=? WHERE l.course_id=? AND p.lesson_id IS NULL""",
                (self.user["id"],course_id)).fetchall()
            db.execute("INSERT OR IGNORE INTO lesson_progress(student_id,lesson_id) SELECT ?,id FROM lessons WHERE course_id=?",(self.user["id"],course_id))
            title=db.execute("SELECT title FROM courses WHERE id=?",(course_id,)).fetchone()[0]
        for lesson in pending:
            record_activity(self.user["id"],"lesson_completed",f"Completed lesson: {lesson['title']}.",course_id)
        if pending:
            record_activity(self.user["id"],"course_lessons_completed",f"Completed all lessons in {title}.",course_id)
        messagebox.showinfo("Progress saved","All course lessons are marked complete.",parent=parent); parent.destroy(); self.open_course(course_id)

    def page_assessments(self):
        self.heading("Assessments", "Check your understanding and track your results.")
        tree=self.table(self.content,("course_id","course","quiz","attempts","best"),("COURSE ID","COURSE","ASSESSMENT","ATTEMPTS","BEST SCORE"),(90,260,280,100,100))
        with connect() as db:
            rows=db.execute("SELECT c.id,c.title,q.title quiz,(SELECT COUNT(*) FROM quiz_attempts a WHERE a.quiz_id=q.id AND a.student_id=?) attempts,(SELECT MAX(score) FROM quiz_attempts a WHERE a.quiz_id=q.id AND a.student_id=?) best FROM enrollments e JOIN courses c ON c.id=e.course_id JOIN quizzes q ON q.course_id=c.id WHERE e.student_id=?",(self.user["id"],self.user["id"],self.user["id"])).fetchall()
        for r in rows:tree.insert("","end",values=(r["id"],r["title"],r["quiz"],r["attempts"],f"{r['best']}%" if r["best"] is not None else "—"))
        tk.Button(self.content,text="Start selected assessment",command=lambda:self.take_quiz(self.selected(tree)),bg=BLUE,fg="white",relief="flat",padx=14,pady=8).pack(anchor="w",pady=12)

    def take_quiz(self, course_id):
        if not course_id:return
        with connect() as db:
            q=db.execute("SELECT * FROM quizzes WHERE course_id=?",(course_id,)).fetchone()
            questions=db.execute("SELECT * FROM questions WHERE quiz_id=? ORDER BY position",(q["id"],)).fetchall() if q else []
            total=db.execute("SELECT COUNT(*) FROM lessons WHERE course_id=?",(course_id,)).fetchone()[0]
            done=db.execute("SELECT COUNT(*) FROM lesson_progress p JOIN lessons l ON l.id=p.lesson_id WHERE p.student_id=? AND l.course_id=?",(self.user["id"],course_id)).fetchone()[0]
        if not q or not questions:return messagebox.showinfo("No assessment","This course does not have an assessment yet.",parent=self)
        if done<total:return messagebox.showinfo("Finish the lessons first",f"Complete all {total} lessons before taking the assessment ({done}/{total} complete).",parent=self)
        d=tk.Toplevel(self); d.title(q["title"]); d.geometry("680x680"); d.configure(bg=BG)
        tk.Label(d,text=q["title"],bg=BG,fg=INK,font=(FONT,19,"bold")).pack(anchor="w",padx=22,pady=(18,4))
        toolbar=tk.Frame(d,bg=BG);toolbar.pack(fill="x",padx=22,pady=(0,8))
        hint=tk.Label(toolbar,text=f"{len(questions)} questions  ·  Pass mark {q['pass_mark']}%  ·  Scroll down to see all questions",bg=BG,fg=MUTED,font=(FONT,10));hint.pack(side="left")
        def exit_assessment():
            if any(v.get() for v in answers) and not messagebox.askyesno("Exit assessment?","Your current answers will be discarded. Exit without submitting?",parent=d):return
            d.destroy()
        def sign_out():
            if not messagebox.askyesno("Sign out?","Your current answers will be discarded and you will be signed out.",parent=d):return
            d.destroy();self.sign_out()
        tk.Button(toolbar,text="Exit assessment",command=exit_assessment,bg="white",fg=INK,relief="solid",padx=9,pady=5,font=(FONT,9)).pack(side="right",padx=(6,0))
        tk.Button(toolbar,text="Sign out",command=sign_out,bg="white",fg="#b33b45",relief="solid",padx=9,pady=5,font=(FONT,9,"bold")).pack(side="right")
        canvas=tk.Canvas(d,bg=BG,highlightthickness=0); sb=ttk.Scrollbar(d,orient="vertical",command=canvas.yview); inner=tk.Frame(canvas,bg=BG)
        inner.bind("<Configure>",lambda e:canvas.configure(scrollregion=canvas.bbox("all"))); canvas.create_window((0,0),window=inner,anchor="nw",width=620); canvas.configure(yscrollcommand=sb.set); canvas.pack(side="left",fill="both",expand=True,padx=(20,0)); sb.pack(side="right",fill="y",padx=(0,10))
        d.bind_all("<MouseWheel>",lambda event:canvas.yview_scroll(int(-event.delta/120),"units"))
        d.bind("<Destroy>",lambda event:d.unbind_all("<MouseWheel>") if event.widget is d else None,add="+")
        d.protocol("WM_DELETE_WINDOW",exit_assessment)
        d.bind("<Escape>",lambda event:exit_assessment())
        answers=[]
        for i,qu in enumerate(questions,1):
            card=tk.Frame(inner,bg="white",padx=14,pady=11); card.pack(fill="x",pady=6)
            tk.Label(card,text=f"{i}.  {qu['prompt']}",bg="white",fg=INK,font=(FONT,10,"bold"),wraplength=570,justify="left").pack(anchor="w")
            var=tk.StringVar(); answers.append(var)
            for letter in "ABCD": tk.Radiobutton(card,text=f"{letter}.  {qu['option_'+letter.lower()]}",variable=var,value=letter,bg="white",activebackground="white",fg=INK,font=(FONT,9),anchor="w").pack(fill="x",anchor="w",pady=2)
        def submit():
            if any(not v.get() for v in answers):return messagebox.showwarning("Incomplete","Answer every question before submitting.",parent=d)
            score=round(100*sum(v.get()==qu["answer"] for v,qu in zip(answers,questions))/len(questions)); passed=score>=q["pass_mark"]
            with connect() as db: db.execute("INSERT INTO quiz_attempts(student_id,quiz_id,score,passed) VALUES(?,?,?,?)",(self.user["id"],q["id"],score,int(passed)))
            record_activity(self.user["id"],"quiz_attempted",f"{q['title']}: scored {score}% ({'passed' if passed else 'not passed'}).",course_id)
            d.destroy(); messagebox.showinfo("Assessment result",f"Your score: {score}%\n"+("Congratulations — you passed!" if passed else f"You need {q['pass_mark']}% to pass. Review the lessons and try again."),parent=self)
            if passed:
                record_course_completion(self.user["id"],course_id)
                self.issue_certificate(course_id)
            self.show_app("Assessments")
        tk.Button(d,text="Submit answers",command=submit,bg=BLUE,fg="white",relief="flat",padx=14,pady=9).pack(side="bottom",anchor="e",padx=22,pady=12)

    def issue_certificate(self,course_id):
        code=None
        with connect() as db:
            existing=db.execute("SELECT 1 FROM certificates WHERE student_id=? AND course_id=?",(self.user["id"],course_id)).fetchone()
            if not existing:
                code="LS-"+secrets.token_hex(5).upper()
                db.execute("INSERT INTO certificates(student_id,course_id,certificate_code) VALUES(?,?,?)",(self.user["id"],course_id,code))
        if code:
            record_activity(self.user["id"],"certificate_issued",f"Certificate {code} issued.",course_id)

    def page_certificates(self):
        self.heading("Certificates", "Celebrate your achievements with printable course certificates.")
        tree=self.table(self.content,("id","course","code","issued"),("ID","COURSE","CERTIFICATE CODE","ISSUED ON"),(50,360,230,150))
        with connect() as db: rows=db.execute("SELECT x.id,c.title,x.certificate_code,x.issued_at FROM certificates x JOIN courses c ON c.id=x.course_id WHERE x.student_id=? ORDER BY x.issued_at DESC",(self.user["id"],)).fetchall()
        for r in rows:tree.insert("","end",values=(r["id"],r["title"],r["certificate_code"],r["issued_at"][:10]))
        tk.Button(self.content,text="Generate / open certificate",command=lambda:self.export_certificate(self.selected(tree)),bg=BLUE,fg="white",relief="flat",padx=14,pady=8).pack(anchor="w",pady=12)

    def export_certificate(self, cert_id):
        if not cert_id:return
        with connect() as db: c=db.execute("SELECT u.full_name,c.title,x.certificate_code,x.issued_at FROM certificates x JOIN users u ON u.id=x.student_id JOIN courses c ON c.id=x.course_id WHERE x.id=? AND x.student_id=?",(cert_id,self.user["id"])).fetchone()
        if not c:return
        path=Path(__file__).with_name("certificates"); path.mkdir(exist_ok=True)
        filename=path/(c["certificate_code"]+".html")
        filename.write_text(f'''<!doctype html><html><head><meta charset="utf-8"><title>LearnSphere Certificate</title><style>@page{{size:landscape;margin:0}}*{{box-sizing:border-box}}body{{margin:0;background:#eef2f8;font-family:Georgia,serif;color:#17253d}}.sheet{{width:1100px;height:760px;margin:30px auto;background:#fff;border:14px solid #17253d;outline:3px solid #c6a65b;outline-offset:-30px;padding:105px 85px;text-align:center;position:relative}}.brand{{font: bold 18px Arial;color:#315cf5;letter-spacing:3px}}h1{{font-size:50px;margin:25px 0 10px}}.sub{{font:16px Arial;color:#687891;letter-spacing:2px;text-transform:uppercase}}.name{{font-size:43px;color:#315cf5;margin:22px}}.course{{font-size:27px;margin:16px}}.foot{{position:absolute;bottom:75px;left:80px;right:80px;display:flex;justify-content:space-between;font:13px Arial;color:#687891}}@media print{{body{{background:white}}.sheet{{margin:0}}}}</style></head><body><main class="sheet"><div class="brand">◈ LEARNSPHERE</div><h1>Certificate of Completion</h1><div class="sub">This certificate is proudly presented to</div><div class="name">{html.escape(c['full_name'])}</div><div class="sub">for successfully passing the assessment for</div><div class="course">{html.escape(c['title'])}</div><div class="foot"><span>ISSUED {html.escape(c['issued_at'][:10])}</span><span>VERIFICATION CODE&nbsp;&nbsp; {html.escape(c['certificate_code'])}</span></div></main><script>window.onload=()=>window.print()</script></body></html>''',encoding="utf-8")
        webbrowser.open(filename.resolve().as_uri())
        messagebox.showinfo("Certificate generated",f"Printable certificate saved to:\n{filename}",parent=self)

    def page_manage_courses(self):
        self.heading("Manage Courses", "Create courses, organize lesson content, and maintain assessments.")
        tree=self.table(self.content,("id","title","category","duration","lessons","students"),("ID","COURSE","CATEGORY","DURATION","LESSONS","STUDENTS"),(50,280,170,120,100,100))
        def load():
            tree.delete(*tree.get_children())
            with connect() as db:rows=db.execute("SELECT c.id,c.title,c.category,c.duration,(SELECT COUNT(*) FROM lessons l WHERE l.course_id=c.id),(SELECT COUNT(*) FROM enrollments e WHERE e.course_id=c.id) FROM courses c ORDER BY c.id DESC").fetchall()
            for r in rows:tree.insert("","end",values=tuple(r))
        load(); bar=tk.Frame(self.content,bg=BG);bar.pack(fill="x",pady=12)
        tk.Button(bar,text="＋  Add course",command=lambda:self.course_form(load),bg=BLUE,fg="white",relief="flat",padx=12,pady=8).pack(side="left")
        tk.Button(bar,text="Edit course",command=lambda:self.course_form(load,self.selected(tree)),bg="white",fg=INK,relief="solid",padx=12,pady=8).pack(side="left",padx=8)
        tk.Button(bar,text="Delete course",command=lambda:self.delete_course(self.selected(tree),load),bg="white",fg="#c23939",relief="solid",padx=12,pady=8).pack(side="left")
        tk.Button(bar,text="Manage lessons & quiz",command=lambda:self.course_content(self.selected(tree)),bg="white",fg=INK,relief="solid",padx=12,pady=8).pack(side="right")

    def course_form(self, refresh, course_id=None):
        record=None
        if course_id:
            with connect() as db:record=db.execute("SELECT * FROM courses WHERE id=?",(course_id,)).fetchone()
        d=tk.Toplevel(self); d.title("Edit course" if record else "Add course"); d.configure(bg="white"); d.resizable(False,False)
        fields={}
        for label,key,value in [("Course title","title",record["title"] if record else ""),("Category","category",record["category"] if record else "General"),("Duration","duration",record["duration"] if record else "4 weeks"),("Description","description",record["description"] if record else "")]:
            tk.Label(d,text=label,bg="white",fg=INK,font=(FONT,9,"bold")).pack(anchor="w",padx=20,pady=(12,0))
            if key=="description":w=tk.Text(d,width=48,height=5,font=(FONT,10),wrap="word");w.insert("1.0",value)
            else:w=ttk.Entry(d,width=50);w.insert(0,value)
            w.pack(padx=20,pady=5);fields[key]=w
        def save():
            vals={k:(w.get("1.0","end-1c").strip() if k=="description" else w.get().strip()) for k,w in fields.items()}
            if not vals["title"]:return messagebox.showwarning("Missing title","Course title is required.",parent=d)
            with connect() as db:
                if record:db.execute("UPDATE courses SET title=?,category=?,duration=?,description=? WHERE id=?",(vals["title"],vals["category"],vals["duration"],vals["description"],course_id))
                else:db.execute("INSERT INTO courses(title,category,duration,description,instructor_id) VALUES(?,?,?,?,?)",(vals["title"],vals["category"],vals["duration"],vals["description"],self.user["id"]))
            d.destroy();refresh()
        tk.Button(d,text="Save course",command=save,bg=BLUE,fg="white",relief="flat",padx=14,pady=8).pack(pady=16)

    def delete_course(self,course_id,refresh):
        if not course_id:return
        if messagebox.askyesno("Delete course","Delete this course and its lessons, enrollments, quiz history, and certificates? This cannot be undone.",parent=self):
            with connect() as db:db.execute("DELETE FROM courses WHERE id=?",(course_id,))
            refresh()

    def course_content(self,course_id):
        if not course_id:return
        d=tk.Toplevel(self);d.title("Course content management");d.geometry("740x600");d.configure(bg=BG)
        tk.Label(d,text="Lessons & assessment",bg=BG,fg=INK,font=(FONT,19,"bold")).pack(anchor="w",padx=20,pady=18)
        tree=self.table(d,("id","position","title"),("ID","ORDER","LESSON TITLE"),(60,90,480))
        def load():
            tree.delete(*tree.get_children())
            with connect() as db:rows=db.execute("SELECT id,position,title FROM lessons WHERE course_id=? ORDER BY position",(course_id,)).fetchall()
            for r in rows:tree.insert("","end",values=tuple(r))
        load();bar=tk.Frame(d,bg=BG);bar.pack(fill="x",padx=20,pady=12)
        tk.Button(bar,text="Add lesson",command=lambda:self.lesson_form(course_id,load),bg=BLUE,fg="white",relief="flat",padx=12,pady=8).pack(side="left")
        tk.Button(bar,text="Edit lesson",command=lambda:self.lesson_form(course_id,load,self.selected(tree)),bg="white",fg=INK,relief="solid",padx=12,pady=8).pack(side="left",padx=8)
        tk.Button(bar,text="Remove lesson",command=lambda:self.remove_lesson(self.selected(tree),load),bg="white",fg="#c23939",relief="solid",padx=12,pady=8).pack(side="left")
        tk.Button(bar,text="Edit quiz questions",command=lambda:self.quiz_editor(course_id),bg="white",fg=INK,relief="solid",padx=12,pady=8).pack(side="right")

    def lesson_form(self,course_id,refresh,lesson_id=None):
        with connect() as db:old=db.execute("SELECT * FROM lessons WHERE id=?",(lesson_id,)).fetchone() if lesson_id else None
        d=tk.Toplevel(self);d.title("Lesson content");d.configure(bg="white")
        tk.Label(d,text="Lesson title",bg="white",fg=INK).pack(anchor="w",padx=18,pady=(15,3));title=ttk.Entry(d,width=55);title.pack(padx=18);title.insert(0,old["title"] if old else "")
        tk.Label(d,text="Position",bg="white",fg=INK).pack(anchor="w",padx=18,pady=(12,3));pos=ttk.Entry(d,width=12);pos.pack(anchor="w",padx=18);pos.insert(0,str(old["position"] if old else 1))
        tk.Label(d,text="Lesson text / learning notes",bg="white",fg=INK).pack(anchor="w",padx=18,pady=(12,3));body=tk.Text(d,width=55,height=10,wrap="word");body.pack(padx=18);body.insert("1.0",old["content"] if old else "")
        def save():
            try:n=int(pos.get())
            except ValueError:return messagebox.showerror("Invalid position","Position must be a whole number.",parent=d)
            if not title.get().strip():return messagebox.showwarning("Missing title","Enter a lesson title.",parent=d)
            try:
                with connect() as db:
                    if old:db.execute("UPDATE lessons SET title=?,content=?,position=? WHERE id=?",(title.get().strip(),body.get("1.0","end-1c").strip(),n,lesson_id))
                    else:db.execute("INSERT INTO lessons(course_id,title,content,position) VALUES(?,?,?,?)",(course_id,title.get().strip(),body.get("1.0","end-1c").strip(),n))
                d.destroy();refresh()
            except sqlite3.IntegrityError:messagebox.showerror("Position in use","Choose a different lesson position.",parent=d)
        tk.Button(d,text="Save lesson",command=save,bg=BLUE,fg="white",relief="flat",padx=14,pady=8).pack(pady=15)

    def remove_lesson(self,lid,refresh):
        if not lid:return
        if messagebox.askyesno("Remove lesson","Remove this lesson and its recorded progress?",parent=self):
            with connect() as db:db.execute("DELETE FROM lessons WHERE id=?",(lid,))
            refresh()

    def quiz_editor(self,course_id):
        with connect() as db:
            q=db.execute("SELECT * FROM quizzes WHERE course_id=?",(course_id,)).fetchone()
            if not q:
                qid=db.execute("INSERT INTO quizzes(course_id,title,pass_mark) VALUES(?,?,60)",(course_id,"Course assessment")).lastrowid
                q=db.execute("SELECT * FROM quizzes WHERE id=?",(qid,)).fetchone()
        d=tk.Toplevel(self);d.title("Assessment questions");d.geometry("760x650");d.configure(bg=BG)
        tk.Label(d,text="Assessment questions",bg=BG,fg=INK,font=(FONT,19,"bold")).pack(anchor="w",padx=20,pady=16)
        listbox=tk.Listbox(d,width=95,height=7,font=(FONT,10));listbox.pack(fill="x",padx=20)
        def load():
            listbox.delete(0,"end")
            with connect() as db:qs=db.execute("SELECT id,prompt,answer FROM questions WHERE quiz_id=? ORDER BY position",(q["id"],)).fetchall()
            for r in qs:listbox.insert("end",f"{r['id']}  |  {r['prompt']}  [Answer: {r['answer']}]")
        load()
        fields={}; labels=[("Question","prompt"),("Option A","a"),("Option B","b"),("Option C","c"),("Option D","d")]
        for label,key in labels:
            tk.Label(d,text=label,bg=BG,fg=INK,font=(FONT,9,"bold")).pack(anchor="w",padx=20,pady=(8,0));ent=ttk.Entry(d);ent.pack(fill="x",padx=20,pady=2);fields[key]=ent
        row=tk.Frame(d,bg=BG);row.pack(fill="x",padx=20,pady=8)
        tk.Label(row,text="Correct option:",bg=BG,fg=INK).pack(side="left");answer=ttk.Combobox(row,values=["A","B","C","D"],state="readonly",width=5);answer.set("A");answer.pack(side="left",padx=8)
        def add():
            vals=[fields[k].get().strip() for k in ("prompt","a","b","c","d")]
            if not all(vals):return messagebox.showwarning("Missing fields","Fill in the question and all four choices.",parent=d)
            with connect() as db:
                pos=db.execute("SELECT COALESCE(MAX(position),0)+1 FROM questions WHERE quiz_id=?",(q["id"],)).fetchone()[0]
                db.execute("INSERT INTO questions(quiz_id,prompt,option_a,option_b,option_c,option_d,answer,position) VALUES(?,?,?,?,?,?,?,?)",(q["id"],*vals,answer.get(),pos))
            for f in fields.values():f.delete(0,"end")
            load()
        def delete():
            if not listbox.curselection():return
            qid=int(listbox.get(listbox.curselection()[0]).split("|")[0].strip())
            with connect() as db:db.execute("DELETE FROM questions WHERE id=?",(qid,))
            load()
        tk.Button(row,text="Add question",command=add,bg=BLUE,fg="white",relief="flat",padx=12,pady=7).pack(side="left",padx=(16,0))
        tk.Button(row,text="Delete selected",command=delete,bg="white",fg="#c23939",relief="solid",padx=12,pady=7).pack(side="left",padx=8)

    def page_students(self):
        self.heading("Students", "Review registered learners, course enrollments, and assessment performance.")
        tree=self.table(self.content,("id","name","email","enrollments","attempts","average"),("ID","STUDENT","EMAIL","ENROLLMENTS","ATTEMPTS","AVG SCORE"),(55,210,250,120,100,100))
        with connect() as db:rows=db.execute("SELECT u.id,u.full_name,u.email,(SELECT COUNT(*) FROM enrollments e WHERE e.student_id=u.id),(SELECT COUNT(*) FROM quiz_attempts a WHERE a.student_id=u.id),(SELECT AVG(score) FROM quiz_attempts a WHERE a.student_id=u.id) FROM users u WHERE u.role='student' ORDER BY u.full_name").fetchall()
        for r in rows:tree.insert("","end",values=(r[0],r[1],r[2],r[3],r[4],f"{r[5]:.0f}%" if r[5] is not None else "—"))
        tk.Button(self.content,text="Remove selected student",command=lambda:self.delete_student(self.selected(tree)),bg="white",fg="#c23939",relief="solid",padx=14,pady=8).pack(anchor="w",pady=12)

    def page_reports(self):
        self.heading("Reports & exports", "Explore live database summaries and export them as CSV files.")
        reports=("Enrollment Summary","Learning Progress","Course Completions","Assessment Results","Assignment Submissions")
        bar=tk.Frame(self.content,bg=BG);bar.pack(fill="x",pady=(0,12))
        choice=ttk.Combobox(bar,values=reports,state="readonly",width=32);choice.current(0);choice.pack(side="left",ipady=5)
        tree=self.table(self.content,("c1","c2","c3","c4","c5","c6"),("COLUMN 1","COLUMN 2","COLUMN 3","COLUMN 4","COLUMN 5","COLUMN 6"),(190,190,190,160,150,210))
        report_data={}
        def load(*_):
            kind=choice.get();tree.delete(*tree.get_children())
            if kind=="Enrollment Summary":
                headers=["Student","Email","Course","Category","Instructor","Enrolled"]
                query="""SELECT u.full_name,u.email,c.title,c.category,COALESCE(i.full_name,'—'),date(e.enrolled_at)
                    FROM enrollments e JOIN users u ON u.id=e.student_id JOIN courses c ON c.id=e.course_id
                    LEFT JOIN users i ON i.id=c.instructor_id ORDER BY c.title,u.full_name"""
            elif kind=="Learning Progress":
                headers=["Student","Course","Lessons done","Total lessons","Progress","Last activity"]
                query="""SELECT u.full_name,c.title,COUNT(DISTINCT p.lesson_id),COUNT(DISTINCT l.id),
                    CASE WHEN COUNT(DISTINCT l.id)=0 THEN '0%' ELSE CAST(ROUND(100.0*COUNT(DISTINCT p.lesson_id)/COUNT(DISTINCT l.id)) AS TEXT)||'%' END,
                    COALESCE(MAX(date(p.completed_at)),'—') FROM enrollments e
                    JOIN users u ON u.id=e.student_id JOIN courses c ON c.id=e.course_id
                    LEFT JOIN lessons l ON l.course_id=c.id LEFT JOIN lesson_progress p ON p.lesson_id=l.id AND p.student_id=e.student_id
                    GROUP BY u.id,c.id ORDER BY u.full_name,c.title"""
            elif kind=="Course Completions":
                headers=["Student","Email","Course","Completed","Final score","Certificate"]
                query="""SELECT u.full_name,u.email,c.title,date(cc.completed_at),cc.final_score||'%',
                    COALESCE(cert.certificate_code,'—') FROM course_completions cc
                    JOIN users u ON u.id=cc.student_id JOIN courses c ON c.id=cc.course_id
                    LEFT JOIN certificates cert ON cert.student_id=cc.student_id AND cert.course_id=cc.course_id
                    ORDER BY cc.completed_at DESC"""
            elif kind=="Assessment Results":
                headers=["Student","Course","Assessment","Score","Result","Attempted"]
                query="""SELECT u.full_name,c.title,q.title,a.score||'%',CASE WHEN a.passed=1 THEN 'Passed' ELSE 'Needs review' END,date(a.attempted_at)
                    FROM quiz_attempts a JOIN users u ON u.id=a.student_id JOIN quizzes q ON q.id=a.quiz_id
                    JOIN courses c ON c.id=q.course_id ORDER BY a.attempted_at DESC"""
            else:
                headers=["Course","Assignment","Student","Submitted","Grade","Feedback"]
                query="""SELECT c.title,a.title,u.full_name,date(s.submitted_at),
                    CASE WHEN s.grade IS NULL THEN 'Not graded' ELSE s.grade||'/'||a.points END,COALESCE(s.feedback,'')
                    FROM submissions s JOIN assignments a ON a.id=s.assignment_id JOIN courses c ON c.id=a.course_id
                    JOIN users u ON u.id=s.student_id ORDER BY s.submitted_at DESC"""
            with connect() as db:rows=db.execute(query).fetchall()
            report_data[kind]=(headers,[tuple(r) for r in rows])
            for i,h in enumerate(headers):tree.heading(f"c{i+1}",text=h.upper())
            for r in rows:tree.insert("","end",values=tuple(r))
        choice.bind("<<ComboboxSelected>>",load);load()
        def export():
            headers,rows=report_data.get(choice.get(),([],[]))
            if not headers:return
            path=filedialog.asksaveasfilename(parent=self,defaultextension=".csv",filetypes=[("CSV files","*.csv")],initialfile=choice.get().lower().replace(" ","_")+".csv")
            if not path:return
            try:
                with open(path,"w",newline="",encoding="utf-8-sig") as f:
                    writer=csv.writer(f);writer.writerow(headers);writer.writerows(rows)
                messagebox.showinfo("Report exported",f"Saved {len(rows)} rows to:\n{path}",parent=self)
            except OSError as exc:messagebox.showerror("Export failed",f"Could not write the CSV file.\n{exc}",parent=self)
        tk.Button(bar,text="Export CSV",command=export,bg=BLUE,fg="white",relief="flat",padx=14,pady=8).pack(side="right")

    def delete_student(self,uid):
        if not uid:return
        if messagebox.askyesno("Remove student","Delete this student account and associated learning records?",parent=self):
            with connect() as db:db.execute("DELETE FROM users WHERE id=? AND role='student'",(uid,))
            self.show_app("Students")


if __name__ == "__main__":
    initialize()
    LearnSphere().mainloop()

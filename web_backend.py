"""Local LearnHub browser interface backed by the Chapter 3 SQLite schema."""
from __future__ import annotations

import json
import hashlib
import html
import os
import secrets
import sqlite3
import re
from datetime import date
from email.parser import BytesParser
from email.policy import default as email_policy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import quote, urlparse
from http.cookies import SimpleCookie
from pathlib import Path

from database import DB_FILE, connect, grade_assignment_submission, initialize_database

ROOT = Path(__file__).resolve().parent
# Override these when running behind a temporary tunnel or hosting platform.
HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8000"))
SESSIONS: dict[str, tuple[str, int]] = {}
UPLOAD_DIRECTORY = ROOT / "uploads" / "assignments"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_UPLOADS = {
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
}


def password_hash(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310_000)
    return f"{salt.hex()}${digest.hex()}"


def password_ok(password: str, stored: str) -> bool:
    try:
        salt, digest = stored.split("$")
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 310_000).hex()
        return secrets.compare_digest(actual, digest)
    except (ValueError, TypeError):
        return False


def parse_submission_form(content_type: str, body: bytes):
    message = BytesParser(policy=email_policy).parsebytes(
        b"Content-Type: " + content_type.encode("latin-1") + b"\r\nMIME-Version: 1.0\r\n\r\n" + body
    )
    if not message.is_multipart():
        raise ValueError("The assignment form could not be read.")
    fields = {}
    uploaded = None
    for part in message.iter_parts():
        name = part.get_param("name", header="content-disposition")
        filename = part.get_filename()
        value = part.get_payload(decode=True) or b""
        if name == "file":
            if filename:
                if uploaded is not None:
                    raise ValueError("Upload one document per assignment submission.")
                uploaded = (filename, value)
        elif name in ("assignment_id", "content"):
            fields[name] = value.decode(part.get_content_charset() or "utf-8", errors="replace")
    return fields, uploaded


def bootstrap(student_id: int | None = None):
    with connect() as db:
        student = db.execute("SELECT student_id id,name full_name,email,'student' role FROM Student WHERE student_id=?", (student_id,)).fetchone() if student_id else None
        if not student:
            raise RuntimeError("Student session is unavailable. Please sign in again.")
        sid = student["id"]
        courses = db.execute("""SELECT c.course_id id,c.title,c.description,c.duration_weeks,c.capacity,
            i.name instructor,e.enrollment_date enrolled_at,e.progress_status status,
            (SELECT COUNT(*) FROM Lesson l WHERE l.course_id=c.course_id) lessons,
            (SELECT COUNT(*) FROM LessonProgress p JOIN Lesson l ON l.lesson_id=p.lesson_id
             WHERE p.student_id=e.student_id AND l.course_id=c.course_id) completed_lessons,
            (SELECT COUNT(*) FROM Enrollment x WHERE x.course_id=c.course_id) enrolled_count
            FROM Enrollment e JOIN Course c ON c.course_id=e.course_id
            LEFT JOIN Instructor i ON i.instructor_id=c.instructor_id
            WHERE e.student_id=? ORDER BY e.enrollment_date DESC""", (sid,)).fetchall()
        lessons = db.execute("""SELECT l.lesson_id id,l.course_id,c.title course,l.lesson_title title,l.content,l.lesson_order position,l.duration_minutes,
            CASE WHEN p.lesson_id IS NULL THEN 0 ELSE 1 END completed
            FROM Lesson l JOIN Course c ON c.course_id=l.course_id
            JOIN Enrollment e ON e.course_id=c.course_id AND e.student_id=?
            LEFT JOIN LessonProgress p ON p.lesson_id=l.lesson_id AND p.student_id=e.student_id
            ORDER BY c.title,l.lesson_order,l.lesson_id""", (sid,)).fetchall()
        catalog = db.execute("""SELECT c.course_id id,c.title,c.description,c.duration_weeks,c.capacity,
            i.name instructor,(SELECT COUNT(*) FROM Enrollment e WHERE e.course_id=c.course_id) enrolled_count,
            EXISTS(SELECT 1 FROM Enrollment e WHERE e.course_id=c.course_id AND e.student_id=?) enrolled
            FROM Course c LEFT JOIN Instructor i ON i.instructor_id=c.instructor_id ORDER BY c.title""", (sid,)).fetchall()
        assignments = db.execute("""SELECT a.assignment_id id,a.title,c.title course,a.due_date,a.max_marks points,
            s.submission_id submission_id,s.file_name,s.file_size,
            s.submission_date submitted_at,s.score grade,s.content,s.status submission_status,
            COALESCE(s.feedback,'') feedback
            FROM Assignment a JOIN Course c ON c.course_id=a.course_id
            JOIN Enrollment e ON e.course_id=c.course_id AND e.student_id=?
            LEFT JOIN Submission s ON s.assignment_id=a.assignment_id AND s.student_id=e.student_id
            ORDER BY a.due_date,a.assignment_id""", (sid,)).fetchall()
        quizzes = []
        for quiz_row in db.execute("""SELECT q.quiz_id id,q.title,c.title course,c.course_id,q.total_marks
            FROM Quiz q JOIN Course c ON c.course_id=q.course_id
            JOIN Enrollment e ON e.course_id=c.course_id WHERE e.student_id=? ORDER BY c.title,q.title""", (sid,)).fetchall():
            quiz = dict(quiz_row)
            quiz_questions = db.execute("""SELECT question_id,prompt,option_a,option_b,option_c,option_d
                FROM QuizQuestion WHERE quiz_id=? ORDER BY question_order""", (quiz["id"],)).fetchall()
            quiz["questions"] = [dict(question) for question in quiz_questions]
            course_progress = next((course for course in courses if course["id"] == quiz["course_id"]), None)
            quiz["lessons_total"] = course_progress["lessons"] if course_progress else 0
            quiz["lessons_done"] = course_progress["completed_lessons"] if course_progress else 0
            quiz["lessons_complete"] = bool(course_progress and course_progress["lessons"] > 0 and
                                             (course_progress["completed_lessons"] == course_progress["lessons"] or
                                              course_progress["status"] == "Completed"))
            quiz["has_questions"] = bool(quiz_questions)
            quiz["can_attempt"] = quiz["lessons_complete"] and quiz["has_questions"]
            quiz.pop("course_id", None)
            quizzes.append(quiz)
        results = db.execute("""SELECT st.name student,c.title course,COALESCE(a.title,q.title) assessment,
            s.score marks,COALESCE(a.max_marks,q.total_marks) maximum,s.submission_date submitted_at,s.content,
            COALESCE(s.feedback,'') feedback
            FROM Submission s JOIN Student st ON st.student_id=s.student_id
            LEFT JOIN Assignment a ON a.assignment_id=s.assignment_id
            LEFT JOIN Quiz q ON q.quiz_id=s.quiz_id
            JOIN Course c ON c.course_id=COALESCE(a.course_id,q.course_id)
            WHERE s.student_id=? AND s.score IS NOT NULL ORDER BY s.submission_date DESC,s.submission_id DESC""", (sid,)).fetchall()
        history = db.execute("""SELECT date,event,course,details FROM (
            SELECT e.enrollment_date AS date,'enrolled' AS event,c.title AS course,
                   'Enrolled in '||c.title AS details,e.enrollment_id AS sort_id
            FROM Enrollment e JOIN Course c ON c.course_id=e.course_id WHERE e.student_id=?
            UNION ALL
            SELECT s.submission_date,'assignment_submitted',c.title,'Submitted '||COALESCE(a.title,q.title),s.submission_id
            FROM Submission s LEFT JOIN Assignment a ON a.assignment_id=s.assignment_id
            LEFT JOIN Quiz q ON q.quiz_id=s.quiz_id JOIN Course c ON c.course_id=COALESCE(a.course_id,q.course_id)
            WHERE s.student_id=?
            UNION ALL
            SELECT p.completed_at,'lesson_completed',c.title,'Completed lesson: '||l.lesson_title,p.lesson_id
            FROM LessonProgress p JOIN Lesson l ON l.lesson_id=p.lesson_id JOIN Course c ON c.course_id=l.course_id
            WHERE p.student_id=?
            ) ORDER BY date DESC,sort_id DESC LIMIT 200""", (sid,sid,sid)).fetchall()
        certificates = db.execute("""SELECT ce.certificate_id id,ce.certificate_code,ce.issue_date,c.title course
            FROM Certificate ce JOIN Enrollment e ON e.enrollment_id=ce.enrollment_id
            JOIN Course c ON c.course_id=e.course_id WHERE e.student_id=? ORDER BY ce.issue_date DESC""", (sid,)).fetchall()
        avg = db.execute("SELECT AVG(score) FROM Submission WHERE student_id=? AND score IS NOT NULL", (sid,)).fetchone()[0]
        pending = sum(1 for row in assignments if row["submitted_at"] is None)
        completed = sum(1 for row in courses if row["status"] == "Completed")
        return {"student": dict(student),
                "stats": {"enrollments": len(courses), "pending_assignments": pending,
                          "average_score": round(avg) if avg is not None else None,
                          "assessment_attempts": db.execute("SELECT COUNT(*) FROM Submission WHERE student_id=?", (sid,)).fetchone()[0],
                          "completed_courses": completed},
                "courses": [dict(row) for row in courses], "catalog": [dict(row) for row in catalog],
                "lessons": [dict(row) for row in lessons], "assignments": [dict(row) for row in assignments],
                "quizzes": [dict(row) for row in quizzes], "results": [dict(row) for row in results],
                "history": [dict(row) for row in history], "certificates": [dict(row) for row in certificates]}


def instructor_bootstrap(instructor_id: int):
    with connect() as db:
        instructor = db.execute("SELECT instructor_id id,name full_name,email,'instructor' role FROM Instructor WHERE instructor_id=?",
                                (instructor_id,)).fetchone()
        if not instructor:
            raise RuntimeError("Instructor session is unavailable. Please sign in again.")
        submissions = db.execute("""SELECT s.submission_id id,st.name student,st.email student_email,
            c.title course,a.title assignment,a.max_marks maximum,s.submission_date submitted_at,
            s.status,s.content,s.file_name,s.file_size,s.score grade,COALESCE(s.feedback,'') feedback,s.graded_at
            FROM Submission s JOIN Assignment a ON a.assignment_id=s.assignment_id
            JOIN Course c ON c.course_id=a.course_id JOIN Student st ON st.student_id=s.student_id
            WHERE c.instructor_id=? ORDER BY (s.score IS NOT NULL),s.submission_date,s.submission_id""",
                                  (instructor_id,)).fetchall()
        pending = sum(1 for row in submissions if row["grade"] is None)
        graded = len(submissions) - pending
        courses = db.execute("SELECT COUNT(*) FROM Course WHERE instructor_id=?", (instructor_id,)).fetchone()[0]
        return {"role": "instructor", "instructor": dict(instructor),
                "stats": {"courses": courses, "submissions": len(submissions),
                          "pending_grading": pending, "graded": graded},
                "submissions": [dict(row) for row in submissions]}


class Handler(BaseHTTPRequestHandler):
    server_version = "LearnHub/1.0"

    def send_json(self, payload, status=200):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def session_identity(self):
        cookie = SimpleCookie()
        cookie.load(self.headers.get("Cookie", ""))
        morsel = cookie.get("learnsphere_session")
        return SESSIONS.get(morsel.value) if morsel else None

    def session_user_id(self):
        identity = self.session_identity()
        return identity[1] if identity and identity[0] == "student" else None

    def session_instructor_id(self):
        identity = self.session_identity()
        return identity[1] if identity and identity[0] == "instructor" else None

    def set_session(self, token):
        self.send_header("Set-Cookie", f"learnsphere_session={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age=86400")

    def do_GET(self):
        route = urlparse(self.path).path
        if route == "/api/bootstrap":
            identity = self.session_identity()
            if not identity:
                return self.send_json({"error": "Please sign in to continue."}, 401)
            try:
                data = instructor_bootstrap(identity[1]) if identity[0] == "instructor" else bootstrap(identity[1])
                self.send_json(data)
            except (sqlite3.Error, RuntimeError) as exc:
                self.send_json({"error": str(exc)}, 500)
            return
        if route.startswith("/api/certificate/"):
            sid = self.session_user_id()
            if not sid:
                return self.send_json({"error": "Please sign in to view this certificate."}, 401)
            try:
                certificate_id = int(route.rsplit("/", 1)[1])
            except ValueError:
                return self.send_error(404)
            with connect() as db:
                certificate = db.execute("""SELECT s.name,c.title,ce.certificate_code,ce.issue_date
                    FROM Certificate ce JOIN Enrollment e ON e.enrollment_id=ce.enrollment_id
                    JOIN Student s ON s.student_id=e.student_id JOIN Course c ON c.course_id=e.course_id
                    WHERE ce.certificate_id=? AND e.student_id=?""", (certificate_id,sid)).fetchone()
            if not certificate:
                return self.send_error(404)
            body = f"""<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>LearnHub Certificate</title><style>body{{margin:0;background:#f1f4f9;color:#17253d;font-family:Georgia,serif}}.sheet{{max-width:900px;margin:5vh auto;background:white;border:12px double #315cf5;padding:72px 45px;text-align:center;box-shadow:0 18px 50px #17253d20}}.brand{{font:700 14px Arial;letter-spacing:4px;color:#315cf5}}h1{{font-size:38px;margin:36px 0 10px}}.sub{{font:14px Arial;color:#738199;letter-spacing:1px}}.name{{font-size:36px;color:#315cf5;margin:24px}}.course{{font-size:25px;margin:20px}}.code{{font:12px Arial;color:#738199;margin-top:45px}}button{{border:0;border-radius:7px;background:#315cf5;color:white;padding:11px 18px;font-weight:700;cursor:pointer;margin-top:26px}}@media print{{body{{background:white}}.sheet{{margin:0 auto;box-shadow:none}}button{{display:none}}}}</style></head><body><main class='sheet'><div class='brand'>LEARNHUB</div><h1>Certificate of Completion</h1><div class='sub'>This certifies that</div><div class='name'>{html.escape(certificate['name'])}</div><div class='sub'>has completed the course</div><div class='course'>{html.escape(certificate['title'])}</div><div class='code'>Issued {html.escape(certificate['issue_date'])} · Certificate code {html.escape(certificate['certificate_code'])}</div><button onclick='window.print()'>Print certificate</button></main></body></html>""".encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if route.startswith("/api/submission-file/"):
            identity = self.session_identity()
            if not identity:
                return self.send_json({"error": "Please sign in to download this submission."}, 401)
            try:
                submission_id = int(route.rsplit("/", 1)[1])
            except ValueError:
                return self.send_error(404)
            with connect() as db:
                if identity[0] == "student":
                    file_row = db.execute("""SELECT s.file_path,s.file_name,s.file_mime_type
                        FROM Submission s WHERE s.submission_id=? AND s.student_id=?""",
                                          (submission_id,identity[1])).fetchone()
                else:
                    file_row = db.execute("""SELECT s.file_path,s.file_name,s.file_mime_type
                        FROM Submission s JOIN Assignment a ON a.assignment_id=s.assignment_id
                        JOIN Course c ON c.course_id=a.course_id
                        WHERE s.submission_id=? AND c.instructor_id=?""",
                                          (submission_id,identity[1])).fetchone()
            if not file_row or not file_row["file_path"]:
                return self.send_error(404)
            upload_root = UPLOAD_DIRECTORY.resolve()
            stored_path = (ROOT / file_row["file_path"]).resolve()
            try:
                stored_path.relative_to(upload_root)
                file_bytes = stored_path.read_bytes()
            except (ValueError, OSError):
                return self.send_error(404)
            filename = re.sub(r"[\x00-\x1f\x7f]", "_", Path(file_row["file_name"]).name)
            fallback_name = re.sub(r'[^A-Za-z0-9._-]', '_', filename) or "assignment-document"
            mime_type = file_row["file_mime_type"] if file_row["file_mime_type"] in ALLOWED_UPLOADS.values() else "application/octet-stream"
            self.send_response(200)
            self.send_header("Content-Type", mime_type)
            self.send_header("Content-Length", str(len(file_bytes)))
            self.send_header("Content-Disposition", f"attachment; filename=\"{fallback_name}\"; filename*=UTF-8''{quote(filename, safe='')}")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(file_bytes)
            return
        if route == "/api/health":
            self.send_json({"ok": True, "database": DB_FILE.name})
            return
        if route == "/" or route == "/index.html":
            body = (ROOT / "index.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_error(404)

    def do_POST(self):
        route = urlparse(self.path).path
        content_type = self.headers.get("Content-Type", "")
        uploaded = None
        try:
            body_size = int(self.headers.get("Content-Length", 0))
            if body_size < 0:
                return self.send_json({"error": "Invalid request size."}, 400)
            if route == "/api/submit" and content_type.lower().startswith("multipart/form-data") and body_size > MAX_UPLOAD_BYTES + 65536:
                return self.send_json({"error": "The upload is too large. The maximum file size is 10 MB."}, 413)
            raw_body = self.rfile.read(body_size)
            if route == "/api/submit" and content_type.lower().startswith("multipart/form-data"):
                payload, uploaded = parse_submission_form(content_type, raw_body)
            else:
                payload = json.loads(raw_body or b"{}")
        except (ValueError, json.JSONDecodeError):
            message = "The assignment upload could not be read." if content_type.lower().startswith("multipart/form-data") else "Request body must be valid JSON."
            return self.send_json({"error": message}, 400)
        if route in ("/api/login", "/api/register"):
            email = str(payload.get("email", "")).strip().lower()
            password = str(payload.get("password", ""))
            role = str(payload.get("role", "student")).strip().lower()
            if role not in ("student", "instructor"):
                return self.send_json({"error": "Choose a valid account type."}, 400)
            if route == "/api/register":
                name = str(payload.get("full_name", "")).strip()
                if len(name) < 2 or "@" not in email or len(password) < 8:
                    return self.send_json({"error": "Enter your name, a valid email, and a password of at least 8 characters."}, 400)
                try:
                    with connect() as db:
                        if role == "student":
                            phone_no = str(payload.get("phone_no") or "").strip()
                            uid = db.execute("INSERT INTO Student(name,email,phone_no,password_hash) VALUES(?,?,?,?)",
                                             (name,email,phone_no or None,password_hash(password))).lastrowid
                        else:
                            account = db.execute("SELECT instructor_id,password_hash FROM Instructor WHERE email=? COLLATE NOCASE",
                                                 (email,)).fetchone()
                            if not account:
                                return self.send_json({"error": "No instructor profile uses this email. Ask the course administrator to add your instructor profile first."}, 403)
                            if account["password_hash"]:
                                return self.send_json({"error": "This instructor account is already activated. Sign in instead."}, 409)
                            uid = account["instructor_id"]
                            db.execute("UPDATE Instructor SET name=?,password_hash=? WHERE instructor_id=?",
                                       (name,password_hash(password),uid))
                except sqlite3.IntegrityError:
                    return self.send_json({"error": "That email address is already registered."}, 409)
            else:
                with connect() as db:
                    if role == "student":
                        account = db.execute("SELECT student_id id,password_hash FROM Student WHERE email=? COLLATE NOCASE", (email,)).fetchone()
                    else:
                        account = db.execute("SELECT instructor_id id,password_hash FROM Instructor WHERE email=? COLLATE NOCASE", (email,)).fetchone()
                if not account or not account["password_hash"] or not password_ok(password, account["password_hash"]):
                    return self.send_json({"error": "Email or password is incorrect."}, 401)
                uid = account["id"]
            token = secrets.token_urlsafe(32)
            SESSIONS[token] = (role, uid)
            with connect() as db:
                if role == "student":
                    user = db.execute("SELECT student_id id,name full_name,email,'student' role FROM Student WHERE student_id=?", (uid,)).fetchone()
                else:
                    user = db.execute("SELECT instructor_id id,name full_name,email,'instructor' role FROM Instructor WHERE instructor_id=?", (uid,)).fetchone()
            body = json.dumps({"ok": True, "user": dict(user)}).encode("utf-8")
            self.send_response(200 if route == "/api/login" else 201)
            self.set_session(token)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if route == "/api/logout":
            cookie = SimpleCookie(); cookie.load(self.headers.get("Cookie", ""))
            morsel = cookie.get("learnsphere_session")
            if morsel: SESSIONS.pop(morsel.value, None)
            body = json.dumps({"ok": True}).encode("utf-8")
            self.send_response(200)
            self.send_header("Set-Cookie", "learnsphere_session=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0")
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if route == "/api/enroll":
            try:
                course_id = int(payload.get("course_id"))
                sid = self.session_user_id()
                if not sid: return self.send_json({"error": "Please sign in to continue."}, 401)
                with connect() as db:
                    course = db.execute("SELECT title,capacity,(SELECT COUNT(*) FROM Enrollment WHERE course_id=Course.course_id) count FROM Course WHERE course_id=?", (course_id,)).fetchone()
                    if not course: return self.send_json({"error": "Course not found."}, 404)
                    if course["count"] >= course["capacity"]: return self.send_json({"error": "This course has reached capacity."}, 409)
                    db.execute("INSERT INTO Enrollment(student_id,course_id) VALUES(?,?)", (sid, course_id))
                return self.send_json({"ok": True}, 201)
            except (TypeError, ValueError):
                return self.send_json({"error": "Choose a valid course."}, 400)
            except sqlite3.IntegrityError as exc:
                return self.send_json({"error": "You are already enrolled, or the selected course is unavailable."}, 409)
            except sqlite3.Error as exc:
                return self.send_json({"error": str(exc)}, 500)
        if route == "/api/lesson/complete":
            try:
                lesson_id = int(payload.get("lesson_id"))
                sid = self.session_user_id()
                if not sid: return self.send_json({"error": "Please sign in to continue."}, 401)
                with connect() as db:
                    lesson = db.execute("""SELECT l.lesson_title title,l.course_id FROM Lesson l
                        JOIN Enrollment e ON e.course_id=l.course_id
                        WHERE l.lesson_id=? AND e.student_id=?""", (lesson_id,sid)).fetchone()
                    if not lesson: return self.send_json({"error": "Lesson is unavailable for your account."}, 404)
                    db.execute("INSERT OR IGNORE INTO LessonProgress(student_id,lesson_id) VALUES(?,?)", (sid,lesson_id))
                    total=db.execute("SELECT COUNT(*) FROM Lesson WHERE course_id=?",(lesson["course_id"],)).fetchone()[0]
                    done=db.execute("SELECT COUNT(*) FROM LessonProgress p JOIN Lesson l ON l.lesson_id=p.lesson_id WHERE p.student_id=? AND l.course_id=?",(sid,lesson["course_id"])).fetchone()[0]
                    state='Completed' if total and done==total else 'In Progress'
                    db.execute("UPDATE Enrollment SET progress_status=? WHERE student_id=? AND course_id=?",(state,sid,lesson["course_id"]))
                    if state=='Completed':
                        enrollment=db.execute("SELECT enrollment_id FROM Enrollment WHERE student_id=? AND course_id=?",(sid,lesson["course_id"])).fetchone()
                        db.execute("INSERT OR IGNORE INTO Certificate(enrollment_id,certificate_code) VALUES(?,?)",(enrollment["enrollment_id"],f"LH-{secrets.token_hex(5).upper()}"))
                return self.send_json({"ok": True, "completed": True})
            except (TypeError, ValueError):
                return self.send_json({"error": "Choose a valid lesson."}, 400)
            except sqlite3.Error as exc:
                return self.send_json({"error": str(exc)}, 500)
        if route == "/api/quiz/submit":
            try:
                quiz_id = int(payload.get("quiz_id"))
                answers = payload.get("answers")
                if not isinstance(answers, dict):
                    return self.send_json({"error": "Submit an answer for each question."}, 400)
                sid = self.session_user_id()
                if not sid: return self.send_json({"error": "Please sign in to continue."}, 401)
                with connect() as db:
                    quiz = db.execute("""SELECT q.quiz_id,q.total_marks,q.course_id,e.progress_status FROM Quiz q
                        JOIN Enrollment e ON e.course_id=q.course_id
                        WHERE q.quiz_id=? AND e.student_id=?""", (quiz_id,sid)).fetchone()
                    if not quiz: return self.send_json({"error": "Quiz unavailable for this student."}, 404)
                    total_lessons = db.execute("SELECT COUNT(*) FROM Lesson WHERE course_id=?", (quiz["course_id"],)).fetchone()[0]
                    done_lessons = db.execute("""SELECT COUNT(*) FROM LessonProgress p JOIN Lesson l ON l.lesson_id=p.lesson_id
                        WHERE p.student_id=? AND l.course_id=?""", (sid,quiz["course_id"])).fetchone()[0]
                    if not total_lessons or (done_lessons < total_lessons and quiz["progress_status"] != "Completed"):
                        return self.send_json({"error": f"This signed-in account has completed {done_lessons} of {total_lessons} lessons. Complete all lessons in this course before taking the quiz."}, 403)
                    questions = db.execute("SELECT question_id,correct_option FROM QuizQuestion WHERE quiz_id=? ORDER BY question_order", (quiz_id,)).fetchall()
                    if not questions: return self.send_json({"error": "This quiz does not have any questions yet."}, 409)
                    if set(map(str,answers.keys())) != {str(q["question_id"]) for q in questions}:
                        return self.send_json({"error": "Answer every question before submitting."}, 400)
                    correct = sum(1 for q in questions if str(answers[str(q["question_id"])]) == q["correct_option"])
                    score = round(quiz["total_marks"] * correct / len(questions), 2)
                    db.execute("INSERT INTO Submission(student_id,quiz_id,score) VALUES(?,?,?)", (sid,quiz_id,score))
                return self.send_json({"ok": True,"correct":correct,"total":len(questions),"score":score,"maximum":quiz["total_marks"]}, 201)
            except (TypeError, ValueError):
                return self.send_json({"error": "Choose a valid quiz."}, 400)
            except sqlite3.Error as exc:
                return self.send_json({"error": str(exc)}, 500)
        if route == "/api/grade":
            instructor_id = self.session_instructor_id()
            if not instructor_id:
                return self.send_json({"error": "Sign in with an instructor account to grade submissions."}, 403)
            try:
                submission_id = int(payload.get("submission_id"))
                score = float(payload.get("score"))
                feedback = str(payload.get("feedback", "")).strip()
                saved_score = grade_assignment_submission(instructor_id,submission_id,score,feedback)
                return self.send_json({"ok": True, "score": saved_score}, 200)
            except LookupError as exc:
                return self.send_json({"error": str(exc)}, 404)
            except (TypeError, ValueError) as exc:
                return self.send_json({"error": str(exc) or "Enter a valid submission and numeric mark."}, 400)
            except sqlite3.IntegrityError as exc:
                return self.send_json({"error": str(exc)}, 400)
            except sqlite3.Error as exc:
                return self.send_json({"error": str(exc)}, 500)
        if route == "/api/submit":
            try:
                assignment_id = int(payload.get("assignment_id"))
                content = str(payload.get("content", "")).strip()
                if not content and uploaded is None:
                    return self.send_json({"error": "Enter assignment text or attach a document."}, 400)
                original_name = stored_name = mime_type = stored_relative_path = None
                file_bytes = None
                if uploaded is not None:
                    raw_name, file_bytes = uploaded
                    original_name = Path(raw_name.replace("\\", "/")).name
                    original_name = re.sub(r"[\x00-\x1f\x7f]", "_", original_name).strip(" .")
                    extension = Path(original_name).suffix.lower()
                    if not original_name or len(original_name) > 200:
                        return self.send_json({"error": "Use a file name between 1 and 200 characters."}, 400)
                    if extension not in ALLOWED_UPLOADS:
                        return self.send_json({"error": "Upload a PDF, DOC, DOCX, or TXT document."}, 415)
                    if not file_bytes or len(file_bytes) > MAX_UPLOAD_BYTES:
                        return self.send_json({"error": "Choose a non-empty document no larger than 10 MB."}, 413)
                    mime_type = ALLOWED_UPLOADS[extension]
                sid = self.session_user_id()
                if not sid: return self.send_json({"error": "Please sign in to continue."}, 401)
                stored_path = None
                try:
                    with connect() as db:
                        assignment = db.execute("""SELECT a.assignment_id id,a.due_date FROM Assignment a
                            JOIN Enrollment e ON e.course_id=a.course_id
                            WHERE a.assignment_id=? AND e.student_id=?""", (assignment_id, sid)).fetchone()
                        if not assignment:
                            return self.send_json({"error": "Assignment unavailable for this student."}, 404)
                        status = "Late" if assignment["due_date"] and assignment["due_date"] < date.today().isoformat() else "Submitted"
                        if uploaded is not None:
                            UPLOAD_DIRECTORY.mkdir(parents=True, exist_ok=True)
                            stored_name = f"{secrets.token_hex(16)}{Path(original_name).suffix.lower()}"
                            stored_path = UPLOAD_DIRECTORY / stored_name
                            stored_path.write_bytes(file_bytes)
                            stored_relative_path = stored_path.relative_to(ROOT).as_posix()
                        db.execute("""INSERT INTO Submission
                            (assignment_id,student_id,content,status,file_name,file_path,file_size,file_mime_type)
                            VALUES(?,?,?,?,?,?,?,?)""",
                                   (assignment_id,sid,content,status,original_name,stored_relative_path,
                                    len(file_bytes) if file_bytes is not None else None,mime_type))
                except Exception:
                    if stored_path and stored_path.exists():
                        stored_path.unlink()
                    raise
                return self.send_json({"ok": True, "status": status}, 201)
            except (TypeError, ValueError):
                return self.send_json({"error": "Choose a valid assignment."}, 400)
            except sqlite3.IntegrityError:
                return self.send_json({"error": "A submission already exists for this assignment."}, 409)
            except OSError as exc:
                return self.send_json({"error": f"The uploaded file could not be saved: {exc}"}, 500)
            except sqlite3.Error as exc:
                return self.send_json({"error": str(exc)}, 500)
        self.send_error(404)

    def log_message(self, fmt, *args):
        print(f"[{self.log_date_time_string()}] {fmt % args}")


def main():
    initialize_database()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"LearnHub web app: http://{HOST}:{PORT}")
    print(f"SQLite database: {DB_FILE}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

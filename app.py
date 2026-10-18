from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATABASE = BASE_DIR / "students.db"
app = Flask(__name__)
app.config["SECRET_KEY"] = "change-this-secret-key-before-deployment"

SUBJECTS = ["Python", "DBMS", "Java", "Networking", "Cloud Computing", "Web Development"]
MAX_MARKS = 100

def get_db():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection

def init_db():
    with get_db() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""")
        db.execute("""CREATE TABLE IF NOT EXISTS marks (
            student_id INTEGER NOT NULL,
            subject TEXT NOT NULL,
            score REAL NOT NULL CHECK(score >= 0 AND score <= 100),
            PRIMARY KEY (student_id, subject),
            FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
        )""")

def calculate_result(scores):
    total = sum(float(scores.get(subject, 0)) for subject in SUBJECTS)
    maximum = len(SUBJECTS) * MAX_MARKS
    percentage = total / maximum * 100
    average = total / len(SUBJECTS)
    if percentage >= 90: grade = "A+"
    elif percentage >= 80: grade = "A"
    elif percentage >= 70: grade = "B"
    elif percentage >= 60: grade = "C"
    elif percentage >= 50: grade = "D"
    else: grade = "F"
    return {"total": total, "maximum": maximum, "percentage": percentage, "average": average, "grade": grade}

def student_record(row, scores):
    return {"id": row["id"], "student_id": row["student_id"], "name": row["name"],
            "created_at": row["created_at"], "marks": scores, "result": calculate_result(scores)}

def get_student(student_pk):
    with get_db() as db:
        row = db.execute("SELECT * FROM students WHERE id = ?", (student_pk,)).fetchone()
        if not row: return None
        mark_rows = db.execute("SELECT subject, score FROM marks WHERE student_id = ?", (student_pk,)).fetchall()
    scores = {r["subject"]: float(r["score"]) for r in mark_rows}
    for subject in SUBJECTS: scores.setdefault(subject, 0.0)
    return student_record(row, scores)

def get_all_students(search=""):
    with get_db() as db:
        if search:
            rows = db.execute("""SELECT * FROM students
                WHERE student_id LIKE ? OR name LIKE ? ORDER BY name COLLATE NOCASE""",
                (f"%{search}%", f"%{search}%")).fetchall()
        else:
            rows = db.execute("SELECT * FROM students ORDER BY name COLLATE NOCASE").fetchall()
        students = []
        for row in rows:
            mark_rows = db.execute("SELECT subject, score FROM marks WHERE student_id = ?", (row["id"],)).fetchall()
            scores = {r["subject"]: float(r["score"]) for r in mark_rows}
            for subject in SUBJECTS: scores.setdefault(subject, 0.0)
            students.append(student_record(row, scores))
    return students

@app.route("/")
def dashboard():
    search = request.args.get("q", "").strip()
    students = get_all_students(search)
    all_students = get_all_students()
    average_percentage = sum(s["result"]["percentage"] for s in all_students) / len(all_students) if all_students else 0
    pass_count = sum(1 for s in all_students if s["result"]["percentage"] >= 50)
    return render_template("dashboard.html", students=students, search=search,
        total_students=len(all_students), average_percentage=average_percentage,
        pass_count=pass_count, subjects=SUBJECTS)

@app.route("/students/new", methods=["GET", "POST"])
def add_student():
    if request.method == "POST":
        student_id = request.form.get("student_id", "").strip()
        name = request.form.get("name", "").strip()
        if not student_id or not name:
            flash("Student ID and name are required.", "error")
            return render_template("student_form.html", student=None, subjects=SUBJECTS)
        scores = {}
        try:
            for subject in SUBJECTS:
                score = float(request.form.get(f"mark_{subject}", "").strip())
                if not 0 <= score <= MAX_MARKS: raise ValueError
                scores[subject] = score
        except ValueError:
            flash("Enter valid marks from 0 to 100 for every subject.", "error")
            return render_template("student_form.html", student=None, subjects=SUBJECTS)
        try:
            with get_db() as db:
                cursor = db.execute("INSERT INTO students (student_id, name) VALUES (?, ?)", (student_id, name))
                pk = cursor.lastrowid
                db.executemany("INSERT INTO marks (student_id, subject, score) VALUES (?, ?, ?)",
                               [(pk, subject, score) for subject, score in scores.items()])
            flash("Student added successfully.", "success")
            return redirect(url_for("student_detail", student_pk=pk))
        except sqlite3.IntegrityError:
            flash("That Student ID already exists. Use a unique ID.", "error")
    return render_template("student_form.html", student=None, subjects=SUBJECTS)

@app.route("/students/<int:student_pk>")
def student_detail(student_pk):
    student = get_student(student_pk)
    if not student:
        flash("Student not found.", "error")
        return redirect(url_for("dashboard"))
    return render_template("student_detail.html", student=student, subjects=SUBJECTS)

@app.route("/students/<int:student_pk>/edit", methods=["GET", "POST"])
def edit_student(student_pk):
    student = get_student(student_pk)
    if not student:
        flash("Student not found.", "error")
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        student_id = request.form.get("student_id", "").strip()
        name = request.form.get("name", "").strip()
        if not student_id or not name:
            flash("Student ID and name are required.", "error")
            return render_template("student_form.html", student=student, subjects=SUBJECTS)
        scores = {}
        try:
            for subject in SUBJECTS:
                score = float(request.form.get(f"mark_{subject}", "").strip())
                if not 0 <= score <= MAX_MARKS: raise ValueError
                scores[subject] = score
        except ValueError:
            flash("Enter valid marks from 0 to 100 for every subject.", "error")
            return render_template("student_form.html", student=student, subjects=SUBJECTS)
        try:
            with get_db() as db:
                db.execute("UPDATE students SET student_id = ?, name = ? WHERE id = ?", (student_id, name, student_pk))
                for subject, score in scores.items():
                    db.execute("""INSERT INTO marks (student_id, subject, score) VALUES (?, ?, ?)
                        ON CONFLICT(student_id, subject) DO UPDATE SET score = excluded.score""",
                        (student_pk, subject, score))
            flash("Student record updated.", "success")
            return redirect(url_for("student_detail", student_pk=student_pk))
        except sqlite3.IntegrityError:
            flash("That Student ID is already in use.", "error")
    return render_template("student_form.html", student=student, subjects=SUBJECTS)

@app.route("/students/<int:student_pk>/delete", methods=["POST"])
def delete_student(student_pk):
    with get_db() as db:
        db.execute("DELETE FROM students WHERE id = ?", (student_pk,))
    flash("Student deleted.", "success")
    return redirect(url_for("dashboard"))

@app.route("/search")
def search():
    return redirect(url_for("dashboard", q=request.args.get("q", "").strip()))

init_db()
if __name__ == "__main__":
    app.run(debug=True)

from flask import Flask, render_template, request, redirect, url_for, session
import datetime
import sqlite3, os
from werkzeug.utils import secure_filename

# ------------------- APP SETUP -------------------
app = Flask(__name__)
app.secret_key = "mysecretkey"
UPLOAD_FOLDER = "static/uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# ------------------- DATABASE SETUP -------------------
def init_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    # Users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        role TEXT
    )
    """)

    # Videos table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS videos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        filename TEXT
    )
    """)

    # Tasks table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER,
        task_text TEXT,
        file TEXT,
        rating TEXT,
        FOREIGN KEY(student_id) REFERENCES users(id)
    )
    """)

    conn.commit()
    conn.close()

    # Add default admin
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username='admin'")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                       ("admin", "admin123", "admin"))
    conn.commit()
    conn.close()

# ------------------- ROUTES -------------------

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
        user = cursor.fetchone()
        conn.close()

        if user:
            session["username"] = user[1]
            session["role"] = user[3]
            if user[3] == "admin":
                return redirect(url_for("admin_dashboard"))
            else:
                return redirect(url_for("student_dashboard"))
        else:
            return "⚠️ Invalid username or password"

    return render_template("login.html")

# ------------------- ADMIN -------------------

@app.route("/admin", methods=["GET", "POST"])
def admin_dashboard():
    if "role" in session and session["role"] == "admin":
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()

        if request.method == "POST":
            # Upload video
            if "title" in request.form:
                title = request.form["title"]
                file = request.files["file"]
                if file:
                    filename = secure_filename(file.filename)
                    file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
                    cursor.execute("INSERT INTO videos (title, filename) VALUES (?, ?)", (title, filename))
                    conn.commit()

            # Add student
            elif "student_username" in request.form:
                student_username = request.form["student_username"]
                student_password = request.form["student_password"]
                try:
                    cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                                   (student_username, student_password, "student"))
                    conn.commit()
                except sqlite3.IntegrityError:
                    return "⚠️ Username already exists"

        # Fetch all videos
        cursor.execute("SELECT * FROM videos")
        videos = cursor.fetchall()

        # Fetch all students
        cursor.execute("SELECT * FROM users WHERE role='student'")
        students = cursor.fetchall()

        conn.close()

        return render_template("admin_dashboard.html",
                               videos=videos,
                               students=students,
                               admin_name=session["username"])

    return redirect(url_for("login"))

@app.route("/admin_tasks", methods=["GET", "POST"])
def admin_tasks():
    if "role" in session and session["role"] == "admin":
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()

        if request.method == "POST":
            task_id = request.form["task_id"]
            rating = request.form["rating"]
            cursor.execute("UPDATE tasks SET rating=? WHERE id=?", (rating, task_id))
            conn.commit()

        cursor.execute("""
        SELECT tasks.id, users.username, tasks.task_text, tasks.file, tasks.rating
        FROM tasks
        JOIN users ON tasks.student_id = users.id
        """)
        tasks = cursor.fetchall()
        conn.close()

        return render_template("admin_tasks.html", tasks=tasks)

    return redirect(url_for("login"))

# ------------------- STUDENT -------------------

@app.route("/student")
def student_dashboard():
    if "role" in session and session["role"] == "student":
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM videos")
        videos = cursor.fetchall()
        conn.close()

        return render_template("student_dashboard.html",
                               videos=videos,
                               student_name=session["username"])

    return redirect(url_for("login"))
@app.route("/my_submissions")
def my_submissions():
    if "role" in session and session["role"] == "student":
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()

        # Fetch student ID
        cursor.execute("SELECT id FROM users WHERE username=?", (session["username"],))
        student_id = cursor.fetchone()[0]

        # Fetch all tasks including submitted_at and rated_at
        cursor.execute("SELECT id, task_text, file, rating, submitted_at, rated_at FROM tasks WHERE student_id=?", (student_id,))
        submissions = cursor.fetchall()
        conn.close()

        return render_template("my_submissions.html",
                               student_name=session["username"],
                               submissions=submissions)
    return redirect(url_for("login"))


@app.route("/logout")
def logout():
    session.clear()   # remove all session data
    return redirect(url_for("login"))

@app.route("/change_password", methods=["GET", "POST"])
def change_password():
    if "username" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        old_password = request.form["old_password"]
        new_password = request.form["new_password"]

        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()

        # Check current password
        cursor.execute("SELECT password FROM users WHERE username=?", (session["username"],))
        current_password = cursor.fetchone()[0]

        if old_password == current_password:
            # Update password
            cursor.execute("UPDATE users SET password=? WHERE username=?", (new_password, session["username"]))
            conn.commit()
            conn.close()
            return "✅ Password updated successfully! <a href='/'>Go back</a>"
        else:
            conn.close()
            return "❌ Old password is incorrect. Try again."

    return render_template("change_password.html", username=session["username"])

@app.route("/rate_task/<int:task_id>", methods=["POST"])
def rate_task(task_id):
    if "role" in session and session["role"] == "admin":
        rating = request.form["rating"]
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE tasks SET rating=?, rated_at=? WHERE id=?",
            (rating, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), task_id)
        )
        conn.commit()
        conn.close()
        return redirect(url_for("admin_tasks"))
    return redirect(url_for("login"))
@app.route("/reset_password/<int:student_id>", methods=["GET", "POST"])
def reset_password(student_id):
    if "role" in session and session["role"] == "admin":
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()

        if request.method == "POST":
            new_password = request.form["new_password"]

            cursor.execute("UPDATE users SET password=? WHERE id=?", (new_password, student_id))
            conn.commit()
            conn.close()
            return f"✅ Password reset for student ID {student_id}! <a href='/admin_dashboard'>Go back</a>"

        # Fetch username for display
        cursor.execute("SELECT username FROM users WHERE id=?", (student_id,))
        student_name = cursor.fetchone()[0]
        conn.close()

        return render_template("reset_password.html", student_name=student_name, student_id=student_id)
    return redirect(url_for("login"))


@app.route("/submit_task", methods=["GET", "POST"])
def submit_task():
    if "role" in session and session["role"] == "student":
        if request.method == "POST":
            task_text = request.form["task_text"]
            file = request.files["file"]

            filename = None
            if file:
                filename = file.filename
                file.save("static/uploads/" + filename)

            conn = sqlite3.connect("database.db")
            cursor = conn.cursor()

            # Get student ID
            cursor.execute("SELECT id FROM users WHERE username=?", (session["username"],))
            student_id = cursor.fetchone()[0]

            # Insert task with timestamp
            cursor.execute(
                "INSERT INTO tasks (student_id, task_text, file, submitted_at) VALUES (?, ?, ?, ?)",
                (student_id, task_text, filename, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            )

            conn.commit()
            conn.close()
            return "✅ Task submitted successfully! <a href='/student_dashboard'>Go back</a>"

        return render_template("submit_task.html", student_name=session["username"])
    return redirect(url_for("login"))

# ------------------- MAIN -------------------
if __name__ == "__main__":
    init_db()
    app.run(debug=True)

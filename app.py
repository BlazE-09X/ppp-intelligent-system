import os

import psycopg
from flask import Flask, render_template, request, redirect, session
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "gcp-internal-key-change-me-в-проде")

# ---------------- DATABASE CONNECTION ----------------
# Строка подключения берётся из переменной окружения DATABASE_URL.
# Пример для локального PostgreSQL (см. файл .env):
# DATABASE_URL=postgresql://gcp_user:gcp_password@localhost:5432/gcp_db

DATABASE_URL = os.environ.get("DATABASE_URL")


def get_connection():
    return psycopg.connect(DATABASE_URL)


LANG = {
    "ru": {
        "title": "Система обработки заявок",
        "desc": "Введите заявку и система автоматически направит её в департамент",
        "button": "Отправить",
        "select": "Выберите департамент (необязательно)",
        "auto": "-- Автоопределение --",
        "result": "Результат"
    },
    "kz": {
        "title": "Өтініштерді өңдеу жүйесі",
        "desc": "Өтінішті енгізіп, жүйе оны автоматты түрде тиісті бөлімге жібереді",
        "button": "Жіберу",
        "select": "Бөлімді таңдаңыз (міндетті емес)",
        "auto": "-- Автоматты анықтау --",
        "result": "Нәтиже"
    },
    "en": {
        "title": "Request Processing System",
        "desc": "Enter request and system routes it automatically",
        "button": "Submit",
        "select": "Choose department (optional)",
        "auto": "-- Auto detection --",
        "result": "Result"
    }
}

ADMIN = {
    "username": "admin",
    "password": "1234"
}

departments = {
    "coordination": {"name": "Координация проектов", "email": "coord@gcp.kz"},
    "evaluation": {"name": "Оценка", "email": "eval@gcp.kz"},
    "research": {"name": "Исследования", "email": "res@gcp.kz"},
    "economy": {"name": "Экономика", "email": "eco@gcp.kz"},
    "expertise": {"name": "Экспертиза", "email": "exp@gcp.kz"},
    "transformation": {"name": "Развитие", "email": "dev@gcp.kz"},
    "legal_hr": {"name": "Право и HR", "email": "hr@gcp.kz"},
    "admin": {"name": "Администрирование", "email": "adm@gcp.kz"}
}


def auto_detect(text):
    text = text.lower()

    if "проект" in text:
        return "coordination"
    elif "оценка" in text:
        return "evaluation"
    elif "исслед" in text:
        return "research"
    elif "финанс" in text:
        return "economy"
    elif "экспертиз" in text:
        return "expertise"
    elif "развит" in text:
        return "transformation"
    elif "прав" in text or "hr" in text:
        return "legal_hr"
    else:
        return "admin"

# ---------------- DATABASE INIT ----------------

def init_db():
    conn = get_connection()
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS requests (
        id SERIAL PRIMARY KEY,
        text TEXT,
        department TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS departments (
        id SERIAL PRIMARY KEY,
        name TEXT,
        email TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS admin (
        id INTEGER PRIMARY KEY,
        username TEXT,
        password TEXT
    )
    """)

    # default admin (логин и пароль берутся из .env / переменных окружения хостинга)
    default_username = os.environ.get("ADMIN_USERNAME", "admin")
    default_password = os.environ.get("ADMIN_PASSWORD", "1234")
    c.execute("""
        INSERT INTO admin (id, username, password) VALUES (1, %s, %s)
        ON CONFLICT (id) DO NOTHING
    """, (default_username, default_password))

    # если в .env / переменных окружения указан пароль - синхронизируем его с базой
    # (на случай если он был изменён после первого запуска)
    if os.environ.get("ADMIN_PASSWORD"):
        c.execute(
            "UPDATE admin SET username=%s, password=%s WHERE id=1",
            (default_username, default_password)
        )

    # default departments (заполняем таблицу, если она пустая)
    c.execute("SELECT COUNT(*) FROM departments")
    if c.fetchone()[0] == 0:
        for dep in departments.values():
            c.execute(
                "INSERT INTO departments (name, email) VALUES (%s, %s)",
                (dep["name"], dep["email"])
            )

    conn.commit()
    conn.close()


init_db()


# ---------------- LOGIC ----------------

def classify(text):
    text = text.lower()

    rules = {
        "Департамент координации проектов ГЧП": ["проект", "координация", "реализация"],
        "Департамент оценки": ["оценка", "анализ"],
        "Департамент исследований и методологии": ["исследование", "методология"],
        "Департамент экономики и бухгалтерского учета": ["финанс", "бюджет", "смета"],
        "Департамент экспертизы": ["экспертиза"],
        "Департамент трансформации и развития": ["развитие", "трансформация"],
        "Департамент правового обеспечения и HR": ["договор", "право", "hr"],
        "Департамент внутреннего администрирования": ["заявка", "документ"]
    }

    for dep, keys in rules.items():
        for k in keys:
            if k in text:
                return dep

    return "Не определено"

# ---------------- SAVE ----------------

def save_request(text, dep):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO requests (text, department) VALUES (%s, %s)", (text, dep))
    conn.commit()
    conn.close()

# ---------------- ROUTES ----------------

@app.route("/", methods=["GET", "POST"])
def index():
    result = None

    lang = request.args.get("lang", "ru")
    t = LANG.get(lang, LANG["ru"])

    if request.method == "POST":
        text = request.form["text"]
        selected = request.form.get("department")

        if selected:
            dept_key = selected
            dept_name = departments.get(dept_key, {}).get("name", dept_key)
        else:
            dept_key = auto_detect(text)
            dept_name = departments.get(dept_key, {}).get("name", dept_key)

        save_request(text, dept_name)
        result = dept_name

    return render_template("index.html", t=t, result=result, lang=lang)


# ---------------- LOGIN ----------------

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None

    if request.method == "POST":
        u = request.form["username"]
        p = request.form["password"]

        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT * FROM admin WHERE username=%s AND password=%s", (u, p))
        admin = c.fetchone()
        conn.close()

        if admin:
            session["admin"] = True
            return redirect("/admin")
        else:
            error = "Неверный логин или пароль"

    return render_template("login.html", error=error)


# ---------------- ADMIN PANEL ----------------

@app.route("/admin")
def admin():
    if "admin" not in session:
        return redirect("/login")

    conn = get_connection()
    c = conn.cursor()

    c.execute("SELECT * FROM requests")
    requests_rows = c.fetchall()

    c.execute("SELECT * FROM departments")
    departments_rows = c.fetchall()

    conn.close()

    return render_template("admin.html", requests=requests_rows, departments=departments_rows)


# ---------------- ADD DEPARTMENT ----------------

@app.route("/add_department", methods=["POST"])
def add_department():
    if "admin" not in session:
        return redirect("/login")

    name = request.form["name"]
    email = request.form["email"]

    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO departments (name, email) VALUES (%s, %s)", (name, email))
    conn.commit()
    conn.close()

    return redirect("/admin")


# ---------------- DELETE ----------------

@app.route("/delete_dept/<int:id>")
def delete_dept(id):
    if "admin" not in session:
        return redirect("/login")

    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM departments WHERE id=%s", (id,))
    conn.commit()
    conn.close()
    return redirect("/admin")


if __name__ == "__main__":
    debug_mode = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(debug=debug_mode)

import os
import re
import json
import sqlite3
import uuid

from pathlib import Path
from datetime import datetime, timezone

from flask import Flask, jsonify, request, render_template, send_from_directory
from werkzeug.utils import secure_filename
from dotenv import load_dotenv


# -----------------------------
# BASIC SETUP
# -----------------------------

load_dotenv()

BASE = Path(__file__).resolve().parent
DB_PATH = BASE / os.getenv("DB_PATH", "issues.db")

UPLOAD_DIR = BASE / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

ALLOWED_FILES = {"png", "jpg", "jpeg", "webp"}

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024


# -----------------------------
# DATABASE HELPERS
# -----------------------------

def current_time():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_db():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_database():
    connection = get_db()

    connection.execute("""
        CREATE TABLE IF NOT EXISTS issues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            title TEXT NOT NULL,
            description TEXT NOT NULL,
            location TEXT NOT NULL,

            category TEXT NOT NULL,
            priority TEXT NOT NULL,

            severity INTEGER NOT NULL DEFAULT 50,
            severity_reason TEXT DEFAULT '',

            status TEXT NOT NULL DEFAULT 'Reported',

            points_awarded INTEGER NOT NULL DEFAULT 0,

            image_name TEXT,

            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    # This allows older databases to keep working
    columns = {
        column["name"]
        for column in connection.execute(
            "PRAGMA table_info(issues)"
        )
    }

    migrations = {
        "severity":
            "ALTER TABLE issues ADD COLUMN severity INTEGER NOT NULL DEFAULT 50",

        "severity_reason":
            "ALTER TABLE issues ADD COLUMN severity_reason TEXT DEFAULT ''",

        "points_awarded":
            "ALTER TABLE issues ADD COLUMN points_awarded INTEGER NOT NULL DEFAULT 0"
    }

    for column, command in migrations.items():

        if column not in columns:
            connection.execute(command)

    connection.commit()
    connection.close()


# -----------------------------
# DEMO DATA
# -----------------------------

def add_demo_data():

    connection = get_db()

    count = connection.execute(
        "SELECT COUNT(*) AS c FROM issues"
    ).fetchone()["c"]

    if count == 0:

        demo_issues = [

            (
                "Water leakage near Physics Lab",
                "Water is continuously leaking and the floor is slippery.",
                "Physics Lab",
                "Plumbing",
                "High",
                92,
                "Possible safety risk.",
                "Reported",
                0
            ),

            (
                "Broken classroom light",
                "One ceiling light is not working.",
                "Block A - Room 204",
                "Electrical",
                "Medium",
                64,
                "Classroom visibility is affected.",
                "In Progress",
                0
            ),

            (
                "Damaged bench",
                "A bench has a broken edge and is difficult to use.",
                "Block B - Room 106",
                "Furniture",
                "Medium",
                55,
                "Furniture needs attention.",
                "Resolved",
                15
            )
        ]

        for issue in demo_issues:

            connection.execute("""
                INSERT INTO issues
                (
                    title,
                    description,
                    location,
                    category,
                    priority,
                    severity,
                    severity_reason,
                    status,
                    points_awarded,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (*issue, current_time(), current_time()))

        connection.commit()

    connection.close()


# -----------------------------
# ISSUE CLASSIFICATION
# -----------------------------

def classify_issue(title, description):

    text = (title + " " + description).lower()

    category_rules = [

        (
            "Safety",
            [
                "fire",
                "smoke",
                "shock",
                "danger",
                "accident",
                "slippery"
            ]
        ),

        (
            "Plumbing",
            [
                "water",
                "leak",
                "tap",
                "pipe",
                "toilet",
                "drain"
            ]
        ),

        (
            "Electrical",
            [
                "light",
                "switch",
                "socket",
                "fan",
                "electric",
                "power"
            ]
        ),

        (
            "Cleanliness",
            [
                "garbage",
                "trash",
                "dirty",
                "waste",
                "smell"
            ]
        ),

        (
            "IT Support",
            [
                "wifi",
                "internet",
                "computer",
                "projector",
                "network"
            ]
        ),

        (
            "Furniture",
            [
                "bench",
                "chair",
                "desk",
                "table",
                "seat"
            ]
        )
    ]

    category = "General"

    for name, words in category_rules:

        if any(word in text for word in words):
            category = name
            break


    # -----------------------------
    # LOCAL PRIORITY RULES
    # -----------------------------

    high_words = [
        "fire",
        "shock",
        "danger",
        "accident",
        "slippery",
        "leak",
        "smoke"
    ]

    medium_words = [
        "broken",
        "not working",
        "damaged",
        "overflow",
        "dirty"
    ]


    if any(word in text for word in high_words):

        priority = "High"
        severity = 85

        reason = (
            "High urgency due to a possible "
            "safety or immediate-impact signal."
        )

    elif any(word in text for word in medium_words):

        priority = "Medium"
        severity = 60

        reason = (
            "Medium urgency because normal "
            "campus use may be affected."
        )

    else:

        priority = "Low"
        severity = 30

        reason = (
            "Low urgency because no immediate "
            "safety signal was detected."
        )


    # -----------------------------
    # OPTIONAL GEMINI AI
    # -----------------------------

    api_key = os.getenv("GEMINI_API_KEY", "").strip()

    if api_key:

        try:

            from google import genai

            client = genai.Client(api_key=api_key)

            model = os.getenv(
                "GEMINI_MODEL",
                "gemini-2.5-flash"
            )

            prompt = f"""
Return ONLY JSON.

The JSON must contain:

category
priority
severity
reason

Priority must be:
High, Medium, or Low.

Severity must be a number from 0 to 100.

Issue title:
{title}

Issue description:
{description}
"""

            response = client.models.generate_content(
                model=model,
                contents=prompt
            )

            raw = response.text.strip()

            raw = re.sub(
                r"^```json\s*|\s*```$",
                "",
                raw,
                flags=re.I
            )

            ai_result = json.loads(raw)

            new_priority = ai_result.get(
                "priority",
                priority
            )

            if new_priority not in {
                "High",
                "Medium",
                "Low"
            }:
                new_priority = "Medium"

            priority = new_priority

            severity = max(
                0,
                min(
                    100,
                    int(
                        ai_result.get(
                            "severity",
                            severity
                        )
                    )
                )
            )

            category = str(
                ai_result.get(
                    "category",
                    category
                )
            )[:60]

            reason = str(
                ai_result.get(
                    "reason",
                    reason
                )
            )[:300]

        except Exception:

            # If AI fails, use the local classifier.
            pass


    return {
        "category": category,
        "priority": priority,
        "severity": severity,
        "reason": reason
    }


# -----------------------------
# HOME PAGE
# -----------------------------

@app.route("/")
def home():

    return render_template("index.html")


# -----------------------------
# IMAGE ROUTE
# -----------------------------

@app.route("/uploads/<path:name>")
def uploaded_image(name):

    return send_from_directory(
        UPLOAD_DIR,
        name
    )


# -----------------------------
# DASHBOARD STATS
# -----------------------------

@app.route("/api/stats")
def statistics():

    connection = get_db()

    data = {

        "total": connection.execute(
            "SELECT COUNT(*) AS c FROM issues"
        ).fetchone()["c"],

        "high": connection.execute(
            "SELECT COUNT(*) AS c FROM issues WHERE priority='High'"
        ).fetchone()["c"],

        "progress": connection.execute(
            "SELECT COUNT(*) AS c FROM issues WHERE status='In Progress'"
        ).fetchone()["c"],

        "resolved": connection.execute(
            "SELECT COUNT(*) AS c FROM issues WHERE status='Resolved'"
        ).fetchone()["c"],

        "points": connection.execute(
            "SELECT COALESCE(SUM(points_awarded),0) AS c FROM issues"
        ).fetchone()["c"]
    }

    connection.close()

    return jsonify(data)


# -----------------------------
# ISSUE API
# -----------------------------

@app.route("/api/issues", methods=["GET", "POST"])
def issues():

    # GET = show issues
    if request.method == "GET":

        query = "SELECT * FROM issues WHERE 1=1"
        parameters = []

        for key in [
            "status",
            "category",
            "priority"
        ]:

            value = request.args.get(
                key,
                ""
            ).strip()

            if value:

                query += f" AND {key}=?"
                parameters.append(value)


        query += """
            ORDER BY
            CASE priority
                WHEN 'High' THEN 1
                WHEN 'Medium' THEN 2
                ELSE 3
            END,
            id DESC
        """

        connection = get_db()

        rows = connection.execute(
            query,
            parameters
        ).fetchall()

        connection.close()

        result = []

        for row in rows:

            issue = dict(row)

            if row["image_name"]:

                issue["image_url"] = (
                    f"/uploads/{row['image_name']}"
                )

            else:

                issue["image_url"] = None

            result.append(issue)

        return jsonify(result)


    # POST = create issue

    title = request.form.get(
        "title",
        ""
    ).strip()

    description = request.form.get(
        "description",
        ""
    ).strip()

    location = request.form.get(
        "location",
        ""
    ).strip()


    if not title or not description or not location:

        return jsonify(
            error="Title, description and location are required."
        ), 400


    result = classify_issue(
        title,
        description
    )


    # -----------------------------
    # IMAGE UPLOAD
    # -----------------------------

    image_name = None

    image = request.files.get("image")

    if image and image.filename:

        extension = (
            Path(
                secure_filename(
                    image.filename
                )
            )
            .suffix
            .lower()
            .lstrip(".")
        )

        if extension not in ALLOWED_FILES:

            return jsonify(
                error="Use PNG, JPG, JPEG or WEBP."
            ), 400


        image_name = (
            f"{uuid.uuid4().hex}.{extension}"
        )

        image.save(
            UPLOAD_DIR / image_name
        )


    # -----------------------------
    # SAVE ISSUE
    # -----------------------------

    connection = get_db()

    cursor = connection.execute(
        """
        INSERT INTO issues
        (
            title,
            description,
            location,
            category,
            priority,
            severity,
            severity_reason,
            status,
            points_awarded,
            image_name,
            created_at,
            updated_at
        )
        VALUES
        (?, ?, ?, ?, ?, ?, ?, 'Reported', 0, ?, ?, ?)
        """,
        (
            title,
            description,
            location,
            result["category"],
            result["priority"],
            result["severity"],
            result["reason"],
            image_name,
            current_time(),
            current_time()
        )
    )

    connection.commit()

    row = connection.execute(
        "SELECT * FROM issues WHERE id=?",
        (cursor.lastrowid,)
    ).fetchone()

    connection.close()


    issue = dict(row)

    if row["image_name"]:

        issue["image_url"] = (
            f"/uploads/{row['image_name']}"
        )

    else:

        issue["image_url"] = None


    return jsonify(
        issue=issue
    ), 201


# -----------------------------
# UPDATE STATUS
# -----------------------------

@app.route(
    "/api/issues/<int:issue_id>/status",
    methods=["PATCH"]
)
def update_status(issue_id):

    data = request.get_json(
        silent=True
    ) or {}

    new_status = data.get(
        "status"
    )


    if new_status not in {
        "Reported",
        "In Progress",
        "Resolved"
    }:

        return jsonify(
            error="Invalid status."
        ), 400


    connection = get_db()

    row = connection.execute(
        "SELECT * FROM issues WHERE id=?",
        (issue_id,)
    ).fetchone()


    if not row:

        connection.close()

        return jsonify(
            error="Issue not found."
        ), 404


    points = row["points_awarded"]


    # Award points only when first resolved

    if (
        new_status == "Resolved"
        and row["status"] != "Resolved"
        and points == 0
    ):

        points = {
            "High": 25,
            "Medium": 15,
            "Low": 10
        }.get(
            row["priority"],
            10
        )


    connection.execute(
        """
        UPDATE issues
        SET
            status=?,
            points_awarded=?,
            updated_at=?
        WHERE id=?
        """,
        (
            new_status,
            points,
            current_time(),
            issue_id
        )
    )

    connection.commit()
    connection.close()


    awarded = (
        points
        if points != row["points_awarded"]
        else 0
    )


    return jsonify(
        points_awarded=awarded
    )


# -----------------------------
# DELETE ISSUE
# -----------------------------

@app.route(
    "/api/issues/<int:issue_id>",
    methods=["DELETE"]
)
def delete_issue(issue_id):

    connection = get_db()

    row = connection.execute(
        "SELECT * FROM issues WHERE id=?",
        (issue_id,)
    ).fetchone()


    if not row:

        connection.close()

        return jsonify(
            error="Issue not found."
        ), 404


    connection.execute(
        "DELETE FROM issues WHERE id=?",
        (issue_id,)
    )

    connection.commit()
    connection.close()


    # Delete uploaded image too

    if row["image_name"]:

        image_path = (
            UPLOAD_DIR /
            row["image_name"]
        )

        if image_path.exists():

            image_path.unlink()


    return jsonify(
        ok=True
    )


# -----------------------------
# ADMIN / CONTROL ROOM
# -----------------------------

@app.route("/api/admin")
def admin_dashboard():

    connection = get_db()


    categories = [

        dict(row)

        for row in connection.execute(
            """
            SELECT
                category,
                COUNT(*) AS count
            FROM issues
            GROUP BY category
            ORDER BY count DESC
            """
        )
    ]


    recent = [

        dict(row)

        for row in connection.execute(
            """
            SELECT
                id,
                title,
                category,
                priority,
                severity,
                status,
                points_awarded
            FROM issues
            ORDER BY id DESC
            LIMIT 8
            """
        )
    ]


    data = {

        "total": connection.execute(
            "SELECT COUNT(*) AS c FROM issues"
        ).fetchone()["c"],

        "high": connection.execute(
            "SELECT COUNT(*) AS c FROM issues WHERE priority='High'"
        ).fetchone()["c"],

        "progress": connection.execute(
            "SELECT COUNT(*) AS c FROM issues WHERE status='In Progress'"
        ).fetchone()["c"],

        "resolved": connection.execute(
            "SELECT COUNT(*) AS c FROM issues WHERE status='Resolved'"
        ).fetchone()["c"],

        "points": connection.execute(
            "SELECT COALESCE(SUM(points_awarded),0) AS c FROM issues"
        ).fetchone()["c"],

        "categories": categories,

        "recent": recent
    }


    connection.close()

    return jsonify(data)


# -----------------------------
# START
# -----------------------------

init_database()
add_demo_data()


if __name__ == "__main__":

    app.run(
        debug=True
    )
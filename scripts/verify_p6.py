"""P6 smoke test — dashboards, navigation, major endpoints, deploy readiness.

Run with the kanachat env from the project root: python scripts/verify_p6.py
"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models import Classroom, Enrollment, User
from seed.load_seed import load_seed

TEST_DB = os.path.join(tempfile.gettempdir(), "kanachat_p6_test.sqlite3")
SEED_JSON = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "seed", "content.json",
)

_results = {"ok": True}


def check(label, cond):
    _results["ok"] = _results["ok"] and bool(cond)
    print(("PASS  " if cond else "FAIL  ") + label)


def main():
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

    app = create_app("testing")
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + TEST_DB

    with open(SEED_JSON, encoding="utf-8") as f:
        data = json.load(f)

    with app.app_context():
        db.create_all()
        load_seed(data)

        teacher = User(username="bu_guru", role="teacher")
        teacher.set_password("gurupass")
        student = User(username="andi", role="student")
        student.set_password("andipass")
        admin = User(username="root", role="admin")
        admin.set_password("rootpass")
        db.session.add_all([teacher, student, admin])
        db.session.commit()

        classroom = Classroom(name="Jepang XII-A", teacher_id=teacher.id)
        db.session.add(classroom)
        db.session.commit()
        db.session.add(Enrollment(student_id=student.id, class_id=classroom.id))
        db.session.commit()

    c = app.test_client()

    # Public home
    check("GET / -> 200", c.get("/").status_code == 200)
    check("GET /healthz -> 200", c.get("/healthz").status_code == 200)

    # Student dashboard links
    c.post("/login", data={"username": "andi", "password": "andipass"})
    r = c.get("/")
    check("student home has Chat link", b"/chat/" in r.data)
    check("student home has Quiz link", b"/quiz/" in r.data)
    check("student home has Dojo link", b"/dojo/" in r.data)
    check("GET /chat/ -> 200", c.get("/chat/").status_code == 200)
    check("GET /quiz/ -> 200", c.get("/quiz/").status_code == 200)
    check("GET /dojo/ -> 200", c.get("/dojo/").status_code == 200)
    c.post("/logout")

    # Teacher dashboard
    c.post("/login", data={"username": "bu_guru", "password": "gurupass"})
    check("GET /teacher -> 200", c.get("/teacher").status_code == 200)
    r = c.get("/teacher")
    check("teacher dashboard shows class", b"Jepang XII-A" in r.data)
    check("teacher dashboard shows student", b"andi" in r.data)
    check("teacher dashboard has totals", b"Total siswa" in r.data)
    check("GET /content/ -> 200", c.get("/content/").status_code == 200)
    c.post("/logout")

    # Admin dashboard
    c.post("/login", data={"username": "root", "password": "rootpass"})
    check("GET /admin/ -> 200", c.get("/admin/").status_code == 200)
    check("GET /teacher -> 200 for admin", c.get("/teacher").status_code == 200)
    c.post("/logout")

    # Student blocked from teacher dashboard
    c.post("/login", data={"username": "andi", "password": "andipass"})
    check("student GET /teacher -> 403", c.get("/teacher").status_code == 403)

    print("\nRESULT:", "ALL PASS" if _results["ok"] else "SOME FAILED")
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    return 0 if _results["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

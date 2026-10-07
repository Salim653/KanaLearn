"""P1 smoke test — exercises auth + classes + admin through the Flask test client.

Uses its own temporary file-based SQLite DB (not dev.sqlite3, not :memory: which
loses data across connections). Run with the kanachat env python from the project
root:  python scripts/verify_p1.py
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models import Classroom, Enrollment, User

TEST_DB = os.path.join(tempfile.gettempdir(), "kanachat_p1_test.sqlite3")
REDIRECTS = (301, 302, 303)

_results = {"ok": True}


def check(label, cond):
    _results["ok"] = _results["ok"] and bool(cond)
    print(("PASS  " if cond else "FAIL  ") + label)


def main():
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

    app = create_app("testing")
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + TEST_DB

    with app.app_context():
        db.create_all()
        teacher = User(username="bu_guru", role="teacher")
        teacher.set_password("gurupass")
        admin = User(username="root", role="admin")
        admin.set_password("rootpass")
        db.session.add_all([teacher, admin])
        db.session.commit()

    c = app.test_client()

    # 1. Register a student through the form
    r = c.post("/register", data={
        "username": "dani", "password": "rahasia1", "confirm_password": "rahasia1",
    })
    check("register student -> redirect", r.status_code in REDIRECTS)
    with app.app_context():
        dani = User.query.filter_by(username="dani").first()
        check("student created with role 'student'", dani is not None and dani.role == "student")

    # 2. Wrong password rejected
    r = c.post("/login", data={"username": "dani", "password": "salah"})
    check("login with wrong password not redirected", r.status_code == 200)

    # 3. Student login
    r = c.post("/login", data={"username": "dani", "password": "rahasia1"})
    check("student login -> redirect", r.status_code in REDIRECTS)

    # 4. Student blocked from creating a class
    check("student GET /classes/new -> 403", c.get("/classes/new").status_code == 403)

    # 5. Teacher creates a class
    c.post("/logout")
    c.post("/login", data={"username": "bu_guru", "password": "gurupass"})
    r = c.post("/classes/new", data={"name": "Jepang XII-A"})
    check("teacher create class -> redirect", r.status_code in REDIRECTS)
    with app.app_context():
        klass = Classroom.query.filter_by(name="Jepang XII-A").first()
        check("class persisted with a join_code", klass is not None and bool(klass.join_code))
        code = klass.join_code if klass else None
        klass_id = klass.id if klass else None

    # 6. Student joins by code
    c.post("/logout")
    c.post("/login", data={"username": "dani", "password": "rahasia1"})
    r = c.post("/join", data={"join_code": code})
    check("student join by code -> redirect", r.status_code in REDIRECTS)
    with app.app_context():
        check("exactly one enrollment created", Enrollment.query.filter_by(class_id=klass_id).count() == 1)

    # 7. Duplicate join is handled gracefully
    r = c.post("/join", data={"join_code": code}, follow_redirects=True)
    check("duplicate join does not crash", r.status_code == 200)
    with app.app_context():
        check("still only one enrollment", Enrollment.query.filter_by(class_id=klass_id).count() == 1)

    # 8. Invalid code rejected
    r = c.post("/join", data={"join_code": "ZZZZZZ"}, follow_redirects=True)
    check("invalid join code handled", r.status_code == 200)

    # 9. Teacher roster
    c.post("/logout")
    c.post("/login", data={"username": "bu_guru", "password": "gurupass"})
    r = c.get(f"/classes/{klass_id}")
    check("teacher roster page -> 200", r.status_code == 200)
    check("roster lists the student", b"dani" in r.data)

    # 10. Admin dashboard + role change
    c.post("/logout")
    c.post("/login", data={"username": "root", "password": "rootpass"})
    check("admin dashboard -> 200", c.get("/admin/").status_code == 200)
    with app.app_context():
        dani_id = User.query.filter_by(username="dani").first().id
    r = c.post(f"/admin/users/{dani_id}/role", data={"role": "teacher"})
    check("admin changes role -> redirect", r.status_code in REDIRECTS)
    with app.app_context():
        check("role updated to teacher", User.query.filter_by(id=dani_id).first().role == "teacher")

    # 11. Admin cannot self-demote
    with app.app_context():
        admin_id = User.query.filter_by(username="root").first().id
    r = c.post(f"/admin/users/{admin_id}/role", data={"role": "student"}, follow_redirects=True)
    with app.app_context():
        check("admin self-demote blocked", User.query.filter_by(id=admin_id).first().role == "admin")

    # 12. Non-admin blocked from admin panel
    c.post("/logout")
    c.post("/login", data={"username": "dani", "password": "rahasia1"})
    check("non-admin GET /admin/ -> 403", c.get("/admin/").status_code == 403)

    print("\nRESULT:", "ALL PASS" if _results["ok"] else "SOME FAILED")
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    return 0 if _results["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

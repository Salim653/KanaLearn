"""P4 smoke test — quiz path, lesson questions, result recording, leaderboard.

Run with the kanachat env from the project root: python scripts/verify_p4.py
"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models import Kana, KanaMastery, Lesson, LessonResult, StudentQuizState, Unit, User
from seed.load_seed import load_seed

TEST_DB = os.path.join(tempfile.gettempdir(), "kanachat_p4_test.sqlite3")
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

        student = User(username="budi", role="student")
        student.set_password("budi1234")
        db.session.add(student)
        db.session.commit()

    c = app.test_client()

    # 1. unauth redirect
    r = c.get("/quiz/")
    check("unauth /quiz/ redirects", r.status_code in (301, 302, 303))

    # 2. login
    c.post("/login", data={"username": "budi", "password": "budi1234"})

    # 3. quiz index shows units
    r = c.get("/quiz/")
    check("quiz index -> 200", r.status_code == 200)
    check("quiz index lists hiragana units", b"Baris Vokal" in r.data)

    # 4. questions endpoint returns mixed question list
    with app.app_context():
        lesson = Lesson.query.join(Unit).filter(Unit.row == "a", Unit.track == "hiragana", Lesson.kind == "learn").first()
        lesson_id = lesson.id

    r = c.get(f"/quiz/lesson/{lesson_id}/questions")
    check("questions endpoint -> 200", r.status_code == 200)
    body = json.loads(r.data)
    questions = body.get("questions", [])
    check("lesson has 10 questions", len(questions) == 10)
    check("questions have types", all("type" in q for q in questions))
    check("at least one kana_to_romaji", any(q["type"] == "kana_to_romaji" for q in questions))
    check("answers present", all("answer" in q for q in questions))
    first_answer = questions[0]["answer"]

    # 5. submit result with all-correct outcomes
    outcomes = [{"correct": True, "kana_char": q.get("kana_char") or q.get("answer")} for q in questions]
    r = c.post(
        f"/quiz/lesson/{lesson_id}/result",
        data=json.dumps({"outcomes": outcomes}),
        content_type="application/json",
    )
    check("result endpoint -> 200", r.status_code == 200)
    result = json.loads(r.data)
    check("xp earned", result.get("xp_earned", 0) > 0)
    check("accuracy 100%", result.get("accuracy") == 100.0)

    with app.app_context():
        state = StudentQuizState.query.filter_by(student_id=1).first()
        check("student quiz state created with xp", state is not None and state.xp > 0)
        lr = LessonResult.query.filter_by(student_id=1, lesson_id=lesson_id).first()
        check("lesson result recorded", lr is not None and lr.correct == 10)
        mastered = KanaMastery.query.filter_by(student_id=1).all()
        check("kana mastery rows created", len(mastered) > 0)

    # 6. leaderboard renders
    r = c.get("/quiz/leaderboard")
    check("leaderboard -> 200", r.status_code == 200)
    check("leaderboard shows budi", b"budi" in r.data)

    # 7. index shows completion badge
    r = c.get("/quiz/")
    check("quiz index after completion -> 200", r.status_code == 200)
    check("completed lesson shows score", b"10/10" in r.data)

    print("\nRESULT:", "ALL PASS" if _results["ok"] else "SOME FAILED")
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    return 0 if _results["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

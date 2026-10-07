"""P3 smoke test — chat simulator: list, play, answer checking, completion, logging.

Uses its own temporary file-based SQLite DB. Run with the kanachat env from the
project root:  python scripts/verify_p3.py
"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models import AnswerLog, Chat, DialogueStep, StudentChatState, User
from seed.load_seed import load_seed

TEST_DB = os.path.join(tempfile.gettempdir(), "kanachat_p3_test.sqlite3")
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
    r = c.get("/chat/")
    check("unauth /chat/ redirects", r.status_code in (301, 302, 303))

    # 2. login student
    r = c.post("/login", data={"username": "budi", "password": "budi1234"})
    check("student login -> redirect", r.status_code in (301, 302, 303))

    # 3. chat list
    r = c.get("/chat/")
    check("chat list -> 200", r.status_code == 200)
    check("list shows sakura intro", b"Kenalan dengan Sakura" in r.data)

    # 4. play page loads
    with app.app_context():
        chat = Chat.query.filter_by(seed_id="sakura_intro").first()
        chat_id = chat.id
        steps = sorted(chat.steps, key=lambda s: s.order)
        required = [s.required_reply_kana for s in steps]

    r = c.get(f"/chat/{chat_id}")
    check("play page -> 200", r.status_code == 200)
    check("play shows first NPC message", b"\u3053\u3093\u306b\u3061\u306f" in r.data)

    # 5. submit a wrong answer
    r = c.post(f"/chat/{chat_id}/submit", data={"reply": "xxx"})
    check("wrong answer -> JSON 200", r.status_code == 200)
    body = json.loads(r.data)
    check("wrong answer marked incorrect", body.get("correct") is False)
    check("wrong answer costs one heart", body.get("hearts") == 4)
    with app.app_context():
        state = StudentChatState.query.filter_by(student_id=1, chat_id=chat_id).first()
        check("wrong_count incremented", state.wrong_count == 1)

    # 6. request hint
    r = c.post(f"/chat/{chat_id}/hint", data={})
    check("hint -> 200", r.status_code == 200)
    body = json.loads(r.data)
    check("hint returns required kana", body.get("hint", {}).get("kana") == required[0])
    with app.app_context():
        state = StudentChatState.query.filter_by(student_id=1, chat_id=chat_id).first()
        check("hint_count incremented", state.hint_count == 1)

    # 7. handwriting step: low score rejected, high score accepted
    with app.app_context():
        hw_index = next(i for i, s in enumerate(steps) if s.is_handwriting_challenge)
    # fast-forward to the handwriting step by answering everything before it
    for i in range(hw_index):
        c.post(f"/chat/{chat_id}/submit", data={"reply": required[i]})
    r = c.post(
        f"/chat/{chat_id}/submit",
        data={"handwriting_data": "x", "handwriting_score": "20"},
    )
    body = json.loads(r.data)
    check("low handwriting score rejected", body.get("correct") is False)
    check("handwriting feedback reported", "Ketepatan" in (body.get("handwriting_feedback") or ""))
    r = c.post(
        f"/chat/{chat_id}/submit",
        data={"handwriting_data": "x", "handwriting_score": "80"},
    )
    body = json.loads(r.data)
    check("high handwriting score accepted", body.get("correct") is True)

    # 8. finish the remaining steps
    done = False
    with app.app_context():
        state = StudentChatState.query.filter_by(student_id=1, chat_id=chat_id).first()
        start_index = state.current_step_order
    final_stars = 1
    for i in range(start_index, len(required)):
        r = c.post(f"/chat/{chat_id}/submit", data={"reply": required[i]})
        body = json.loads(r.data)
        if body.get("done"):
            done = True
            final_stars = body.get("stars")
            break
    check("chat completed", done)
    check("final stars >= 1", final_stars >= 1)

    with app.app_context():
        state = StudentChatState.query.filter_by(student_id=1, chat_id=chat_id).first()
        check("state marked completed", state.completed)
        check("state step at end", state.current_step_order == len(steps))
        logs = AnswerLog.query.filter_by(student_id=1, chat_id=chat_id).all()
        check("AnswerLogs recorded for this chat", len(logs) >= len(steps))
        correct_logs = [l for l in logs if l.is_correct]
        check("at least one correct AnswerLog", len(correct_logs) >= 1)

    # 9. reset chat
    r = c.post(f"/chat/{chat_id}/reset", data={})
    check("reset -> redirect", r.status_code in (301, 302, 303))
    with app.app_context():
        state = StudentChatState.query.filter_by(student_id=1, chat_id=chat_id).first()
        check("state reset to step 0", state.current_step_order == 0)
        check("state not completed after reset", not state.completed)

    print("\nRESULT:", "ALL PASS" if _results["ok"] else "SOME FAILED")
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    return 0 if _results["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""P2 smoke test — content models + seed loader.

Uses its own temporary file-based SQLite DB (not dev.sqlite3). Run with the
kanachat env python from the project root:  python scripts/verify_p2.py
"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models import Kana, Character, KanaRow, Chat, DialogueStep
from seed.load_seed import load_seed

TEST_DB = os.path.join(tempfile.gettempdir(), "kanachat_p2_test.sqlite3")
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

        # 1. Initial load -> expected totals
        counts = load_seed(data)
        check("92 kana loaded", counts["kana"] == 92)
        check("4 characters loaded", counts["characters"] == 4)
        check("22 kana rows loaded", counts["rows"] == 22)
        check("4 chats loaded", counts["chats"] == 4)
        check("18 dialogue steps loaded", counts["steps"] == 18)

        # 2. Kana spot checks (hiragana + katakana)
        a = Kana.query.filter_by(char="あ").first()
        check("あ romaji/type/row correct",
              a is not None and a.romaji == "a" and a.type == "hiragana" and a.row == "a")
        check("あ has example_word with meaning",
              isinstance(a.example_word, dict) and a.example_word.get("meaning") == "Pagi hari")
        check("あ has stroke data (for P5/P7)",
              isinstance(a.strokes, list) and len(a.strokes) == 3)
        check("あ has similar_confusions list",
              isinstance(a.similar_confusions, list) and "お" in a.similar_confusions)
        ka = Kana.query.filter_by(char="ア").first()
        check("ア is katakana", ka is not None and ka.type == "katakana")

        # 3. Kana rows
        check("11 hiragana rows", KanaRow.query.filter_by(type="hiragana").count() == 11)
        check("11 katakana rows", KanaRow.query.filter_by(type="katakana").count() == 11)
        row_a = KanaRow.query.filter_by(row_id="a", type="hiragana").first()
        check("row 'a' chars ordered あいうえお",
              row_a is not None and row_a.chars == ["あ", "い", "う", "え", "お"])

        # 4. Characters + chats wired together
        sakura = Character.query.filter_by(seed_id="sakura").first()
        check("sakura character loaded", sakura is not None and sakura.name == "Sakura")
        chats = Chat.query.order_by(Chat.level_number).all()
        check("chat levels ordered 1..4", [c.level_number for c in chats] == [1, 2, 3, 4])
        intro = Chat.query.filter_by(seed_id="sakura_intro").first()
        check("sakura_intro belongs to sakura",
              intro is not None and intro.character.seed_id == "sakura")
        check("context_theme defaults to character role",
              intro.context_theme == sakura.role)

        # 5. Dialogue steps
        check("sakura_intro has 5 steps in order",
              len(intro.steps) == 5 and [s.order for s in intro.steps] == [0, 1, 2, 3, 4])
        step1 = intro.steps[0]
        check("step 1 is a voice note with reply spec",
              step1.is_voice_note and step1.required_reply_kana == "はい"
              and step1.required_reply_romaji == "hai")
        check("step 1 kana pool + alternatives are lists",
              isinstance(step1.available_kana_pool, list)
              and isinstance(step1.allowed_alternatives, list))
        step3 = intro.steps[2]
        check("step 3 is a handwriting challenge on あ",
              step3.is_handwriting_challenge and step3.handwriting_target_char == "あ")
        check("PLAYER_NAME placeholder preserved",
              any("{PLAYER_NAME}" in s.npc_message for s in intro.steps))

        # 6. Idempotent re-run -> same totals, no duplicates
        counts2 = load_seed(data)
        check("re-seed keeps 92 kana", counts2["kana"] == 92)
        check("re-seed keeps 18 steps", counts2["steps"] == 18)

        # 7. Teacher edits survive re-seeding
        custom = DialogueStep(
            chat_id=intro.id, seed_id="teacher_custom_1", order=99,
            npc_message="Pertanyaan tambahan dari guru.",
        )
        db.session.add(custom)
        db.session.commit()
        counts3 = load_seed(data)
        check("teacher-added step survives re-seed",
              counts3["steps"] == 19
              and DialogueStep.query.filter_by(seed_id="teacher_custom_1").count() == 1)
        check("seed-owned fields still refresh on re-seed",
              DialogueStep.query.filter_by(seed_id="s1_step1").first().required_reply_kana == "はい")

        # 8. Cascade: deleting a character removes its chats + steps
        ren = Character.query.filter_by(seed_id="ren").first()
        ren_chat_ids = [c.id for c in ren.chats]
        n_steps = DialogueStep.query.filter(DialogueStep.chat_id.in_(ren_chat_ids)).count()
        db.session.delete(ren)
        db.session.commit()
        check("character delete cascades to chats + steps",
              Chat.query.filter(Chat.id.in_(ren_chat_ids)).count() == 0
              and DialogueStep.query.filter(DialogueStep.chat_id.in_(ren_chat_ids)).count() == 0
              and n_steps > 0)

        # clean up teacher-added step so editor tests start from a known sequential state
        custom = DialogueStep.query.filter_by(seed_id="teacher_custom_1").first()
        if custom:
            chat = custom.chat
            db.session.delete(custom)
            db.session.commit()
            for i, s in enumerate(sorted(chat.steps, key=lambda x: x.order)):
                s.order = i
            db.session.commit()

    # ---------- editor routes (P2b) ----------
    with app.app_context():
        from app.models import User

        teacher = User(username="guru_jepang", role="teacher")
        teacher.set_password("gurupass")
        student = User(username="murid_a", role="student")
        student.set_password("muridpass")
        db.session.add_all([teacher, student])
        db.session.commit()

    c = app.test_client()

    # 1. unauthenticated request -> redirect to login
    r = c.get("/content/")
    check("unauth /content/ redirects", r.status_code in (301, 302, 303))

    # 2. student blocked
    c.post("/login", data={"username": "murid_a", "password": "muridpass"})
    check("student GET /content/ -> 403", c.get("/content/").status_code == 403)
    c.post("/logout")

    # 3. teacher accesses editor index
    c.post("/login", data={"username": "guru_jepang", "password": "gurupass"})
    r = c.get("/content/")
    check("teacher GET /content/ -> 200", r.status_code == 200)
    check("index lists sakura chat", b"Kenalan dengan Sakura" in r.data)

    # 4. edit chat title + context
    with app.app_context():
        chat_id = Chat.query.filter_by(seed_id="sakura_intro").first().id
        sakura_char_id = Character.query.filter_by(seed_id="sakura").first().id
    r = c.post(
        f"/content/chats/{chat_id}/edit",
        data={
            "title": "Kenalan dengan Sakura (revisi)",
            "level_number": "1",
            "character_id": sakura_char_id,
            "intro_summary": "Ringkasan revisi.",
            "context_theme": "kelas/perkenalan",
            "kanas_introduced": "あ\nい\nう",
        },
    )
    check("edit chat -> redirect", r.status_code in (301, 302, 303))
    with app.app_context():
        chat = Chat.query.get(chat_id)
        check("chat title updated", chat.title == "Kenalan dengan Sakura (revisi)")
        check("context_theme updated", chat.context_theme == "kelas/perkenalan")
        check("kanas_introduced updated", chat.kanas_introduced == ["あ", "い", "う"])

    # 5. edit a dialogue step message
    with app.app_context():
        step_id = DialogueStep.query.filter_by(seed_id="s1_step1").first().id
    r = c.post(
        f"/content/steps/{step_id}/edit",
        data={
            "npc_message": "こんにちは！selamat datang!",
            "npc_romaji": "Konnichiwa!",
            "npc_indonesian": "Halo!",
            "is_voice_note": "1",
            "required_reply_kana": "はい",
            "required_reply_romaji": "hai",
            "available_kana_pool": "は\nい\nあ",
        },
    )
    check("edit step -> redirect", r.status_code in (301, 302, 303))
    with app.app_context():
        step = DialogueStep.query.get(step_id)
        check("step message updated", "selamat datang" in step.npc_message)
        check("step voice note kept", step.is_voice_note)
        check("step kana pool parsed", step.available_kana_pool == ["は", "い", "あ"])

    # 6. add new step at the end
    with app.app_context():
        before = DialogueStep.query.filter_by(chat_id=chat_id).count()
    r = c.post(
        f"/content/chats/{chat_id}/steps/new",
        data={"npc_message": "Langkah tambahan.", "required_reply_kana": "はい"},
    )
    check("add step -> redirect", r.status_code in (301, 302, 303))
    with app.app_context():
        after = DialogueStep.query.filter_by(chat_id=chat_id).count()
        check("step count +1", after == before + 1)
        max_order = DialogueStep.query.filter_by(chat_id=chat_id).order_by(DialogueStep.order.desc()).first().order
        check("new step has highest order", max_order == before)

    # 7. move step down one slot (swap first and second)
    with app.app_context():
        steps = DialogueStep.query.filter_by(chat_id=chat_id).order_by(DialogueStep.order).all()
        first_id = steps[0].id
    r = c.post(f"/content/steps/{first_id}/move/down")
    check("move step -> redirect", r.status_code in (301, 302, 303))
    with app.app_context():
        ordered = DialogueStep.query.filter_by(chat_id=chat_id).order_by(DialogueStep.order).all()
        check("step moved down one slot", ordered[1].id == first_id)

    # 8. delete step; ensure sequential orders
    with app.app_context():
        step_to_delete = DialogueStep.query.filter_by(chat_id=chat_id, order=before).first()
        del_id = step_to_delete.id
    r = c.post(f"/content/steps/{del_id}/delete")
    check("delete step -> redirect", r.status_code in (301, 302, 303))
    with app.app_context():
        check("deleted step removed", DialogueStep.query.get(del_id) is None)
        orders = [s.order for s in Chat.query.get(chat_id).steps]
        check("steps renumbered sequentially", orders == list(range(len(orders))))

    # 9. edit character
    with app.app_context():
        char_id = Character.query.filter_by(seed_id="sakura").first().id
    r = c.post(
        f"/content/characters/{char_id}/edit",
        data={"name": "Sakura-san", "role": "Ketua kelas", "avatar_emoji": "🌸"},
    )
    check("edit character -> redirect", r.status_code in (301, 302, 303))
    with app.app_context():
        char = Character.query.get(char_id)
        check("character role updated", char.role == "Ketua kelas")

    # 10. edit kana example word
    with app.app_context():
        kana_id = Kana.query.filter_by(char="あ").first().id
    r = c.post(
        f"/content/kana/{kana_id}/edit",
        data={
            "romaji": "a",
            "row": "a",
            "mnemonic": "apel besar",
            "ex_kana": "あさ",
            "ex_romaji": "asa",
            "ex_meaning": "Pagi",
            "ex_emoji": "🌅",
            "similar_confusions": "お\nめ",
        },
    )
    check("edit kana -> redirect", r.status_code in (301, 302, 303))
    with app.app_context():
        kana = Kana.query.get(kana_id)
        check("kana mnemonic updated", kana.mnemonic == "apel besar")
        check("kana example word updated", kana.example_word == {"kana": "あさ", "romaji": "asa", "meaning": "Pagi", "emoji": "🌅"})
        check("kana confusions updated", kana.similar_confusions == ["お", "め"])

    print("\nRESULT:", "ALL PASS" if _results["ok"] else "SOME FAILED")
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    return 0 if _results["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

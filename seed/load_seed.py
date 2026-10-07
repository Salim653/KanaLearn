"""Idempotent loader for seed/content.json (exported from the legacy React app).

Upserts by stable seed keys and never deletes rows absent from the seed,
so teacher edits made through the web editor survive re-seeding.
Dropped by design: unlockRequirement (no gating) and stickerReward.
"""

from app.extensions import db
from app.models import Kana, Character, KanaRow, Chat, DialogueStep, Lesson, Unit


UNIT_KINDS = ("learn", "checkpoint")

def _upsert(model, lookup: dict, fields: dict):
    row = db.session.query(model).filter_by(**lookup).first()
    if row is None:
        row = model(**lookup, **fields)
        db.session.add(row)
    else:
        for key, value in fields.items():
            setattr(row, key, value)
    return row


def _load_rows(data: dict) -> None:
    rows = data.get("hiraganaRows", []) + data.get("katakanaRows", [])
    for row_data in rows:
        _upsert(
            KanaRow,
            {"row_id": row_data["rowId"], "type": row_data["type"]},
            {"name": row_data["rowName"], "chars": row_data["chars"]},
        )


def _load_units_and_lessons(data: dict) -> None:
    """Derive quiz units/lessons from seeded gojūon rows (idempotent)."""
    seen_track_rows = []
    for row_data in data.get("hiraganaRows", []) + data.get("katakanaRows", []):
        seen_track_rows.append(row_data)

    # order by appearance in the seed (gojūon order)
    for i, row_data in enumerate(seen_track_rows):
        unit = _upsert(
            Unit,
            {"track": row_data["type"], "row": row_data["rowId"]},
            {
                "order": i,
                "title": row_data["rowName"],
            },
        )
        db.session.flush()  # unit.id needed below

        _upsert(
            Lesson,
            {"unit_id": unit.id, "kind": "learn"},
            {
                "order": 1,
                "title": f"Pelajaran 1: {row_data['rowName']}",
                "n_questions": 10,
                "requires_prior": False,
            },
        )
        _upsert(
            Lesson,
            {"unit_id": unit.id, "kind": "checkpoint"},
            {
                "order": 2,
                "title": f"Checkpoint: {row_data['rowName']}",
                "n_questions": 10,
                "requires_prior": True,
            },
        )
        _upsert(
            Lesson,
            {"unit_id": unit.id, "kind": "practice"},
            {
                "order": 3,
                "title": f"Latihan: {row_data['rowName']}",
                "n_questions": 10,
                "requires_prior": False,
            },
        )


def _load_kana(data: dict) -> None:
    for char, k in data.get("kana", {}).items():
        _upsert(
            Kana,
            {"char": char},
            {
                "romaji": k["romaji"],
                "type": k["type"],
                "row": k["row"],
                "mnemonic": k.get("mnemonic"),
                "example_word": k.get("exampleWord"),
                "similar_confusions": k.get("similarConfusions"),
                "strokes": k.get("strokes"),
            },
        )


def _load_characters(data: dict) -> None:
    for seed_id, c in data.get("characters", {}).items():
        _upsert(
            Character,
            {"seed_id": seed_id},
            {
                "name": c["name"],
                "katakana_name": c.get("katakanaName"),
                "role": c.get("role"),
                "avatar_emoji": c.get("avatarEmoji"),
                "avatar_bg": c.get("avatarBg"),
                "theme_color": c.get("themeColor"),
                "personality": c.get("personality"),
                "greeting_voice_note": c.get("greetingVoiceNote"),
            },
        )


def _step_fields(index: int, s: dict) -> dict:
    return {
        "order": index,
        "npc_message": s["npcMessage"],
        "npc_romaji": s.get("npcRomaji"),
        "npc_indonesian": s.get("npcIndonesian"),
        "is_voice_note": bool(s.get("isVoiceNote", False)),
        "is_handwriting_challenge": bool(s.get("isHandwritingChallenge", False)),
        "handwriting_target_char": s.get("handwritingTargetChar"),
        "required_reply_kana": s.get("requiredReplyKana"),
        "required_reply_romaji": s.get("requiredReplyRomaji"),
        "required_reply_indonesian": s.get("requiredReplyIndonesian"),
        "allowed_alternatives": s.get("allowedAlternatives"),
        "available_kana_pool": s.get("availableKanaPool"),
        "wrong_reaction": s.get("wrongReaction"),
        "wrong_reaction_romaji": s.get("wrongReactionRomaji"),
    }


def _load_chats(data: dict) -> None:
    characters = {c.seed_id: c for c in db.session.query(Character).all()}

    for chat_data in data.get("chatLevels", []):
        character = characters.get(chat_data["npcId"])
        if character is None:
            raise ValueError(
                f"Chat {chat_data['id']!r} references unknown npcId "
                f"{chat_data['npcId']!r}"
            )
        chat = _upsert(
            Chat,
            {"seed_id": chat_data["id"]},
            {
                "level_number": chat_data["levelNumber"],
                "title": chat_data["title"],
                "character_id": character.id,
                "intro_summary": chat_data.get("introSummary"),
                "context_theme": character.role,
                "kanas_introduced": chat_data.get("kanasIntroduced"),
            },
        )
        db.session.flush()  # chat.id must exist before steps

        existing_steps = {s.seed_id: s for s in chat.steps}
        for index, step_data in enumerate(chat_data.get("dialogueSteps", [])):
            fields = _step_fields(index, step_data)
            step = existing_steps.get(step_data["id"])
            if step is None:
                db.session.add(
                    DialogueStep(chat_id=chat.id, seed_id=step_data["id"], **fields)
                )
            else:
                for key, value in fields.items():
                    setattr(step, key, value)


def load_seed(data: dict) -> dict:
    """Upsert all seed content; return total row counts per table."""
    _load_rows(data)
    _load_units_and_lessons(data)
    _load_kana(data)
    _load_characters(data)
    db.session.flush()
    _load_chats(data)
    db.session.commit()
    return {
        "kana": db.session.query(Kana).count(),
        "characters": db.session.query(Character).count(),
        "rows": db.session.query(KanaRow).count(),
        "chats": db.session.query(Chat).count(),
        "steps": db.session.query(DialogueStep).count(),
        "units": db.session.query(Unit).count(),
        "lessons": db.session.query(Lesson).count(),
    }

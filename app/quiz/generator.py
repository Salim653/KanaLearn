"""Procedural question generator for the Duolingo-style quiz.

All question types are built from the Kana table (and its JSON helper fields).
No hand-authored question bank is required for v1.
"""

import random
from datetime import datetime, timedelta

from app.extensions import db
from app.models import Kana, KanaMastery, KanaRow, Lesson, Unit


def _shuffle(items):
    s = list(items)
    random.shuffle(s)
    return s


def _distractors(target: Kana, pool: list[Kana], n=3):
    """Pick plausible distractors for a target kana."""
    candidates = []
    # prefer similar confusions
    if target.similar_confusions:
        for char in target.similar_confusions:
            k = next((x for x in pool if x.char == char), None)
            if k and k.char != target.char:
                candidates.append(k)
    # fall back to same-row / same-type pool
    for k in pool:
        if k.char != target.char and k not in candidates:
            candidates.append(k)
    random.shuffle(candidates)
    seen = {target.char}
    out = []
    for k in candidates:
        if k.char not in seen:
            out.append(k)
            seen.add(k.char)
        if len(out) >= n:
            break
    return out


def _sample(pool: list[Kana], n: int):
    return random.sample(pool, min(n, len(pool)))


def q_kana_to_romaji(target: Kana, pool: list[Kana]) -> dict:
    opts = _distractors(target, pool, 3)
    options = _shuffle([target.romaji] + [k.romaji for k in opts])
    return {
        "type": "kana_to_romaji",
        "prompt": target.char,
        "options": options,
        "answer": target.romaji,
        "tts_text": target.char,
        "explain": f"{target.char} dibaca '{target.romaji}'.",
    }


def q_romaji_to_kana(target: Kana, pool: list[Kana]) -> dict:
    opts = _distractors(target, pool, 3)
    options = _shuffle([target.char] + [k.char for k in opts])
    return {
        "type": "romaji_to_kana",
        "prompt": target.romaji,
        "options": options,
        "answer": target.char,
        "tts_text": target.char,
        "explain": f"'{target.romaji}' ditulis {target.char}.",
    }


def q_listen_pick_kana(target: Kana, pool: list[Kana]) -> dict:
    opts = _distractors(target, pool, 3)
    options = _shuffle([target.char] + [k.char for k in opts])
    return {
        "type": "listen_pick_kana",
        "prompt": "Dengarkan dan pilih hurufnya",
        "options": options,
        "answer": target.char,
        "tts_text": target.char,
        "explain": f"Huruf yang dibaca adalah {target.char} ({target.romaji}).",
    }


def q_build_word_from_tiles(target: Kana, pool: list[Kana]) -> dict:
    # find an example word in the target row, preferably 2-4 kana long
    candidates = [k for k in pool if k.example_word and k.example_word.get("kana")]
    random.shuffle(candidates)
    word = None
    for k in candidates:
        w = k.example_word["kana"]
        if 2 <= len(w) <= 4:
            word = w
            target = k
            break
    if not word:
        # fallback to a simple 2-char combo within the row
        if len(pool) >= 2:
            pair = random.sample(pool, 2)
            word = pair[0].char + pair[1].char
        else:
            word = target.char
    tiles = list(word)
    # add distractor tiles from pool (limit total tiles)
    extra = _distractors(target, pool, len(word))
    for k in extra:
        if k.char not in tiles:
            tiles.append(k.char)
    return {
        "type": "build_word",
        "prompt": f"Susun kata: {target.example_word.get('meaning', 'kata')} {target.example_word.get('emoji', '')}".strip(),
        "tiles": _shuffle(tiles),
        "answer": word,
        "tts_text": word,
        "explain": f"'{word}' dibaca '{target.example_word.get('romaji', target.romaji)}' — artinya '{target.example_word.get('meaning', '')}'.",
    }


def q_word_to_meaning(target: Kana, pool: list[Kana]) -> dict:
    meaning = target.example_word.get("meaning") if target.example_word else None
    if not meaning:
        return q_kana_to_romaji(target, pool)
    opts = _distractors(target, pool, 3)
    distractor_meanings = []
    for k in opts:
        if k.example_word and k.example_word.get("meaning"):
            distractor_meanings.append(k.example_word["meaning"])
    # ensure 3 options
    while len(distractor_meanings) < 3:
        for k in random.sample(pool, min(len(pool), 3)):
            m = k.example_word.get("meaning") if k.example_word else None
            if m and m not in distractor_meanings and m != meaning:
                distractor_meanings.append(m)
                if len(distractor_meanings) >= 3:
                    break
    options = _shuffle([meaning] + distractor_meanings[:3])
    return {
        "type": "word_to_meaning",
        "prompt": target.example_word.get("kana", target.char),
        "options": options,
        "answer": meaning,
        "tts_text": target.example_word.get("kana", target.char),
        "explain": f"'{target.example_word.get('kana', target.char)}' artinya '{meaning}'.",
    }


def q_lookalike_discrimination(target: Kana, pool: list[Kana]) -> dict:
    opts = _distractors(target, pool, 3)
    options = _shuffle([target.char] + [k.char for k in opts])
    return {
        "type": "lookalike",
        "prompt": f"Pilih huruf {target.romaji}",
        "options": options,
        "answer": target.char,
        "tts_text": target.char,
        "explain": target.mnemonic or f"Ini adalah {target.char}.",
    }


def q_match_pairs(targets: list[Kana]) -> dict:
    # Simplify matching to a single MCQ on the first pair; keeps the client small.
    target = targets[0]
    distractors = [k.romaji for k in targets[1:]]
    while len(distractors) < 3:
        distractors.append("-")
    options = _shuffle([target.romaji] + distractors[:3])
    return {
        "type": "match_pairs",
        "prompt": f"Pilih romaji untuk {target.char}",
        "options": options,
        "answer": target.romaji,
        "kana_char": target.char,
        "tts_text": target.char,
        "explain": f"{target.char} dibaca '{target.romaji}'.",
    }


BUILDERS = {
    "learn": [q_kana_to_romaji, q_romaji_to_kana, q_listen_pick_kana, q_build_word_from_tiles, q_word_to_meaning],
    "checkpoint": [q_kana_to_romaji, q_romaji_to_kana, q_listen_pick_kana, q_word_to_meaning, q_lookalike_discrimination, q_match_pairs],
    "practice": [q_kana_to_romaji, q_romaji_to_kana, q_listen_pick_kana, q_lookalike_discrimination, q_match_pairs, q_word_to_meaning],
}


def _row_chars(track: str, row_id: str):
    row = KanaRow.query.filter_by(type=track, row_id=row_id).first()
    return row.chars if row else []


def _pool_for_lesson(lesson: Lesson, student_id: int):
    """Return the kana pool for a lesson."""
    unit = db.session.get(Unit, lesson.unit_id)
    row_chars = list(_row_chars(unit.track, unit.row) or [])
    # include a few previously learned rows for review in checkpoint/practice
    prior = []
    if lesson.kind in ("checkpoint", "practice"):
        prior_units = Unit.query.filter(
            Unit.track == unit.track,
            Unit.order < unit.order,
        ).order_by(Unit.order.desc()).limit(1).all()
        for u in prior_units:
            prior.extend(_row_chars(u.track, u.row) or [])
    pool_chars = list(dict.fromkeys(row_chars + prior))
    pool = Kana.query.filter(Kana.char.in_(pool_chars)).all()
    if lesson.kind == "practice":
        due = KanaMastery.query.filter(
            KanaMastery.student_id == student_id,
            KanaMastery.next_due <= datetime.utcnow() + timedelta(days=1),
        ).all()
        due_chars = [m.kana_char for m in due if m.kana_char in pool_chars]
        if due_chars:
            due_pool = [k for k in pool if k.char in due_chars]
            if due_pool:
                return due_pool, pool
    return pool, pool


def generate_lesson_questions(lesson: Lesson, student_id: int, n: int | None = None) -> list[dict]:
    """Build a list of question dicts for a lesson."""
    if n is None:
        n = lesson.n_questions or 10
    pool, fallback_pool = _pool_for_lesson(lesson, student_id)
    if not pool:
        pool = fallback_pool
    if not pool:
        return []

    builders = BUILDERS.get(lesson.kind, BUILDERS["learn"])
    questions = []
    used = set()
    max_attempts = n * 10
    attempts = 0
    while len(questions) < n and attempts < max_attempts:
        attempts += 1
        builder = random.choice(builders)
        if builder == q_match_pairs:
            sample = _sample(pool, min(4, len(pool)))
            q = q_match_pairs(sample)
            key = (q["type"], tuple(sorted(p["kana"] for p in q["answer"])))
        else:
            target = random.choice(pool)
            q = builder(target, pool)
            key = (q["type"], q.get("answer"))
        if key in used:
            continue
        used.add(key)
        questions.append(q)
    return questions

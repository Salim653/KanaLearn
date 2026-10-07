"""Teacher/admin content editor: chats, dialogue steps, characters, kana.

Content is global (not per class), so both teachers and admins may edit.
Seed-owned rows keep their seed_id; re-running `flask seed-content` refreshes
seed fields but never deletes rows added here.
"""

import re
import uuid

from flask import abort, flash, redirect, render_template, request, url_for
from sqlalchemy import func

from app.auth.decorators import roles_required
from app.content import bp
from app.extensions import db
from app.models import Chat, Character, DialogueStep, Kana, KanaRow

editors_only = roles_required("teacher", "admin")


# ---------- helpers ----------

def _get_or_404(model, obj_id):
    obj = db.session.get(model, obj_id)
    if obj is None:
        abort(404)
    return obj


def _parse_list(raw):
    """Textarea/CSV input -> list[str] (None when empty)."""
    if raw is None:
        return None
    items = [part.strip() for part in re.split(r"[\n,]", raw)]
    items = [item for item in items if item]
    return items or None


def _list_to_text(value):
    return "\n".join(value) if value else ""


def _slugify(text):
    slug = re.sub(r"[^a-z0-9]+", "_", (text or "").strip().lower()).strip("_")
    return slug or "chat"


def _unique_seed_id(base):
    seed_id = base
    counter = 2
    while Chat.query.filter_by(seed_id=seed_id).first() is not None:
        seed_id = f"{base}_{counter}"
        counter += 1
    return seed_id


def _renumber(chat):
    for index, step in enumerate(sorted(chat.steps, key=lambda s: s.order)):
        step.order = index


def _kana_order_map():
    """(type, char) -> display index, following the seeded row order."""
    order = {}
    position = 0
    for kana_type in ("hiragana", "katakana"):
        rows = KanaRow.query.filter_by(type=kana_type).order_by(KanaRow.id).all()
        for row in rows:
            for char in row.chars or []:
                order[(kana_type, char)] = position
                position += 1
    return order


# ---------- dashboard ----------

@bp.route("/")
@editors_only
def index():
    chats = Chat.query.order_by(Chat.level_number, Chat.id).all()
    characters = Character.query.order_by(Character.name).all()
    kana_count = db.session.query(func.count(Kana.id)).scalar()
    return render_template(
        "content/index.html",
        chats=chats,
        characters=characters,
        kana_count=kana_count,
    )


# ---------- chats ----------

def _apply_chat_form(chat, form):
    title = (form.get("title") or "").strip()
    character = Character.query.filter_by(id=form.get("character_id", type=int)).first()
    if not title:
        flash("Judul chat wajib diisi.", "error")
        return False
    if character is None:
        flash("Pilih karakter untuk chat ini.", "error")
        return False

    chat.title = title
    chat.character_id = character.id
    chat.level_number = form.get("level_number", type=int) or chat.level_number or 1
    chat.intro_summary = (form.get("intro_summary") or "").strip() or None
    chat.context_theme = (form.get("context_theme") or "").strip() or None
    chat.kanas_introduced = _parse_list(form.get("kanas_introduced"))
    return True


@bp.route("/chats/new", methods=["GET", "POST"])
@editors_only
def chat_new():
    if request.method == "POST":
        form = request.form
        title = (form.get("title") or "").strip()
        chat = Chat(
            seed_id=_unique_seed_id(_slugify(form.get("seed_id") or title)),
            title=title or "(tanpa judul)",
            level_number=form.get("level_number", type=int)
            or (db.session.query(func.max(Chat.level_number)).scalar() or 0) + 1,
        )
        db.session.add(chat)
        if _apply_chat_form(chat, form):
            db.session.commit()
            flash(f'Chat "{chat.title}" dibuat. Sekarang tambahkan langkah dialognya.', "success")
            return redirect(url_for("content.chat_edit", chat_id=chat.id))
        db.session.rollback()
    return render_template(
        "content/chat_edit.html",
        chat=None,
        characters=Character.query.order_by(Character.name).all(),
        next_level=(db.session.query(func.max(Chat.level_number)).scalar() or 0) + 1,
    )


@bp.route("/chats/<int:chat_id>/edit", methods=["GET", "POST"])
@editors_only
def chat_edit(chat_id):
    chat = _get_or_404(Chat, chat_id)
    if request.method == "POST":
        if _apply_chat_form(chat, request.form):
            db.session.commit()
            flash("Perubahan chat disimpan.", "success")
            return redirect(url_for("content.chat_edit", chat_id=chat.id))
        db.session.rollback()
    return render_template(
        "content/chat_edit.html",
        chat=chat,
        characters=Character.query.order_by(Character.name).all(),
        next_level=chat.level_number,
    )


@bp.route("/chats/<int:chat_id>/delete", methods=["POST"])
@editors_only
def chat_delete(chat_id):
    chat = _get_or_404(Chat, chat_id)
    db.session.delete(chat)  # cascades to its steps
    db.session.commit()
    flash("Chat dihapus beserta langkah dialognya.", "success")
    return redirect(url_for("content.index"))


# ---------- dialogue steps ----------

def _apply_step_form(step, form):
    message = (form.get("npc_message") or "").strip()
    if not message:
        flash("Pesan NPC wajib diisi.", "error")
        return False
    step.npc_message = message
    step.npc_romaji = (form.get("npc_romaji") or "").strip() or None
    step.npc_indonesian = (form.get("npc_indonesian") or "").strip() or None
    step.is_voice_note = bool(form.get("is_voice_note"))
    step.is_handwriting_challenge = bool(form.get("is_handwriting_challenge"))
    step.handwriting_target_char = (form.get("handwriting_target_char") or "").strip() or None
    step.required_reply_kana = (form.get("required_reply_kana") or "").strip() or None
    step.required_reply_romaji = (form.get("required_reply_romaji") or "").strip() or None
    step.required_reply_indonesian = (form.get("required_reply_indonesian") or "").strip() or None
    step.allowed_alternatives = _parse_list(form.get("allowed_alternatives"))
    step.available_kana_pool = _parse_list(form.get("available_kana_pool"))
    step.wrong_reaction = (form.get("wrong_reaction") or "").strip() or None
    step.wrong_reaction_romaji = (form.get("wrong_reaction_romaji") or "").strip() or None
    return True


@bp.route("/chats/<int:chat_id>/steps/new", methods=["GET", "POST"])
@editors_only
def step_new(chat_id):
    chat = _get_or_404(Chat, chat_id)
    if request.method == "POST":
        next_order = max([s.order for s in chat.steps], default=-1) + 1
        step = DialogueStep(
            chat_id=chat.id,
            seed_id=f"custom_{uuid.uuid4().hex[:8]}",
            order=next_order,
            npc_message="",
        )
        db.session.add(step)
        if _apply_step_form(step, request.form):
            db.session.commit()
            flash("Langkah dialog ditambahkan.", "success")
            return redirect(url_for("content.chat_edit", chat_id=chat.id))
        db.session.rollback()
    return render_template("content/step_edit.html", chat=chat, step=None)


@bp.route("/steps/<int:step_id>/edit", methods=["GET", "POST"])
@editors_only
def step_edit(step_id):
    step = _get_or_404(DialogueStep, step_id)
    if request.method == "POST":
        if _apply_step_form(step, request.form):
            db.session.commit()
            flash("Langkah dialog diperbarui.", "success")
            return redirect(url_for("content.chat_edit", chat_id=step.chat_id))
        db.session.rollback()
    return render_template("content/step_edit.html", chat=step.chat, step=step)


@bp.route("/steps/<int:step_id>/delete", methods=["POST"])
@editors_only
def step_delete(step_id):
    step = _get_or_404(DialogueStep, step_id)
    chat_id = step.chat_id
    chat = step.chat
    db.session.delete(step)
    db.session.flush()
    _renumber(chat)
    db.session.commit()
    flash("Langkah dialog dihapus.", "success")
    return redirect(url_for("content.chat_edit", chat_id=chat_id))


@bp.route("/steps/<int:step_id>/move/<direction>", methods=["POST"])
@editors_only
def step_move(step_id, direction):
    if direction not in ("up", "down"):
        abort(404)
    step = _get_or_404(DialogueStep, step_id)
    chat = step.chat
    siblings = sorted(chat.steps, key=lambda s: s.order)
    index = siblings.index(step)
    target = index - 1 if direction == "up" else index + 1
    if 0 <= target < len(siblings):
        siblings[index].order, siblings[target].order = (
            siblings[target].order,
            siblings[index].order,
        )
        _renumber(chat)
        db.session.commit()
    return redirect(url_for("content.chat_edit", chat_id=chat.id))


# ---------- characters ----------

def _apply_character_form(character, form):
    name = (form.get("name") or "").strip()
    if not name:
        flash("Nama karakter wajib diisi.", "error")
        return False
    character.name = name
    character.katakana_name = (form.get("katakana_name") or "").strip() or None
    character.role = (form.get("role") or "").strip() or None
    character.avatar_emoji = (form.get("avatar_emoji") or "").strip() or None
    character.avatar_bg = (form.get("avatar_bg") or "").strip() or None
    character.theme_color = (form.get("theme_color") or "").strip() or None
    character.personality = (form.get("personality") or "").strip() or None
    character.greeting_voice_note = (form.get("greeting_voice_note") or "").strip() or None
    return True


@bp.route("/characters/new", methods=["GET", "POST"])
@editors_only
def character_new():
    if request.method == "POST":
        character = Character(seed_id=f"npc_{uuid.uuid4().hex[:8]}", name="-")
        db.session.add(character)
        if _apply_character_form(character, request.form):
            db.session.commit()
            flash(f'Karakter "{character.name}" dibuat.', "success")
            return redirect(url_for("content.index"))
        db.session.rollback()
    return render_template("content/character_edit.html", character=None)


@bp.route("/characters/<int:character_id>/edit", methods=["GET", "POST"])
@editors_only
def character_edit(character_id):
    character = _get_or_404(Character, character_id)
    if request.method == "POST":
        if _apply_character_form(character, request.form):
            db.session.commit()
            flash("Karakter diperbarui.", "success")
            return redirect(url_for("content.index"))
        db.session.rollback()
    return render_template("content/character_edit.html", character=character)


@bp.route("/characters/<int:character_id>/delete", methods=["POST"])
@editors_only
def character_delete(character_id):
    character = _get_or_404(Character, character_id)
    if character.chats:
        flash("Karakter masih dipakai oleh chat. Hapus atau pindahkan chatnya dulu.", "error")
        return redirect(url_for("content.index"))
    db.session.delete(character)
    db.session.commit()
    flash("Karakter dihapus.", "success")
    return redirect(url_for("content.index"))


# ---------- kana ----------

@bp.route("/kana")
@editors_only
def kana_list():
    kana_type = request.args.get("type", "all")
    query = (request.args.get("q") or "").strip()
    kanas = Kana.query
    if kana_type in ("hiragana", "katakana"):
        kanas = kanas.filter_by(type=kana_type)
    if query:
        pattern = f"%{query}%"
        kanas = kanas.filter(
            db.or_(Kana.char.like(pattern), Kana.romaji.ilike(pattern))
        )
    order_map = _kana_order_map()
    kanas = kanas.all()
    kanas.sort(key=lambda k: order_map.get((k.type, k.char), 10_000))
    return render_template(
        "content/kana_list.html", kanas=kanas, kana_type=kana_type, query=query
    )


@bp.route("/kana/<int:kana_id>/edit", methods=["GET", "POST"])
@editors_only
def kana_edit(kana_id):
    kana = _get_or_404(Kana, kana_id)
    if request.method == "POST":
        form = request.form
        kana.romaji = (form.get("romaji") or "").strip() or kana.romaji
        kana.row = (form.get("row") or "").strip() or kana.row
        kana.mnemonic = (form.get("mnemonic") or "").strip() or None
        example_word = {
            "kana": (form.get("ex_kana") or "").strip(),
            "romaji": (form.get("ex_romaji") or "").strip(),
            "meaning": (form.get("ex_meaning") or "").strip(),
            "emoji": (form.get("ex_emoji") or "").strip(),
        }
        kana.example_word = example_word if any(example_word.values()) else None
        kana.similar_confusions = _parse_list(form.get("similar_confusions"))
        db.session.commit()
        flash(f"Kana {kana.char} diperbarui.", "success")
        return redirect(url_for("content.kana_list", type=request.form.get("return_type", "all")))

    row_ids = [
        r.row_id
        for r in KanaRow.query.filter_by(type=kana.type).order_by(KanaRow.id).all()
    ]
    if kana.row not in row_ids:
        row_ids.insert(0, kana.row)
    return render_template(
        "content/kana_edit.html",
        kana=kana,
        row_ids=row_ids,
        return_type=request.args.get("type", "all"),
    )

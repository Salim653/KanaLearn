"""Student-facing chat simulator.

All chats are reachable without gating (Dojo is fully decoupled).
State is stored server-side in StudentChatState; answer attempts are
logged to AnswerLog for P8 adaptive drill.
"""

from datetime import datetime

from flask import abort, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.chat import bp
from app.extensions import db
from app.models import AnswerLog, Chat, DialogueStep, Kana, StudentChatState


def _state_or_create(student_id: int, chat_id: int) -> StudentChatState:
    state = StudentChatState.query.filter_by(student_id=student_id, chat_id=chat_id).first()
    if state is None:
        state = StudentChatState(student_id=student_id, chat_id=chat_id, current_step_order=0)
        db.session.add(state)
        db.session.commit()
    return state


def _format_npc_text(text: str, username: str) -> str:
    # Replace {PLAYER_NAME} with username + optional san removed if username contains katakana
    return text.replace("{PLAYER_NAME}", username)


def _get_step_messages(state: StudentChatState) -> list:
    """Return message history up to the current step, suitable for JSON/template."""
    chat = state.chat
    steps = sorted(chat.steps, key=lambda s: s.order)
    messages = []
    username = current_user.username

    for i, step in enumerate(steps):
        if i > state.current_step_order:
            break
        messages.append({
            "sender": "npc",
            "text": _format_npc_text(step.npc_message, username),
            "romaji": _format_npc_text(step.npc_romaji or "", username),
            "indonesian": _format_npc_text(step.npc_indonesian or "", username),
            "is_voice_note": step.is_voice_note,
            "is_handwriting": step.is_handwriting_challenge,
            "handwriting_target": step.handwriting_target_char,
        })
        if i < state.current_step_order:
            # add the player reply that passed this step
            messages.append({
                "sender": "player",
                "text": step.required_reply_kana,
                "is_handwriting": step.is_handwriting_challenge,
            })

    return messages


def _stars(state: StudentChatState, steps_count: int) -> int:
    """Award 3/2/1 stars based on wrong attempts + hints, but always at least 1 on completion."""
    if not state.completed:
        return 0
    penalties = state.wrong_count + state.hint_count
    return max(1, min(3, 3 - penalties))


@bp.route("/")
@login_required
def index():
    chats = Chat.query.order_by(Chat.level_number, Chat.id).all()
    states = {
        s.chat_id: s for s in StudentChatState.query.filter_by(student_id=current_user.id).all()
    }
    return render_template("chat/index.html", chats=chats, states=states)


@bp.route("/<int:chat_id>")
@login_required
def play(chat_id: int):
    chat = Chat.query.get_or_404(chat_id)
    state = _state_or_create(current_user.id, chat.id)
    steps = sorted(chat.steps, key=lambda s: s.order)
    messages = _get_step_messages(state)
    current_step = steps[state.current_step_order] if state.current_step_order < len(steps) else None

    current_step_data = _step_payload(current_step, current_user.username) if current_step else None

    return render_template(
        "chat/play.html",
        chat=chat,
        state=state,
        messages=messages,
        current_step=current_step,
        current_step_data=current_step_data,
        completed=state.completed,
        stars=_stars(state, len(steps)),
    )


def _step_payload(step, username):
    if step is None:
        return None
    strokes = []
    if step.is_handwriting_challenge and step.handwriting_target_char:
        kana = Kana.query.filter_by(char=step.handwriting_target_char).first()
        if kana and kana.strokes:
            strokes = kana.strokes
    return {
        "npc_message": step.npc_message,
        "npc_romaji": step.npc_romaji or "",
        "npc_indonesian": step.npc_indonesian or "",
        "is_voice_note": step.is_voice_note,
        "is_handwriting_challenge": step.is_handwriting_challenge,
        "handwriting_target_char": step.handwriting_target_char,
        "handwriting_strokes": strokes,
        "required_reply_kana": step.required_reply_kana,
        "available_kana_pool": step.available_kana_pool or [],
    }


@bp.route("/<int:chat_id>/state")
@login_required
def state(chat_id: int):
    chat = Chat.query.get_or_404(chat_id)
    st = _state_or_create(current_user.id, chat.id)
    steps = sorted(chat.steps, key=lambda s: s.order)
    current = steps[st.current_step_order] if st.current_step_order < len(steps) else None
    return jsonify({
        "current_step": _step_payload(current, current_user.username),
        "completed": st.completed,
        "hearts": st.hearts or 5,
        "stars": _stars(st, len(steps)),
        "order": st.current_step_order,
        "total_steps": len(steps),
    })


@bp.route("/<int:chat_id>/reset", methods=["POST"])
@login_required
def reset(chat_id: int):
    state = StudentChatState.query.filter_by(student_id=current_user.id, chat_id=chat_id).first()
    if state:
        state.current_step_order = 0
        state.completed = False
        state.hearts = 5
        state.wrong_count = 0
        state.hint_count = 0
        state.stars = 0
        db.session.commit()
    return redirect(url_for("chat.play", chat_id=chat_id))


@bp.route("/<int:chat_id>/submit", methods=["POST"])
@login_required
def submit(chat_id: int):
    chat = Chat.query.get_or_404(chat_id)
    state = _state_or_create(current_user.id, chat.id)
    steps = sorted(chat.steps, key=lambda s: s.order)

    if state.completed or state.current_step_order >= len(steps):
        return jsonify({"done": True, "stars": _stars(state, len(steps))})

    step = steps[state.current_step_order]
    reply = (request.form.get("reply") or "").strip()
    start_ms = request.form.get("start_ms", type=int)
    response_ms = None
    if start_ms:
        response_ms = int(datetime.utcnow().timestamp() * 1000) - start_ms

    is_handwriting = step.is_handwriting_challenge
    handwriting_feedback = None
    if is_handwriting:
        # The client now scores the drawing against the reference strokes and
        # sends a similarity percent. Accept only decent attempts; fall back to
        # "any non-empty drawing counts" when no score is provided (old client).
        hw_score = request.form.get("handwriting_score", type=float)
        has_drawing = bool(request.form.get("handwriting_data"))
        if hw_score is not None:
            is_correct = hw_score >= 55.0
            handwriting_feedback = f"Ketepatan tulisan: {hw_score:.0f}%"
        else:
            is_correct = bool(reply) or has_drawing
    else:
        is_correct = reply == (step.required_reply_kana or "")
        if not is_correct and step.allowed_alternatives:
            is_correct = reply in step.allowed_alternatives

    log = AnswerLog(
        student_id=current_user.id,
        chat_id=chat.id,
        step_id=step.id,
        question_type="chat",
        is_correct=is_correct,
        response_ms=response_ms,
    )
    db.session.add(log)

    if is_correct:
        state.current_step_order += 1
        if state.current_step_order >= len(steps):
            state.completed = True
            state.stars = _stars(state, len(steps))
    else:
        state.wrong_count += 1
        state.hearts = max(0, (state.hearts or 5) - 1)

    db.session.commit()

    next_step = steps[state.current_step_order] if state.current_step_order < len(steps) else None
    return jsonify({
        "correct": is_correct,
        "done": state.completed,
        "game_over": state.hearts == 0 and not state.completed,
        "hearts": state.hearts or 5,
        "stars": _stars(state, len(steps)),
        "handwriting_feedback": handwriting_feedback,
        "wrong_reaction": _format_npc_text(step.wrong_reaction or "", current_user.username) if not is_correct else None,
        "next_message": {
            "sender": "npc",
            "text": _format_npc_text(next_step.npc_message, current_user.username),
            "romaji": _format_npc_text(next_step.npc_romaji or "", current_user.username),
            "indonesian": _format_npc_text(next_step.npc_indonesian or "", current_user.username),
            "is_voice_note": next_step.is_voice_note,
            "is_handwriting": next_step.is_handwriting_challenge,
            "handwriting_target": next_step.handwriting_target_char,
        } if next_step and is_correct else None,
    })


@bp.route("/<int:chat_id>/hint", methods=["POST"])
@login_required
def hint(chat_id: int):
    chat = Chat.query.get_or_404(chat_id)
    state = _state_or_create(current_user.id, chat.id)
    steps = sorted(chat.steps, key=lambda s: s.order)

    if state.completed or state.current_step_order >= len(steps):
        return jsonify({"hint": None})

    state.hint_count += 1
    db.session.commit()

    step = steps[state.current_step_order]
    return jsonify({
        "hint": {
            "kana": step.required_reply_kana,
            "romaji": step.required_reply_romaji,
            "indonesian": step.required_reply_indonesian,
        }
    })

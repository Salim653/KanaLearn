"""Duolingo-style quiz routes: lesson path, lesson runner, result recording."""

import random
from datetime import datetime, timedelta

from flask import abort, jsonify, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func

from app.extensions import db
from app.models import Classroom, Enrollment, Kana, KanaMastery, Lesson, LessonResult, StudentQuizState, Unit, User
from app.quiz import bp
from app.quiz.generator import generate_lesson_questions


def _quiz_state(student_id: int) -> StudentQuizState:
    state = StudentQuizState.query.filter_by(student_id=student_id).first()
    if state is None:
        state = StudentQuizState(student_id=student_id)
        db.session.add(state)
        db.session.commit()
    return state


def _classmates_for_leaderboard(student_id: int):
    """Return IDs in the same class as the student, or all students if no class."""
    class_ids = [e.class_id for e in Enrollment.query.filter_by(student_id=student_id).all()]
    if not class_ids:
        return []
    return [
        e.student_id
        for e in Enrollment.query.filter(Enrollment.class_id.in_(class_ids)).all()
    ]


def _update_mastery(student_id: int, kana_char: str, is_correct: bool):
    mastery = KanaMastery.query.filter_by(student_id=student_id, kana_char=kana_char).first()
    if mastery is None:
        mastery = KanaMastery(
            student_id=student_id,
            kana_char=kana_char,
            n_correct=0,
            n_incorrect=0,
            half_life=1.0,
            next_due=datetime.utcnow(),
        )
        db.session.add(mastery)

    mastery.last_seen = datetime.utcnow()
    if mastery.n_correct is None:
        mastery.n_correct = 0
    if mastery.n_incorrect is None:
        mastery.n_incorrect = 0
    if mastery.half_life is None:
        mastery.half_life = 1.0
    if is_correct:
        mastery.n_correct += 1
        # grow half-life up to 30 days
        mastery.half_life = min(30.0, mastery.half_life * 1.5)
    else:
        mastery.n_incorrect += 1
        mastery.half_life = max(0.25, mastery.half_life * 0.7)

    # HLR-lite: next_due = now + half-life days, jittered
    due_days = mastery.half_life
    mastery.next_due = datetime.utcnow() + timedelta(days=due_days)
    return mastery


def _mastery_for(student_id: int):
    return {m.kana_char: m for m in KanaMastery.query.filter_by(student_id=student_id).all()}


@bp.route("/")
@login_required
def index():
    track = request.args.get("track", "hiragana")
    if track not in ("hiragana", "katakana"):
        track = "hiragana"

    units = Unit.query.filter_by(track=track).order_by(Unit.order).all()
    mastery = _mastery_for(current_user.id)
    results = {
        (r.lesson_id): r for r in LessonResult.query.filter_by(student_id=current_user.id).all()
    }

    # compute unit progress: a kana counts "learned" if n_correct >= 2 across >= 1 type
    rows = []
    for unit in units:
        kana_chars = [k.char for k in Kana.query.filter_by(type=track, row=unit.row).all()]
        learned = sum(
            1
            for c in kana_chars
            if mastery.get(c) and mastery[c].n_correct >= 2
        )
        total = len(kana_chars) or 1
        pct = int(100 * learned / total)
        rows.append({
            "unit": unit,
            "lessons": sorted(unit.lessons, key=lambda l: l.order),
            "results": results,
            "progress": pct,
        })

    return render_template(
        "quiz/index.html",
        track=track,
        units=rows,
        xp=_quiz_state(current_user.id).xp,
    )


@bp.route("/lesson/<int:lesson_id>")
@login_required
def play(lesson_id: int):
    lesson = Lesson.query.get_or_404(lesson_id)
    return render_template("quiz/play.html", lesson=lesson)


@bp.route("/lesson/<int:lesson_id>/questions")
@login_required
def questions(lesson_id: int):
    lesson = Lesson.query.get_or_404(lesson_id)
    qs = generate_lesson_questions(lesson, current_user.id)
    return jsonify({"questions": qs, "hearts_enabled": _quiz_state(current_user.id).hearts_enabled})


@bp.route("/lesson/<int:lesson_id>/result", methods=["POST"])
@login_required
def result(lesson_id: int):
    lesson = Lesson.query.get_or_404(lesson_id)
    payload = request.get_json(silent=True) or {}
    outcomes = payload.get("outcomes", [])

    correct_count = sum(1 for o in outcomes if o.get("correct"))
    total = len(outcomes)
    xp_earned = correct_count + (5 if correct_count == total else 0)

    state = _quiz_state(current_user.id)
    state.xp += xp_earned

    result_record = LessonResult(
        student_id=current_user.id,
        lesson_id=lesson.id,
        xp=xp_earned,
        correct=correct_count,
        total=total,
    )
    db.session.add(result_record)

    # update mastery for each outcome that names a kana char
    for o in outcomes:
        kana_char = o.get("kana_char")
        if kana_char:
            _update_mastery(current_user.id, kana_char, bool(o.get("correct")))

    db.session.commit()

    return jsonify({
        "xp_earned": xp_earned,
        "total_xp": state.xp,
        "correct": correct_count,
        "total": total,
        "accuracy": round(100 * correct_count / total, 1) if total else 0,
    })


@bp.route("/leaderboard")
@login_required
def leaderboard():
    class_id = request.args.get("class_id", type=int)
    class_name = None
    if class_id:
        klass = Classroom.query.get_or_404(class_id)
        ids = [e.student_id for e in klass.enrollments]
        class_name = klass.name
    else:
        ids = _classmates_for_leaderboard(current_user.id)
        if ids:
            klass = Enrollment.query.filter_by(student_id=current_user.id).first()
            class_name = klass.classroom.name if klass else None

    if not ids:
        # fallback to just the current user
        ids = [current_user.id]

    rows = (
        db.session.query(
            StudentQuizState.student_id,
            User.username,
            func.sum(StudentQuizState.xp).label("xp"),
        )
        .join(User, StudentQuizState.student_id == User.id)
        .filter(StudentQuizState.student_id.in_(ids))
        .group_by(StudentQuizState.student_id)
        .order_by(func.sum(StudentQuizState.xp).desc())
        .all()
    )

    entries = [
        {"rank": i + 1, "username": username, "xp": xp}
        for i, (_, username, xp) in enumerate(rows)
    ]
    return render_template(
        "quiz/leaderboard.html",
        entries=entries,
        class_name=class_name,
        class_id=class_id,
    )

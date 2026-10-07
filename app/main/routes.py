from flask import render_template
from flask_login import current_user

from app.extensions import db
from app.main import bp
from app.models import (
    AnswerLog,
    Classroom,
    Enrollment,
    Kana,
    KanaMastery,
    LessonResult,
    StudentChatState,
    StudentQuizState,
    User,
)


@bp.route("/")
def home():
    stats = {}
    if current_user.is_authenticated:
        if current_user.is_student:
            enrolled = len(current_user.enrollments)
            completed_chats = StudentChatState.query.filter_by(
                student_id=current_user.id, completed=True
            ).count()
            quiz_state = StudentQuizState.query.filter_by(student_id=current_user.id).first()
            mastered = KanaMastery.query.filter(
                KanaMastery.student_id == current_user.id,
                KanaMastery.n_correct >= 2,
            ).count()
            stats = {
                "enrolled": enrolled,
                "completed_chats": completed_chats,
                "xp": quiz_state.xp if quiz_state else 0,
                "mastered": mastered,
            }
        elif current_user.is_teacher:
            classes = current_user.taught_classes
            total_students = (
                db.session.query(Enrollment)
                .filter(Enrollment.class_id.in_([c.id for c in classes]))
                .count()
            )
            stats = {"classes": len(classes), "students": total_students}
        elif current_user.is_admin:
            stats = {
                "users": User.query.count(),
                "classes": Classroom.query.count(),
                "kana": Kana.query.count(),
            }

    return render_template("main/home.html", stats=stats)


@bp.route("/teacher")
def teacher_dashboard():
    if not (current_user.is_authenticated and (current_user.is_teacher or current_user.is_admin)):
        return render_template("auth/placeholder.html", message="Halaman ini hanya untuk guru/admin."), 403

    classes = (
        current_user.taught_classes
        if current_user.is_teacher
        else Classroom.query.order_by(Classroom.created_at.desc()).all()
    )
    rows = []
    total_students = 0
    total_completed_lessons = 0
    for klass in classes:
        students = [e.student for e in klass.enrollments]
        completed_lessons = (
            db.session.query(LessonResult)
            .filter(LessonResult.student_id.in_([s.id for s in students]))
            .count()
        )
        total_students += len(students)
        total_completed_lessons += completed_lessons
        rows.append({
            "classroom": klass,
            "students": students,
            "completed_lessons": completed_lessons,
        })
    return render_template(
        "main/teacher_dashboard.html",
        rows=rows,
        total_classes=len(classes),
        total_students=total_students,
        total_completed_lessons=total_completed_lessons,
    )


@bp.route("/healthz")
def health():
    return {"status": "ok"}, 200

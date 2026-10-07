from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.auth.decorators import roles_required
from app.classes import bp
from app.extensions import db
from app.models import Classroom, Enrollment, User


@bp.route("/classes")
@login_required
def class_list():
    if current_user.is_admin:
        classes = Classroom.query.order_by(Classroom.created_at.desc()).all()
    elif current_user.is_teacher:
        classes = sorted(current_user.taught_classes, key=lambda c: c.created_at, reverse=True)
    else:
        classes = [e.classroom for e in current_user.enrollments]
    return render_template("classes/list.html", classes=classes)


@bp.route("/classes/new", methods=["GET", "POST"])
@roles_required("teacher", "admin")
def class_new():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Nama kelas tidak boleh kosong.", "error")
            return render_template("classes/new.html", name=name)

        teacher = current_user
        if current_user.is_admin:
            teacher_username = request.form.get("teacher_username", "").strip()
            if teacher_username:
                candidate = User.query.filter_by(username=teacher_username).first()
                if candidate is not None and candidate.role in ("teacher", "admin"):
                    teacher = candidate
                else:
                    flash("Pengajar tidak ditemukan; kelas dibuat atas nama Anda.", "error")

        classroom = Classroom(name=name, teacher_id=teacher.id)
        db.session.add(classroom)
        db.session.commit()
        flash(f"Kelas '{classroom.name}' dibuat. Kode gabung: {classroom.join_code}", "success")
        return redirect(url_for("classes.class_detail", class_id=classroom.id))

    return render_template("classes/new.html", name="")


@bp.route("/classes/<int:class_id>")
@login_required
def class_detail(class_id):
    classroom = Classroom.query.get_or_404(class_id)
    is_manager = current_user.is_admin or (
        current_user.is_teacher and classroom.teacher_id == current_user.id
    )
    is_member = any(e.class_id == classroom.id for e in current_user.enrollments)
    if not (is_manager or is_member):
        abort(403)

    students = [e.student for e in classroom.enrollments]
    return render_template(
        "classes/detail.html",
        classroom=classroom,
        students=students,
        is_manager=is_manager,
    )


@bp.route("/classes/<int:class_id>/remove/<int:student_id>", methods=["POST"])
@roles_required("teacher", "admin")
def class_remove_student(class_id, student_id):
    classroom = Classroom.query.get_or_404(class_id)
    if not (current_user.is_admin or classroom.teacher_id == current_user.id):
        abort(403)

    enrollment = Enrollment.query.filter_by(class_id=class_id, student_id=student_id).first()
    if enrollment is not None:
        db.session.delete(enrollment)
        db.session.commit()
        flash("Siswa dikeluarkan dari kelas.", "success")
    else:
        flash("Siswa tidak ditemukan di kelas ini.", "error")
    return redirect(url_for("classes.class_detail", class_id=class_id))


@bp.route("/join", methods=["GET", "POST"])
@login_required
def join_class():
    if request.method == "POST":
        code = request.form.get("join_code", "").strip().upper()
        if not code:
            flash("Masukkan kode gabung kelas.", "error")
            return render_template("classes/join.html")

        classroom = Classroom.query.filter_by(join_code=code).first()
        if classroom is None:
            flash("Kode gabung tidak valid.", "error")
            return render_template("classes/join.html")

        already = Enrollment.query.filter_by(
            class_id=classroom.id, student_id=current_user.id
        ).first()
        if already is not None:
            flash("Kamu sudah terdaftar di kelas itu.", "info")
            return redirect(url_for("classes.class_detail", class_id=classroom.id))

        db.session.add(Enrollment(student_id=current_user.id, class_id=classroom.id))
        db.session.commit()
        flash(f"Berhasil bergabung ke kelas '{classroom.name}'!", "success")
        return redirect(url_for("classes.class_detail", class_id=classroom.id))

    return render_template("classes/join.html")

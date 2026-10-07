from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user

from app.admin import bp
from app.auth.decorators import roles_required
from app.extensions import db
from app.models import Classroom, User

VALID_ROLES = ("student", "teacher", "admin")


@bp.route("/")
@roles_required("admin")
def index():
    users = User.query.order_by(User.created_at.desc()).all()
    classes = Classroom.query.order_by(Classroom.created_at.desc()).all()
    return render_template("admin/index.html", users=users, classes=classes)


@bp.route("/users/<int:user_id>/role", methods=["POST"])
@roles_required("admin")
def set_user_role(user_id):
    user = User.query.get_or_404(user_id)
    new_role = request.form.get("role", "").strip()

    if new_role not in VALID_ROLES:
        flash("Peran tidak valid.", "error")
        return redirect(url_for("admin.index"))

    if user.id == current_user.id and new_role != "admin":
        flash("Kamu tidak bisa menurunkan peran akunmu sendiri (menghindari terkunci).", "error")
        return redirect(url_for("admin.index"))

    user.role = new_role
    db.session.commit()
    flash(f"Peran {user.username} diubah menjadi {new_role}.", "success")
    return redirect(url_for("admin.index"))

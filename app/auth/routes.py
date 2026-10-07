from urllib.parse import urlsplit

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.auth import bp
from app.extensions import db
from app.models import User


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.home"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm_password = (
            request.form.get("confirm_password")
            or request.form.get("confirm")
            or request.form.get("password_confirm")
            or ""
        )

        if not username:
            flash("Username tidak boleh kosong.", "error")
            return render_template("auth/register.html", username=username)

        if len(password) < 6:
            flash("Password minimal 6 karakter.", "error")
            return render_template("auth/register.html", username=username)

        if password != confirm_password:
            flash("Konfirmasi password tidak cocok.", "error")
            return render_template("auth/register.html", username=username)

        role = request.form.get("role", "student")
        if role not in ("student", "teacher"):
            role = "student"

        existing_user = User.query.filter_by(username=username).first()
        if existing_user is not None:
            flash("Username sudah digunakan. Silakan pilih username lain.", "error")
            return render_template("auth/register.html", username=username)

        try:
            user = User(username=username, role=role)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
        except Exception:
            db.session.rollback()
            flash("Terjadi kesalahan saat pendaftaran. Silakan coba lagi.", "error")
            return render_template("auth/register.html", username=username)

        flash("Pendaftaran berhasil! Silakan masuk dengan akun barumu.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html", username="")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.home"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = User.query.filter_by(username=username).first()
        if user is None or not user.check_password(password):
            flash("Username atau password salah.", "error")
            return render_template("auth/login.html", username=username)

        login_user(user)

        next_page = request.args.get("next") or request.form.get("next")
        if not next_page or urlsplit(next_page).netloc != "":
            next_page = url_for("main.home")
        return redirect(next_page)

    return render_template("auth/login.html", username="")


@bp.route("/logout", methods=["GET", "POST"])
@login_required
def logout():
    logout_user()
    return redirect(url_for("main.home"))

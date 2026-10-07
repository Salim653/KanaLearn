"""Dojo Menulis — decoupled handwriting practice.

Reachable anytime; no unlock requirement. P7 later adds stroke-order verification.
"""

from flask import render_template, request, url_for
from flask_login import login_required

from app.dojo import bp
from app.extensions import db
from app.models import Kana


@bp.route("/")
@login_required
def index():
    kana_type = request.args.get("type", "hiragana")
    if kana_type not in ("hiragana", "katakana"):
        kana_type = "hiragana"

    rows = db.session.query(Kana.row).filter_by(type=kana_type).distinct().order_by(Kana.row).all()
    row_ids = [r[0] for r in rows]
    grid = []
    for row_id in row_ids:
        chars = Kana.query.filter_by(type=kana_type, row=row_id).order_by(Kana.id).all()
        grid.append({"row_id": row_id, "chars": chars})

    selected_char = request.args.get("char")
    kana = None
    if selected_char:
        kana = Kana.query.filter_by(char=selected_char, type=kana_type).first()
    if kana is None:
        first = Kana.query.filter_by(type=kana_type).order_by(Kana.id).first()
        if first:
            kana = first

    return render_template(
        "dojo/index.html",
        kana=kana,
        grid=grid,
        kana_type=kana_type,
    )

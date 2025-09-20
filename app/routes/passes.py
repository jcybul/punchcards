# app/routes/passes.py
from flask import Blueprint, send_file, abort
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.models import WalletCard, PunchProgram
from app.apple_passes import build_pkpass  # you'll create this

bp = Blueprint("passes", __name__)

@bp.route("/passes/<uuid:card_id>.pkpass")
def get_pass(card_id):
    db: Session = SessionLocal()
    card = db.get(WalletCard, card_id)
    if not card:
        abort(404, "Card not found")

    program = db.get(PunchProgram, card.program_id)
    if not program:
        abort(404, "Program not found")

    # build the pass bundle
    pkpass_path = build_pkpass(card, program)

    return send_file(
        pkpass_path,
        mimetype="application/vnd.apple.pkpass",
        as_attachment=True,
        download_name=f"{card.id}.pkpass",
    )

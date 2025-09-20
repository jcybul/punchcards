from flask import Blueprint, jsonify, request
from sqlalchemy import text
from ..db import engine

bp = Blueprint("api", __name__)

@bp.get("/time")
def server_time():
    with engine.begin() as conn:
        now = conn.execute(text("select now()")).scalar_one()
    return jsonify({"time": now.isoformat()})


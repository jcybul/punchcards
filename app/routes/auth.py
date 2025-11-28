# app/routes/auth.py
from __future__ import annotations

import os
import requests
from flask import Blueprint, request, jsonify, abort
from app.services.auth_service import require_auth, current_user_id , update_profile

bp = Blueprint("auth_routes", __name__)

SUPABASE_URL = os.getenv("SUPABASE_URL")
ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
SERVICE_ROLE = os.getenv("SUPABASE_SERVICE_ROLE_KEY")  # optional

if not SUPABASE_URL or not ANON_KEY:
    raise RuntimeError("Set SUPABASE_URL and SUPABASE_ANON_KEY env vars.")

def _json_error(status: int, msg: str):
    resp = jsonify({"error": msg})
    resp.status_code = status
    return resp


@bp.get("/me")
@require_auth
def me():
    """Return the caller’s user_id as verified by our server (no round-trip to Supabase)."""
    return jsonify({"user_id": current_user_id()}), 200




@bp.post("/update_user_profile")
@require_auth
def update_user_profile():
    """Update user's profile information."""
    try:
        user_id = current_user_id()
        data = request.json
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        first_name = data.get('first_name', '').strip()
        last_name = data.get('last_name', '').strip()
        birth_date = data.get('birth_date')
        
        # Validate required fields
        if not first_name or not last_name:
            return jsonify({'error': 'first_name and last_name are required'}), 400
        
        # Update profile
        profile = update_profile(user_id, first_name, last_name, birth_date)
        
        return jsonify({
            'success': True,
            'user_id': str(user_id),
            'first_name': profile.first_name,
            'last_name': profile.last_name,
            'birth_date': profile.birthdate.isoformat() if profile.birthdate else None
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500




@bp.post("/signup-admin")
def signup_admin():
    """Create a user as admin (auto-confirm). Do NOT expose this publicly; protect with your own secret or platform role."""
    if not SERVICE_ROLE:
        return _json_error(500, "SERVICE_ROLE not configured")
    secret = request.headers.get("X-Admin-Secret")
    if secret != os.getenv("INTERNAL_ADMIN_SECRET"):
        abort(403)

    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip()
    password = (data.get("password") or "").strip()
    if not email or not password:
        return _json_error(400, "email and password required")

    url = f"{SUPABASE_URL}/auth/v1/admin/users"
    headers = {
        "apikey": SERVICE_ROLE,
        "Authorization": f"Bearer {SERVICE_ROLE}",
        "Content-Type": "application/json",
    }
    r = requests.post(url, headers=headers, json={
        "email": email,
        "password": password,
        "email_confirm": True
    })
    if r.status_code >= 300:
        try:
            err = r.json()
        except Exception:
            err = {"error": r.text}
        return _json_error(r.status_code, err.get("message") or str(err))

    return jsonify(r.json()), 201



import os
from flask import Flask
from .db import engine
from .models import Base
from dotenv import load_dotenv
from app.routes.api import bp as api_bp
from app.routes.auth import bp as auth_bp


load_dotenv()
def create_app():

    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")

    # ensure DB reachable (no-op metadata create; we use Alembic for real schema)
    with engine.begin() as conn:
        pass

    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(auth_bp,url_prefix="/auth")

    @app.get("/health")
    def health():
        return {"ok": True}
    
    @app.route("/")
    def index():
        return {"message": "Hello, Punchcards!"}

    return app

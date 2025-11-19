import os
from flask import Flask
from .db import engine
from .models import Base
from dotenv import load_dotenv
from app.routes.api import bp as api_bp
from app.routes.auth import bp as auth_bp
from app.routes.passes import bp as passes_bp
from app.routes import wallet_service
from app.routes import google_wallet
from app.routes.redemptions import bp as redemption_bp
from app.routes.user import bp as user_bp
from app.routes.program import bp as program_bp
from flask_cors import CORS
from app.routes.cron import bp as cron_bp
import logging
load_dotenv()
def create_app():

    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
    
    CORS(app, resources={
        r"/api/*": {
            "origins": "*",
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"]
        }
    })
    
    level=os.getenv("level") or "info"
    print(level)
    
    if level == "debug":
    
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    else:
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

    # ensure DB reachable (no-op metadata create; we use Alembic for real schema)
    # with engine.begin() as conn:
    #     pass

    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(user_bp,url_prefix="/api/user")
    app.register_blueprint(auth_bp,url_prefix="/auth")
    app.register_blueprint(passes_bp,url_prefix="/api/passes")
    app.register_blueprint(redemption_bp,url_prefix="/api/redemptions")
    app.register_blueprint(program_bp,url_prefix="/api/program")
    app.register_blueprint(cron_bp,url_prefix="/api/cron")
    app.register_blueprint(google_wallet.bp)
    app.register_blueprint(wallet_service.bp)

    @app.get("/health")
    def health():
        return {"ok": True}
    
    @app.route("/")
    def index():
        return {"message": "Hello, Punchcards! v1"}

    return app

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize extensions globally
db = SQLAlchemy()
socketio = SocketIO(cors_allowed_origins="*")


def create_app():
    app = Flask(
        __name__,
        instance_relative_config=True,
        template_folder=os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "templates"
        ),
        static_folder=os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "static"
        ),
    )

    # Configuration
    project_root = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(project_root, "..", "database.db")
    print("Database path:", db_path)  # Debug

    app.config.from_mapping(
        SECRET_KEY=os.getenv("SECRET_KEY", "your-secret-key"),
        SQLALCHEMY_DATABASE_URI=f"sqlite:///{db_path}",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        UPLOAD_FOLDER=os.path.join(project_root, "..", "static", "Uploads"),
        ALLOWED_EXTENSIONS={"png", "jpg", "jpeg"},
        MAX_CONTENT_LENGTH=5 * 1024 * 1024,
    )

    # Initialize extensions
    db.init_app(app)
    socketio.init_app(app)

    # Create upload folder
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # Create database tables
    with app.app_context():
        from .models import User, Scan

        try:
            print("Creating tables...")
            db.create_all()
            print("Tables created:", db.metadata.tables.keys())
        except Exception as e:
            print("Error creating tables:", e)

    # Register routes
    from .routes import init_routes

    init_routes(app)

    print("Static folder:", app.static_folder)
    print("GROQ_API_KEY set:", bool(os.getenv("GROQ_API_KEY")))  # Debug
    return app, socketio


app, socketio = create_app()

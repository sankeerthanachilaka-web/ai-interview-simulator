import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"

load_dotenv(
    dotenv_path=ENV_FILE,
    override=True
)
class Config:


    SECRET_KEY = os.getenv(
        "SECRET_KEY",
        "change-this-development-secret-key"
    )

    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{BASE_DIR / 'instance' / 'interview_simulator.db'}"
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    MAX_CONTENT_LENGTH = 5 * 1024 * 1024

    UPLOAD_FOLDER = str(
        BASE_DIR / "uploads"
    )

    INSTANCE_PATH = str(
        BASE_DIR / "instance"
    )

    ALLOWED_RESUME_EXTENSIONS = {
        "pdf",
        "doc",
        "docx"
    }

    MAX_QUESTIONS = int(
        os.getenv(
            "MAX_QUESTIONS",
            "10"
        )
    )
    GROQ_API_KEY = os.getenv(
        "GROQ_API_KEY",
        ""
    )

    GROQ_MODEL = os.getenv(
        "GROQ_MODEL",
        "openai/gpt-oss-20b"
    )

    GROQ_STT_MODEL = os.getenv(
        "GROQ_STT_MODEL",
        "whisper-large-v3-turbo"
    )

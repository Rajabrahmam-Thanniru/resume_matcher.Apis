import os
from pathlib import Path

SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-keep-it-secret")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:1.5b")
OLLAMA_TIMEOUT_SECONDS = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "120"))
ANALYSIS_TIMEOUT_SECONDS = float(os.getenv("ANALYSIS_TIMEOUT_SECONDS", "300"))
OLLAMA_REQUIREMENTS_MAX_TOKENS = int(os.getenv("OLLAMA_REQUIREMENTS_MAX_TOKENS", "2048"))
OLLAMA_TAILOR_MAX_TOKENS = int(os.getenv("OLLAMA_TAILOR_MAX_TOKENS", "3072"))

BASE_DIR = Path(__file__).resolve().parent.parent.parent
TEMP_PDF_DIR = BASE_DIR / "temp_resumes"
TEMP_PDF_DIR.mkdir(parents=True, exist_ok=True)
FONT_PATH = Path(r"C:\Windows\Fonts\arial.ttf")

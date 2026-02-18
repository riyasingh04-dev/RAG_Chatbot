from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

class Settings(BaseSettings):
    PROJECT_NAME: str = "Enterprise RAG Chatbot"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"

    # Database
    DATABASE_URL: str
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Auth
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # OAuth
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = ""

    # AI
    GROQ_API_KEY: str
    MODEL_NAME: str = "llama3-70b-8192"
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    DEBUG_RAG: bool = False

    # Paths
    UPLOAD_DIR: str = "data/uploads"
    INDEX_PATH: str = "db/faiss_index"
    TESSERACT_PATH: str = "" # Optional: Direct path to tesseract.exe
    POPPLER_PATH: str = ""    # Optional: Direct path to poppler/bin

    # Email / SMTP
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAILS_FROM: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

@lru_cache()
def get_settings():
    return Settings()

settings = get_settings()

"""Application configuration settings"""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

# Always resolve .env relative to this file's directory (backend/)
_ENV_FILE = str(Path(__file__).resolve().parent.parent / ".env")


class Settings(BaseSettings):
    """Application settings"""

    # Application
    APP_NAME: str = "FP&A Platform"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # Database - SQL Server
    DATABASE_DRIVER: str = "ODBC Driver 17 for SQL Server"
    DATABASE_SERVER: str = "localhost"
    DATABASE_PORT: int = 1433
    DATABASE_NAME: str = "fpna_db"
    DATABASE_USER: str = "fpna_user"
    DATABASE_PASSWORD: str = "YourSecurePassword123!"

    # Security
    SECRET_KEY: str = "your-secret-key-change-this-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # CORS (localhost and 127.0.0.1 for dev with proxy or direct backend URL)
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8000,http://localhost:8001,http://127.0.0.1:3000,http://127.0.0.1:8000,http://127.0.0.1:8001"

    # File Upload
    MAX_UPLOAD_SIZE: int = 10485760  # 10MB
    ALLOWED_EXTENSIONS: str = "xlsx,xls,csv"
    UPLOAD_FOLDER: str = "./uploads"

    # AI
    ANTHROPIC_API_KEY: str = ""
    BUDGETING_V2_METADATA_ENABLED: bool = False

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins into list"""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(',')]

    @property
    def allowed_extensions_list(self) -> List[str]:
        """Parse allowed extensions into list"""
        return [ext.strip() for ext in self.ALLOWED_EXTENSIONS.split(',')]

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        case_sensitive=True,
        extra="ignore",
        env_ignore_empty=True,
    )


settings = Settings()

from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///:memory:"  # 테스트/import 시 기본값; 실서버는 .env에서 주입
    api_port: int = 8000
    cors_origins: list[str] = ["http://localhost:8501", "http://localhost:3000"]
    log_level: str = "INFO"
    db_pool_size: int = 10
    db_max_overflow: int = 20

    model_config = {"env_prefix": "SCENARIO_DB_", "env_file": ".env", "extra": "ignore"}


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings

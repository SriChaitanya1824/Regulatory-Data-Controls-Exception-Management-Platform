from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./governance.db"
    jwt_secret: str = "development-only-change-me-at-least-32-bytes"
    cors_origins: str = "http://localhost:5173"
    ai_provider: str = "deterministic-demo"
    ai_api_key: str | None = None
    ai_model: str = "demo-governance-assistant"
    evidence_dir: str = "./storage/evidence"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()

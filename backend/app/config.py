from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    internal_api_token: str
    n8n_webhook_url: str
    session_cookie_name: str = "session"
    session_ttl_seconds: int = 60 * 60 * 24 * 7
    frontend_origins: str = "http://localhost:4200"
    cookie_secure: bool = False
    cookie_samesite: str = "lax"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()

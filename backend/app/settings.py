from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    kogito_base_url: str = "http://localhost:8080"
    kogito_timeout_seconds: float = 10.0
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="",
        extra="ignore",
    )


settings = Settings()

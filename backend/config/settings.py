"""Configuración central de la aplicación.

Único módulo del proyecto autorizado a leer variables de entorno. El resto del
código importa `settings` desde aquí y nunca toca `os.environ` directamente
(ver SEGURIDAD-PENTEST.md sección 1).
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Variables de entorno tipadas y validadas al arrancar la app."""

    # App
    app_env: str = "development"
    secret_key: str

    # Anthropic
    anthropic_api_key: str

    # Supabase
    supabase_url: str
    supabase_service_key: str
    supabase_anon_key: str

    # Auth
    jwt_secret: str
    jwt_expiration_minutes: int = 60
    refresh_token_expiration_days: int = 30

    # CORS — lista separada por comas, se parsea en main.py
    allowed_origins: str = "http://localhost:3000"

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()

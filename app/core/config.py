"""Configuración de la aplicación cargada desde variables de entorno (.env)."""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "StockBarrio"
    app_env: str = "development"
    debug: bool = True

    secret_key: str = "dev-secret-key-change-in-production"
    session_expire_hours: int = 12

    database_url: str = "sqlite:///./stockbarrio_dev.db"

    default_store_name: str = "Almacén de Barrio"
    default_admin_user: str = "admin"
    default_admin_pin: str = "1234"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def normalized_database_url(self) -> str:
        """Normaliza URLs postgres:// de proveedores cloud a postgresql+psycopg://."""
        url = self.database_url.strip()
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+psycopg://", 1)
        if url.startswith("postgresql://") and "+psycopg" not in url:
            return url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()

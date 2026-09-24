from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# repo root .env (backend/app/config.py -> backend/app -> backend -> repo root)
_REPO_ROOT_ENV = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    """Runtime configuration, populated from environment / .env.

    Field names mirror the .env keys defined at the repo root
    (see .env.example) so no duplication is needed.
    """

    model_config = SettingsConfigDict(
        env_file=str(_REPO_ROOT_ENV),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Postgres / PostGIS
    postgres_db: str = "nwis"
    postgres_user: str = "nwis"
    postgres_password: str = "nwis_dev_password"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    # Qdrant
    qdrant_host: str = "localhost"
    qdrant_http_port: int = 6333
    qdrant_grpc_port: int = 6334

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    secret_key: str = "change_me"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    timezone: str = "Asia/Shanghai"

    db_host: str = "localhost"
    db_port: int = 5432
    postgres_user: str = "pa_user"
    postgres_password: str = "change_me"
    postgres_db: str = "pa_db"

    upload_dir: str = "/data/uploads"
    max_upload_mb: int = 20
    max_pdf_pages: int = 200
    max_text_chars: int = 100000
    max_image_pixels: int = 20000000

    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    embedding_base_url: str = ""
    embedding_api_key: str = ""
    embedding_model: str = ""

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.db_host}:{self.db_port}/{self.postgres_db}"
        )

    @property
    def sync_database_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.db_host}:{self.db_port}/{self.postgres_db}"
        )

    @property
    def is_demo_mode(self) -> bool:
        return not (self.llm_base_url and self.llm_api_key and self.llm_model)


settings = Settings()

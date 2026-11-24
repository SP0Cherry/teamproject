from zoneinfo import ZoneInfo
from pydantic import Field, field_validator

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

    llm_request_timeout: float = Field(default=30, gt=0, le=30)
    llm_total_timeout: float = Field(default=60, gt=0, le=60)
    llm_max_retries: int = Field(default=1, ge=0, le=1)

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value):
        try:
            ZoneInfo(value)
        except (ValueError, KeyError):
            raise ValueError("timezone must be a valid IANA timezone") from None
        return value

    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    embedding_base_url: str = ""
    embedding_api_key: str = ""
    embedding_model: str = ""

    # Agent / MCP tool runtime
    duckduckgo_max_results: int = Field(default=5, ge=1, le=10)
    agent_max_tool_iterations: int = Field(default=3, ge=1, le=10)
    agent_max_total_tool_calls: int = Field(default=10, ge=1, le=50)
    tool_result_max_chars: int = Field(default=4000, ge=200, le=20000)
    mcp_tool_server_base_url: str = "http://mcp-server:8090"
    mcp_server_token_encrypt_key: str = "change_me_replace_with_32_byte_key"

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

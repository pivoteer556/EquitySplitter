from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    app_name: str = "Equity Splitter API"
    app_env: str = "dev"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/equity_splitter"
    jwt_secret_seed: str = "replace_me_with_32_plus_characters_seed_value"
    jwt_exp_minutes: int = 10
    jwt_rotation_days: int = 30

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    def redacted_database_target(self) -> str:
        url = make_url(self.database_url)
        user = url.username or "<none>"
        host = url.host or "<none>"
        port = str(url.port) if url.port else "<none>"
        database = url.database or "<none>"
        driver = url.drivername
        return f"{driver}://{user}:***@{host}:{port}/{database}"


settings = Settings()

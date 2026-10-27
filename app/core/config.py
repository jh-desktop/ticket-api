from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """환경변수(.env)를 타입 있는 객체로 읽어들인다.

    .env 의 APP_ENV=dev  →  settings.app_env == "dev"
    대소문자는 구분하지 않는다.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_env: str = "dev"
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db_name: str = "ticket_api"
    jwt_secret: str
    jwt_expire_minutes: int = 60
    cookie_secure: bool = False  # 운영(HTTPS)에서는 .env 로 True


@lru_cache
def get_settings() -> Settings:
    """Settings 를 한 번만 만들어서 재사용한다 (요청마다 .env 를 다시 읽지 않음)."""
    return Settings()  # pyright: ignore[reportCallIssue]

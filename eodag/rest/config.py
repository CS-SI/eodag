from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Define EODAG Server configuration, potentially through environment variables.
    See https://pydantic-docs.helpmanual.io/usage/settings/.
    """

    redis_hostname: Optional[str] = Field(default=None)
    redis_password: Optional[str] = Field(default=None)
    redis_port: int = Field(default=6379)
    redis_ssl: bool = True
    redis_ttl: int = Field(default=600)  # 10 minutes

    @classmethod
    @lru_cache(maxsize=1)
    def from_environment(cls) -> Settings:
        return Settings()

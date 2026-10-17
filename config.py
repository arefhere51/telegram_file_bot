import os
from pathlib import Path
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    API_ID: int
    API_HASH: str
    BOT_TOKEN: str
    ADMIN_IDS: str = ""

    WEB_HOST: str = "0.0.0.0"
    WEB_PORT: int = 14141
    PUBLIC_BASE_URL: str = "http://127.0.0.1:14141"

    DATA_DIR: str = "./data"
    MAX_FILE_SIZE_GB: float = 2.0
    AUTO_DELETE_DAYS: int = 0

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

    @property
    def admin_ids(self) -> List[int]:
        if not self.ADMIN_IDS.strip():
            return []
        return [int(x.strip()) for x in self.ADMIN_IDS.split(",") if x.strip()]

    @property
    def max_file_size_bytes(self) -> int:
        return int(self.MAX_FILE_SIZE_GB * 1024 * 1024 * 1024)

    @property
    def data_path(self) -> Path:
        p = Path(self.DATA_DIR)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def files_path(self) -> Path:
        p = self.data_path / "files"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def db_path(self) -> Path:
        return self.data_path / "files.db"


settings = Settings()

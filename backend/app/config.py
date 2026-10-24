"""应用配置：全部走环境变量，敏感项不入代码。"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="WOWFC_", env_file=".env", extra="ignore")

    app_name: str = "WoW-F-BussinessClac"
    # 开发默认 SQLite 零依赖启动；生产用 PostgreSQL：
    # WOWFC_DATABASE_URL=postgresql+psycopg://wowfc:wowfc@localhost:5432/wowfc
    database_url: str = "sqlite:///./wowfc.db"
    cors_origins: str = "*"  # 生产建议改为具体域名，逗号分隔
    # 涨点概率（WoW 经典近似值）：橙/黄/绿/灰
    prob_orange: float = 1.0
    prob_yellow: float = 0.5
    prob_green: float = 0.25
    prob_gray: float = 0.0
    # 中位数统计窗口（天）；0 表示不限制
    median_window_days: int = 0

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()

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
    # 拍卖行手续费率：成交后系统抽成，卖家到手 = 成交价 ×(1-费率)。
    # 经典旧世/无限均为 5%；改成 0 即按「不扣手续费」的旧口径计算。
    ah_cut_rate: float = 0.05
    # 云价格有效期（小时）：超过这个时长的报价会被标成「可能过期」。
    # 只做提示，不改变计算（老价格仍按最新口径参与，由用户自己判断要不要重新导价）。
    price_valid_hours: int = 24

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()

"""FastAPI 应用入口。"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .database import init_db
from .routers import items, prices, professions, routes, servers

settings = get_settings()

# 前端构建产物目录（Docker 镜像内为 /srv/static；本地开发可指向 frontend/dist）
STATIC_DIR = Path(__file__).resolve().parents[1] / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    # 开发/单容器部署：启动即建表（生产建议 Alembic 管理迁移，见 README）
    init_db()
    yield


app = FastAPI(
    title="WoW-F-BussinessClac API",
    description="魔兽世界无限 · 制造业冲级价格计算器",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_PREFIX = "/api/v1"
app.include_router(servers.router, prefix=API_PREFIX)
app.include_router(professions.router, prefix=API_PREFIX)
app.include_router(prices.router, prefix=API_PREFIX)
app.include_router(routes.router, prefix=API_PREFIX)
app.include_router(items.router, prefix=API_PREFIX)


@app.get("/health")
def health() -> dict:
    return {"ok": True, "app": settings.app_name}


# ---- 前端静态托管（存在构建产物时启用，单端口部署）----
if STATIC_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/", include_in_schema=False)
    def spa_index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str) -> FileResponse:
        # 非 API 路径一律回退 index.html（vue-router history 模式）
        candidate = STATIC_DIR / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(STATIC_DIR / "index.html")

else:

    @app.get("/")
    def root() -> dict:
        return {
            "app": settings.app_name,
            "docs": "/docs",
            "api": API_PREFIX,
            "professions": f"{API_PREFIX}/professions",
        }

"""Admin panel FastAPI routes — mounted on NoneBot2's FastAPI driver."""
from __future__ import annotations

import json
from pathlib import Path

from qq_bot.config import config

TEMPLATE_DIR = Path(__file__).parent / "templates"


def check_auth(auth_header: str | None) -> bool:
    if not auth_header:
        return False
    token = auth_header.replace("Bearer ", "")
    return token == config.ADMIN_TOKEN


def register_admin_routes(app):
    """Mount admin routes onto the FastAPI app (NoneBot2 driver)."""
    from fastapi.responses import HTMLResponse, JSONResponse
    from fastapi import Request

    @app.get("/admin")
    async def admin_index():
        html = (TEMPLATE_DIR / "index.html").read_text(encoding="utf-8")
        return HTMLResponse(content=html)

    @app.get("/admin/api/config")
    async def get_config(request: Request):
        if not check_auth(request.headers.get("Authorization")):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        return JSONResponse({
            "bot_name": config.BOT_NAME,
            "llm_provider": config.LLM_PROVIDER,
            "search_backend": config.SEARCH_BACKEND,
            "debug_mode": config.DEBUG_MODE,
            "max_plan_steps": config.AGENT_MAX_PLAN_STEPS,
            "max_retry": config.AGENT_MAX_RETRY,
        })

    @app.get("/admin/api/logs")
    async def get_logs(request: Request, limit: int = 50):
        if not check_auth(request.headers.get("Authorization")):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        return JSONResponse({"logs": []})

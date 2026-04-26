# main.py — RepurposeSnap / Комбайн Смыслов
# FastAPI backend
# Запуск: uvicorn main:app --reload

import asyncio
import os
import time
from typing import Optional

import anthropic
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, validator

from prompts import PLATFORM_PROMPTS, build_system_prompt, build_user_prompt

# ─── Инициализация ────────────────────────────────────────────────────────────

app = FastAPI(
    title="RepurposeSnap — Комбайн Смыслов",
    description="Один текст → 7 платформ",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
if not ANTHROPIC_API_KEY:
    print("⚠️  ANTHROPIC_API_KEY не задан — установи переменную окружения")

ai_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# ─── Простой in-memory rate limiter (без Redis для MVP) ──────────────────────
# ip → [timestamp, timestamp, ...]
_rate_store: dict[str, list[float]] = {}
RATE_LIMIT = 10        # запросов
RATE_WINDOW = 3600     # за 1 час


def check_rate_limit(ip: str) -> None:
    now = time.time()
    hits = [t for t in _rate_store.get(ip, []) if now - t < RATE_WINDOW]
    if len(hits) >= RATE_LIMIT:
        raise HTTPException(
            status_code=429,
            detail=f"Лимит: {RATE_LIMIT} запросов в час. Попробуй позже."
        )
    hits.append(now)
    _rate_store[ip] = hits


# ─── Модели запросов/ответов ──────────────────────────────────────────────────

class RepurposeRequest(BaseModel):
    source_text: str
    platforms: list[str]
    author_style: Optional[str] = ""

    @validator("source_text")
    def text_not_empty(cls, v):
        v = v.strip()
        if len(v) < 50:
            raise ValueError("Текст слишком короткий (минимум 50 символов)")
        if len(v) > 8000:
            raise ValueError("Текст слишком длинный (максимум 8000 символов)")
        return v

    @validator("platforms")
    def platforms_valid(cls, v):
        valid = set(PLATFORM_PROMPTS.keys())
        invalid = [p for p in v if p not in valid]
        if invalid:
            raise ValueError(f"Неизвестные платформы: {invalid}")
        if not v:
            raise ValueError("Выбери хотя бы одну платформу")
        if len(v) > 8:
            raise ValueError("Максимум 8 платформ за раз")
        return v


class PlatformResult(BaseModel):
    platform: str
    label: str
    emoji: str
    content: str
    error: Optional[str] = None


class RepurposeResponse(BaseModel):
    results: list[PlatformResult]
    processing_time: float


# ─── Генерация для одной платформы ───────────────────────────────────────────

async def generate_for_platform(
    platform_key: str,
    source_text: str,
    author_style: str,
) -> PlatformResult:
    """Вызывает Claude для одной платформы. Запускается параллельно."""
    platform_info = PLATFORM_PROMPTS[platform_key]

    def _sync_call():
        return ai_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            system=build_system_prompt(author_style),
            messages=[{
                "role": "user",
                "content": build_user_prompt(platform_key, source_text)
            }],
        )

    try:
        response = await asyncio.to_thread(_sync_call)
        content = response.content[0].text.strip()
        return PlatformResult(
            platform=platform_key,
            label=platform_info["label"],
            emoji=platform_info["emoji"],
            content=content,
        )
    except Exception as e:
        return PlatformResult(
            platform=platform_key,
            label=platform_info["label"],
            emoji=platform_info["emoji"],
            content="",
            error=str(e),
        )


# ─── Эндпоинты ───────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    """Отдаёт фронтенд."""
    html_path = os.path.join(os.path.dirname(__file__), "index.html")
    if os.path.exists(html_path):
        with open(html_path, encoding="utf-8") as f:
            return HTMLResponse(f.read())
    return HTMLResponse("<h1>index.html not found</h1>", status_code=404)


@app.get("/api/platforms")
async def get_platforms():
    """Список доступных платформ."""
    return {
        "platforms": [
            {
                "key": key,
                "label": info["label"],
                "emoji": info["emoji"],
            }
            for key, info in PLATFORM_PROMPTS.items()
        ]
    }


@app.post("/api/repurpose", response_model=RepurposeResponse)
async def repurpose(request: Request, body: RepurposeRequest):
    """
    Основной эндпоинт: принимает текст + платформы,
    возвращает адаптированный контент для каждой платформы параллельно.
    """
    client_ip = request.client.host
    check_rate_limit(client_ip)

    start = time.time()

    # Запускаем генерацию для всех платформ параллельно
    tasks = [
        generate_for_platform(platform, body.source_text, body.author_style)
        for platform in body.platforms
    ]
    results = await asyncio.gather(*tasks)

    return RepurposeResponse(
        results=list(results),
        processing_time=round(time.time() - start, 2),
    )


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "api_key_set": bool(ANTHROPIC_API_KEY),
        "platforms_count": len(PLATFORM_PROMPTS),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
        

from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from config import settings
from database import db, NewsItem
from scheduler import scheduler

app = FastAPI(
    title="Good News AI",
    description="API do canal de boas notícias curadas por IA",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class NewsResponse(BaseModel):
    id: Optional[int]
    title: str
    summary: str
    url: str
    source: str
    category: str
    positivity_score: float
    tags: list[str]
    image_url: Optional[str]
    published_at: Optional[str]
    collected_at: str

    @classmethod
    def from_item(cls, item: NewsItem) -> "NewsResponse":
        return cls(**{k: v for k, v in item.__dict__.items()})


class PaginatedNews(BaseModel):
    items: list[NewsResponse]
    total: int
    page: int
    per_page: int
    has_more: bool


class StatsResponse(BaseModel):
    total_news: int
    avg_positivity_score: float
    by_category: dict[str, int]
    last_run: Optional[dict]
    next_run: str


class TriggerResponse(BaseModel):
    message: str
    triggered_at: str


@app.get("/", tags=["Health"])
def root():
    return {"status": "ok", "service": "Good News AI", "version": "1.0.0"}


@app.get("/health", tags=["Health"])
def health():
    stats = db.get_stats()
    return {
        "status": "healthy",
        "total_news": stats["total_news"],
        "next_run": scheduler.get_next_run(),
    }


@app.get("/news", response_model=PaginatedNews, tags=["News"])
def list_news(
    page: int = Query(1, ge=1, description="Página"),
    per_page: int = Query(20, ge=1, le=100, description="Itens por página"),
    category: Optional[str] = Query(None, description="Filtrar por categoria"),
    min_score: float = Query(0, ge=0, le=10, description="Pontuação mínima"),
):
    offset = (page - 1) * per_page
    items = db.get_latest(
        limit=per_page + 1, 
        offset=offset,
        category=category,
        min_score=min_score,
    )
    has_more = len(items) > per_page
    items = items[:per_page]

    return PaginatedNews(
        items=[NewsResponse.from_item(i) for i in items],
        total=len(items),
        page=page,
        per_page=per_page,
        has_more=has_more,
    )


@app.get("/news/{news_id}", response_model=NewsResponse, tags=["News"])
def get_news(news_id: int):
    item = db.get_by_id(news_id)
    if not item:
        raise HTTPException(status_code=404, detail="Notícia não encontrada")
    return NewsResponse.from_item(item)


@app.get("/categories", tags=["News"])
def list_categories():
    return {"categories": db.get_categories()}


@app.get("/stats", response_model=StatsResponse, tags=["Stats"])
def get_stats():
    stats = db.get_stats()
    return StatsResponse(
        total_news=stats["total_news"],
        avg_positivity_score=stats["avg_positivity_score"],
        by_category=stats["by_category"],
        last_run=stats["last_run"],
        next_run=scheduler.get_next_run(),
    )


@app.post("/collect", response_model=TriggerResponse, tags=["Admin"])
def trigger_collection():
    import threading
    thread = threading.Thread(target=scheduler.trigger_now, daemon=True)
    thread.start()
    return TriggerResponse(
        message="Coleta iniciada em background. Verifique /stats para acompanhar.",
        triggered_at=datetime.utcnow().isoformat(),
    )


def start_api():
    import uvicorn
    from scheduler import setup_signal_handlers

    setup_signal_handlers()
    scheduler.start()

    uvicorn.run(
        app,
        host=settings.API_HOST,
        port=settings.API_PORT,
        log_level="info",
    )


if __name__ == "__main__":
    start_api()
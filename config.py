import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL: str = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

    DAILY_RUN_TIME: str = os.getenv("DAILY_RUN_TIME", "08:00")

    NEWS_PER_CATEGORY: int = int(os.getenv("NEWS_PER_CATEGORY", "5"))
    MAX_NEWS_IN_DB: int = int(os.getenv("MAX_NEWS_IN_DB", "500"))

    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")

    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "good_news.db")

    SEARCH_CATEGORIES: list[str] = [
        c.strip()
        for c in os.getenv(
            "SEARCH_CATEGORIES",
            "ciência,meio ambiente,saúde,inovação,comunidade,educação,animais,espaço",
        ).split(",")
    ]

    MIN_POSITIVITY_SCORE: float = float(os.getenv("MIN_POSITIVITY_SCORE", "7.0"))


settings = Settings()
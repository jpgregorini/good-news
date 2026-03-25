
import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field, asdict

from config import settings


@dataclass
class NewsItem:
    title: str
    summary: str
    url: str
    source: str
    category: str
    positivity_score: float
    tags: list[str] = field(default_factory=list)
    image_url: Optional[str] = None
    published_at: Optional[str] = None
    collected_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    id: Optional[int] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["tags"] = json.dumps(d["tags"])
        return d

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "NewsItem":
        d = dict(row)
        d["tags"] = json.loads(d.get("tags", "[]"))
        return cls(**d)


class Database:
    def __init__(self, path: str = settings.DATABASE_PATH):
        self.path = path
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS news (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    title           TEXT NOT NULL,
                    summary         TEXT NOT NULL,
                    url             TEXT UNIQUE NOT NULL,
                    source          TEXT,
                    category        TEXT,
                    positivity_score REAL DEFAULT 0,
                    tags            TEXT DEFAULT '[]',
                    image_url       TEXT,
                    published_at    TEXT,
                    collected_at    TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS collection_runs (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at  TEXT NOT NULL,
                    finished_at TEXT,
                    total_found INTEGER DEFAULT 0,
                    total_saved INTEGER DEFAULT 0,
                    status      TEXT DEFAULT 'running',
                    error       TEXT
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_category ON news(category)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_score ON news(positivity_score)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_collected ON news(collected_at)")
            conn.commit()

    def save_news(self, item: NewsItem) -> Optional[int]:
        with self._connect() as conn:
            try:
                d = item.to_dict()
                d.pop("id", None)
                cols = ", ".join(d.keys())
                placeholders = ", ".join(["?"] * len(d))
                cursor = conn.execute(
                    f"INSERT OR IGNORE INTO news ({cols}) VALUES ({placeholders})",
                    list(d.values()),
                )
                conn.commit()
                return cursor.lastrowid if cursor.rowcount > 0 else None
            except sqlite3.Error as e:
                print(f"[DB] Erro ao salvar notícia: {e}")
                return None

    def save_many(self, items: list[NewsItem]) -> int:
        saved = 0
        for item in items:
            if self.save_news(item) is not None:
                saved += 1
        return saved

    def get_latest(
        self,
        limit: int = 50,
        offset: int = 0,
        category: Optional[str] = None,
        min_score: float = 0,
    ) -> list[NewsItem]:
        query = "SELECT * FROM news WHERE positivity_score >= ?"
        params: list = [min_score]
        if category:
            query += " AND category = ?"
            params.append(category)
        query += " ORDER BY collected_at DESC LIMIT ? OFFSET ?"
        params += [limit, offset]

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [NewsItem.from_row(r) for r in rows]

    def get_by_id(self, news_id: int) -> Optional[NewsItem]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM news WHERE id = ?", (news_id,)).fetchone()
        return NewsItem.from_row(row) if row else None

    def get_categories(self) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT category FROM news ORDER BY category"
            ).fetchall()
        return [r["category"] for r in rows if r["category"]]

    def get_stats(self) -> dict:
        with self._connect() as conn:
            total = conn.execute("SELECT COUNT(*) as c FROM news").fetchone()["c"]
            by_cat = conn.execute(
                "SELECT category, COUNT(*) as c FROM news GROUP BY category ORDER BY c DESC"
            ).fetchall()
            avg_score = conn.execute(
                "SELECT AVG(positivity_score) as a FROM news"
            ).fetchone()["a"]
            last_run = conn.execute(
                "SELECT * FROM collection_runs ORDER BY started_at DESC LIMIT 1"
            ).fetchone()
        return {
            "total_news": total,
            "avg_positivity_score": round(avg_score or 0, 2),
            "by_category": {r["category"]: r["c"] for r in by_cat},
            "last_run": dict(last_run) if last_run else None,
        }

    def cleanup_old_news(self):
        with self._connect() as conn:
            count = conn.execute("SELECT COUNT(*) as c FROM news").fetchone()["c"]
            excess = count - settings.MAX_NEWS_IN_DB
            if excess > 0:
                conn.execute(
                    """
                    DELETE FROM news WHERE id IN (
                        SELECT id FROM news ORDER BY collected_at ASC LIMIT ?
                    )
                    """,
                    (excess,),
                )
                conn.commit()
                print(f"[DB] Limpeza: {excess} notícias antigas removidas.")


    def start_run(self) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO collection_runs (started_at, status) VALUES (?, 'running')",
                (datetime.utcnow().isoformat(),),
            )
            conn.commit()
            return cursor.lastrowid

    def finish_run(self, run_id: int, found: int, saved: int, error: Optional[str] = None):
        status = "error" if error else "success"
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE collection_runs
                SET finished_at = ?, total_found = ?, total_saved = ?, status = ?, error = ?
                WHERE id = ?
                """,
                (datetime.utcnow().isoformat(), found, saved, status, error, run_id),
            )
            conn.commit()


db = Database()
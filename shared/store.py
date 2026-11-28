"""Tiny shared cache on SQLAlchemy Core. CACHE_DB_URL (default: sqlite file data/cache.db); Postgres works unchanged.

Only PUBLIC data goes here (guard verdicts, extracted events, resolver results): never user profile data.
Values are JSON. Tables are created on first use. The MCP server subprocess and the concierge share the file (WAL).
"""
import json
import os
import time
from pathlib import Path

from sqlalchemy import Column, Float, MetaData, String, Table, Text, create_engine, delete, event, insert, select

ROOT = Path(__file__).resolve().parents[1]
_meta = MetaData()
# guard: sha1(mode+text) -> bool | events: sha1(post url+text) -> list of finalized events | resolver: key -> result dict
# fetches: city slug -> {started, failed?} | day-<date> -> number of live fetches started (see mcp_servers/event_sources), progress-<slug> -> fetch progress
# progress: user id -> {ts, city, stage, pct, text} of the running scan (shared/progress.py)
TABLES = {n: Table(n, _meta, Column("key", String(255), primary_key=True), Column("value", Text, nullable=False),
                   Column("ts", Float, nullable=False)) for n in ("guard", "events", "resolver", "fetches", "progress")}
_engines: dict = {}  # per URL; tests clear it to simulate a new process


def _engine():
    url = os.getenv("CACHE_DB_URL") or f"sqlite:///{ROOT / 'data' / 'cache.db'}"
    if url not in _engines:
        if url.startswith("sqlite"):
            (ROOT / "data").mkdir(exist_ok=True)
        eng = create_engine(url)
        if eng.dialect.name == "sqlite":
            @event.listens_for(eng, "connect")
            def _wal(conn, _):
                conn.execute("PRAGMA journal_mode=WAL")
        _meta.create_all(eng)
        _engines[url] = eng
    return _engines[url]


def get(table: str, key: str, ttl: float | None = None):
    """Stored value or None (also when older than ttl seconds)."""
    t = TABLES[table]
    with _engine().connect() as c:
        row = c.execute(select(t.c.value, t.c.ts).where(t.c.key == key)).first()
    if row is None or (ttl is not None and time.time() - row.ts >= ttl):
        return None
    return json.loads(row.value)


def put(table: str, key: str, value) -> None:
    t = TABLES[table]
    with _engine().begin() as c:  # delete + insert: portable upsert
        c.execute(delete(t).where(t.c.key == key))
        c.execute(insert(t).values(key=key, value=json.dumps(value, ensure_ascii=False), ts=time.time()))


def clear(table: str) -> None:
    with _engine().begin() as c:
        c.execute(delete(TABLES[table]))

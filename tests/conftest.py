import pytest


@pytest.fixture(autouse=True)
def cache_db(tmp_path, monkeypatch):
    """Every test gets its own empty cache DB, never data/cache.db."""
    monkeypatch.setenv("CACHE_DB_URL", f"sqlite:///{tmp_path / 'cache.db'}")
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)  # .env may hold a real key: tests stay offline

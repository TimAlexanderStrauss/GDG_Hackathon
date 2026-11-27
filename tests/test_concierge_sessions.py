import asyncio

from agents.concierge import app as concierge


def _extract(value):
    token = concierge._header_user.set(value)
    try:
        return concierge.extract_user_id()
    finally:
        concierge._header_user.reset(token)


def test_extractor():
    assert _extract("google:a@b.de") == "google:a@b.de"
    assert _extract("demo_user") == "demo_user"
    assert _extract(None) == "demo_user"
    assert _extract("") == "demo_user"
    assert _extract("admin") == "demo_user"
    assert _extract("google:x y@b.de") == "demo_user"


def test_sessions_survive_new_service(tmp_path):
    url = f"sqlite+aiosqlite:///{tmp_path / 's.db'}"

    async def run():
        first = concierge.make_session_service(url)
        s = await first.create_session(app_name="event_scout", user_id="google:a@b.de", state={"interests": ["jazz"]})
        second = concierge.make_session_service(url)
        got = await second.get_session(app_name="event_scout", user_id="google:a@b.de", session_id=s.id)
        other = await second.get_session(app_name="event_scout", user_id="demo_user", session_id=s.id)
        return got, other

    got, other = asyncio.run(run())
    assert got.state["interests"] == ["jazz"]
    assert other is None


def test_user_id_survives_into_the_streamed_run():
    """The agent run reads the user id while the response streams, after the middleware's call_next returned."""
    import asyncio

    from fastapi import FastAPI
    from fastapi.responses import StreamingResponse
    from fastapi.testclient import TestClient

    import agents.concierge.app as m
    t = FastAPI()
    t.middleware("http")(m._read_user_header)

    @t.post("/")
    async def run():
        async def gen():
            await asyncio.sleep(0.01)
            yield m.extract_user_id()
        return StreamingResponse(gen())

    c = TestClient(t)
    assert c.post("/", headers={"X-Sidequest-User": "google:lea@example.com"}).text == "google:lea@example.com"
    assert c.post("/", headers={"X-Sidequest-User": "admin"}).text == "demo_user"

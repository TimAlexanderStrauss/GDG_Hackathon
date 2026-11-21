import json
from pathlib import Path

from shared.schemas import SocialPost

FIXTURES = Path(__file__).parent.parent / "fixtures" / "posts.json"


def test_fixture_posts_match_contract():
    posts = [SocialPost.model_validate(p) for p in json.loads(FIXTURES.read_text())]
    assert {p.platform for p in posts} == {"instagram", "tiktok", "web"}
    assert any("ignore all previous instructions" in p.text for p in posts), "demo needs the poisoned post"

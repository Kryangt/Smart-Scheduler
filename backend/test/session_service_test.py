import json

from backend.app.services import session_service


class FakeRedis:
    def __init__(self):
        self.values = {}

    def set(self, name, value, ex):
        self.values[name] = value

    def get(self, name):
        return self.values.get(name)

    def delete(self, name):
        self.values.pop(name, None)


def test_session_round_trip(monkeypatch):
    fake_redis = FakeRedis()
    monkeypatch.setattr(session_service, "redis_client", fake_redis)

    session_service.save_session("abc", 7, {"token": "secret"})

    assert json.loads(fake_redis.values["session:abc"])["user_id"] == 7
    assert session_service.get_session("abc") == {
        "user_id": 7,
        "credentials": {"token": "secret"},
    }


def test_missing_session_returns_none(monkeypatch):
    monkeypatch.setattr(session_service, "redis_client", FakeRedis())
    assert session_service.get_session("missing") is None

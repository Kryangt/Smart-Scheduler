from datetime import datetime

from backend.app.services import scheduler_service


def freeze_scheduler(monkeypatch, now_hour=8, now_minute=0):
    class ScenarioDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            value = cls(2026, 8, 9, now_hour, now_minute)
            return value if tz is None else value.astimezone(tz)

    monkeypatch.setattr(scheduler_service, "datetime", ScenarioDateTime)
    monkeypatch.setattr(
        scheduler_service,
        "get_events",
        lambda creds, end_time=None: {"events": []},
    )


def test_scheduler_uses_a_slot_that_ends_before_deadline(monkeypatch):
    freeze_scheduler(monkeypatch)
    result = scheduler_service.schedule(None, [{
        "title": "Morning task",
        "deadline": "2026-08-09T10:00:00",
        "estimated_duration": 1,
    }])

    assert len(result["scheduled"]) == 1
    assert datetime.fromisoformat(result["scheduled"][0]["end"]).hour == 9
    assert result["deadline_misses"] == 0


def test_scheduler_respects_dependencies(monkeypatch):
    freeze_scheduler(monkeypatch)
    result = scheduler_service.schedule(None, [
        {
            "title": "Write",
            "deadline": "2026-08-10",
            "estimated_duration": 1,
            "depends_on": ["Research"],
        },
        {
            "title": "Research",
            "deadline": "2026-08-10",
            "estimated_duration": 2,
        },
    ])

    by_title = {task["title"]: task for task in result["scheduled"]}
    assert datetime.fromisoformat(by_title["Research"]["end"]) <= datetime.fromisoformat(by_title["Write"]["start"])


def test_scheduler_measures_lateness(monkeypatch):
    freeze_scheduler(monkeypatch, now_hour=21, now_minute=30)
    result = scheduler_service.schedule(None, [{
        "title": "Late task",
        "deadline": "2026-08-09T22:00:00",
        "estimated_duration": 1,
    }])

    assert result["deadline_misses"] == 1
    assert result["total_lateness"] > 0
    assert datetime.fromisoformat(result["scheduled"][0]["start"]).hour >= scheduler_service.WORK_START


def test_scheduler_rejects_dependency_cycles(monkeypatch):
    freeze_scheduler(monkeypatch)
    result = scheduler_service.schedule(None, [
        {"title": "A", "deadline": "2026-08-10", "estimated_duration": 1, "depends_on": ["B"]},
        {"title": "B", "deadline": "2026-08-10", "estimated_duration": 1, "depends_on": ["A"]},
    ])

    assert not result["scheduled"]
    assert {task["reason"] for task in result["unscheduled"]} == {"dependency_cycle"}

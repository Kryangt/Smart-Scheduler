import asyncio
import time
from types import SimpleNamespace
import httpx
import pytest
from fastapi.testclient import TestClient
from backend.app.services.classifier_service import classify_text

VALID = {'domain': 'work', 'effort': 'mental', 'domain_confidence': 0.9,
         'effort_confidence': 0.8, 'model_version': 'test-v1'}

@pytest.fixture(autouse=True)
def configure(monkeypatch):
    monkeypatch.setenv('CLASSIFIER_URL', 'http://classifier.test')
    monkeypatch.delenv('CLASSIFIER_API_TOKEN', raising=False)

def call(handler, **kwargs):
    return asyncio.run(classify_text('Prepare a report', transport=httpx.MockTransport(handler), **kwargs))

def test_success():
    assert call(lambda r: httpx.Response(200, json=VALID)) == {'status': 'classified', **VALID}

def test_low_confidence():
    assert call(lambda r: httpx.Response(200, json={**VALID, 'effort_confidence': 0.4}))['status'] == 'uncertain'

def test_disabled(monkeypatch):
    monkeypatch.delenv('CLASSIFIER_URL')
    assert call(lambda r: pytest.fail('Must not call service')) == {'status': 'disabled'}

@pytest.mark.parametrize('status,attempts', [(503, 2), (502, 2), (504, 2), (500, 1), (401, 1), (422, 1)])
def test_bounded_retries(status, attempts):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(status)
    assert call(handler)['status'] == 'unavailable'
    assert len(calls) == attempts

def test_recovers_after_retry():
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(503) if len(calls) == 1 else httpx.Response(200, json=VALID)
    assert call(handler)['status'] == 'classified'
    assert len(calls) == 2

def test_connection_refused():
    calls = []
    def handler(request):
        calls.append(request)
        raise httpx.ConnectError('refused', request=request)
    assert call(handler)['reason'] == 'connection_error'
    assert len(calls) == 2

def test_deadline():
    async def slow(request):
        await asyncio.sleep(1)
        return httpx.Response(200, json=VALID)
    started = time.monotonic()
    assert call(slow, deadline=0.03)['reason'] == 'timeout'
    assert time.monotonic() - started < 0.5

@pytest.mark.parametrize('body', [b'not json', b'{}', b'{"domain": 7}'])
def test_invalid_response(body):
    assert call(lambda r: httpx.Response(200, content=body))['reason'] == 'invalid_response'

def test_invalid_probability():
    assert call(lambda r: httpx.Response(200, json={**VALID, 'domain_confidence': 2}))['reason'] == 'invalid_response'

def test_task_created_once_during_outage(monkeypatch):
    from backend.app import main as api
    calls = []
    def create(*args):
        calls.append(args)
        return {'id': 'google-task-1', 'title': 'Prepare a report'}
    monkeypatch.setattr(api, 'create_task', create)
    monkeypatch.setattr(api, 'get_session_credentials', lambda request: object())
    def unavailable(text):
        def handler(request):
            raise httpx.ConnectError('refused', request=request)
        return asyncio.run(classify_text(text, transport=httpx.MockTransport(handler)))
    monkeypatch.setattr(api, 'classify_task', unavailable)
    old = api.app.dependency_overrides.copy()
    api.app.dependency_overrides[api.get_current_user] = lambda: SimpleNamespace(id=1)
    api.app.dependency_overrides[api.get_db] = lambda: object()
    try:
        with TestClient(api.app) as client:
            response = client.post('/tasks', json={'title': 'Prepare a report'})
    finally:
        api.app.dependency_overrides.clear()
        api.app.dependency_overrides.update(old)
    assert response.status_code == 200, response.text
    assert response.json()['task']['id'] == 'google-task-1'
    assert response.json()['classification']['status'] == 'unavailable'
    assert len(calls) == 1

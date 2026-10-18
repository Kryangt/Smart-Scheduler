"""Optional external classification; never retries task creation."""
import asyncio
import logging
import os
import random
import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

log = logging.getLogger(__name__)

class Prediction(BaseModel):
    model_config = ConfigDict(strict=True, extra='forbid')
    domain: str = Field(min_length=1, max_length=100)
    effort: str = Field(min_length=1, max_length=100)
    domain_confidence: float = Field(ge=0, le=1, allow_inf_nan=False)
    effort_confidence: float = Field(ge=0, le=1, allow_inf_nan=False)
    model_version: str = Field(min_length=1, max_length=200)

async def classify_text(text, *, transport=None, deadline=2.0):
    url = os.getenv('CLASSIFIER_URL', '').rstrip('/')
    if not url:
        return {'status': 'disabled'}
    if not isinstance(text, str) or not text.strip() or len(text) > 2000:
        return {'status': 'unavailable', 'reason': 'unsupported_input'}

    async def request_prediction():
        headers = {}
        token = os.getenv('CLASSIFIER_API_TOKEN')
        if token:
            headers['X-Classifier-Token'] = token
        async with httpx.AsyncClient(transport=transport, timeout=httpx.Timeout(1.0, connect=0.3),
                                     headers=headers, follow_redirects=False) as client:
            for attempt in range(2):
                try:
                    response = await client.post(url + '/classify', json={'text': text})
                except httpx.ConnectError:
                    if attempt:
                        raise
                else:
                    if response.status_code not in (502, 503, 504) or attempt:
                        response.raise_for_status()
                        return Prediction.model_validate(response.json())
                await asyncio.sleep(0.05 + random.uniform(0, 0.05))

    try:
        prediction = await asyncio.wait_for(request_prediction(), timeout=deadline)
        # Provisional threshold, not a calibrated probability of correctness.
        status = ('classified' if min(prediction.domain_confidence,
                  prediction.effort_confidence) >= 0.6 else 'uncertain')
        return {'status': status, **prediction.model_dump()}
    except (asyncio.TimeoutError, httpx.TimeoutException):
        reason = 'timeout'
    except (ValidationError, ValueError):
        reason = 'invalid_response'
    except httpx.HTTPStatusError:
        reason = 'http_error'
    except (httpx.RequestError, httpx.InvalidURL):
        reason = 'connection_error'
    log.warning('classification_unavailable reason=%s', reason)
    return {'status': 'unavailable', 'reason': reason}

def classify_titles(titles):
    async def batch():
        results = {}
        async def collect():
            for title in dict.fromkeys(titles):
                results[title] = await classify_text(title)
        try:
            await asyncio.wait_for(collect(), timeout=3.0)
        except asyncio.TimeoutError:
            pass
        return [results.get(title, {'status': 'unavailable', 'reason': 'batch_timeout'})
                for title in titles]
    return asyncio.run(batch())


def classify_task(text):
    # /tasks is a synchronous FastAPI route, executed in its thread pool.
    return asyncio.run(classify_text(text))

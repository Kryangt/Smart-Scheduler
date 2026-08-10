import os

try:
    import redis
except ImportError:  # Allows unit tests to inject a fake client before Redis is installed.
    redis = None


if redis is not None:
    RedisError = redis.exceptions.RedisError
else:
    class RedisError(Exception):
        pass

    class MissingRedisClient:
        def _missing(self, *args, **kwargs):
            raise RedisError("The 'redis' package is required for session storage")

        get = set = delete = ping = _missing

REDIS_URL = os.getenv(
    "REDIS_URL",
    "redis://localhost:6379/0",
)

#same as database and openAI clients
redis_client = (
    redis.Redis.from_url(
        REDIS_URL,
        decode_responses=True,
    )
    if redis is not None
    else MissingRedisClient()
)

def check_redis_connection() -> bool:
    try:
        return redis_client.ping()
    except RedisError as exc:
        raise RuntimeError("could not connect to Redis") from exc

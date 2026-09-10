import json
try:
    import redis
except ImportError:
    redis = None
from app.core.config import settings

_client = None

def publish(channel: str, payload: dict) -> bool:
    global _client
    if redis is None:
        return False
    try:
        if _client is None:
            _client = redis.from_url(settings.redis_url, decode_responses=True)
        _client.publish(channel, json.dumps(payload))
        return True
    except Exception:
        return False

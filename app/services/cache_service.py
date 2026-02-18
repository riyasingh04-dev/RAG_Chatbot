import redis
import json
from loguru import logger
from app.core.config import settings

class CacheService:
    def __init__(self):
        try:
            self.redis = redis.from_url(
                settings.REDIS_URL, 
                decode_responses=True,
                socket_connect_timeout=2
            )
            # Connectivity check
            self.redis.ping()
            logger.info("Connected to Redis cache.")
        except Exception as e:
            logger.warning(f"Redis unavailable (Work mode: Local-only): {e}")
            self.redis = None

    def get_session_history(self, session_id: str, limit: int = 10) -> list:
        if not self.redis: return []
        data = self.redis.lrange(f"chat_history:{session_id}", -limit, -1)
        return [json.loads(item) for item in data]

    def add_to_history(self, session_id: str, role: str, content: str):
        if not self.redis: return
        msg = json.dumps({"role": role, "content": content})
        self.redis.rpush(f"chat_history:{session_id}", msg)
        self.redis.ltrim(f"chat_history:{session_id}", -50, -1) # Keep last 50

    def set_cache(self, key: str, value: str, expire: int = 3600):
        if self.redis:
            self.redis.setex(f"cache:{key}", expire, value)

    def get_cache(self, key: str) -> str:
        if self.redis:
            return self.redis.get(f"cache:{key}")
        return None

cache_service = CacheService()

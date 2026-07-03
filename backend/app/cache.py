import logging
import json
from typing import Optional, Dict, Any

logger = logging.getLogger("quantforge.cache")

try:
    import redis
    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False

class HybridCache:
    def __init__(self):
        self.client = None
        self.memory_store = {}
        self.memory_expiry = {}
        self.status = "offline"
        
        if HAS_REDIS:
            from app.config import settings
            try:
                self.client = redis.Redis(
                    host=settings.REDIS_HOST,
                    port=settings.REDIS_PORT,
                    password=settings.REDIS_PASSWORD,
                    socket_connect_timeout=1,
                    decode_responses=True
                )
                self.client.ping()
                self.status = "online"
                logger.info("Connected to Redis cache server successfully.")
            except Exception as e:
                logger.warning(f"Redis connection failed: {e}. Falling back to in-memory cache.")
                self.client = None
                self.status = "fallback"
        else:
            logger.info("redis-py package not found. Using in-memory cache fallback.")
            self.status = "fallback"
            
    def get(self, key: str) -> Optional[str]:
        import time
        if self.status == "online" and self.client:
            try:
                return self.client.get(key)
            except Exception as e:
                logger.error(f"Redis get error: {e}")
                self.status = "fallback"
                
        # Memory get
        if key in self.memory_store:
            expiry = self.memory_expiry.get(key, 0)
            if expiry == 0 or expiry > time.time():
                return self.memory_store[key]
            else:
                # Expired
                del self.memory_store[key]
                del self.memory_expiry[key]
        return None
        
    def set(self, key: str, value: str, expire_seconds: int = 60) -> bool:
        import time
        if self.status == "online" and self.client:
            try:
                self.client.set(key, value, ex=expire_seconds)
                return True
            except Exception as e:
                logger.error(f"Redis set error: {e}")
                self.status = "fallback"
                
        # Memory set
        self.memory_store[key] = value
        self.memory_expiry[key] = time.time() + (expire_seconds if expire_seconds else 0)
        return True
        
    def health(self) -> Dict[str, Any]:
        import time
        # Purge expired keys in memory first if we are in fallback mode
        if self.status == "fallback":
            now = time.time()
            expired_keys = [k for k, exp in self.memory_expiry.items() if exp > 0 and exp < now]
            for k in expired_keys:
                del self.memory_store[k]
                del self.memory_expiry[k]
                
        provider = "Redis" if self.status == "online" else "In-Memory (Redis Offline)"
        keys_count = 0
        if self.status == "online" and self.client:
            try:
                keys_count = self.client.dbsize()
            except Exception:
                keys_count = 0
        else:
            keys_count = len(self.memory_store)
            
        return {
            "status": "healthy",
            "provider": provider,
            "keys_cached": keys_count
        }

cache = HybridCache()

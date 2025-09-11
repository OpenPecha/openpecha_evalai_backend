import redis
import json
import os
from typing import Optional, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class RedisClient:
    """Redis client for caching API responses with configurable expiry times"""
    
    def __init__(self):
        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            raise ValueError("REDIS_URL is not set in your .env file!")
        
        self.redis_client = redis.from_url(redis_url, decode_responses=True)
        
        # Test connection
        try:
            self.redis_client.ping()
            print("✅ Redis connection successful")
        except redis.ConnectionError as e:
            print(f"❌ Redis connection failed: {e}")
            raise e
    
    def set_cache(self, key: str, value: Any, expire_seconds: int = 3600) -> bool:
        """
        Store data in Redis with expiration
        
        Args:
            key: Cache key
            value: Data to cache (will be JSON serialized)
            expire_seconds: Expiration time in seconds (default: 1 hour)
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            serialized_value = json.dumps(value, default=str)
            return self.redis_client.setex(key, expire_seconds, serialized_value)
        except Exception as e:
            print(f"Error setting cache for key {key}: {e}")
            return False
    
    def get_cache(self, key: str) -> Optional[Any]:
        """
        Retrieve data from Redis cache
        
        Args:
            key: Cache key
            
        Returns:
            Cached data or None if not found/expired
        """
        try:
            cached_value = self.redis_client.get(key)
            if cached_value:
                return json.loads(cached_value)
            return None
        except Exception as e:
            print(f"Error getting cache for key {key}: {e}")
            return None
    
    def delete_cache(self, key: str) -> bool:
        """
        Delete specific cache entry
        
        Args:
            key: Cache key to delete
            
        Returns:
            bool: True if deleted, False if key didn't exist
        """
        try:
            return bool(self.redis_client.delete(key))
        except Exception as e:
            print(f"Error deleting cache for key {key}: {e}")
            return False
    
    def clear_all_cache(self) -> bool:
        """
        Clear all cache entries
        
        Returns:
            bool: True if successful
        """
        try:
            self.redis_client.flushall()
            return True
        except Exception as e:
            print(f"Error clearing all cache: {e}")
            return False
    
    def clear_pattern_cache(self, pattern: str) -> int:
        """
        Clear cache entries matching a pattern
        
        Args:
            pattern: Redis pattern (e.g., "leaderboard:*", "arena:*")
            
        Returns:
            int: Number of keys deleted
        """
        try:
            keys = self.redis_client.keys(pattern)
            if keys:
                return self.redis_client.delete(*keys)
            return 0
        except Exception as e:
            print(f"Error clearing pattern cache {pattern}: {e}")
            return 0
    
    def get_cache_info(self) -> dict:
        """
        Get Redis cache information and statistics
        
        Returns:
            dict: Cache information including memory usage and key count
        """
        try:
            info = self.redis_client.info()
            key_count = self.redis_client.dbsize()
            
            return {
                "status": "connected",
                "memory_used": info.get("used_memory_human", "N/A"),
                "total_keys": key_count,
                "redis_version": info.get("redis_version", "N/A"),
                "uptime_seconds": info.get("uptime_in_seconds", 0)
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }

# Global Redis client instance
redis_client = RedisClient()

# Cache key generators for consistent naming
class CacheKeys:
    """Cache key generators for consistent Redis key naming"""
    
    @staticmethod
    def arena_score(model_id: str = "all") -> str:
        """Arena score cache key - expires in 60 minutes"""
        return f"arena:score:{model_id}"
    
    @staticmethod 
    def leaderboard(challenge_id: str = "all") -> str:
        """Leaderboard cache key - expires in 1 day"""
        return f"leaderboard:{challenge_id}"
    
    @staticmethod
    def user_vote_leaderboard() -> str:
        """User vote leaderboard cache key - expires in 1 day"""
        return "leaderboard:user_votes"
    
    @staticmethod
    def vote_stats() -> str:
        """Vote statistics cache key - expires in 1 day"""
        return "stats:votes"
    
    @staticmethod
    def model_scores() -> str:
        """Model scores cache key - expires in 1 day"""
        return "scores:models"
    
    @staticmethod
    def model_vote_leaderboard() -> str:
        """Model vote leaderboard cache key - expires in 60 minutes"""
        return "leaderboard:model_votes"

# Cache expiry constants (in seconds)
class CacheExpiry:
    """Cache expiration times in seconds"""
    ARENA_SCORE = 60 * 60  # 60 minutes for arena scores
    LEADERBOARD = 24 * 60 * 60  # 1 day for leaderboards
    DEFAULT = 60 * 60  # 1 hour default

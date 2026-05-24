import redis
import json
from .config import settings

redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
CACHE_TTL = 300  # 5 minutes

def cache_wallet_balance(wallet_id: str, balance: float, available: float):
    """Met en cache le solde du wallet"""
    data = json.dumps({"balance": str(balance), "available": str(available)})
    redis_client.setex(f"wallet:balance:{wallet_id}", CACHE_TTL, data)

def get_cached_balance(wallet_id: str) -> dict | None:
    """Récupère le solde depuis le cache"""
    cached = redis_client.get(f"wallet:balance:{wallet_id}")
    if cached:
        return json.loads(cached)
    return None

def invalidate_wallet_cache(wallet_id: str):
    """Invalide le cache du wallet"""
    redis_client.delete(f"wallet:balance:{wallet_id}")

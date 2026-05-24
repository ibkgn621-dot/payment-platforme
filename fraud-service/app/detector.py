import redis
import json
import logging
from datetime import datetime, timedelta
from typing import List, Tuple
from .config import settings

logger = logging.getLogger(__name__)
redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

class FraudDetector:
    """Moteur de détection de fraude basé sur des règles"""

    # Définition des règles
    RULES = {
        "high_amount": {
            "description": "Montant élevé (> 2,000,000 GNF)",
            "score": 20,
        },
        "very_high_amount": {
            "description": "Montant très élevé (> 5,000,000 GNF)",
            "score": 40,
        },
        "too_many_transactions_hour": {
            "description": "Trop de transactions en 1 heure",
            "score": 30,
        },
        "daily_limit_exceeded": {
            "description": "Limite journalière dépassée",
            "score": 35,
        },
        "blacklisted_phone": {
            "description": "Numéro de téléphone blacklisté",
            "score": 80,
        },
        "blacklisted_ip": {
            "description": "Adresse IP blacklistée",
            "score": 70,
        },
        "rapid_retry": {
            "description": "Tentatives répétées rapides",
            "score": 25,
        },
        "odd_hours": {
            "description": "Transaction en dehors des heures normales (00h-05h)",
            "score": 10,
        },
        "round_amount": {
            "description": "Montant rond suspect",
            "score": 5,
        },
    }

    def analyze(self, data: dict) -> Tuple[int, List[str]]:
        """
        Analyse une transaction et retourne (score, règles déclenchées)
        Score de 0 à 100.
        """
        score = 0
        triggered = []

        amount = data.get("amount", 0)
        phone = data.get("phone_number", "")
        ip = data.get("ip_address", "")
        reference = data.get("reference", "")

        # Règle: montant élevé
        if amount > 5_000_000:
            score += self.RULES["very_high_amount"]["score"]
            triggered.append("very_high_amount")
        elif amount > 2_000_000:
            score += self.RULES["high_amount"]["score"]
            triggered.append("high_amount")

        # Règle: montant rond (ex: 500000, 1000000)
        if amount > 0 and amount % 100_000 == 0:
            score += self.RULES["round_amount"]["score"]
            triggered.append("round_amount")

        # Règle: heures suspectes
        hour = datetime.utcnow().hour
        if 0 <= hour < 5:
            score += self.RULES["odd_hours"]["score"]
            triggered.append("odd_hours")

        # Règle: blacklist téléphone
        if phone and redis_client.sismember("fraud:blacklist:phones", phone):
            score += self.RULES["blacklisted_phone"]["score"]
            triggered.append("blacklisted_phone")

        # Règle: blacklist IP
        if ip and redis_client.sismember("fraud:blacklist:ips", ip):
            score += self.RULES["blacklisted_ip"]["score"]
            triggered.append("blacklisted_ip")

        # Règle: trop de transactions par heure (par téléphone)
        if phone:
            hour_key = f"fraud:txn_count:{phone}:{datetime.utcnow().strftime('%Y%m%d%H')}"
            txn_count = redis_client.incr(hour_key)
            redis_client.expire(hour_key, 3600)
            if txn_count > settings.MAX_TRANSACTIONS_PER_HOUR:
                score += self.RULES["too_many_transactions_hour"]["score"]
                triggered.append("too_many_transactions_hour")

        # Règle: limite journalière (par téléphone)
        if phone:
            day_key = f"fraud:daily_amount:{phone}:{datetime.utcnow().strftime('%Y%m%d')}"
            daily_total = float(redis_client.get(day_key) or 0) + amount
            redis_client.setex(day_key, 86400, daily_total)
            if daily_total > settings.MAX_AMOUNT_PER_DAY:
                score += self.RULES["daily_limit_exceeded"]["score"]
                triggered.append("daily_limit_exceeded")

        # Règle: tentatives rapides (même référence en moins de 60 sec)
        retry_key = f"fraud:rapid_retry:{phone}:{int(amount)}"
        if redis_client.get(retry_key):
            score += self.RULES["rapid_retry"]["score"]
            triggered.append("rapid_retry")
        else:
            redis_client.setex(retry_key, 60, "1")

        # Plafonner à 100
        score = min(score, 100)
        return score, triggered

    def get_risk_level(self, score: int) -> str:
        if score >= 80:
            return "critical"
        elif score >= 60:
            return "high"
        elif score >= 30:
            return "medium"
        return "low"

    def get_action(self, score: int) -> str:
        if score >= settings.FRAUD_SCORE_THRESHOLD:
            return "block"
        elif score >= 30:
            return "review"
        return "allow"

    def add_to_blacklist(self, phone: str = None, ip: str = None):
        if phone:
            redis_client.sadd("fraud:blacklist:phones", phone)
        if ip:
            redis_client.sadd("fraud:blacklist:ips", ip)

    def remove_from_blacklist(self, phone: str = None, ip: str = None):
        if phone:
            redis_client.srem("fraud:blacklist:phones", phone)
        if ip:
            redis_client.srem("fraud:blacklist:ips", ip)

detector = FraudDetector()

import httpx
import logging
from ..config import settings

logger = logging.getLogger(__name__)

class WaveConnector:
    """Connecteur Wave"""

    def __init__(self):
        self.api_url = settings.WAVE_API_URL
        self.api_key = settings.WAVE_API_KEY

    async def initiate_checkout(
        self,
        phone: str,
        amount: float,
        reference: str,
        description: str = ""
    ) -> dict:
        """Initie un paiement Wave"""
        try:
            async with httpx.AsyncClient() as client:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                }
                payload = {
                    "currency": "GNF",
                    "amount": str(int(amount)),
                    "error_url": "",
                    "success_url": "",
                    "payment_reason": description or reference,
                }
                response = await client.post(
                    f"{self.api_url}/checkout/sessions",
                    json=payload,
                    headers=headers,
                    timeout=30
                )
                response.raise_for_status()
                data = response.json()
                return {
                    "success": True,
                    "operator_reference": data.get("id"),
                    "checkout_url": data.get("wave_launch_url"),
                    "raw": data
                }
        except Exception as e:
            logger.error(f"Wave error: {e}")
            return {"success": False, "error": str(e)}

    async def check_payment_status(self, operator_reference: str) -> dict:
        """Vérifie le statut d'un paiement Wave"""
        try:
            async with httpx.AsyncClient() as client:
                headers = {"Authorization": f"Bearer {self.api_key}"}
                response = await client.get(
                    f"{self.api_url}/checkout/sessions/{operator_reference}",
                    headers=headers,
                    timeout=30
                )
                data = response.json()
                status = data.get("payment_status", "").lower()
                return {
                    "success": status == "succeeded",
                    "status": status,
                    "raw": data
                }
        except Exception as e:
            return {"success": False, "error": str(e)}

wave = WaveConnector()

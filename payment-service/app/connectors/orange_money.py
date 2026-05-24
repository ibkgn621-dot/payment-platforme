import httpx
import logging
from typing import Optional
from ..config import settings

logger = logging.getLogger(__name__)

class OrangeMoneyConnector:
    """Connecteur Orange Money Guinée"""

    def __init__(self):
        self.api_url = settings.ORANGE_MONEY_API_URL
        self.api_key = settings.ORANGE_MONEY_API_KEY

    async def initiate_payment(
        self,
        phone: str,
        amount: float,
        reference: str,
        description: str = ""
    ) -> dict:
        """Initie un paiement Orange Money"""
        try:
            async with httpx.AsyncClient() as client:
                payload = {
                    "merchant_key": self.api_key,
                    "currency": "GNF",
                    "order_id": reference,
                    "amount": str(int(amount)),
                    "return_url": "",
                    "cancel_url": "",
                    "notif_url": "",
                    "lang": "fr",
                    "reference": reference,
                }
                response = await client.post(
                    f"{self.api_url}/webpayment",
                    json=payload,
                    timeout=30
                )
                response.raise_for_status()
                data = response.json()
                return {
                    "success": True,
                    "operator_reference": data.get("pay_token"),
                    "payment_url": data.get("payment_url"),
                    "raw": data
                }
        except Exception as e:
            logger.error(f"Orange Money error: {e}")
            return {"success": False, "error": str(e)}

    async def check_payment_status(self, operator_reference: str) -> dict:
        """Vérifie le statut d'un paiement Orange Money"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.api_url}/transactionstatus",
                    params={"order_id": operator_reference},
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    timeout=30
                )
                data = response.json()
                status = data.get("status", "").upper()
                return {
                    "success": status == "SUCCESS",
                    "status": status,
                    "raw": data
                }
        except Exception as e:
            logger.error(f"Orange Money status check error: {e}")
            return {"success": False, "error": str(e)}

orange_money = OrangeMoneyConnector()

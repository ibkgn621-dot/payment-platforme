import httpx
import uuid
import logging
from ..config import settings

logger = logging.getLogger(__name__)

class MTNMomoConnector:
    """Connecteur MTN Mobile Money"""

    def __init__(self):
        self.api_url = settings.MTN_MOMO_API_URL
        self.api_key = settings.MTN_MOMO_API_KEY

    async def request_to_pay(
        self,
        phone: str,
        amount: float,
        reference: str,
        description: str = ""
    ) -> dict:
        """Initie une demande de paiement MTN MoMo"""
        try:
            external_id = str(uuid.uuid4())
            async with httpx.AsyncClient() as client:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "X-Reference-Id": external_id,
                    "X-Target-Environment": "sandbox",
                    "Content-Type": "application/json",
                    "Ocp-Apim-Subscription-Key": self.api_key,
                }
                payload = {
                    "amount": str(int(amount)),
                    "currency": "GNF",
                    "externalId": reference,
                    "payer": {
                        "partyIdType": "MSISDN",
                        "partyId": phone.lstrip("+"),
                    },
                    "payerMessage": description,
                    "payeeNote": reference,
                }
                response = await client.post(
                    f"{self.api_url}/collection/v1_0/requesttopay",
                    json=payload,
                    headers=headers,
                    timeout=30
                )
                if response.status_code == 202:
                    return {"success": True, "operator_reference": external_id}
                return {"success": False, "error": response.text}
        except Exception as e:
            logger.error(f"MTN MoMo error: {e}")
            return {"success": False, "error": str(e)}

    async def check_payment_status(self, operator_reference: str) -> dict:
        """Vérifie le statut d'un paiement MTN"""
        try:
            async with httpx.AsyncClient() as client:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "X-Target-Environment": "sandbox",
                    "Ocp-Apim-Subscription-Key": self.api_key,
                }
                response = await client.get(
                    f"{self.api_url}/collection/v1_0/requesttopay/{operator_reference}",
                    headers=headers,
                    timeout=30
                )
                data = response.json()
                status = data.get("status", "").upper()
                return {
                    "success": status == "SUCCESSFUL",
                    "status": status,
                    "raw": data
                }
        except Exception as e:
            return {"success": False, "error": str(e)}

mtn_momo = MTNMomoConnector()

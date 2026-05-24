import aio_pika
import json
import logging
from .config import settings

logger = logging.getLogger(__name__)

EXCHANGE_NAME = "payment_events"

async def get_connection():
    return await aio_pika.connect_robust(settings.RABBITMQ_URL)

async def publish_event(event_type: str, data: dict):
    """Publie un événement de paiement sur RabbitMQ"""
    try:
        connection = await get_connection()
        async with connection:
            channel = await connection.channel()
            exchange = await channel.declare_exchange(
                EXCHANGE_NAME,
                aio_pika.ExchangeType.TOPIC,
                durable=True
            )
            message_body = json.dumps({
                "event_type": event_type,
                "data": data
            }).encode()
            message = aio_pika.Message(
                body=message_body,
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                content_type="application/json"
            )
            routing_key = f"payment.{event_type}"
            await exchange.publish(message, routing_key=routing_key)
            logger.info(f"Événement publié: {routing_key}")
    except Exception as e:
        logger.error(f"Erreur publication RabbitMQ: {e}")

# Événements disponibles
async def publish_payment_created(transaction: dict):
    await publish_event("created", transaction)

async def publish_payment_success(transaction: dict):
    await publish_event("success", transaction)

async def publish_payment_failed(transaction: dict):
    await publish_event("failed", transaction)

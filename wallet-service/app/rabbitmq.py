import aio_pika
import json
import asyncio
import logging
from .config import settings

logger = logging.getLogger(__name__)

async def start_consumer(process_message_func):
    """Démarre le consumer RabbitMQ pour les événements de paiement"""
    try:
        connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=10)

        exchange = await channel.declare_exchange(
            "payment_events",
            aio_pika.ExchangeType.TOPIC,
            durable=True
        )

        queue = await channel.declare_queue("wallet_payment_events", durable=True)
        await queue.bind(exchange, routing_key="payment.success")
        await queue.bind(exchange, routing_key="payment.failed")

        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process():
                    try:
                        body = json.loads(message.body.decode())
                        await process_message_func(body)
                    except Exception as e:
                        logger.error(f"Erreur traitement message: {e}")

    except Exception as e:
        logger.error(f"Erreur RabbitMQ consumer: {e}")
        await asyncio.sleep(5)
        await start_consumer(process_message_func)

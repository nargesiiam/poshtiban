"""
همان فایل apps/events/topology.py سمت backend — عمداً کپی شده، نه import
مشترک بین دو سرویس مجزا با build context جدا. توضیح کامل چرایی این تصمیم
در نسخه‌ی backend آمده.
"""

COMMANDS_EXCHANGE = "relay.commands"
COMMANDS_RETRY_EXCHANGE = "relay.commands.retry"
COMMANDS_QUEUE = "ai_worker.commands"
COMMANDS_RETRY_QUEUE = "ai_worker.commands.retry"
COMMANDS_DLQ = "ai_worker.commands.dlq"

EVENTS_EXCHANGE = "relay.events"
BACKEND_EVENTS_QUEUE = "backend.events"

MAX_RETRIES = 5
BASE_DELAY_MS = 1000  # نمایی: 1s, 2s, 4s, 8s, 16s


def declare_topology(channel):
    channel.exchange_declare(exchange=COMMANDS_EXCHANGE, exchange_type="topic", durable=True)
    channel.exchange_declare(exchange=COMMANDS_RETRY_EXCHANGE, exchange_type="topic", durable=True)

    channel.queue_declare(queue=COMMANDS_DLQ, durable=True)

    channel.queue_declare(
        queue=COMMANDS_RETRY_QUEUE,
        durable=True,
        arguments={
            "x-dead-letter-exchange": COMMANDS_EXCHANGE,
            "x-dead-letter-routing-key": "command.#",
        },
    )
    channel.queue_bind(queue=COMMANDS_RETRY_QUEUE, exchange=COMMANDS_RETRY_EXCHANGE, routing_key="#")

    channel.queue_declare(
        queue=COMMANDS_QUEUE,
        durable=True,
        arguments={
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": COMMANDS_DLQ,
        },
    )
    channel.queue_bind(queue=COMMANDS_QUEUE, exchange=COMMANDS_EXCHANGE, routing_key="command.#")

    channel.exchange_declare(exchange=EVENTS_EXCHANGE, exchange_type="topic", durable=True)
    channel.queue_declare(queue=BACKEND_EVENTS_QUEUE, durable=True)
    channel.queue_bind(queue=BACKEND_EVENTS_QUEUE, exchange=EVENTS_EXCHANGE, routing_key="event.#")


def retry_delay_ms(retry_count: int) -> int:
    return BASE_DELAY_MS * (2 ** retry_count)

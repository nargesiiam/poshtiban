import json
import uuid
from datetime import datetime, timezone

import pika

from . import config
from .topology import COMMANDS_RETRY_EXCHANGE, EVENTS_EXCHANGE, declare_topology


def connection():
    credentials = pika.PlainCredentials(config.RABBITMQ_USER, config.RABBITMQ_PASSWORD)
    params = pika.ConnectionParameters(host=config.RABBITMQ_HOST, credentials=credentials)
    return pika.BlockingConnection(params)


def build_envelope(event_type: str, payload: dict, correlation_id: str) -> dict:
    return {
        "event_id": str(uuid.uuid4()),
        "correlation_id": correlation_id,
        "event_type": event_type,
        "kind": "event",
        "version": 1,
        "producer": "ai-worker",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }


def publish_event(channel, event_type: str, payload: dict, correlation_id: str) -> dict:
    """
    عامل هنگام هر قدم مهم (فراخوانی ابزار، تولید delta پاسخ، تصمیم نهایی)
    یک event منتشر می‌کند. این رویدادها به backend.events می‌رسند و پل SSE
    (بخش ۶) آن‌ها را به مرورگر کاربر می‌رساند — بدون این‌که ai-worker اصلاً
    بداند SSE یا React وجود دارد. جدایی کامل تولیدکننده از مصرف‌کننده،
    همان چیزی است که معماری رویدادمحور را رویدادمحور می‌کند.
    """
    envelope = build_envelope(event_type, payload, correlation_id)
    channel.basic_publish(
        exchange=EVENTS_EXCHANGE,
        routing_key=f"event.{event_type}",
        body=json.dumps(envelope).encode("utf-8"),
        properties=pika.BasicProperties(content_type="application/json", delivery_mode=2),
    )
    return envelope


def republish_for_retry(channel, envelope: dict, delay_ms: int, retry_count: int):
    channel.basic_publish(
        exchange=COMMANDS_RETRY_EXCHANGE,
        routing_key="retry",
        body=json.dumps(envelope).encode("utf-8"),
        properties=pika.BasicProperties(
            content_type="application/json",
            delivery_mode=2,
            expiration=str(delay_ms),  # TTL این پیام در صف تأخیر — رمز backoff نمایی
            headers={"x-retry-count": retry_count},  # وقتی dead-letter به صف اصلی برگردد، این عدد باید حفظ شود
        ),
    )


def ensure_topology(channel):
    declare_topology(channel)

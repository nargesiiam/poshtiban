"""
انتشاردهنده‌ی پیام از سمت backend.

هر پیام (command یا event) یک ساختار یکسان و نسخه‌دار دارد:

    {
        "event_id":       UUID یکتا برای همین پیام — کلید idempotency
        "correlation_id": UUID مشترک در کل مسیر یک درخواست
        "event_type":     مثلا "chat.message.process"
        "kind":           "command" یا "event"
        "version":        1  — تغییر ساختار payload یعنی افزایش این عدد،
                              نه شکستن مصرف‌کننده‌های قدیمی
        "producer":       "backend"
        "occurred_at":    ISO 8601 UTC
        "payload":        دیتای مخصوص همین نوع پیام
    }

publisher confirms را روشن می‌کنیم (`confirm_delivery`) — یعنی backend
مطمئن می‌شود پیام واقعاً به بروکر رسیده، نه فقط اینکه TCP write بدون خطا
برگشته. بدون این، اگر RabbitMQ لحظه‌ی publish در حال failover باشد،
پیام بی‌صدا گم می‌شود و کاربر هرگز پاسخی نمی‌بیند، بدون هیچ خطای قابل‌مشاهده.
"""
import json
import uuid
from datetime import datetime, timezone

import pika
from django.conf import settings

from .models import EventLog
from .topology import COMMANDS_EXCHANGE, EVENTS_EXCHANGE, declare_topology


def _connection():
    credentials = pika.PlainCredentials(settings.RABBITMQ_USER, settings.RABBITMQ_PASSWORD)
    params = pika.ConnectionParameters(host=settings.RABBITMQ_HOST, credentials=credentials)
    return pika.BlockingConnection(params)


def _build_envelope(event_type: str, kind: str, payload: dict, correlation_id: uuid.UUID) -> dict:
    return {
        "event_id": str(uuid.uuid4()),
        "correlation_id": str(correlation_id),
        "event_type": event_type,
        "kind": kind,
        "version": 1,
        "producer": "backend",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }


def _publish(exchange: str, routing_key: str, envelope: dict):
    # اتصال کوتاه‌عمر به‌ازای هر publish — برای حجم این پروژه ساده و کافی است.
    # در production واقعی، یک connection pool یا یک producer طولانی‌مدت به‌جای
    # باز و بسته کردن اتصال در هر request به‌صرفه‌تر است؛ نقطه‌ی بهینه‌سازی شناخته‌شده.
    connection = _connection()
    try:
        channel = connection.channel()
        declare_topology(channel)
        channel.confirm_delivery()
        try:
            channel.basic_publish(
                exchange=exchange,
                routing_key=routing_key,
                body=json.dumps(envelope).encode("utf-8"),
                properties=pika.BasicProperties(
                    content_type="application/json",
                    delivery_mode=2,  # persistent — پیام روی دیسک هم نوشته شود
                ),
                mandatory=True,
            )
        except (pika.exceptions.NackError, pika.exceptions.UnroutableError) as exc:
            # نکته‌ی مهم درباره‌ی pika: با publisher confirms روشن،
            # basic_publish در موفقیت چیزی برنمی‌گرداند (None) و فقط در
            # شکست («nack» از بروکر، یا mandatory+بدون صف مقصد) استثنا
            # پرتاب می‌کند. این‌جا دقیقاً همان استثناها را می‌گیریم —
            # چک کردن مقدار بازگشتی (که همیشه None است) اشتباه است.
            raise RuntimeError(
                f"RabbitMQ publish confirm نشد: {envelope['event_type']}"
            ) from exc
    finally:
        connection.close()

    EventLog.objects.create(
        event_id=envelope["event_id"],
        correlation_id=envelope["correlation_id"],
        event_type=envelope["event_type"],
        kind=envelope["kind"],
        version=envelope["version"],
        producer=envelope["producer"],
        payload=envelope["payload"],
    )
    return envelope


def publish_command(command_type: str, payload: dict, correlation_id: uuid.UUID) -> dict:
    """
    مثال: publish_command("chat.message.process", {...}, correlation_id)
    routing key به شکل command.<نوع> است تا با binding بخش topology جور دربیاید.
    """
    envelope = _build_envelope(command_type, "command", payload, correlation_id)
    _publish(COMMANDS_EXCHANGE, f"command.{command_type}", envelope)
    return envelope


def publish_event(event_type: str, payload: dict, correlation_id: uuid.UUID) -> dict:
    envelope = _build_envelope(event_type, "event", payload, correlation_id)
    _publish(EVENTS_EXCHANGE, f"event.{event_type}", envelope)
    return envelope

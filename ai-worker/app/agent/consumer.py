"""
نقطه‌ی ورود ai-worker.

قابلیت اطمینان اینجا پیاده می‌شود:

  - manual ack: هیچ پیامی «موفق» فرض نمی‌شود مگر پردازشش (و commit
    تراکنش دیتابیس مربوطه) واقعاً کامل شده باشد. auto_ack خاموش است.

  - idempotency: پیش از هر پردازش، atomic_command_processing تلاش می‌کند
    در events_processedcommand رکورد بسازد. اگر تکراری بود، پردازش رد
    می‌شود و فقط ack می‌شویم — یعنی اگر همان command دوبار برسد (مثلاً
    چون backend به‌خاطر timeout دوباره publish کرده)، دو پاسخ برای کاربر
    ساخته نمی‌شود.

  - retry با تأخیر نمایی: اگر پردازش با خطای غیرمنتظره مواجه شود (نه
    duplicate)، شمارنده‌ی retry از header پیام خوانده می‌شود؛ اگر کمتر از
    MAX_RETRIES بود، نسخه‌ای از پیام با شمارنده‌ی +۱ و TTL نمایی به صف
    تأخیر می‌رود، پیام اصلی ack می‌شود (چون مسئولیتش را به نسخه‌ی جدید
    منتقل کردیم). اگر به سقف رسیده بود، مستقیم به DLQ می‌رود — worker
    برای همیشه روی یک command خراب گیر نمی‌کند.
"""
import json
import time

import pika

from . import config
from .db import DuplicateCommand, atomic_command_processing, log_event
from .handlers import HANDLERS, mark_document_ingestion_failed
from .messaging import ensure_topology, republish_for_retry
from .topology import COMMANDS_DLQ, COMMANDS_QUEUE, MAX_RETRIES, retry_delay_ms


def _get_retry_count(properties) -> int:
    headers = properties.headers or {}
    return int(headers.get("x-retry-count", 0))


def _handle_delivery(channel, method, properties, body):
    envelope = json.loads(body)
    event_id = envelope["event_id"]
    event_type = envelope["event_type"]
    correlation_id = envelope["correlation_id"]
    retry_count = _get_retry_count(properties)

    handler = HANDLERS.get(event_type)
    if handler is None:
        print(f"[ai-worker] نوع command ناشناخته: {event_type} — به DLQ می‌رود")
        channel.basic_publish(exchange="", routing_key=COMMANDS_DLQ, body=body)
        channel.basic_ack(delivery_tag=method.delivery_tag)
        return

    try:
        with atomic_command_processing(event_id) as (conn, cur):
            log_event(cur, envelope, retry_count=retry_count)
            handler(envelope, conn, cur, channel)
        channel.basic_ack(delivery_tag=method.delivery_tag)
        print(f"[ai-worker] پردازش شد: {event_type} correlation={correlation_id}")

    except DuplicateCommand:
        print(f"[ai-worker] تکراری، پردازش نشد: event_id={event_id}")
        channel.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as exc:  # noqa: BLE001 — عمداً گسترده؛ هر خطا باید مسیر retry/DLQ را طی کند
        print(f"[ai-worker] خطا در پردازش {event_type}: {exc!r}")
        if retry_count < MAX_RETRIES:
            republish_for_retry(
                channel,
                envelope,
                delay_ms=retry_delay_ms(retry_count),
                retry_count=retry_count + 1,
            )
            print(f"[ai-worker] retry #{retry_count + 1} برنامه‌ریزی شد")
        else:
            print(f"[ai-worker] سقف retry رد شد، به DLQ می‌رود: {event_id}")
            channel.basic_publish(exchange="", routing_key=COMMANDS_DLQ, body=body)
            if event_type == "document.ingest":
                try:
                    mark_document_ingestion_failed(envelope["payload"]["document_id"])
                except Exception as status_exc:  # noqa: BLE001 — این آپدیت کمکی است؛ شکستش نباید ack را متوقف کند
                    print(f"[ai-worker] ثبت وضعیت «ناموفق» سند هم شکست خورد: {status_exc!r}")
        channel.basic_ack(delivery_tag=method.delivery_tag)


def _warm_up_embedding_model():
    """
    اولین باری که کالکشن ChromaDB چیزی add می‌کند، کتابخانه‌ی کلاینت مدل
    embedding پیش‌فرض (all-MiniLM-L6-v2، حدود ۸۰ مگابایت) را از اینترنت
    دانلود می‌کند. اگر این دانلود وسط پردازشِ اولین سند اتفاق بیفتد، با
    محدودیت زمانیِ HTTP client چروما تداخل می‌کند و به ReadTimeout می‌خورد
    (دقیقاً همان چیزی که دیدیم). برای همین، همین‌جا و قبل از ورود به حلقه‌ی
    اصلی، یک بار با صبرِ نامحدود دانلودش می‌کنیم. اگر قبلاً دانلود شده
    باشد (روی volume دائمی chroma_cache)، این تابع تقریباً آنی برمی‌گردد.
    """
    try:
        from chromadb.utils import embedding_functions

        print("[ai-worker] در حال آماده‌سازی مدل embedding (اولین‌بار ممکن است چند دقیقه طول بکشد)...")
        ef = embedding_functions.DefaultEmbeddingFunction()
        ef(["warm up"])
        print("[ai-worker] مدل embedding آماده است.")
    except Exception as exc:  # noqa: BLE001 — اگر گرم‌کردن شکست بخورد، همچنان اجازه بده worker بالا بیاید؛ خطای واقعی موقع پردازش سند دوباره دیده خواهد شد
        print(f"[ai-worker] هشدار: آماده‌سازی مدل embedding شکست خورد: {exc!r}")


def main():
    _warm_up_embedding_model()
    while True:
        try:
            credentials = pika.PlainCredentials(config.RABBITMQ_USER, config.RABBITMQ_PASSWORD)
            params = pika.ConnectionParameters(host=config.RABBITMQ_HOST, credentials=credentials)
            connection = pika.BlockingConnection(params)
            channel = connection.channel()
            ensure_topology(channel)

            # prefetch=1 یعنی worker یک command را کامل تمام می‌کند قبل از
            # گرفتن بعدی — برای این پروژه که تولید پاسخ می‌تواند طول بکشد
            # و ترتیب هر مکالمه مهم است، درست‌تر از پردازش موازی بی‌قاعده است.
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(
                queue=COMMANDS_QUEUE,
                on_message_callback=_handle_delivery,
                auto_ack=False,
            )
            print("[ai-worker] در حال گوش دادن به صف command ها...")
            channel.start_consuming()

        except pika.exceptions.AMQPConnectionError:
            print("[ai-worker] اتصال به RabbitMQ برقرار نشد، تلاش دوباره در ۳ ثانیه...")
            time.sleep(3)


if __name__ == "__main__":
    main()

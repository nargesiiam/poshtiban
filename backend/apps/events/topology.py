"""
تعریف توپولوژی RabbitMQ.

این فایل عمداً در backend و ai-worker هر دو تکرار شده (کپی، نه import
مشترک). دو سرویس، دو مخزن build جدا در Docker؛ برای پروژه‌ای به این
اندازه، ساختن یک پکیج pip مشترک فقط برای ~۶۰ خط پیچیدگی build اضافه
می‌کند بدون سود واقعی. اگر تعداد سرویس‌ها بیشتر شود، این تصمیم عوض
می‌شود.

--- Command و Event: تمایز و چرایی ---

command یعنی «این کار را انجام بده» — دقیقاً یک مصرف‌کننده‌ی مشخص دارد
(ai-worker) و انتظار می‌رود اتفاق بیفتد. اگر پردازش نشود، مشکل واقعی است.

event یعنی «این اتفاق افتاد» — ممکن است صفر، یک، یا چند مصرف‌کننده داشته
باشد و هیچ‌کدام «منتظرش» نیستند. اگر امروز هیچ‌کس event.agent.tool.called
را مصرف نکند، سیستم هیچ کم‌وکسری ندارد؛ فردا اگر یک سرویس analytics
اضافه شود، فقط یک binding جدید به exchange رویدادها می‌زند.

به همین دلیل دو exchange جدا داریم: یکی برای command (مقصد مشخص)،
یکی برای event (پخش به هرکسی که علاقه‌مند است، از جمله هیچ‌کس).

--- Retry با تأخیر نمایی ---

الگوی رایج RabbitMQ برای exponential backoff بدون افزونه‌ی اضافه:
هر بار که پردازش شکست می‌خورد، پیام با یک `expiration` (TTL) متفاوت —
که خودِ تولیدکننده هنگام publish مجدد تعیین می‌کند — به exchange تأخیر
فرستاده می‌شود. وقتی TTL آن پیام در صف تأخیر تمام شود، RabbitMQ آن را
به‌خاطر dead-letter-exchange این صف، به exchange اصلیِ command برمی‌گرداند.

محدودیت شناخته‌شده: صف‌های classic RabbitMQ فقط از ابتدای صف منقضی
می‌کنند؛ اگر پیامی با TTL کوتاه‌تر بعد از پیامی با TTL بلندتر برسد،
ممکن است دیرتر از حد انتظار تحویل داده شود. برای حجم و مقیاس این پروژه
قابل قبول است؛ در production واقعی باید صف‌های جدا به‌ازای هر پله از
تأخیر ساخت.
"""

COMMANDS_EXCHANGE = "relay.commands"
COMMANDS_RETRY_EXCHANGE = "relay.commands.retry"
COMMANDS_QUEUE = "ai_worker.commands"
COMMANDS_RETRY_QUEUE = "ai_worker.commands.retry"
COMMANDS_DLQ = "ai_worker.commands.dlq"

EVENTS_EXCHANGE = "relay.events"
BACKEND_EVENTS_QUEUE = "backend.events"  # مصرف‌کننده‌اش پل SSE در بخش ۶ است

MAX_RETRIES = 5
BASE_DELAY_MS = 1000  # ۱ ثانیه پایه؛ نمایی: 1s, 2s, 4s, 8s, 16s


def declare_topology(channel):
    """
    این تابع idempotent است — صدا زدنش چندبار (هم از backend هنگام start،
    هم از ai-worker) خطا نمی‌دهد، فقط تضمین می‌کند توپولوژی موجود است.
    هیچ سرویسی نباید فرض کند «سرویس دیگر قبلاً صف را ساخته».
    """
    # --- مسیر command ---
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
            # اگر worker پیام را nack کند بدون مسیر retry صریح (خطای غیرمنتظره)،
            # به DLQ می‌رود، نه اینکه بی‌نهایت redeliver شود.
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": COMMANDS_DLQ,
        },
    )
    channel.queue_bind(queue=COMMANDS_QUEUE, exchange=COMMANDS_EXCHANGE, routing_key="command.#")

    # --- مسیر event ---
    channel.exchange_declare(exchange=EVENTS_EXCHANGE, exchange_type="topic", durable=True)
    channel.queue_declare(queue=BACKEND_EVENTS_QUEUE, durable=True)
    channel.queue_bind(queue=BACKEND_EVENTS_QUEUE, exchange=EVENTS_EXCHANGE, routing_key="event.#")


def retry_delay_ms(retry_count: int) -> int:
    """تأخیر نمایی: 1s, 2s, 4s, 8s, 16s برای retry_count های ۰ تا ۴."""
    return BASE_DELAY_MS * (2 ** retry_count)

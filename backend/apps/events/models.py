import uuid

from django.db import models


class EventLog(models.Model):
    """
    رکورد کامل هر پیامی (command یا event) که از صف عبور کرده.
    این جدول دو نقش دارد:
      ۱. رصدپذیری (بخش ۷) — می‌شود همه‌ی پیام‌های یک correlation_id را
         بازسازی و کل مسیر یک درخواست را دید.
      ۲. مستندسازی زنده‌ی «قرارداد پیام» — به‌جای یک فایل جدا که ممکن است
         با کد واقعی هم‌راستا نماند، خودِ داده‌ی تولیدشده گواه ساختار پیام‌هاست.

    backend این جدول را با migration می‌سازد (چون صاحب schema است)، اما
    ai-worker هم مستقیماً با psycopg رویش می‌نویسد و می‌خواند — دو سرویس،
    یک جدول مشترک در Postgres. این تصمیم آگاهانه است: صف پیام (RabbitMQ)
    برای orchestration است، نه برای audit trail بلندمدت؛ Postgres برای آن
    ساخته شده.
    """

    KIND_CHOICES = [("command", "command"), ("event", "event")]

    event_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    correlation_id = models.UUIDField(db_index=True)
    event_type = models.CharField(max_length=100, db_index=True)
    kind = models.CharField(max_length=10, choices=KIND_CHOICES)
    version = models.PositiveSmallIntegerField(default=1)
    producer = models.CharField(max_length=50)  # "backend" یا "ai-worker"
    payload = models.JSONField()
    retry_count = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["correlation_id", "created_at"]),
        ]

    def __str__(self):
        return f"{self.kind}:{self.event_type} [{str(self.correlation_id)[:8]}]"


class ProcessedCommand(models.Model):
    """
    دروازه‌ی idempotency. پیش از پردازش واقعیِ هر command، ai-worker تلاش
    می‌کند یک ردیف با همین event_id اینجا بسازد. اگر constraint یکتایی
    (که همان primary key است) نقض شود، یعنی این command قبلاً پردازش شده —
    worker بدون هیچ پردازشی فقط ack می‌کند و کار تمام است.

    این INSERT همیشه در همان تراکنش دیتابیسی‌ای انجام می‌شود که اثر جانبیِ
    واقعی command هم در آن ثبت می‌شود (مثلاً ساخت Message یا تغییر
    RefundRequest). یعنی یا هر دو با هم commit می‌شوند، یا هیچ‌کدام —
    این دقیقاً چیزی است که به سؤال «worker وسط کار کرش کند چه می‌شود؟»
    جواب می‌دهد.
    """

    event_id = models.UUIDField(primary_key=True)
    processed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return str(self.event_id)

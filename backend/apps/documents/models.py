from django.conf import settings
from django.db import models


class Document(models.Model):
    """
    اسناد دانش شرکت (سیاست بازگشت کالا و مشابه) — برخلاف Order، این داده
    مالِ یک کاربر خاص نیست، مالِ کل سازمان است. پس این مدل نیازی به
    فیلتر بر اساس کاربر ندارد؛ مجوزدهیِ اینجا در سطح «چه کسی حق آپلود دارد»ست
    (views.py) نه «چه کسی حق دیدن دارد».

    ingestion_status نشان می‌دهد آیا این سند هنوز در بخش ۵ (RAG) توسط
    ai-worker خوانده، chunk و در ChromaDB embed شده یا نه — آپلود فایل و
    embed شدنش دو مرحله‌ی جدا و ناهمزمان هستند.
    """

    class IngestionStatus(models.TextChoices):
        PENDING = "pending", "در انتظار پردازش"
        PROCESSING = "processing", "در حال embed شدن"
        READY = "ready", "آماده برای بازیابی"
        FAILED = "failed", "پردازش ناموفق"

    title = models.CharField(max_length=200)
    file = models.FileField(upload_to="documents/%Y/%m/")
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="uploaded_documents",
    )
    ingestion_status = models.CharField(
        max_length=20,
        choices=IngestionStatus.choices,
        default=IngestionStatus.PENDING,
    )
    chroma_collection = models.CharField(max_length=100, default="company_docs")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

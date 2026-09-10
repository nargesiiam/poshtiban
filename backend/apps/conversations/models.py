from django.conf import settings
from django.db import models

from apps.orders.models import Order


class ConversationQuerySet(models.QuerySet):
    def for_user(self, user):
        return self.filter(user=user)


class Conversation(models.Model):
    """
    یک نشست چت بین کاربر و Maya. اگر مربوط به سفارش خاصی باشد order پر
    می‌شود، ولی می‌تواند سؤال عمومی (بیرون از سفارش) هم باشد پس order
    اختیاری است.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="conversations",
    )
    order = models.ForeignKey(
        Order, on_delete=models.SET_NULL, null=True, blank=True, related_name="conversations"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    objects = ConversationQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Conversation #{self.pk} — {self.user.username}"


class Message(models.Model):
    class Role(models.TextChoices):
        USER = "user", "کاربر"
        ASSISTANT = "assistant", "دستیار"
        SYSTEM = "system", "سیستم"

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=16, choices=Role.choices)
    content = models.TextField()
    # منبع پاسخ (db / rag / web / action / none) — برای اینکه در UI بشود ارجاع داخلی
    # را از ارجاع وب متمایز نشان داد (الزام بخش ۵)
    source = models.CharField(max_length=16, blank=True)
    # --- بخش ۷: رصدپذیری و هزینه — فقط روی پیام‌های assistant پر می‌شود ---
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    search_credits = models.PositiveIntegerField(default=0)
    estimated_cost_usd = models.DecimalField(max_digits=12, decimal_places=6, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"[{self.role}] {self.content[:40]}"

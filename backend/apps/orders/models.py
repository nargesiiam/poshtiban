from django.conf import settings
from django.db import models


class Product(models.Model):
    """محصولات — داده‌ی عمومی، مالِ کاربر خاصی نیست، پس نیازی به فیلتر کاربر ندارد."""
    name = models.CharField(max_length=200)
    sku = models.CharField(max_length=64, unique=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class OrderQuerySet(models.QuerySet):
    def for_user(self, user):
        """
        نقطه‌ی مرکزیِ اجرای مجوز روی سفارش‌ها.
        هر جای کد — چه یک ویو DRF، چه یک tool که عامل هوش مصنوعی صدا می‌زند —
        باید از همین متد عبور کند. این یعنی مجوزدهی یک بار در یک جا تعریف شده،
        نه پخش‌شده و قابل‌فراموشی در ده جای مختلف.
        """
        return self.filter(user=user)


class Order(models.Model):
    class Status(models.TextChoices):
        PROCESSING = "processing", "در حال پردازش"
        SHIPPED = "shipped", "ارسال شده"
        DELIVERED = "delivered", "تحویل شده"
        CANCELLED = "cancelled", "لغو شده"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="orders",
    )
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="orders")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PROCESSING)
    tracking_number = models.CharField(max_length=64, blank=True)
    carrier = models.CharField(max_length=64, blank=True)
    shipping_address = models.CharField(max_length=300)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = OrderQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Order #{self.pk} — {self.user.username}"


class RefundRequestQuerySet(models.QuerySet):
    def for_user(self, user):
        return self.filter(order__user=user)


class RefundRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "در انتظار بررسی"
        APPROVED = "approved", "تأیید شده"
        DENIED = "denied", "رد شده"
        ESCALATED = "escalated", "ارجاع به تیم ریسک"

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="refund_requests")
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    decided_by_agent = models.CharField(
        max_length=32,
        blank=True,
        help_text="کدام لایه تصمیم گرفت: maya / manager / risk",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    objects = RefundRequestQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Refund #{self.pk} for Order #{self.order_id}"

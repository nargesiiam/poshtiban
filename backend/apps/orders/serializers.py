from rest_framework import serializers

from .models import Order, Product, RefundRequest


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ["id", "name", "sku", "price", "description"]


class OrderSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)

    class Meta:
        model = Order
        fields = [
            "id", "product", "status", "tracking_number", "carrier",
            "shipping_address", "amount", "created_at", "updated_at",
        ]
        read_only_fields = fields  # سفارش‌ها از این API فقط خوانده می‌شوند


class RefundRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = RefundRequest
        fields = ["id", "order", "reason", "status", "decided_by_agent", "created_at", "resolved_at"]
        read_only_fields = ["id", "status", "decided_by_agent", "created_at", "resolved_at"]

    def validate_order(self, order):
        """
        این خط دقیقاً همان چیزی است که سند می‌گوید: مجوزدهی در کد.
        حتی اگر کاربر شناسه‌ی سفارشِ کاربر دیگری را در بدنه‌ی درخواست بفرستد،
        اینجا رد می‌شود — نه چون prompt به مدل گفته «فقط سفارش خودت»، بلکه چون
        کوئری اصلاً چیزی جز سفارش‌های خودِ کاربر را نمی‌بیند.
        """
        request = self.context["request"]
        if not Order.objects.for_user(request.user).filter(pk=order.pk).exists():
            raise serializers.ValidationError("این سفارش متعلق به شما نیست.")
        return order

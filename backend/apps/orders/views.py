from rest_framework import generics, permissions

from .models import Order, RefundRequest
from .serializers import OrderSerializer, RefundRequestSerializer


class OrderListView(generics.ListAPIView):
    """
    لیست سفارش‌های کاربر جاری.
    get_queryset را override می‌کنیم، نه اینکه به کلاینت اجازه بدهیم user_id
    بفرستد. اگر کوئری‌ست اصلاً شامل داده‌ی کاربر دیگر نباشد، هیچ باگ منطقی
    بعدی نمی‌تواند آن را نشت بدهد — این تفاوتِ «فیلتر در لایه‌ی داده» با
    «فیلتر در لایه‌ی نمایش» است.
    """
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Order.objects.for_user(self.request.user)


class OrderDetailView(generics.RetrieveAPIView):
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # همین یک خط یعنی درخواست GET /api/orders/17/ برای سفارشِ کاربر دیگر
        # نتیجه‌اش 404 است، نه 403 — عمداً؛ حتی وجود سفارش را هم فاش نمی‌کنیم.
        return Order.objects.for_user(self.request.user)


class RefundRequestListCreateView(generics.ListCreateAPIView):
    serializer_class = RefundRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return RefundRequest.objects.for_user(self.request.user)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

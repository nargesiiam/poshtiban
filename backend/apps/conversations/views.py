import uuid

from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.events.messaging import publish_command
from apps.orders.models import Order

from .models import Conversation, Message
from .serializers import ConversationListSerializer, ConversationSerializer, SendMessageSerializer


class ConversationListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Conversation.objects.for_user(self.request.user)

    def get_serializer_class(self):
        # فهرست (نوار کناری) سبک است — فقط پیش‌نمایش؛ ساخت مکالمه‌ی تازه
        # هم چیزی برای نمایش کامل ندارد پس همین سریالایزر برایش هم کافی است.
        return ConversationListSerializer

    def perform_create(self, serializer):
        order = None
        order_id = self.request.data.get("order")
        if order_id:
            # همان الگوی همیشگی: سفارش فقط اگر مالِ همین کاربر باشد قابل اتصال است
            order = get_object_or_404(Order.objects.for_user(self.request.user), pk=order_id)
        serializer.save(user=self.request.user, order=order)


class ConversationDetailView(generics.RetrieveDestroyAPIView):
    """
    واکشیِ یک مکالمه به‌همراه تمام پیام‌هایش — همان مسیری که فرانت‌اند
    بعد از دریافت رویداد «پایان پاسخ» از SSE صدا می‌زند تا نسخه‌ی معتبرِ
    نهاییِ پیام‌ها را از Postgres بگیرد (نه از بایت‌های استریم).

    حذف (DELETE) هم همین‌جاست: چون Message.conversation با
    on_delete=CASCADE تعریف شده، حذف یک Conversation تمام پیام‌هایش را
    هم به‌صورت اتمیک در دیتابیس پاک می‌کند — نیازی به حذف دستیِ پیام‌ها
    قبل از آن نیست.
    """
    serializer_class = ConversationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Conversation.objects.for_user(self.request.user)


class SendMessageView(APIView):
    """
    نقطه‌ای که یک درخواست HTTP همزمان را به یک مسیر ناهمزمان (asynchronous)
    تبدیل می‌کند — دقیقاً همان جایی که این پروژه از دوره جدا می‌شود.

    این ویو خودش پاسخ عامل را تولید نمی‌کند و منتظرش هم نمی‌ماند. فقط:
      ۱. پیام کاربر را در دیتابیس ذخیره می‌کند (بلافاصله در UI قابل دیدن باشد)
      ۲. یک correlation_id تازه می‌سازد — از همین لحظه تا جواب نهایی، این
         شناسه کل مسیر (command → ai-worker → tool calls → event → SSE) را
         به هم وصل می‌کند
      ۳. command «chat.message.process» را روی صف می‌گذارد
      ۴. فوراً 202 Accepted برمی‌گرداند — نه 200، چون کار هنوز تمام نشده،
         فقط پذیرفته شده

    کلاینت (React) پاسخ Maya را از مسیر SSE می‌گیرد (بخش ۶)، نه از پاسخ
    همین درخواست.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        conversation = get_object_or_404(
            Conversation.objects.for_user(request.user), pk=pk
        )
        serializer = SendMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        message = Message.objects.create(
            conversation=conversation,
            role=Message.Role.USER,
            content=serializer.validated_data["content"],
        )

        correlation_id = uuid.uuid4()
        publish_command(
            "chat.message.process",
            payload={
                "conversation_id": conversation.id,
                "message_id": message.id,
                "user_id": request.user.id,
                "order_id": conversation.order_id,
                "content": message.content,
            },
            correlation_id=correlation_id,
        )

        return Response(
            {
                "message_id": message.id,
                "correlation_id": str(correlation_id),
            },
            status=status.HTTP_202_ACCEPTED,
        )

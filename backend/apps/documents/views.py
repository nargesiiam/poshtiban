import os
import uuid

from rest_framework import generics, permissions, serializers

from apps.events.messaging import publish_command

from .models import Document
from .serializers import DocumentSerializer

ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md"}


class IsStaffOrReadOnly(permissions.BasePermission):
    """
    هر کاربر لاگین‌کرده می‌تواند فهرست اسناد را ببیند (چون عامل هوش مصنوعی
    باید بتواند برایشان از این اسناد جواب بدهد)، اما فقط staff می‌تواند
    سند جدید آپلود کند. این مرز عمداً جداست از مرز «مالکیت داده‌ی شخصی»
    در orders — اینجا کنترل دسترسی بر اساس نقش است، آنجا بر اساس مالکیت.
    """

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return request.user and request.user.is_authenticated
        return request.user and request.user.is_staff


class DocumentListCreateView(generics.ListCreateAPIView):
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer
    permission_classes = [IsStaffOrReadOnly]

    def perform_create(self, serializer):
        uploaded_file = self.request.FILES.get("file")
        ext = os.path.splitext(uploaded_file.name)[1].lower() if uploaded_file else ""
        if ext not in ALLOWED_EXTENSIONS:
            # این بررسی عمداً همین‌جا و پیش از publish کردن command است، نه
            # داخل ai-worker — چون پایپ‌لاین embed کردن (بخش ۵) فقط استخراج
            # متن از PDF یا فایل متنی ساده را بلد است. اگر عکس یا فرمت دیگری
            # به دستش برسد، به‌جای خطای گنگِ «سند خالی است» بعد از چند retry
            # ناموفق، همین اول با پیام روشن رد می‌شود.
            raise serializers.ValidationError(
                {
                    "file": (
                        "فقط فایل PDF یا متنی (.txt/.md) پشتیبانی می‌شود. "
                        "پردازش تصویر یا فرمت‌های دیگر در این نسخه پیاده‌سازی نشده است."
                    )
                }
            )

        document = serializer.save(uploaded_by=self.request.user)
        # command، نه event — دقیقاً یک مصرف‌کننده (ai-worker) قرار است
        # این سند را embed کند؛ اگر پردازش نشود، مشکل واقعی است.
        publish_command(
            "document.ingest",
            payload={
                "document_id": document.id,
                # مسیر مطلق داخل کانتینر — backend و ai-worker هر دو همین
                # مسیر را روی یک bind mount مشترک (./backend/media) می‌بینند.
                "file_path": document.file.path,
                "title": document.title,
                "chroma_collection": document.chroma_collection,
            },
            correlation_id=uuid.uuid4(),
        )

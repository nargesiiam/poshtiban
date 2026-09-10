from rest_framework import serializers

from .models import Conversation, Message


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = [
            "id", "role", "content", "source",
            "input_tokens", "output_tokens", "search_credits", "estimated_cost_usd",
            "created_at",
        ]
        read_only_fields = fields


class ConversationListSerializer(serializers.ModelSerializer):
    """
    برای فهرست کناریِ مکالمات — فقط یک پیش‌نمایش از آخرین پیام، نه کل
    تاریخچه (که در ConversationSerializer کامل هست). واکشی سبک‌تر یعنی
    باز کردن نوار کناری کند نمی‌شود، حتی وقتی مکالمه‌ها طولانی‌اند.
    """
    preview = serializers.SerializerMethodField()
    message_count = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = ["id", "order", "created_at", "preview", "message_count"]
        read_only_fields = fields

    def get_preview(self, obj):
        last = obj.messages.order_by("-created_at").first()
        if not last:
            return ""
        text = last.content.strip()
        return text if len(text) <= 60 else text[:60] + "…"

    def get_message_count(self, obj):
        return obj.messages.count()


class ConversationSerializer(serializers.ModelSerializer):
    messages = MessageSerializer(many=True, read_only=True)

    class Meta:
        model = Conversation
        fields = ["id", "order", "created_at", "messages"]
        read_only_fields = ["id", "created_at", "messages"]


class SendMessageSerializer(serializers.Serializer):
    content = serializers.CharField(max_length=4000, trim_whitespace=True)

    def validate_content(self, value):
        if not value.strip():
            raise serializers.ValidationError("پیام نمی‌تواند خالی باشد.")
        return value

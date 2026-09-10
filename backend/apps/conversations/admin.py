from django.contrib import admin

from .models import Conversation, Message


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = [
        "role", "content", "source",
        "input_tokens", "output_tokens", "search_credits", "estimated_cost_usd",
        "created_at",
    ]


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "order", "created_at"]
    inlines = [MessageInline]

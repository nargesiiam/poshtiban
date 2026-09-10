from django.contrib import admin

from .models import EventLog, ProcessedCommand


@admin.register(EventLog)
class EventLogAdmin(admin.ModelAdmin):
    list_display = ["created_at", "kind", "event_type", "correlation_id", "producer", "retry_count"]
    list_filter = ["kind", "event_type", "producer"]
    search_fields = ["correlation_id__exact", "event_id__exact"]
    readonly_fields = [f.name for f in EventLog._meta.fields]


@admin.register(ProcessedCommand)
class ProcessedCommandAdmin(admin.ModelAdmin):
    list_display = ["event_id", "processed_at"]

from django.contrib import admin

from .models import Order, Product, RefundRequest


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ["name", "sku", "price"]
    search_fields = ["name", "sku"]


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "product", "status", "amount", "created_at"]
    list_filter = ["status"]
    search_fields = ["user__username", "tracking_number"]


@admin.register(RefundRequest)
class RefundRequestAdmin(admin.ModelAdmin):
    list_display = ["id", "order", "status", "decided_by_agent", "created_at"]
    list_filter = ["status"]

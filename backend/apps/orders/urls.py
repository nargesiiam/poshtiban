from django.urls import path

from .views import OrderDetailView, OrderListView, RefundRequestListCreateView

urlpatterns = [
    path("", OrderListView.as_view(), name="order-list"),
    path("<int:pk>/", OrderDetailView.as_view(), name="order-detail"),
    path("refunds/", RefundRequestListCreateView.as_view(), name="refund-list-create"),
]

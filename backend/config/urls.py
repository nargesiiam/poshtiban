from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenRefreshView

from apps.accounts.views import LoginView, MeView, RegisterView

urlpatterns = [
    path("admin/", admin.site.urls),

    # --- احراز هویت ---
    path("api/auth/register/", RegisterView.as_view(), name="register"),
    path("api/auth/login/", LoginView.as_view(), name="login"),
    path("api/auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/auth/me/", MeView.as_view(), name="me"),

    # --- دامنه ---
    path("api/orders/", include("apps.orders.urls")),
    path("api/documents/", include("apps.documents.urls")),
    path("api/conversations/", include("apps.conversations.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


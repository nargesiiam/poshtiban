import os
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# نکته‌ی معماری: چرا اصلاً ASGI و نه WSGI ساده؟
# SSE یعنی یک اتصال HTTP باز می‌ماند و پیام‌ها به‌مرور روی همان اتصال جاری می‌شوند.
# یک worker همزمان WSGI (مثل gunicorn sync) در تمام آن مدت اشغال می‌ماند و
# نمی‌تواند درخواست دیگری را سرویس بدهد. ASGI (و سرور daphne) اجازه می‌دهد
# صدها اتصال SSE هم‌زمان باز بمانند بدون اینکه هر کدام یک worker کامل قفل کند.
# پیاده‌سازی کامل مسیر SSE در بخش ۶ به این فایل اضافه می‌شود (ProtocolTypeRouter).
django_asgi_app = get_asgi_application()

application = django_asgi_app

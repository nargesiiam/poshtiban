"""
پل بین RabbitMQ و SSE.

در دوره، عامل و نمای SSE از طریق یک صف درون‌حافظه‌ای در همان فرایند حرف
می‌زنند — چون همه‌چیز یک فرایند است. اینجا ai-worker یک فرایند کاملاً
جداست، پس رویدادها باید واقعاً از RabbitMQ عبور کنند تا به یک اتصال SSE
روی این فرایند (backend/ASGI) برسند.

معماری: یک consumer تنها (EventBroadcaster) که در کل عمر پردازش backend
یک‌بار به صف backend.events متصل می‌شود و هر envelope را بر اساس
conversation_id به صف‌های داخلی (asyncio.Queue) مربوط به اتصال‌های SSE
زنده پخش می‌کند. یک consumer مشترک، نه یکی به‌ازای هر کاربر — با صدها
کاربر هم‌زمان، صدها binding جدا به RabbitMQ نه لازم است و نه به‌صرفه.

هر اتصال SSE، subscribe/unsubscribe کوتاه‌عمر خودش را دارد (الزام صریح
سند): وقتی کلاینت قطع می‌شود، generator با GeneratorExit بسته می‌شود،
بلوک finally اجرا و صف مربوطه از broadcaster حذف می‌شود.
"""
import asyncio
import json

import aio_pika
from django.conf import settings
from django.contrib.auth.models import User
from django.http import HttpResponseForbidden, HttpResponseNotFound, StreamingHttpResponse
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken

from .models import Conversation

HEARTBEAT_SECONDS = 15


class EventBroadcaster:
    _instance = None
    _init_lock = asyncio.Lock()

    def __init__(self):
        self._subscribers: dict[int, set[asyncio.Queue]] = {}
        self._started = False

    @classmethod
    async def get_instance(cls) -> "EventBroadcaster":
        async with cls._init_lock:
            if cls._instance is None:
                cls._instance = cls()
            if not cls._instance._started:
                cls._instance._started = True
                asyncio.create_task(cls._instance._consume_forever())
            return cls._instance

    async def _consume_forever(self):
        while True:
            try:
                connection = await aio_pika.connect_robust(
                    host=settings.RABBITMQ_HOST,
                    login=settings.RABBITMQ_USER,
                    password=settings.RABBITMQ_PASSWORD,
                )
                async with connection:
                    channel = await connection.channel()
                    queue = await channel.declare_queue("backend.events", durable=True)
                    async with queue.iterator() as it:
                        async for message in it:
                            async with message.process():
                                await self._dispatch(json.loads(message.body))
            except Exception as exc:  # noqa: BLE001 — اتصال RabbitMQ قطع شد، دوباره وصل شو
                print(f"[sse-bridge] اتصال RabbitMQ قطع شد: {exc!r} — تلاش دوباره در ۲ ثانیه")
                await asyncio.sleep(2)

    async def _dispatch(self, envelope: dict):
        conversation_id = envelope.get("payload", {}).get("conversation_id")
        if conversation_id is None:
            return
        for q in list(self._subscribers.get(conversation_id, [])):
            await q.put(envelope)

    def subscribe(self, conversation_id: int) -> asyncio.Queue:
        q = asyncio.Queue()
        self._subscribers.setdefault(conversation_id, set()).add(q)
        return q

    def unsubscribe(self, conversation_id: int, q: asyncio.Queue):
        subs = self._subscribers.get(conversation_id)
        if subs:
            subs.discard(q)
            if not subs:
                self._subscribers.pop(conversation_id, None)


def _sse_line(event_type: str, payload: dict) -> str:
    data = json.dumps({"event_type": event_type, "payload": payload}, ensure_ascii=False)
    return f"data: {data}\n\n"


async def _event_stream(conversation_id: int):
    broadcaster = await EventBroadcaster.get_instance()
    queue = broadcaster.subscribe(conversation_id)
    try:
        yield _sse_line("connection.state", {"state": "connected"})
        while True:
            try:
                envelope = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_SECONDS)
                yield _sse_line(envelope["event_type"], envelope["payload"])
            except asyncio.TimeoutError:
                # ضربان قلب — به کلاینت می‌گوید سرور هنوز زنده است، حتی
                # وقتی چیزی برای گفتن ندارد. بدون این، کلاینت نمی‌تواند
                # «قطعی بی‌صدا» را از «سکوت طبیعی» تشخیص بدهد.
                yield _sse_line("heartbeat", {})
    finally:
        broadcaster.unsubscribe(conversation_id, queue)


async def stream_conversation(request, pk: int):
    """
    احراز هویت دستی (نه DRF permission_classes) چون این یک async view
    خام است، نه APIView — پشتیبانی async کامل DRF در نسخه‌ی فعلی هنوز
    یکدست نیست. توکن از هدر Authorization می‌آید، نه از query string —
    تا در لاگ‌های سرور و تاریخچه‌ی مرورگر باقی نماند.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return HttpResponseForbidden("Authorization header لازم است.")

    try:
        token = AccessToken(auth_header.removeprefix("Bearer "))
        user = await User.objects.aget(pk=token["user_id"])
    except (TokenError, User.DoesNotExist):
        return HttpResponseForbidden("توکن نامعتبر است.")

    owns_conversation = await Conversation.objects.filter(pk=pk, user=user).aexists()
    if not owns_conversation:
        return HttpResponseNotFound()

    response = StreamingHttpResponse(_event_stream(pk), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"  # جلوگیری از بافر شدن SSE پشت یک proxy مثل nginx
    return response

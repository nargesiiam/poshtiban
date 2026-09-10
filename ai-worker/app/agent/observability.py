"""
اتصال به Langfuse برای رصدپذیری (بخش ۷).

نکته‌ی مهم برای دفاع: trace_id در Langfuse را برابر همان correlation_id
می‌گذاریم که در بخش ۳ کل مسیر RabbitMQ (command → event ها) را دنبال
می‌کرد. یعنی یک شناسه، دو ابزار رصدپذیری مکمل:
  - EventLog در Postgres → مسیر سیستمی (کدام command، کدام event، کِی)
  - Langfuse                → مسیر مدل (کدام prompt، کدام ابزار، چند توکن)
هر دو با یک correlation_id قابل جست‌وجوی متقابل‌اند.

اگر کلیدهای Langfuse تنظیم نشده باشند (مثلاً محیط توسعه‌ی محلی بدون
حساب Langfuse)، این ماژول بی‌صدا غیرفعال می‌ماند — نبودِ ابزار رصدپذیری
نباید کل عامل را از کار بیندازد.
"""
from langfuse import Langfuse

from .. import config

_client = None
if config.LANGFUSE_PUBLIC_KEY and config.LANGFUSE_SECRET_KEY:
    _client = Langfuse(
        public_key=config.LANGFUSE_PUBLIC_KEY,
        secret_key=config.LANGFUSE_SECRET_KEY,
        host=config.LANGFUSE_HOST,
    )


def start_trace(*, correlation_id: str, conversation_id: int, user_id: int):
    if _client is None:
        return None
    return _client.trace(
        id=correlation_id,
        name="chat.message.process",
        user_id=str(user_id),
        metadata={"conversation_id": conversation_id},
    )


def flush():
    if _client is not None:
        _client.flush()

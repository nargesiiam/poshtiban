"""
هر handler یک command_type را می‌گیرد و کار واقعی را انجام می‌دهد.
امضا: handler(envelope, conn, cur, channel)
  - conn, cur: همان تراکنش idempotency (بخش ۳) — هر INSERT/UPDATE اینجا
    اتمیک با ثبت «پردازش شد» است.
  - channel: برای انتشار event های میانی (agent.tool.called و مشابه) به
    مصرف‌کنندگان دیگر (پل SSE در بخش ۶) بدون اینکه handler چیزی درباره‌ی
    SSE یا React بداند.
"""
from . import db
from .agent.graph import run_agent
from .messaging import publish_event
from .rag import ingest_document


def handle_chat_message_process(envelope: dict, conn, cur, channel):
    payload = envelope["payload"]
    conversation_id = payload["conversation_id"]
    correlation_id = envelope["correlation_id"]

    # تاریخچه‌ی مکالمه را از همان تراکنش می‌خوانیم — شامل همان پیام کاربری
    # که Django قبل از publish کردن command ذخیره کرده بود.
    cur.execute(
        "SELECT role, content FROM conversations_message WHERE conversation_id = %s ORDER BY created_at",
        (conversation_id,),
    )
    history = [
        {"role": "assistant" if role == "assistant" else "user", "content": content}
        for role, content in cur.fetchall()
    ]

    def on_event(event_type, data):
        publish_event(channel, event_type, {**data, "conversation_id": conversation_id}, correlation_id)

    final_reply, source, usage = run_agent(
        messages=history,
        user_id=payload["user_id"],
        order_id=payload.get("order_id"),
        correlation_id=correlation_id,
        conversation_id=conversation_id,
        on_event=on_event,
    )

    cur.execute(
        """
        INSERT INTO conversations_message
            (conversation_id, role, content, source, input_tokens, output_tokens,
             search_credits, estimated_cost_usd, created_at)
        VALUES (%s, 'assistant', %s, %s, %s, %s, %s, %s, now())
        """,
        (
            conversation_id,
            final_reply,
            source,
            usage["input_tokens"],
            usage["output_tokens"],
            usage["search_credits"],
            usage["estimated_cost_usd"],
        ),
    )

    publish_event(
        channel,
        "agent.reply.completed",
        {"conversation_id": conversation_id, "content": final_reply, "source": source, **usage},
        correlation_id,
    )


def handle_document_ingest(envelope: dict, conn, cur, channel):
    payload = envelope["payload"]
    correlation_id = envelope["correlation_id"]
    document_id = payload["document_id"]

    result = ingest_document(
        document_id=document_id,
        file_path=payload["file_path"],
        title=payload["title"],
        collection_name=payload.get("chroma_collection", "company_docs"),
        cur=cur,
    )

    publish_event(
        channel,
        "document.ingested",
        {"document_id": document_id, **result},
        correlation_id,
    )


HANDLERS = {
    "chat.message.process": handle_chat_message_process,
    "document.ingest": handle_document_ingest,
}


def mark_document_ingestion_failed(document_id: int):
    """
    وقتی command از نوع document.ingest بعد از تمام retry ها هنوز شکست
    می‌خورد و به DLQ می‌رود، تراکنش اصلی‌اش rollback شده (طبق طراحی
    atomic_command_processing) — یعنی هیچ UPDATE ای روی وضعیت سند ثبت
    نشده. بدون این تابع، سند برای همیشه روی «در انتظار پردازش» می‌ماند،
    در حالی که واقعیت این است که دیگر قرار نیست پردازش شود. این یک
    اتصال و تراکنشِ کوچک و جداگانه است، دقیقاً برای همین یک هدف.
    """
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE documents_document SET ingestion_status = 'failed' WHERE id = %s",
                (document_id,),
            )
        conn.commit()
    finally:
        conn.close()

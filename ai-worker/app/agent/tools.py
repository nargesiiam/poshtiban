"""
مرزبندی ابزارها — دقیقاً همان چیزی که سند می‌خواهد:

  «ورودی هر ابزار اعتبارسنجی شود، مدل نتواند پرس‌وجوی دلخواه بسازد.»

هر schema فقط فیلدهای محدود و تایپ‌دار می‌گیرد (order_id عدد، query رشته)
— هیچ ابزاری پارامتری مثل "sql" یا "filter" آزاد نمی‌گیرد که مدل بتواند
از طریق آن هر چیزی از دیتابیس بخواند. حتی وقتی order_id از مدل می‌آید،
executor همیشه با `AND user_id = %s` (از ctx، نه از مدل) فیلتر می‌کند —
یعنی حتی اگر مدل عمداً یا اشتباهاً order_id کاربر دیگری را حدس بزند،
چیزی برنمی‌گردد. این همان الگوی for_user() بخش ۲ است، فقط این‌بار در
دنیای ابزارهای عامل.
"""
import chromadb
import requests

from .. import config
from ..db import get_connection


# ----------------------------------------------------------------------
# ابزار ۱ — داده‌ی ساخت‌یافته: وضعیت سفارش
# ----------------------------------------------------------------------
def get_order_status(input_data: dict, ctx: dict) -> dict:
    order_id = input_data.get("order_id")
    if not isinstance(order_id, int):
        raise ValueError("order_id باید یک عدد صحیح باشد.")

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT o.status, o.tracking_number, o.carrier, o.amount, p.name
                FROM orders_order o
                JOIN orders_product p ON p.id = o.product_id
                WHERE o.id = %s AND o.user_id = %s
                """,
                (order_id, ctx["user_id"]),
            )
            row = cur.fetchone()
    finally:
        conn.close()

    if row is None:
        return {"error": "سفارشی با این شماره برای این کاربر پیدا نشد."}

    status, tracking_number, carrier, amount, product_name = row
    return {
        "order_id": order_id,
        "product": product_name,
        "status": status,
        "tracking_number": tracking_number or None,
        "carrier": carrier or None,
        "amount": str(amount),
    }


# ----------------------------------------------------------------------
# ابزار ۲ — داده‌ی ساخت‌یافته: سابقه‌ی بازگشت وجه
# ----------------------------------------------------------------------
def get_refund_history(input_data: dict, ctx: dict) -> dict:
    order_id = input_data.get("order_id")
    if order_id is not None and not isinstance(order_id, int):
        raise ValueError("order_id باید عدد صحیح یا خالی باشد.")

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if order_id:
                cur.execute(
                    """
                    SELECT r.order_id, r.status, r.reason, r.created_at
                    FROM orders_refundrequest r
                    JOIN orders_order o ON o.id = r.order_id
                    WHERE o.user_id = %s AND r.order_id = %s
                    ORDER BY r.created_at DESC
                    """,
                    (ctx["user_id"], order_id),
                )
            else:
                cur.execute(
                    """
                    SELECT r.order_id, r.status, r.reason, r.created_at
                    FROM orders_refundrequest r
                    JOIN orders_order o ON o.id = r.order_id
                    WHERE o.user_id = %s
                    ORDER BY r.created_at DESC
                    LIMIT 10
                    """,
                    (ctx["user_id"],),
                )
            rows = cur.fetchall()
    finally:
        conn.close()

    return {
        "refunds": [
            {"order_id": r[0], "status": r[1], "reason": r[2], "created_at": r[3].isoformat()}
            for r in rows
        ]
    }


# ----------------------------------------------------------------------
# ابزار ۳ — داده‌ی غیرساخت‌یافته‌ی داخلی: RAG روی اسناد شرکت
# پایپ‌لاین embedding کامل در بخش ۵ ساخته می‌شود؛ این ابزار همان لحظه که
# آن پایپ‌لاین چیزی در ChromaDB ذخیره کند، بدون تغییر کار می‌کند —
# رابط ابزار (بخش ۴) و پایپ‌لاین پرکردنش (بخش ۵) عمداً مستقل‌اند.
# ----------------------------------------------------------------------
def search_company_documents(input_data: dict, ctx: dict) -> dict:
    query = input_data.get("query")
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query نمی‌تواند خالی باشد.")

    client = chromadb.HttpClient(host=config.CHROMADB_HOST, port=8000)
    collection = client.get_or_create_collection("company_docs")
    result = collection.query(query_texts=[query.strip()], n_results=3)

    documents = result.get("documents", [[]])[0]
    metadatas = result.get("metadatas", [[]])[0]

    if not documents:
        return {"results": [], "note": "هیچ سند مرتبطی پیدا نشد."}

    return {
        "results": [
            {
                "text": doc,
                # پیشوند "internal:" عمداً — الزام سند که ارجاع داخلی نباید
                # شبیه ارجاع وب به‌نظر برسد
                "source": f"internal:{meta.get('title', 'unknown')}",
            }
            for doc, meta in zip(documents, metadatas)
        ]
    }


# ----------------------------------------------------------------------
# ابزار ۴ — داده‌ی بیرونی: جست‌وجوی وب عمومی
# ----------------------------------------------------------------------
def search_web(input_data: dict, ctx: dict) -> dict:
    query = input_data.get("query")
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query نمی‌تواند خالی باشد.")

    response = requests.post(
        "https://google.serper.dev/search",
        headers={"X-API-KEY": config.SERPER_API_KEY, "Content-Type": "application/json"},
        json={"q": query.strip(), "num": 3},
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()

    return {
        "results": [
            {
                "text": item.get("snippet", ""),
                # پیشوند "web:" — تا در UI هرگز با ارجاع داخلی قاطی نشود
                "source": f"web:{item.get('link', '')}",
            }
            for item in data.get("organic", [])[:3]
        ]
    }


# ----------------------------------------------------------------------
# ابزار ۵ — اقدام (نه فقط خواندن): ثبت درخواست بازگشت وجه
# ----------------------------------------------------------------------
def create_refund_request(input_data: dict, ctx: dict) -> dict:
    order_id = input_data.get("order_id")
    reason = input_data.get("reason")

    if not isinstance(order_id, int):
        raise ValueError("order_id باید عدد صحیح باشد.")
    if not isinstance(reason, str) or len(reason.strip()) < 5:
        raise ValueError("reason باید حداقل ۵ نویسه توضیح معتبر باشد.")

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # دقیقاً همان الگوی for_user: حتی برای نوشتن هم مالکیت چک می‌شود
            cur.execute(
                "SELECT id FROM orders_order WHERE id = %s AND user_id = %s",
                (order_id, ctx["user_id"]),
            )
            if cur.fetchone() is None:
                raise ValueError("این سفارش پیدا نشد یا متعلق به شما نیست.")

            cur.execute(
                """
                INSERT INTO orders_refundrequest (order_id, reason, status, decided_by_agent, created_at)
                VALUES (%s, %s, 'pending', 'maya', now())
                RETURNING id
                """,
                (order_id, reason.strip()),
            )
            refund_id = cur.fetchone()[0]
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return {"refund_request_id": refund_id, "status": "pending"}


TOOL_EXECUTORS = {
    "get_order_status": get_order_status,
    "get_refund_history": get_refund_history,
    "search_company_documents": search_company_documents,
    "search_web": search_web,
    "create_refund_request": create_refund_request,
}

# برای برچسب‌زدن به منبع پاسخ در UI (الزام بخش ۵ — ارجاع داخلی با ارجاع وب یکسان به‌نظر نرسد)
TOOL_SOURCE_MAP = {
    "get_order_status": "db",
    "get_refund_history": "db",
    "search_company_documents": "rag",
    "search_web": "web",
    "create_refund_request": "action",
}

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_order_status",
            "description": (
                "وضعیت سفارش، شماره‌ی پیگیری، شرکت حمل‌ونقل و مبلغ را از پایگاه‌داده‌ی "
                "داخلی برمی‌گرداند. همیشه برای سؤال درباره‌ی «سفارش من کجاست» یا "
                "«وضعیت سفارش» از این ابزار استفاده کن، نه از حافظه یا جست‌وجوی وب."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "integer", "description": "شناسه‌ی عددی سفارش."},
                },
                "required": ["order_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_refund_history",
            "description": "سابقه‌ی درخواست‌های بازگشت وجه کاربر را برمی‌گرداند (برای یک سفارش خاص یا کل سابقه).",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "integer", "description": "اختیاری — اگر خالی باشد، کل سابقه برمی‌گردد."},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_company_documents",
            "description": (
                "در اسناد داخلی شرکت (سیاست بازگشت کالا، گارانتی، رویه‌های رسمی) جست‌وجوی "
                "معنایی می‌کند. برای هر سؤال درباره‌ی سیاست یا قوانین شرکت از این ابزار "
                "استفاده کن، نه از حافظه‌ی خودت."
            ),
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "سؤال یا موضوع برای جست‌وجو."}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": (
                "در وب عمومی جست‌وجو می‌کند. فقط برای سؤالاتی که کاملاً بیرون از شرکت‌اند "
                "(اخبار، آب‌وهوا، اعتصاب حمل‌ونقل). هرگز برای چیزی که در پایگاه‌داده یا "
                "اسناد داخلی است از این ابزار استفاده نکن."
            ),
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "عبارت جست‌وجو."}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_refund_request",
            "description": (
                "یک درخواست بازگشت وجه رسمی برای سفارش کاربر ثبت می‌کند. فقط وقتی کاربر "
                "صراحتاً و آگاهانه درخواست بازگشت وجه کرده استفاده کن، نه به‌صورت حدسی."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "integer", "description": "شناسه‌ی سفارشی که باید مسترد شود."},
                    "reason": {"type": "string", "description": "دلیل درخواست، به‌نقل از کاربر."},
                },
                "required": ["order_id", "reason"],
            },
        },
    },
]

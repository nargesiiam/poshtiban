"""
پایپ‌لاین ingestion اسناد — از فایل آپلودشده تا chunk های embed شده در
ChromaDB. ابزار بازیابی (search_company_documents در بخش ۴) از این
پایپ‌لاین کاملاً بی‌خبر است؛ فقط می‌داند یک collection در ChromaDB هست که
باید در آن جست‌وجو کند. این فایل همان collection را پر می‌کند.

تصمیم مهم: این تابع عمداً خطاها را قورت نمی‌دهد و خودش try/except برای
«failed» نمی‌سازد. اگر استخراج متن یا embedding شکست بخورد، exception
raise می‌شود و به بیرون (consumer.py) می‌رود — یعنی از همان مکانیزم
اطمینانِ بخش ۳ (retry نمایی، idempotency، DLQ) دوباره استفاده می‌شود، به‌جای
ساختن یک سیستم موازیِ جدا برای «خطاهای ingestion». یک مکانیزم اطمینان،
برای هر دو نوع command.
"""
import os

import chromadb
from pypdf import PdfReader

from . import config


def extract_text(file_path: str) -> str:
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        reader = PdfReader(file_path)
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 100) -> list[str]:
    """
    chunk بر اساس کاراکتر با هم‌پوشانی — برای اسناد کوتاه سیاست‌گذاری
    (سیاست بازگشت کالا و مشابه) ساده و کافی است. برای اسناد بزرگ‌تر و
    ساخت‌یافته‌تر (جدول، heading تودرتو)، chunk بر اساس ساختار سند نتیجه‌ی
    بهتری می‌دهد — نقطه‌ی توسعه‌ی شناخته‌شده، نه نیاز فعلی این پروژه.
    """
    text = text.strip()
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        start = end - overlap
    return chunks


def ingest_document(*, document_id: int, file_path: str, title: str, collection_name: str, cur) -> dict:
    text = extract_text(file_path)
    chunks = chunk_text(text)
    if not chunks:
        raise ValueError("سند خالی است یا متن قابل‌استخراجی ندارد.")

    client = chromadb.HttpClient(host=config.CHROMADB_HOST, port=8000)
    collection = client.get_or_create_collection(collection_name)

    # id قطعی و قابل‌پیش‌بینی (doc{id}-chunk{i}) — اگر همین سند دوباره
    # ingest شود (مثلاً به‌خاطر retry)، chunk های قبلی overwrite می‌شوند
    # نه duplicate — idempotency در سطح ChromaDB هم رعایت شده.
    collection.add(
        documents=chunks,
        metadatas=[
            {"title": title, "document_id": document_id, "chunk_index": i}
            for i in range(len(chunks))
        ],
        ids=[f"doc{document_id}-chunk{i}" for i in range(len(chunks))],
    )

    cur.execute(
        "UPDATE documents_document SET ingestion_status = 'ready' WHERE id = %s",
        (document_id,),
    )
    return {"chunk_count": len(chunks)}

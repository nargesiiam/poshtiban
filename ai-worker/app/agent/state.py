from typing import Any, List, Optional, TypedDict


class AgentState(TypedDict):
    messages: List[dict]           # تاریخچه‌ی مکالمه به فرمت پیام‌های Anthropic
    user_id: int                   # از payload تأییدشده‌ی backend می‌آید، نه از ورودی مدل
    order_id: Optional[int]
    correlation_id: str
    conversation_id: int
    step_count: int                # سقف گام‌ها — بخش «مرزبندی ابزارها»ی سند
    final_reply: Optional[str]
    reply_source: Optional[str]    # db / rag / web / action / step_limit / none
    pending_tool_calls: List[Any]  # بین گره‌ی agent و گره‌ی tools رد و بدل می‌شود
    total_input_tokens: int        # جمع توکن‌های ورودی روی همه‌ی گام‌های این اجرا — بخش ۷
    total_output_tokens: int
    search_credits: int            # هر بار search_web موفق صدا زده شود، +۱

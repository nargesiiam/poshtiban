"""
سند صریح می‌گوید: «API رایگان است، اما "رایگان بود" پاسخ این پرسش نیست:
tokenها را واقعی بشمارید، اعتبارهای جست‌وجوی وب را اضافه کنید.»

این فایل دقیقاً همان کار را می‌کند. اعداد قیمت زیر تقریبی‌اند و باید با
نرخ واقعیِ حساب‌های خودتان (سرویس‌دهنده‌ی LLM انتخابی و serper.dev/pricing)
به‌روزرسانی شوند — هدف اثبات مکانیزم شمارش واقعی
است، نه قفل کردن یک عدد ثابت که فردا با تغییر تعرفه غلط از آب درمی‌آید.
"""

PRICE_PER_MILLION_INPUT_TOKENS_USD = 3.0
PRICE_PER_MILLION_OUTPUT_TOKENS_USD = 15.0
SEARCH_CREDIT_COST_USD = 0.0003  # هر جست‌وجوی Serper.dev، طبق تعرفه‌ی پلن پایه (~$0.30 به‌ازای هزار)


def estimate_cost_usd(*, input_tokens: int, output_tokens: int, search_credits: int) -> float:
    llm_cost = (
        input_tokens / 1_000_000 * PRICE_PER_MILLION_INPUT_TOKENS_USD
        + output_tokens / 1_000_000 * PRICE_PER_MILLION_OUTPUT_TOKENS_USD
    )
    search_cost = search_credits * SEARCH_CREDIT_COST_USD
    return round(llm_cost + search_cost, 6)

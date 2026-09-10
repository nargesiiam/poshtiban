from decouple import config

POSTGRES_HOST = config("POSTGRES_HOST", default="postgres")
POSTGRES_DB = config("POSTGRES_DB", default="relay")
POSTGRES_USER = config("POSTGRES_USER", default="relay")
POSTGRES_PASSWORD = config("POSTGRES_PASSWORD", default="relay")

RABBITMQ_HOST = config("RABBITMQ_HOST", default="rabbitmq")
RABBITMQ_USER = config("RABBITMQ_USER", default="relay")
RABBITMQ_PASSWORD = config("RABBITMQ_PASSWORD", default="relay")

CHROMADB_HOST = config("CHROMADB_HOST", default="chromadb")

# --- مدل زبانی — provider-agnostic از طریق فرمت OpenAI-compatible ---
# کار می‌کند با DeepSeek، Qwen (DashScope)، یا هر سرویس‌دهنده‌ی دیگری که
# همین فرمت را پیاده کند. فقط این سه مقدار عوض می‌شوند، هیچ کد دیگری نه.
LLM_API_KEY = config("LLM_API_KEY", default="")
LLM_BASE_URL = config("LLM_BASE_URL", default="https://api.deepseek.com")
LLM_MODEL = config("LLM_MODEL", default="deepseek-chat")

SERPER_API_KEY = config("SERPER_API_KEY", default="")

LANGFUSE_PUBLIC_KEY = config("LANGFUSE_PUBLIC_KEY", default="")
LANGFUSE_SECRET_KEY = config("LANGFUSE_SECRET_KEY", default="")
LANGFUSE_HOST = config("LANGFUSE_HOST", default="https://cloud.langfuse.com")

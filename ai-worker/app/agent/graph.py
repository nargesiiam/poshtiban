"""
یک عامل خوش‌ساخت، نه چند عامل نمایشی — دقیقاً همان چیزی که سند می‌خواهد
(«عمق نمره دارد، تعداد عامل نه»). یک گراف کوچک با دو گره:

  agent  → مدل را با تاریخچه‌ی مکالمه و ۵ ابزار صدا می‌زند؛ یا متن نهایی
           تولید می‌کند (پایان) یا درخواست فراخوانی ابزار می‌دهد.
  tools  → درخواست‌های ابزار را واقعاً اجرا می‌کند (با اعتبارسنجی و
           فیلتر کاربر در tools.py) و نتیجه را به‌عنوان پیام بعدی برمی‌گرداند.

  agent → tools → agent → ... تا وقتی مدل دیگر ابزاری نخواهد، یا سقف
  گام‌ها برسد.

نکته‌ی مهم درباره‌ی provider: این فایل از فرمت OpenAI-compatible استفاده
می‌کند (function calling با tool_calls، نه Anthropic tool_use). به همین
دلیل با هر سرویس‌دهنده‌ای که همین فرمت را پیاده کند کار می‌کند — فقط با
عوض کردن LLM_BASE_URL/LLM_MODEL در تنظیمات، بدون تغییر این فایل.
"""
import json
from types import SimpleNamespace

from langgraph.graph import END, StateGraph
from openai import OpenAI

from .. import config
from .observability import flush as flush_trace
from .observability import start_trace
from .pricing import estimate_cost_usd
from .prompts import SYSTEM_PROMPT
from .state import AgentState
from .tools import TOOL_EXECUTORS, TOOL_SCHEMAS, TOOL_SOURCE_MAP

# سقف گام‌ها — بدون این، یک حلقه‌ی نادر (مثلاً مدل مدام همان ابزار را با
# ورودی کمی متفاوت صدا بزند) می‌تواند در یک درخواست، اعتبار API را بسوزاند.
MAX_STEPS = 8

# رویدادهای تدریجی را بافر می‌کنیم — الزام صریح سند: «به‌ازای هر token یک
# پیام روی صف نفرستید». هر ۴۰ کاراکتر (یا در انتهای پاسخ) یک event
# agent.reply.delta منتشر می‌شود، نه هر توکن.
DELTA_BUFFER_CHARS = 40

_client = OpenAI(api_key=config.LLM_API_KEY, base_url=config.LLM_BASE_URL)


def _agent_node_factory(on_event, trace):
    def _agent_node(state: AgentState) -> AgentState:
        if state["step_count"] >= MAX_STEPS:
            state["final_reply"] = (
                "متأسفم، این درخواست پیچیده‌تر از چیزی بود که بتوانم در زمان "
                "معقول پاسخ بدهم. لطفاً با پشتیبانی انسانی تماس بگیرید."
            )
            state["reply_source"] = "step_limit"
            state["pending_tool_calls"] = []
            return state

        messages_with_system = [{"role": "system", "content": SYSTEM_PROMPT}, *state["messages"]]

        full_text = ""
        delta_buffer = ""
        tool_call_chunks: dict[int, dict] = {}
        finish_reason = None
        usage = None

        stream = _client.chat.completions.create(
            model=config.LLM_MODEL,
            messages=messages_with_system,
            tools=TOOL_SCHEMAS,
            stream=True,
            stream_options={"include_usage": True},
        )

        for chunk in stream:
            if getattr(chunk, "usage", None):
                usage = chunk.usage
            if not chunk.choices:
                continue
            choice = chunk.choices[0]
            if choice.finish_reason:
                finish_reason = choice.finish_reason
            delta = choice.delta

            if delta.content:
                full_text += delta.content
                delta_buffer += delta.content
                if len(delta_buffer) >= DELTA_BUFFER_CHARS and on_event:
                    on_event("agent.reply.delta", {"chunk": delta_buffer})
                    delta_buffer = ""

            if delta.tool_calls:
                for tc in delta.tool_calls:
                    entry = tool_call_chunks.setdefault(tc.index, {"id": None, "name": "", "arguments": ""})
                    if tc.id:
                        entry["id"] = tc.id
                    if tc.function and tc.function.name:
                        entry["name"] += tc.function.name
                    if tc.function and tc.function.arguments:
                        entry["arguments"] += tc.function.arguments

        if delta_buffer and on_event:
            on_event("agent.reply.delta", {"chunk": delta_buffer})

        # شمارش واقعی توکن — برخی سرویس‌دهنده‌های OpenAI-compatible ممکن
        # است usage را در استریم برنگردانند؛ در آن صورت این گام صفر حساب
        # می‌شود (کم‌شماری، نه crash) — نکته‌ای که در بخش ۷ باید بدانی.
        if usage:
            state["total_input_tokens"] += usage.prompt_tokens
            state["total_output_tokens"] += usage.completion_tokens

        state["step_count"] += 1

        if finish_reason == "tool_calls" and tool_call_chunks:
            ordered = [tool_call_chunks[i] for i in sorted(tool_call_chunks)]
            state["messages"].append(
                {
                    "role": "assistant",
                    "content": full_text or None,
                    "tool_calls": [
                        {
                            "id": tc["id"],
                            "type": "function",
                            "function": {"name": tc["name"], "arguments": tc["arguments"]},
                        }
                        for tc in ordered
                    ],
                }
            )
            state["pending_tool_calls"] = [
                SimpleNamespace(id=tc["id"], name=tc["name"], input=json.loads(tc["arguments"] or "{}"))
                for tc in ordered
            ]
            output_summary = "[tool_calls requested]"
        else:
            text = full_text.strip()
            state["final_reply"] = text or "متوجه نشدم، می‌شود دوباره توضیح بدهید؟"
            state["messages"].append({"role": "assistant", "content": state["final_reply"]})
            state["pending_tool_calls"] = []
            output_summary = state["final_reply"]

        if trace:
            trace.generation(
                name=f"agent-step-{state['step_count']}",
                model=config.LLM_MODEL,
                input=state["messages"][:-1],
                output=output_summary,
                usage={
                    "input": usage.prompt_tokens if usage else 0,
                    "output": usage.completion_tokens if usage else 0,
                    "unit": "TOKENS",
                },
            )

        return state

    return _agent_node


def _make_tools_node(on_event, trace):
    def _tools_node(state: AgentState) -> AgentState:
        ctx = {"user_id": state["user_id"], "order_id": state["order_id"]}

        for call in state["pending_tool_calls"]:
            if on_event:
                on_event("agent.tool.called", {"tool": call.name, "input": call.input})

            executor = TOOL_EXECUTORS.get(call.name)
            try:
                if executor is None:
                    raise ValueError(f"ابزار ناشناخته: {call.name}")
                result = executor(call.input, ctx)
                if "error" not in result:
                    state["reply_source"] = TOOL_SOURCE_MAP.get(call.name, state.get("reply_source"))
                    if call.name == "search_web":
                        state["search_credits"] += 1
            except Exception as exc:  # ورودی نامعتبر یا خطای اجرا — به مدل برمی‌گردد، نه crash کل worker
                result = {"error": str(exc)}

            if on_event:
                on_event("agent.tool.completed", {"tool": call.name, "result": result})

            if trace:
                trace.span(name=f"tool:{call.name}", input=call.input, output=result)

            # فرمت OpenAI-compatible: هر نتیجه‌ی ابزار پیام مستقل با نقش
            # "tool" است، نه یک بلوک داخل پیام کاربر (که فرمت Anthropic بود).
            state["messages"].append(
                {"role": "tool", "tool_call_id": call.id, "content": _to_text(result)}
            )

        return state

    return _tools_node


def _to_text(result: dict) -> str:
    return json.dumps(result, ensure_ascii=False)


def _should_continue(state: AgentState) -> str:
    return END if state.get("final_reply") else "tools"


def build_graph(on_event, trace):
    graph = StateGraph(AgentState)
    graph.add_node("agent", _agent_node_factory(on_event, trace))
    graph.add_node("tools", _make_tools_node(on_event, trace))
    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", _should_continue, {END: END, "tools": "tools"})
    graph.add_edge("tools", "agent")
    return graph.compile()


def run_agent(*, messages, user_id, order_id, correlation_id, conversation_id, on_event=None):
    trace = start_trace(correlation_id=correlation_id, conversation_id=conversation_id, user_id=user_id)
    app = build_graph(on_event, trace)

    initial_state: AgentState = {
        "messages": messages,
        "user_id": user_id,
        "order_id": order_id,
        "correlation_id": correlation_id,
        "conversation_id": conversation_id,
        "step_count": 0,
        "final_reply": None,
        "reply_source": None,
        "pending_tool_calls": [],
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "search_credits": 0,
    }
    final_state = app.invoke(initial_state)

    usage = {
        "input_tokens": final_state["total_input_tokens"],
        "output_tokens": final_state["total_output_tokens"],
        "search_credits": final_state["search_credits"],
        "estimated_cost_usd": estimate_cost_usd(
            input_tokens=final_state["total_input_tokens"],
            output_tokens=final_state["total_output_tokens"],
            search_credits=final_state["search_credits"],
        ),
    }

    if trace:
        trace.update(output=final_state.get("final_reply"))
        flush_trace()

    return final_state["final_reply"], final_state.get("reply_source") or "none", usage

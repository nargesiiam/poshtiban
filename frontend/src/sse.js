import { getTokens, API_BASE } from "./api.js";

/**
 * کلاینت SSE سفارشی به‌جای EventSource بومی مرورگر.
 *
 * چرا؟ EventSource اجازه‌ی هدر Authorization سفارشی نمی‌دهد — تنها راهش
 * قرار دادن توکن در query string است، یعنی توکن در لاگ‌های سرور و
 * تاریخچه‌ی مرورگر می‌ماند. اینجا با fetch + ReadableStream همان الگوی
 * SSE را پیاده می‌کنیم اما با هدر امن، و کنترل کامل روی وضعیت اتصال داریم.
 *
 * وضعیت‌ها همیشه از یک اتفاق واقعی می‌آیند، نه فرض:
 *   connecting     → اولین تلاش برای اتصال
 *   connected      → سرور رویداد connection.state دریافت شد
 *   reconnecting   → استریم قطع شد، در حال تلاش دوباره با تأخیر نمایی
 *   failed         → بعد از ۶ تلاش ناموفق، دیگر خودکار تلاش نمی‌کند
 *   disconnected   → کاربر/کامپوننت صراحتاً بست
 */
export function connectConversationStream(conversationId, { onEvent, onStateChange }) {
  let stopped = false;
  let attempt = 0;

  const setState = (state) => onStateChange && onStateChange(state);

  async function run() {
    while (!stopped) {
      setState(attempt === 0 ? "connecting" : "reconnecting");
      try {
        const { access } = getTokens();
        const res = await fetch(`${API_BASE}/api/conversations/${conversationId}/stream/`, {
          headers: { Authorization: `Bearer ${access}` },
        });
        if (!res.ok || !res.body) throw new Error(`stream failed: ${res.status}`);

        attempt = 0;
        setState("connected");

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (!stopped) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          let sepIndex;
          while ((sepIndex = buffer.indexOf("\n\n")) !== -1) {
            const rawEvent = buffer.slice(0, sepIndex);
            buffer = buffer.slice(sepIndex + 2);
            const line = rawEvent.split("\n").find((l) => l.startsWith("data: "));
            if (!line) continue;
            const parsed = JSON.parse(line.slice(6));
            if (parsed.event_type === "heartbeat") continue;
            if (parsed.event_type === "connection.state") continue; // خودمان از res.ok مدیریتش می‌کنیم
            onEvent && onEvent(parsed);
          }
        }

        if (!stopped) throw new Error("stream ended unexpectedly");
      } catch (err) {
        if (stopped) return;
        attempt += 1;
        if (attempt > 6) {
          setState("failed");
          return; // تلاش خودکار متوقف می‌شود — کاربر باید صفحه را رفرش یا دوباره وارد شود
        }
        const delay = Math.min(1000 * 2 ** attempt, 15000);
        await new Promise((r) => setTimeout(r, delay));
      }
    }
  }

  run();

  return function disconnect() {
    stopped = true;
    setState("disconnected");
  };
}

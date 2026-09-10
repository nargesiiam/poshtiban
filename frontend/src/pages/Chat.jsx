import { useEffect, useRef, useState } from "react";
import {
  createConversation,
  deleteConversation,
  getConversation,
  listConversations,
  sendMessage,
} from "../api.js";
import { connectConversationStream } from "../sse.js";

const STATE_LABELS = {
  connecting: { text: "در حال اتصال...", cls: "state-connecting" },
  connected: { text: "متصل", cls: "state-connected" },
  reconnecting: { text: "در حال اتصال مجدد...", cls: "state-reconnecting" },
  failed: { text: "اتصال ناموفق — صفحه را رفرش کنید", cls: "state-failed" },
  disconnected: { text: "قطع شده", cls: "state-disconnected" },
};

export default function Chat() {
  const [conversations, setConversations] = useState([]);
  const [conversationId, setConversationId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState("");
  const [connectionState, setConnectionState] = useState("connecting");
  const [liveActivity, setLiveActivity] = useState([]); // پنل فعالیت زنده — فراخوانی ابزارها
  const [streamingReply, setStreamingReply] = useState(""); // متن در حال تایپ، هنوز رکورد رسمی نیست
  const disconnectRef = useRef(null);

  // --- فهرست نوار کناری — سبک، فقط برای نمایش، نه منبع رسمی پیام‌ها ---
  async function refreshConversationList() {
    const list = await listConversations();
    setConversations(list);
    return list;
  }

  // --- انتخاب/ساخت اولین مکالمه هنگام باز شدن صفحه ---
  useEffect(() => {
    (async () => {
      const list = await refreshConversationList();
      if (list.length > 0) {
        setConversationId(list[0].id);
      } else {
        const conv = await createConversation();
        setConversationId(conv.id);
        await refreshConversationList();
      }
    })();
  }, []);

  // --- بارگذاری پیام‌ها از REST — همیشه منبع حقیقت است، نه استریم ---
  async function refreshMessages(id) {
    const conv = await getConversation(id);
    setMessages(conv.messages);
  }

  useEffect(() => {
    if (!conversationId) return;
    setStreamingReply("");
    setLiveActivity([]);
    refreshMessages(conversationId);
  }, [conversationId]);

  // --- اتصال SSE ---
  useEffect(() => {
    if (!conversationId) return;

    let justReconnected = false;

    const disconnect = connectConversationStream(conversationId, {
      onStateChange: (state) => {
        setConnectionState((prev) => {
          // اگر از reconnecting به connected رسیدیم، ممکن است رویدادهایی
          // را در فاصله‌ی قطعی از دست داده باشیم — به‌جای تلاش برای ادامه‌ی
          // یک استریم نیمه‌کاره، دوباره از REST همگام می‌شویم. این همان
          // تصمیم طراحی است: منبع حقیقت Postgres است، نه بایت‌های استریم.
          if (prev === "reconnecting" && state === "connected") {
            justReconnected = true;
          }
          return state;
        });
        if (justReconnected && state === "connected") {
          justReconnected = false;
          refreshMessages(conversationId);
        }
      },
      onEvent: (envelope) => {
        const { event_type, payload } = envelope;

        if (event_type === "agent.tool.called") {
          setLiveActivity((prev) => [...prev, { type: "called", tool: payload.tool, ts: Date.now() }]);
        } else if (event_type === "agent.tool.completed") {
          setLiveActivity((prev) => [...prev, { type: "completed", tool: payload.tool, ts: Date.now() }]);
        } else if (event_type === "agent.reply.delta") {
          setStreamingReply((prev) => prev + payload.chunk);
        } else if (event_type === "agent.reply.completed") {
          // پاسخ نهایی و رسمی — همیشه از REST دوباره می‌خوانیم، نه از
          // متنی که خودمان از delta ها سرهم کرده بودیم. اگر جریان وسط
          // تولید قطع شده باشد، همین‌جا کاربر جواب کامل و درست را می‌بیند،
          // نه یک جمله‌ی نصفه.
          setStreamingReply("");
          setLiveActivity([]);
          refreshMessages(conversationId);
          refreshConversationList(); // پیش‌نمایش نوار کناری هم به‌روز شود
        }
      },
    });

    disconnectRef.current = disconnect;
    return () => disconnect();
  }, [conversationId]);

  async function handleSend(e) {
    e.preventDefault();
    if (!draft.trim() || !conversationId) return;
    const content = draft.trim();
    setDraft("");
    await sendMessage(conversationId, content);
    await refreshMessages(conversationId); // پیام کاربر بلافاصله در UI دیده شود
    await refreshConversationList();
  }

  async function handleNewConversation() {
    const conv = await createConversation();
    await refreshConversationList();
    setConversationId(conv.id);
  }

  async function handleDeleteConversation(id, e) {
    e.stopPropagation(); // کلیک روی دکمه‌ی حذف نباید مکالمه را هم انتخاب کند
    if (!window.confirm("این گفت‌وگو برای همیشه حذف شود؟")) return;

    await deleteConversation(id);
    const list = await refreshConversationList();

    if (id === conversationId) {
      // مکالمه‌ی فعال حذف شد — برو سراغ اولین مکالمه‌ی باقی‌مانده،
      // یا اگر هیچ‌کدام نمانده بود یک مکالمه‌ی تازه بساز
      if (list.length > 0) {
        setConversationId(list[0].id);
      } else {
        const conv = await createConversation();
        await refreshConversationList();
        setConversationId(conv.id);
      }
    }
  }

  const stateInfo = STATE_LABELS[connectionState] || STATE_LABELS.disconnected;

  return (
    <div className="chat-shell">
      <aside className="conversation-sidebar">
        <button className="new-chat-btn" onClick={handleNewConversation}>
          + گفت‌وگوی جدید
        </button>

        <div className="conversation-list">
          {conversations.length === 0 && (
            <div className="sidebar-empty">هنوز گفت‌وگویی نداری</div>
          )}
          {conversations.map((c) => (
            <div
              key={c.id}
              className={`conversation-item ${c.id === conversationId ? "active" : ""}`}
              onClick={() => setConversationId(c.id)}
            >
              <div className="conversation-item-body">
                <div className="conversation-item-preview">
                  {c.preview ? c.preview : <span className="conversation-item-empty">گفت‌وگوی تازه</span>}
                </div>
                <div className="conversation-item-meta">{c.message_count} پیام</div>
              </div>
              <button
                className="conversation-delete-btn"
                onClick={(e) => handleDeleteConversation(c.id, e)}
                title="حذف گفت‌وگو"
              >
                ×
              </button>
            </div>
          ))}
        </div>
      </aside>

      <div className="chat-page">
        <div className="chat-header">
          <h2>گفت‌وگو با مایا</h2>
          <span className={`state-badge ${stateInfo.cls}`}>{stateInfo.text}</span>
        </div>

        <div className="chat-messages">
          {messages.map((m) => (
            <div key={m.id} className={`bubble bubble-${m.role}`}>
              <div className="bubble-content">{m.content}</div>
              <div className="bubble-meta">
                {m.source && m.source !== "none" && <span>منبع: {m.source}</span>}
                {Number(m.estimated_cost_usd) > 0 && (
                  <span> · هزینه: ${Number(m.estimated_cost_usd).toFixed(6)}</span>
                )}
              </div>
            </div>
          ))}

          {streamingReply && (
            <div className="bubble bubble-assistant bubble-streaming">
              <div className="bubble-content">{streamingReply}</div>
            </div>
          )}

          {liveActivity.length > 0 && (
            <div className="activity-panel">
              {liveActivity.map((a, i) => (
                <div key={i} className="activity-line">
                  {a.type === "called" ? `⏳ در حال استفاده از ابزار: ${a.tool}` : `✓ ${a.tool} تمام شد`}
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="cost-footer">
          هزینه‌ی تخمینی این گفت‌وگو: $
          {messages.reduce((sum, m) => sum + Number(m.estimated_cost_usd || 0), 0).toFixed(6)}
        </div>

        <form className="chat-input" onSubmit={handleSend}>
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="سؤال خود را بنویسید..."
          />
          <button type="submit">ارسال</button>
        </form>
      </div>
    </div>
  );
}

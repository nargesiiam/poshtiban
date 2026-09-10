const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

function getTokens() {
  return {
    access: localStorage.getItem("relay_access"),
    refresh: localStorage.getItem("relay_refresh"),
  };
}

function setTokens({ access, refresh }) {
  if (access) localStorage.setItem("relay_access", access);
  if (refresh) localStorage.setItem("relay_refresh", refresh);
}

export function clearTokens() {
  localStorage.removeItem("relay_access");
  localStorage.removeItem("relay_refresh");
}

let refreshPromise = null; // جلوگیری از چند refresh هم‌زمان وقتی چند درخواست با هم 401 می‌خورند

async function refreshAccessToken() {
  const { refresh } = getTokens();
  if (!refresh) throw new Error("no refresh token");

  const res = await fetch(`${API_BASE}/api/auth/refresh/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh }),
  });
  if (!res.ok) throw new Error("refresh failed");
  const data = await res.json();
  setTokens({ access: data.access, refresh: data.refresh });
  return data.access;
}

async function request(path, { method = "GET", body, isForm = false, _retried = false } = {}) {
  const { access } = getTokens();
  const headers = {};
  if (!isForm) headers["Content-Type"] = "application/json";
  if (access) headers["Authorization"] = `Bearer ${access}`;

  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: isForm ? body : body ? JSON.stringify(body) : undefined,
  });

  if (res.status === 401 && !_retried && !path.includes("/api/auth/refresh/") && !path.includes("/api/auth/login/")) {
    // توکن دسترسی منقضی شده (طول عمرش ۱ ساعت است) — یک بار تلاش می‌کنیم با
    // refresh token یک توکن تازه بگیریم و همین درخواست را دوباره بفرستیم،
    // به‌جای اینکه کاربر با یک پیام گنگ («توکن معتبر نیست») مواجه شود.
    try {
      if (!refreshPromise) refreshPromise = refreshAccessToken().finally(() => (refreshPromise = null));
      await refreshPromise;
      return request(path, { method, body, isForm, _retried: true });
    } catch {
      clearTokens();
      window.location.reload(); // برگشت تمیز به صفحه‌ی ورود
      throw new Error("نشست شما منقضی شده — دوباره وارد شوید.");
    }
  }

  if (!res.ok) {
    const raw = await res.text();
    let message = raw;
    try {
      const parsed = JSON.parse(raw);
      // خطاهای DRF معمولاً به شکل {"field": ["پیام"]} یا {"detail": "پیام"} هستند
      const firstValue = Object.values(parsed)[0];
      message = Array.isArray(firstValue) ? firstValue[0] : firstValue || raw;
    } catch {
      // بدنه‌ی خطا JSON نبود (مثلاً صفحه‌ی 404/500 خودِ جنگو) — همان متن خام کافی است
    }
    throw new Error(message);
  }
  if (res.status === 204) return null;
  return res.json();
}

export async function login(username, password) {
  const data = await request("/api/auth/login/", { method: "POST", body: { username, password } });
  setTokens({ access: data.access, refresh: data.refresh });
  return data;
}

export async function register(username, password, email) {
  return request("/api/auth/register/", { method: "POST", body: { username, password, email } });
}

export async function me() {
  return request("/api/auth/me/");
}

export async function listConversations() {
  return request("/api/conversations/");
}

export async function createConversation(orderId) {
  return request("/api/conversations/", { method: "POST", body: orderId ? { order: orderId } : {} });
}

export async function getConversation(id) {
  return request(`/api/conversations/${id}/`);
}

export async function deleteConversation(id) {
  return request(`/api/conversations/${id}/`, { method: "DELETE" });
}

export async function sendMessage(conversationId, content) {
  return request(`/api/conversations/${conversationId}/messages/`, { method: "POST", body: { content } });
}

export async function listDocuments() {
  return request("/api/documents/");
}

export async function uploadDocument(title, file) {
  const form = new FormData();
  form.append("title", title);
  form.append("file", file);
  return request("/api/documents/", { method: "POST", body: form, isForm: true });
}

export { API_BASE, getTokens };

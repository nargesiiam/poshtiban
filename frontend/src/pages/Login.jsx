import { useState } from "react";
import { login, register } from "../api.js";

export default function Login({ onLoggedIn }) {
  const [mode, setMode] = useState("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [email, setEmail] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      if (mode === "register") {
        await register(username, password, email);
      }
      await login(username, password);
      onLoggedIn();
    } catch (err) {
      setError("ورود ناموفق بود. نام کاربری یا رمز عبور را بررسی کنید.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-page">
      <form className="auth-card" onSubmit={handleSubmit}>
        <div className="auth-mark">R</div>
        <h1>Relay</h1>
        <p className="subtitle">دستیار پشتیبانی مشتری</p>

        <label>نام کاربری</label>
        <input value={username} onChange={(e) => setUsername(e.target.value)} required />

        {mode === "register" && (
          <>
            <label>ایمیل</label>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
          </>
        )}

        <label>رمز عبور</label>
        <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />

        {error && <div className="error-text">{error}</div>}

        <button type="submit" disabled={busy}>
          {busy ? "..." : mode === "login" ? "ورود" : "ثبت‌نام و ورود"}
        </button>

        <button
          type="button"
          className="link-btn"
          onClick={() => setMode(mode === "login" ? "register" : "login")}
        >
          {mode === "login" ? "حساب ندارید؟ ثبت‌نام کنید" : "قبلاً ثبت‌نام کرده‌اید؟ وارد شوید"}
        </button>
      </form>
    </div>
  );
}

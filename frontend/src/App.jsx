import { useEffect, useState } from "react";
import { clearTokens, getTokens, me } from "./api.js";
import Login from "./pages/Login.jsx";
import Chat from "./pages/Chat.jsx";
import Documents from "./pages/Documents.jsx";

export default function App() {
  const [user, setUser] = useState(null);
  const [checked, setChecked] = useState(false);
  const [tab, setTab] = useState("chat");

  async function checkAuth() {
    const { access } = getTokens();
    if (!access) {
      setChecked(true);
      return;
    }
    try {
      setUser(await me());
    } catch {
      clearTokens();
    } finally {
      setChecked(true);
    }
  }

  useEffect(() => {
    checkAuth();
  }, []);

  if (!checked) return null;

  if (!user) {
    return <Login onLoggedIn={checkAuth} />;
  }

  return (
    <div className="app-shell">
      <nav className="top-nav">
        <span className="brand">Relay</span>
        <button className={tab === "chat" ? "active" : ""} onClick={() => setTab("chat")}>
          گفت‌وگو
        </button>
        <button className={tab === "documents" ? "active" : ""} onClick={() => setTab("documents")}>
          اسناد
        </button>
        <span className="spacer" />
        <span className="username">{user.username}</span>
        <button
          className="logout-btn"
          onClick={() => {
            clearTokens();
            setUser(null);
          }}
        >
          خروج
        </button>
      </nav>

      <main>
        {tab === "chat" && <Chat />}
        {tab === "documents" && <Documents isStaff={user.is_staff} />}
      </main>
    </div>
  );
}

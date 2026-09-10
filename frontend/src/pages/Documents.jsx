import { useEffect, useState } from "react";
import { listDocuments, uploadDocument } from "../api.js";

const STATUS_LABELS = {
  pending: "در انتظار پردازش",
  processing: "در حال embed شدن",
  ready: "آماده برای بازیابی",
  failed: "پردازش ناموفق",
};

const ALLOWED_EXTENSIONS = [".pdf", ".txt", ".md"];

export default function Documents({ isStaff }) {
  const [documents, setDocuments] = useState([]);
  const [title, setTitle] = useState("");
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function refresh() {
    setDocuments(await listDocuments());
  }

  useEffect(() => {
    refresh();
  }, []);

  function handleFileChange(e) {
    const picked = e.target.files[0];
    setError(null);
    if (picked) {
      const ext = "." + picked.name.split(".").pop().toLowerCase();
      if (!ALLOWED_EXTENSIONS.includes(ext)) {
        setError("فقط فایل PDF یا متنی (.txt/.md) پشتیبانی می‌شود — عکس یا فرمت‌های دیگر قابل پردازش نیستند.");
        setFile(null);
        e.target.value = "";
        return;
      }
    }
    setFile(picked);
  }

  async function handleUpload(e) {
    e.preventDefault();
    if (!file || !title.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await uploadDocument(title.trim(), file);
      setTitle("");
      setFile(null);
      await refresh();
    } catch (err) {
      setError(err?.message || "آپلود ناموفق بود.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="documents-page">
      <h2>اسناد دانش شرکت</h2>

      {isStaff && (
        <form className="upload-form" onSubmit={handleUpload}>
          <input
            placeholder="عنوان سند"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
          <input type="file" accept=".pdf,.txt,.md" onChange={handleFileChange} />
          <button type="submit" disabled={busy}>
            {busy ? "در حال آپلود..." : "آپلود"}
          </button>
          {error && <div className="error-text">{error}</div>}
        </form>
      )}

      <table className="documents-table">
        <thead>
          <tr>
            <th>عنوان</th>
            <th>وضعیت</th>
            <th>تاریخ</th>
          </tr>
        </thead>
        <tbody>
          {documents.map((doc) => (
            <tr key={doc.id}>
              <td>{doc.title}</td>
              <td>
                <span className={`status-pill status-${doc.ingestion_status}`}>
                  {STATUS_LABELS[doc.ingestion_status] || doc.ingestion_status}
                </span>
              </td>
              <td>{new Date(doc.created_at).toLocaleDateString("fa-IR")}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

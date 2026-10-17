const BASE = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

async function request(path, options) {
  let res;
  try {
    res = await fetch(BASE + path, options);
  } catch {
    throw new Error("Cannot reach the API. Is the backend running on port 8000?");
  }
  if (!res.ok) {
    let message = res.statusText;
    try {
      const body = await res.json();
      message = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch { /* keep statusText */ }
    throw new Error(message);
  }
  return res.json();
}

export const getSummary = () => request("/dashboard/summary");

export const getTransactions = (params = {}) => {
  const q = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => v && q.set(k, v));
  return request("/transactions?" + q.toString());
};

export const getTransaction = (id) => request(`/transactions/${encodeURIComponent(id)}`);

export const reconcile = (file) => {
  if (!file) return request("/reconcile", { method: "POST" }); // backend uses the sample CSV
  const body = new FormData();
  body.append("file", file);
  return request("/reconcile", { method: "POST", body });
};
export const STATUS_COLORS = {
  PENDING: "#6b7280",
  PARTIAL: "#d97706",
  FULLY_SETTLED: "#16a34a",
  OVER_SETTLED: "#dc2626",
  REFUNDED: "#2563eb",
  NOT_APPLICABLE: "#94a3b8",
};

export const STATUS_LABELS = {
  PENDING: "Pending",
  PARTIAL: "Partial",
  FULLY_SETTLED: "Fully settled",
  OVER_SETTLED: "Over settled",
  REFUNDED: "Refunded",
  NOT_APPLICABLE: "N/A",
};

export function StatusBadge({ status }) {
  return (
    <span className="badge" style={{ background: STATUS_COLORS[status] || "#6b7280" }}>
      {STATUS_LABELS[status] || status}
    </span>
  );
}

export function FlagBadge({ flag }) {
  if (!flag) return <span className="muted">OK</span>;
  return (
    <span className={`flag ${flag === "CRITICAL" ? "flag-critical" : "flag-warning"}`}>
      {flag === "CRITICAL" ? "Critical" : "Warning"}
    </span>
  );
}

export const money = (n, currency = "USD") =>
  n == null
    ? "-"
    : new Intl.NumberFormat("en-US", { style: "currency", currency }).format(n);
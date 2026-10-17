import { useEffect, useRef, useState } from "react";
import { Bar, BarChart, Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { getSummary, reconcile } from "../api.js";
import { STATUS_COLORS, STATUS_LABELS, money } from "../ui.jsx";

function Card({ label, value, tone }) {
  return (
    <div className={`card ${tone || ""}`}>
      <div className="card-value">{value}</div>
      <div className="card-label">{label}</div>
    </div>
  );
}

export default function Dashboard() {
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const fileRef = useRef(null);

  const load = () => getSummary().then(setSummary).catch((e) => setError(e.message));
  useEffect(() => { load(); }, []);

  const run = async () => {
    setBusy(true);
    setError("");
    try {
      const file = fileRef.current?.files?.[0];
      setResult(await reconcile(file));
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  if (error && !summary) return <p className="error">{error}</p>;
  if (!summary) return <p>Loading...</p>;

  const pieData = Object.entries(summary.status_breakdown)
    .filter(([, v]) => v > 0)
    .map(([k, v]) => ({ key: k, name: STATUS_LABELS[k], value: v }));
  const issueData = Object.entries(summary.issues_by_type).map(([k, v]) => ({
    name: k.replaceAll("_", " ").toLowerCase(),
    count: v,
  }));
  const b = summary.status_breakdown;

  return (
    <>
      <section className="panel">
        <h2>Run reconciliation</h2>
        <div className="row">
          <input type="file" accept=".csv" ref={fileRef} />
          <button onClick={run} disabled={busy}>{busy ? "Processing..." : "Reconcile"}</button>
        </div>
        <p className="muted">Choose a settlement CSV, or leave empty to use the sample file.</p>
        {error && <p className="error">{error}</p>}
        {result && (
          <div className="result">
            <strong>Done:</strong> {result.inserted} inserted, {result.duplicates_skipped} duplicates skipped,{" "}
            {result.matched_by_lifecycle_id} matched by lifecycle ID, {result.matched_by_fallback} by fallback,{" "}
            {result.exceptions.length} exceptions, {result.rejected_rows.length} rejected rows.
            {result.exceptions.length > 0 && (
              <ul>{result.exceptions.map((e, i) => <li key={i}>{e.settlement_id}: {e.reason}</li>)}</ul>
            )}
            {result.rejected_rows.length > 0 && (
              <ul>{result.rejected_rows.map((r, i) => <li key={i}>Row {r.row}: {r.errors.join("; ")}</li>)}</ul>
            )}
          </div>
        )}
      </section>

      <section className="cards">
        <Card label="Transactions" value={summary.total_transactions} />
        <Card label="Settlements processed" value={summary.total_settlements} />
        <Card label="Critical issues" value={summary.critical_issues} tone="critical" />
        <Card label="Warnings" value={summary.warnings} tone="warning" />
        <Card label="Outstanding amount" value={money(summary.total_outstanding_amount)} />
        <Card label="Avg days to settle" value={summary.avg_days_to_settle ?? "-"} />
        <Card label="Settlement rate" value={`${summary.settlement_rate}%`} />
        <Card label="Unmatched rows" value={summary.unmatched_exceptions} />
      </section>

      <section className="card-row">
        <div className="card wide"><span className="muted">Pending</span> <strong>{b.PENDING}</strong></div>
        <div className="card wide"><span className="muted">Partial</span> <strong>{b.PARTIAL}</strong></div>
        <div className="card wide"><span className="muted">Fully settled</span> <strong>{b.FULLY_SETTLED}</strong></div>
        <div className="card wide"><span className="muted">Over settled</span> <strong>{b.OVER_SETTLED}</strong></div>
        <div className="card wide"><span className="muted">Refunded</span> <strong>{b.REFUNDED}</strong></div>
      </section>

      <section className="charts">
        <div className="panel">
          <h2>Settlement status</h2>
          <ResponsiveContainer width="100%" height={280}>
            <PieChart>
              <Pie data={pieData} dataKey="value" nameKey="name" innerRadius={55} outerRadius={95} label>
                {pieData.map((d) => <Cell key={d.key} fill={STATUS_COLORS[d.key]} />)}
              </Pie>
              <Tooltip />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </div>
        <div className="panel">
          <h2>Issues by type</h2>
          {issueData.length === 0 ? (
            <p className="muted">No issues detected.</p>
          ) : (
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={issueData} layout="vertical" margin={{ left: 40 }}>
                <XAxis type="number" allowDecimals={false} />
                <YAxis type="category" dataKey="name" width={170} />
                <Tooltip />
                <Bar dataKey="count" fill="#dc2626" />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </section>
      <p className="muted">7-day rule evaluated as of {summary.as_of}.</p>
    </>
  );
}
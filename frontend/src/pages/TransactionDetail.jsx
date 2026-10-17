import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getTransaction } from "../api.js";
import { FlagBadge, StatusBadge, money } from "../ui.jsx";

export default function TransactionDetail() {
  const { id } = useParams();
  const [d, setD] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    setD(null);
    getTransaction(id).then(setD).catch((e) => setError(e.message));
  }, [id]);

  if (error) return <><Link to="/transactions">&larr; Back</Link><p className="error">{error}</p></>;
  if (!d) return <p>Loading...</p>;

  const t = d.transaction;
  const cur = t.currency;

  return (
    <>
      <Link to="/transactions">&larr; Back to transactions</Link>
      <h2>{t.transaction_id} <StatusBadge status={d.settlement_status} /> <FlagBadge flag={d.flag} /></h2>

      <section className="panel info-grid">
        <div><span className="muted">Merchant</span><br />{t.merchant_name}</div>
        <div><span className="muted">Account</span><br />{t.account_id}</div>
        <div><span className="muted">Lifecycle ID</span><br />{t.lifecycle_id || "-"}</div>
        <div><span className="muted">Date</span><br />{t.transaction_date}</div>
        <div><span className="muted">Amount</span><br />{money(t.amount, cur)}</div>
        <div><span className="muted">Transaction status</span><br />{t.transaction_status}</div>
        <div><span className="muted">Debits</span><br />{money(d.totals.debits, cur)}</div>
        <div><span className="muted">Credits</span><br />{money(d.totals.credits, cur)}</div>
        <div><span className="muted">Net settled</span><br /><strong>{money(d.totals.net, cur)}</strong></div>
      </section>

      <section className="panel">
        <h3>Issues and recommendations</h3>
        {d.issues.length === 0 ? (
          <p className="ok">No issues detected.</p>
        ) : (
          d.issues.map((i) => (
            <div key={i.code} className={`issue ${i.severity === "CRITICAL" ? "issue-critical" : "issue-warning"}`}>
              <strong>{i.severity === "CRITICAL" ? "Critical" : "Warning"}: {i.message}</strong>
              <div>Recommendation: {i.recommendation}</div>
            </div>
          ))
        )}
      </section>

      <section className="panel">
        <h3>Settlement timeline</h3>
        <div className="timeline">
          <div className="tl-item">
            <div className="tl-dot tl-start" />
            <div className="tl-date">{t.transaction_date}</div>
            <div>Transaction</div>
            <div>{money(t.amount, cur)}</div>
          </div>
          {d.timeline.map((e) => (
            <div className="tl-item" key={e.settlement_id}>
              <div className={`tl-dot ${e.type === "DEBIT" ? "tl-debit" : "tl-credit"}`} />
              <div className="tl-date">{e.date}</div>
              <div>{e.type === "DEBIT" ? "+" : "-"}{money(e.amount, cur)}</div>
              <div className="muted">Net {money(e.running_net, cur)}</div>
            </div>
          ))}
          {d.timeline.length === 0 && <div className="muted tl-empty">No settlements yet.</div>}
        </div>
      </section>

      <section className="panel">
        <h3>Settlement history</h3>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Settlement ID</th><th>Date</th><th>Type</th><th className="num">Amount</th></tr></thead>
            <tbody>
              {d.settlements.map((s) => (
                <tr key={s.settlement_id}>
                  <td>{s.settlement_id}</td>
                  <td>{s.settlement_date}</td>
                  <td>{s.settlement_type}</td>
                  <td className="num">{money(s.settlement_amount, s.currency)}</td>
                </tr>
              ))}
              {d.settlements.length === 0 && <tr><td colSpan={4} className="muted">No settlements.</td></tr>}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getTransactions } from "../api.js";
import { FlagBadge, STATUS_LABELS, StatusBadge, money } from "../ui.jsx";

export default function TransactionList() {
  const [rows, setRows] = useState(null);
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");
  const [flag, setFlag] = useState("");
  const [search, setSearch] = useState("");
  const navigate = useNavigate();

  useEffect(() => {
    const timer = setTimeout(() => {
      getTransactions({ status, flag, search })
        .then((data) => { setRows(data); setError(""); })
        .catch((e) => setError(e.message));
    }, 250);                                   // small delay while typing in search
    return () => clearTimeout(timer);
  }, [status, flag, search]);

  return (
    <>
      <div className="filters">
        <select value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">All statuses</option>
          {Object.entries(STATUS_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <select value={flag} onChange={(e) => setFlag(e.target.value)}>
          <option value="">All issue levels</option>
          <option value="CRITICAL">Critical</option>
          <option value="WARNING">Warning</option>
        </select>
        <input placeholder="Search id, merchant, account" value={search} onChange={(e) => setSearch(e.target.value)} />
      </div>

      {error && <p className="error">{error}</p>}
      {!rows && !error && <p>Loading...</p>}
      {rows && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Transaction ID</th><th>Date</th><th>Merchant</th><th className="num">Amount</th>
                <th>Settlement status</th><th className="num">Settled</th><th>Issue</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr
                  key={r.transaction_id}
                  className={`clickable ${r.flag ? "row-" + r.flag.toLowerCase() : ""}`}
                  onClick={() => navigate(`/transactions/${r.transaction_id}`)}
                >
                  <td>{r.transaction_id}</td>
                  <td>{r.date}</td>
                  <td>{r.merchant_name}</td>
                  <td className="num">{money(r.amount, r.currency)}</td>
                  <td><StatusBadge status={r.settlement_status} /></td>
                  <td className="num">{money(r.settled_amount, r.currency)}</td>
                  <td><FlagBadge flag={r.flag} /></td>
                </tr>
              ))}
              {rows.length === 0 && <tr><td colSpan={7} className="muted">No transactions match.</td></tr>}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
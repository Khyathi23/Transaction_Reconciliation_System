import { NavLink, Route, Routes } from "react-router-dom";
import Dashboard from "./pages/Dashboard.jsx";
import TransactionList from "./pages/TransactionList.jsx";
import TransactionDetail from "./pages/TransactionDetail.jsx";

export default function App() {
  return (
    <>
      <header className="topbar">
        <h1>Reconciliation</h1>
        <nav>
          <NavLink to="/" end>Dashboard</NavLink>
          <NavLink to="/transactions">Transactions</NavLink>
        </nav>
      </header>
      <main className="container">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/transactions" element={<TransactionList />} />
          <Route path="/transactions/:id" element={<TransactionDetail />} />
          <Route path="*" element={<p>Page not found.</p>} />
        </Routes>
      </main>
    </>
  );
}
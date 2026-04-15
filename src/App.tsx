import { useState, useEffect } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Navigation } from "@/components/navigation";
import { loadFromServer } from "@/lib/db";
import { HomePage } from "./pages/HomePage";
import { PositionsPage } from "./pages/PositionsPage";
import { AccountsPage } from "./pages/AccountsPage";
import { TransactionsPage } from "./pages/TransactionsPage";
import { DataSourcesPage } from "./pages/DataSourcesPage";

export default function App() {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    loadFromServer().finally(() => setReady(true));
  }, []);

  if (!ready) {
    return (
      <div className="loading-screen">
        <div className="loading-spinner" />
        <span>加载数据中…</span>
      </div>
    );
  }

  return (
    <BrowserRouter>
      <div className="app-shell">
        <Navigation />
        <main>
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/positions" element={<PositionsPage />} />
            <Route path="/accounts" element={<AccountsPage />} />
            <Route path="/transactions" element={<TransactionsPage />} />
            <Route path="/data-sources" element={<DataSourcesPage />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}

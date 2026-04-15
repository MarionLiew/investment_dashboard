import { useState } from "react";
import { TransactionsTable } from "@/components/transactions-table";
import { TransactionForm } from "@/components/transaction-form";

export function TransactionsPage() {
  const [version, setVersion] = useState(0);

  return (
    <div className="page-grid">
      <section className="hero-card compact">
        <div className="hero-copy">
          <p className="eyebrow">Transactions</p>
          <h2>统一交易流水，支持手动录入和 API 导入</h2>
          <p>首版已经定义统一交易结构，可直接接入导入器、CSV 和交易所同步。</p>
        </div>
      </section>
      <TransactionForm onAdded={() => setVersion((v) => v + 1)} />
      <TransactionsTable key={version} />
    </div>
  );
}

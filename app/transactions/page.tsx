import { TransactionsTable } from "@/components/transactions-table";

export default function TransactionsPage() {
  return (
    <div className="page-grid">
      <section className="hero-card compact">
        <div className="hero-copy">
          <p className="eyebrow">Transactions</p>
          <h2>统一交易流水，支持手动录入和 API 导入</h2>
          <p>首版已经定义统一交易结构，可直接接入导入器、CSV 和交易所同步。</p>
        </div>
      </section>
      <TransactionsTable />
      <section className="panel">
        <div className="panel-heading">
          <h3>手动录入 API 示例</h3>
        </div>
        <pre className="code-block">{`POST /api/transactions
{
  "accountId": "acct_manual_cn",
  "asset": {
    "assetType": "stock",
    "symbol": "000858",
    "name": "五粮液",
    "market": "CN-SZ",
    "currency": "CNY"
  },
  "type": "buy",
  "quantity": 50,
  "price": 138.4,
  "fee": 12,
  "currency": "CNY",
  "executedAt": "2026-04-10T09:30:00+08:00"
}`}</pre>
      </section>
    </div>
  );
}

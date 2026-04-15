import { useSearchParams, Link } from "react-router-dom";
import { PositionsTable } from "@/components/positions-table";
import { db } from "@/lib/db";
import type { BaseCurrency } from "@/lib/types";

export function PositionsPage() {
  const [searchParams] = useSearchParams();
  const raw = searchParams.get("baseCurrency");
  const baseCurrency: BaseCurrency = raw === "USD" || raw === "CNY" ? raw : "CNY";
  const accountId = searchParams.get("accountId") ?? undefined;
  const assetType = searchParams.get("assetType") ?? undefined;
  const accounts = db.getAccounts();

  return (
    <div className="page-grid">
      <section className="hero-card compact">
        <div className="hero-copy">
          <p className="eyebrow">Positions</p>
          <h2>按资产类别、账户和市场查看当前持仓</h2>
        </div>
        <div className="filter-row">
          <Link to={`/positions?baseCurrency=${baseCurrency}`} className={!assetType && !accountId ? "chip active" : "chip"}>
            全部持仓
          </Link>
          <Link to={`/positions?baseCurrency=${baseCurrency}&assetType=stock`} className={assetType === "stock" ? "chip active" : "chip"}>
            股票
          </Link>
          <Link to={`/positions?baseCurrency=${baseCurrency}&assetType=fund`} className={assetType === "fund" ? "chip active" : "chip"}>
            基金
          </Link>
          <Link to={`/positions?baseCurrency=${baseCurrency}&assetType=crypto`} className={assetType === "crypto" ? "chip active" : "chip"}>
            加密
          </Link>
          {accounts.map((account) => (
            <Link
              key={account.id}
              to={`/positions?baseCurrency=${baseCurrency}&accountId=${account.id}`}
              className={accountId === account.id ? "chip active" : "chip"}
            >
              {account.name}
            </Link>
          ))}
        </div>
      </section>
      <PositionsTable baseCurrency={baseCurrency} accountId={accountId} assetType={assetType} />
    </div>
  );
}

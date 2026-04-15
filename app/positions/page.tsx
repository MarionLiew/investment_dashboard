import { PositionsTable } from "@/components/positions-table";
import { BaseCurrency } from "@/lib/types";
import { db } from "@/lib/db";

export default async function PositionsPage({
  searchParams
}: {
  searchParams?: Promise<{ baseCurrency?: BaseCurrency; accountId?: string; assetType?: string }>;
}) {
  const params = await searchParams;
  const baseCurrency =
    params?.baseCurrency === "USD" || params?.baseCurrency === "CNY"
      ? params.baseCurrency
      : "CNY";
  const accounts = db.getAccounts();

  return (
    <div className="page-grid">
      <section className="hero-card compact">
        <div className="hero-copy">
          <p className="eyebrow">Positions</p>
          <h2>按资产类别、账户和市场查看当前持仓</h2>
        </div>
        <div className="filter-row">
          <a href={`/positions?baseCurrency=${baseCurrency}`} className="chip active">
            全部持仓
          </a>
          <a href={`/positions?baseCurrency=${baseCurrency}&assetType=stock`} className="chip">
            股票
          </a>
          <a href={`/positions?baseCurrency=${baseCurrency}&assetType=fund`} className="chip">
            基金
          </a>
          <a href={`/positions?baseCurrency=${baseCurrency}&assetType=crypto`} className="chip">
            加密
          </a>
          {accounts.map((account) => (
            <a
              key={account.id}
              href={`/positions?baseCurrency=${baseCurrency}&accountId=${account.id}`}
              className="chip"
            >
              {account.name}
            </a>
          ))}
        </div>
      </section>
      <PositionsTable
        baseCurrency={baseCurrency}
        accountId={params?.accountId}
        assetType={params?.assetType}
      />
    </div>
  );
}

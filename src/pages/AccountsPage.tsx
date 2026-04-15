import { useSearchParams } from "react-router-dom";
import { AccountsPanel } from "@/components/accounts-panel";
import type { BaseCurrency } from "@/lib/types";

export function AccountsPage() {
  const [searchParams] = useSearchParams();
  const raw = searchParams.get("baseCurrency");
  const baseCurrency: BaseCurrency = raw === "USD" || raw === "CNY" ? raw : "CNY";

  return (
    <div className="page-grid">
      <section className="hero-card compact">
        <div className="hero-copy">
          <p className="eyebrow">Accounts</p>
          <h2>账户维度查看净值、净投入与累计收益</h2>
        </div>
      </section>
      <AccountsPanel baseCurrency={baseCurrency} />
    </div>
  );
}

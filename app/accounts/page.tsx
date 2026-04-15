import { AccountsPanel } from "@/components/accounts-panel";
import { BaseCurrency } from "@/lib/types";

export default async function AccountsPage({
  searchParams
}: {
  searchParams?: Promise<{ baseCurrency?: BaseCurrency }>;
}) {
  const params = await searchParams;
  const baseCurrency =
    params?.baseCurrency === "USD" || params?.baseCurrency === "CNY"
      ? params.baseCurrency
      : "CNY";

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

import { Dashboard } from "@/components/dashboard";
import { BaseCurrency } from "@/lib/types";

export default async function Home({
  searchParams
}: {
  searchParams?: Promise<{ baseCurrency?: BaseCurrency }>;
}) {
  const params = await searchParams;
  const baseCurrency =
    params?.baseCurrency === "USD" || params?.baseCurrency === "CNY"
      ? params.baseCurrency
      : "CNY";

  return <Dashboard baseCurrency={baseCurrency} />;
}

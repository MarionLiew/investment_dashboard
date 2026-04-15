import { useSearchParams } from "react-router-dom";
import { Dashboard } from "@/components/dashboard";
import type { BaseCurrency } from "@/lib/types";

export function HomePage() {
  const [searchParams] = useSearchParams();
  const raw = searchParams.get("baseCurrency");
  const baseCurrency: BaseCurrency = raw === "USD" || raw === "CNY" ? raw : "CNY";
  return <Dashboard baseCurrency={baseCurrency} />;
}

import { db } from "@/lib/db";
import { Asset, PriceSnapshot } from "@/lib/types";

const fallbackQuotes: Record<string, { price: number; source: string }> = {
  "600519": { price: 1688, source: "demo-cn-quote" },
  "161725": { price: 0.93, source: "demo-cn-fund" },
  BTC: { price: 90120, source: "demo-okx-ticker" },
  ETH: { price: 2140, source: "demo-okx-ticker" },
  CNY: { price: 1, source: "fixed" },
  USDT: { price: 1, source: "stablecoin" }
};

export const quote = (symbol: string, market: string) => {
  const asset = db
    .getAssets()
    .find((item) => item.symbol === symbol && item.market === market);
  if (!asset) {
    return null;
  }
  return getLatestPrice(asset);
};

export const batchQuote = (assetIds: string[]) =>
  assetIds
    .map((assetId) => {
      const asset = db.getAssets().find((item) => item.id === assetId);
      if (!asset) {
        return null;
      }
      return getLatestPrice(asset);
    })
    .filter(Boolean) as PriceSnapshot[];

export const getLatestPrice = (asset: Asset) => {
  const existing = db.getPrices().find((item) => item.assetId === asset.id);
  if (existing) {
    return existing;
  }

  const fallback = fallbackQuotes[asset.symbol];
  if (!fallback) {
    return null;
  }

  const snapshot: PriceSnapshot = {
    assetId: asset.id,
    price: fallback.price,
    currency: asset.currency,
    updatedAt: new Date().toISOString(),
    source: fallback.source,
    stale: true
  };
  db.upsertPrice(snapshot);
  return snapshot;
};

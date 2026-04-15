import { db } from "@/lib/db";
import { Asset } from "@/lib/types";
import { makeId } from "@/lib/utils";

const cnSearchCatalog: Asset[] = [
  {
    id: "asset_510300",
    assetType: "fund",
    symbol: "510300",
    name: "沪深300ETF",
    market: "CN-ETF",
    currency: "CNY"
  },
  {
    id: "asset_000858",
    assetType: "stock",
    symbol: "000858",
    name: "五粮液",
    market: "CN-SZ",
    currency: "CNY"
  },
  {
    id: "asset_159915",
    assetType: "fund",
    symbol: "159915",
    name: "创业板ETF",
    market: "CN-ETF",
    currency: "CNY"
  }
];

export const searchAssets = (keyword: string) => {
  const normalized = keyword.trim().toLowerCase();
  if (!normalized) {
    return [];
  }

  const existing = db.getAssets();
  const merged = [...existing];
  for (const asset of cnSearchCatalog) {
    if (!merged.some((item) => item.id === asset.id)) {
      merged.push(asset);
    }
  }

  return merged.filter((asset) => {
    const haystack = `${asset.symbol} ${asset.name} ${asset.market}`.toLowerCase();
    return haystack.includes(normalized);
  });
};

export const ensureAsset = (partial: Omit<Asset, "id"> & { id?: string }) => {
  const existing = db
    .getAssets()
    .find(
      (asset) =>
        asset.symbol === partial.symbol &&
        asset.market === partial.market &&
        asset.assetType === partial.assetType
    );

  if (existing) {
    return existing;
  }

  const asset: Asset = {
    id: partial.id ?? makeId("asset"),
    ...partial
  };
  db.upsertAsset(asset);
  return asset;
};

export type AssetType = "stock" | "fund" | "crypto" | "cash";
export type AccountSourceType = "manual" | "okx" | "broker" | "fund_platform";
export type AccountStatus = "active" | "error" | "syncing";
export type BaseCurrency = "CNY" | "USD";
export type TransactionType =
  | "buy"
  | "sell"
  | "dividend"
  | "interest"
  | "fee"
  | "transfer_in"
  | "transfer_out"
  | "deposit"
  | "withdrawal";

export interface Asset {
  id: string;
  assetType: AssetType;
  symbol: string;
  name: string;
  market: string;
  currency: string;
}

export interface Account {
  id: string;
  sourceType: AccountSourceType;
  name: string;
  baseCurrency: BaseCurrency;
  status: AccountStatus;
  updatedAt: string;
}

export interface Transaction {
  id: string;
  accountId: string;
  assetId: string;
  type: TransactionType;
  quantity: number;
  price: number;
  fee: number;
  currency: string;
  executedAt: string;
  note?: string;
  metadata?: Record<string, string | number | boolean | null>;
}

export interface PriceSnapshot {
  assetId: string;
  price: number;
  currency: string;
  updatedAt: string;
  source: string;
  stale: boolean;
}

export interface FxRateSnapshot {
  pair: string;
  baseCurrency: string;
  quoteCurrency: string;
  rate: number;
  updatedAt: string;
  source: string;
  stale: boolean;
}

export interface DailyPortfolioValue {
  date: string;          // "YYYY-MM-DD"
  cumulativePnl: number; // USD
  returnRate: number | null; // fraction, e.g. 0.1595
}

export interface ConnectorConfig {
  id: string;
  accountId: string;
  connector: "okx";
  apiKey: string;
  secretKey: string;
  passphrase: string;
  lastSyncedAt?: string;
  status: "configured" | "error" | "pending";
  lastError?: string;
  realizedTwr?: number | null;
  dailyPortfolioValues?: DailyPortfolioValue[];
}

export interface SyncLog {
  id: string;
  accountId: string;
  connector: "okx";
  status: "success" | "error";
  message: string;
  createdAt: string;
}

export interface PositionView {
  assetId: string;
  symbol: string;
  name: string;
  assetType: AssetType;
  market: string;
  accountId: string;
  accountName: string;
  currency: string;
  quantity: number;
  avgCost: number;
  costBasis: number;
  latestPrice: number | null;
  latestPriceCurrency: string | null;
  marketValueOriginal: number | null;
  marketValueBase: number | null;
  costBasisBase: number;
  unrealizedPnlBase: number | null;
  unrealizedPnlRate: number | null;
  realizedPnlBase: number;
  soldQuantity: number;
  priceUpdatedAt: string | null;
  stalePrice: boolean;
}

export interface CategorySummary {
  assetType: AssetType;
  marketValueBase: number;
  costBasisBase: number;
  unrealizedPnlBase: number;
  weight: number;
}

export interface AccountPerformance {
  accountId: string;
  accountName: string;
  sourceType: AccountSourceType;
  status: AccountStatus;
  baseCurrency: BaseCurrency;
  marketValueBase: number;
  costBasisBase: number;
  unrealizedPnlBase: number;
  totalNetInflowBase: number;
  transferredOutBase: number;
  cumulativeReturnBase: number;
  cumulativeReturnRate: number | null;
  cashBalanceBase: number;
  lastSyncedAt?: string;
}

export interface PortfolioSummary {
  baseCurrency: BaseCurrency;
  totalMarketValueBase: number;
  totalCostBasisBase: number;
  totalNetInflowBase: number;
  totalTransferredOutBase: number;
  cumulativeReturnBase: number;
  cumulativeReturnRate: number | null;
  realizedTwr: number | null;
  dailyPortfolioValues: DailyPortfolioValue[];
  unrealizedPnlBase: number;
  totalRealizedPnlBase: number;
  priceTimestamp: string;
  categories: CategorySummary[];
  accounts: AccountPerformance[];
}

import {
  Account,
  Asset,
  ConnectorConfig,
  FxRateSnapshot,
  PriceSnapshot,
  SyncLog,
  Transaction
} from "@/lib/types";

const now = "2026-04-10T11:00:00+08:00";

export const assetsSeed: Asset[] = [
  {
    id: "asset_600519",
    assetType: "stock",
    symbol: "600519",
    name: "贵州茅台",
    market: "CN-SH",
    currency: "CNY"
  },
  {
    id: "asset_161725",
    assetType: "fund",
    symbol: "161725",
    name: "招商中证白酒指数A",
    market: "CN-FUND",
    currency: "CNY"
  },
  {
    id: "asset_btc",
    assetType: "crypto",
    symbol: "BTC",
    name: "Bitcoin",
    market: "CRYPTO",
    currency: "USD"
  },
  {
    id: "asset_eth",
    assetType: "crypto",
    symbol: "ETH",
    name: "Ethereum",
    market: "CRYPTO",
    currency: "USD"
  },
  {
    id: "asset_cash_cny",
    assetType: "cash",
    symbol: "CNY",
    name: "人民币现金",
    market: "CASH",
    currency: "CNY"
  },
  {
    id: "asset_cash_usdt",
    assetType: "cash",
    symbol: "USDT",
    name: "Tether",
    market: "CRYPTO",
    currency: "USD"
  }
];

export const accountsSeed: Account[] = [
  {
    id: "acct_manual_cn",
    sourceType: "manual",
    name: "手动-国内资产",
    baseCurrency: "CNY",
    status: "active",
    updatedAt: now
  },
  {
    id: "acct_okx",
    sourceType: "okx",
    name: "欧易主账户",
    baseCurrency: "USD",
    status: "active",
    updatedAt: now
  }
];

export const transactionsSeed: Transaction[] = [
  {
    id: "txn_1",
    accountId: "acct_manual_cn",
    assetId: "asset_cash_cny",
    type: "deposit",
    quantity: 500000,
    price: 1,
    fee: 0,
    currency: "CNY",
    executedAt: "2026-03-01T09:00:00+08:00",
    note: "初始入金"
  },
  {
    id: "txn_2",
    accountId: "acct_manual_cn",
    assetId: "asset_600519",
    type: "buy",
    quantity: 120,
    price: 1528,
    fee: 25,
    currency: "CNY",
    executedAt: "2026-03-05T10:12:00+08:00"
  },
  {
    id: "txn_3",
    accountId: "acct_manual_cn",
    assetId: "asset_161725",
    type: "buy",
    quantity: 15000,
    price: 0.82,
    fee: 0,
    currency: "CNY",
    executedAt: "2026-03-10T13:00:00+08:00"
  },
  {
    id: "txn_4",
    accountId: "acct_okx",
    assetId: "asset_cash_usdt",
    type: "deposit",
    quantity: 30000,
    price: 1,
    fee: 0,
    currency: "USD",
    executedAt: "2026-03-01T09:00:00+08:00"
  },
  {
    id: "txn_5",
    accountId: "acct_okx",
    assetId: "asset_btc",
    type: "buy",
    quantity: 0.32,
    price: 81500,
    fee: 35,
    currency: "USD",
    executedAt: "2026-03-12T20:00:00+08:00"
  },
  {
    id: "txn_6",
    accountId: "acct_okx",
    assetId: "asset_eth",
    type: "buy",
    quantity: 4.6,
    price: 1820,
    fee: 12,
    currency: "USD",
    executedAt: "2026-03-20T11:00:00+08:00"
  },
  {
    id: "txn_7",
    accountId: "acct_okx",
    assetId: "asset_btc",
    type: "sell",
    quantity: 0.05,
    price: 86200,
    fee: 8,
    currency: "USD",
    executedAt: "2026-04-01T16:05:00+08:00"
  }
];

export const priceSnapshotsSeed: PriceSnapshot[] = [
  {
    assetId: "asset_600519",
    price: 1688,
    currency: "CNY",
    updatedAt: now,
    source: "demo-cn-quote",
    stale: false
  },
  {
    assetId: "asset_161725",
    price: 0.93,
    currency: "CNY",
    updatedAt: now,
    source: "demo-cn-fund",
    stale: false
  },
  {
    assetId: "asset_btc",
    price: 90120,
    currency: "USD",
    updatedAt: now,
    source: "demo-okx-ticker",
    stale: false
  },
  {
    assetId: "asset_eth",
    price: 2140,
    currency: "USD",
    updatedAt: now,
    source: "demo-okx-ticker",
    stale: false
  },
  {
    assetId: "asset_cash_cny",
    price: 1,
    currency: "CNY",
    updatedAt: now,
    source: "fixed",
    stale: false
  },
  {
    assetId: "asset_cash_usdt",
    price: 1,
    currency: "USD",
    updatedAt: now,
    source: "stablecoin",
    stale: false
  }
];

export const fxRatesSeed: FxRateSnapshot[] = [
  {
    pair: "USD/CNY",
    baseCurrency: "USD",
    quoteCurrency: "CNY",
    rate: 7.24,
    updatedAt: now,
    source: "demo-fx",
    stale: false
  },
  {
    pair: "CNY/USD",
    baseCurrency: "CNY",
    quoteCurrency: "USD",
    rate: 1 / 7.24,
    updatedAt: now,
    source: "demo-fx",
    stale: false
  }
];

export const connectorConfigsSeed: ConnectorConfig[] = [
  {
    id: "cfg_okx_1",
    accountId: "acct_okx",
    connector: "okx",
    apiKey: "",
    secretKey: "",
    passphrase: "",
    lastSyncedAt: "2026-04-10T10:30:00+08:00",
    status: "configured"
  }
];

export const syncLogsSeed: SyncLog[] = [
  {
    id: "log_1",
    accountId: "acct_okx",
    connector: "okx",
    status: "success",
    message: "同步完成：2 个币种余额、3 条交易流水",
    createdAt: "2026-04-10T10:30:00+08:00"
  }
];

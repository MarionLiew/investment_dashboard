import {
  accountsSeed,
  assetsSeed,
  connectorConfigsSeed,
  fxRatesSeed,
  priceSnapshotsSeed,
  syncLogsSeed,
  transactionsSeed
} from "@/lib/data/sample-data";
import {
  Account,
  Asset,
  ConnectorConfig,
  FxRateSnapshot,
  PriceSnapshot,
  SyncLog,
  Transaction
} from "@/lib/types";

type MemoryStore = {
  assets: Asset[];
  accounts: Account[];
  transactions: Transaction[];
  prices: PriceSnapshot[];
  fxRates: FxRateSnapshot[];
  connectorConfigs: ConnectorConfig[];
  syncLogs: SyncLog[];
};

function makeSeedStore(): MemoryStore {
  return {
    assets: [...assetsSeed],
    accounts: [...accountsSeed],
    transactions: [...transactionsSeed],
    prices: [...priceSnapshotsSeed],
    fxRates: [...fxRatesSeed],
    connectorConfigs: [...connectorConfigsSeed],
    syncLogs: [...syncLogsSeed]
  };
}

const store: MemoryStore = makeSeedStore();

const SERVER_URL = "http://localhost:3001/api/store";

export async function loadFromServer(): Promise<void> {
  try {
    const res = await fetch(SERVER_URL);
    if (!res.ok) return;
    const data = (await res.json()) as MemoryStore | null;
    if (data) {
      store.assets = data.assets ?? store.assets;
      store.accounts = data.accounts ?? store.accounts;
      store.transactions = data.transactions ?? store.transactions;
      store.prices = data.prices ?? store.prices;
      store.fxRates = data.fxRates ?? store.fxRates;
      store.connectorConfigs = data.connectorConfigs ?? store.connectorConfigs;
      store.syncLogs = data.syncLogs ?? store.syncLogs;
    }
  } catch {
    // backend not running — use seed data silently
  }
}

function persistToServer(): void {
  fetch(SERVER_URL, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(store)
  }).catch(() => {});
}

export const db = {
  getAssets: () => store.assets,
  getAccounts: () => store.accounts,
  getTransactions: () => store.transactions,
  getPrices: () => store.prices,
  getFxRates: () => store.fxRates,
  getConnectorConfigs: () => store.connectorConfigs,
  getSyncLogs: () => store.syncLogs,

  upsertAsset(asset: Asset) {
    const index = store.assets.findIndex((item) => item.id === asset.id);
    if (index >= 0) {
      store.assets[index] = asset;
    } else {
      store.assets.push(asset);
    }
    persistToServer();
    return asset;
  },
  addAccount(account: Account) {
    store.accounts.unshift(account);
    persistToServer();
    return account;
  },
  updateAccount(id: string, patch: Partial<Account>) {
    const index = store.accounts.findIndex((a) => a.id === id);
    if (index >= 0) {
      store.accounts[index] = { ...store.accounts[index], ...patch };
      persistToServer();
      return store.accounts[index];
    }
    return null;
  },
  addTransaction(transaction: Transaction) {
    store.transactions.unshift(transaction);
    persistToServer();
    return transaction;
  },
  upsertPrice(price: PriceSnapshot) {
    const index = store.prices.findIndex((item) => item.assetId === price.assetId);
    if (index >= 0) {
      store.prices[index] = price;
    } else {
      store.prices.push(price);
    }
    persistToServer();
    return price;
  },
  upsertFxRate(rate: FxRateSnapshot) {
    const index = store.fxRates.findIndex((item) => item.pair === rate.pair);
    if (index >= 0) {
      store.fxRates[index] = rate;
    } else {
      store.fxRates.push(rate);
    }
    persistToServer();
    return rate;
  },
  upsertConnectorConfig(config: ConnectorConfig) {
    const index = store.connectorConfigs.findIndex((item) => item.id === config.id);
    if (index >= 0) {
      store.connectorConfigs[index] = config;
    } else {
      store.connectorConfigs.push(config);
    }
    persistToServer();
    return config;
  },
  deleteAccount(id: string) {
    store.accounts = store.accounts.filter((a) => a.id !== id);
    store.connectorConfigs = store.connectorConfigs.filter((c) => c.accountId !== id);
    persistToServer();
  },
  deleteTransaction(id: string) {
    store.transactions = store.transactions.filter((t) => t.id !== id);
    persistToServer();
  },
  addSyncLog(log: SyncLog) {
    store.syncLogs.unshift(log);
    persistToServer();
    return log;
  },
  resetToSampleData() {
    const seed = makeSeedStore();
    Object.assign(store, seed);
    persistToServer();
  },
  clearAllData() {
    store.transactions = [];
    store.accounts = [];
    store.assets = [...assetsSeed]; // keep asset catalog
    store.prices = [...priceSnapshotsSeed];
    store.fxRates = [...fxRatesSeed];
    store.connectorConfigs = [];
    store.syncLogs = [];
    persistToServer();
  }
};

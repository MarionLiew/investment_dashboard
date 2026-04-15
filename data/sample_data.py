import copy

NOW = "2026-04-10T11:00:00+08:00"

ASSETS_SEED = [
    {"id": "asset_600519", "assetType": "stock", "symbol": "600519", "name": "贵州茅台", "market": "CN-SH", "currency": "CNY"},
    {"id": "asset_161725", "assetType": "fund", "symbol": "161725", "name": "招商中证白酒指数A", "market": "CN-FUND", "currency": "CNY"},
    {"id": "asset_btc", "assetType": "crypto", "symbol": "BTC", "name": "Bitcoin", "market": "CRYPTO", "currency": "USD"},
    {"id": "asset_eth", "assetType": "crypto", "symbol": "ETH", "name": "Ethereum", "market": "CRYPTO", "currency": "USD"},
    {"id": "asset_cash_cny", "assetType": "cash", "symbol": "CNY", "name": "人民币现金", "market": "CASH", "currency": "CNY"},
    {"id": "asset_cash_usdt", "assetType": "cash", "symbol": "USDT", "name": "Tether", "market": "CRYPTO", "currency": "USD"},
]

ACCOUNTS_SEED = [
    {"id": "acct_manual_cn", "sourceType": "manual", "name": "手动-国内资产", "baseCurrency": "CNY", "status": "active", "updatedAt": NOW},
    {"id": "acct_okx", "sourceType": "okx", "name": "欧易主账户", "baseCurrency": "USD", "status": "active", "updatedAt": NOW},
]

TRANSACTIONS_SEED = [
    {"id": "txn_1", "accountId": "acct_manual_cn", "assetId": "asset_cash_cny", "type": "deposit", "quantity": 500000, "price": 1, "fee": 0, "currency": "CNY", "executedAt": "2026-03-01T09:00:00+08:00", "note": "初始入金"},
    {"id": "txn_2", "accountId": "acct_manual_cn", "assetId": "asset_600519", "type": "buy", "quantity": 120, "price": 1528, "fee": 25, "currency": "CNY", "executedAt": "2026-03-05T10:12:00+08:00", "note": ""},
    {"id": "txn_3", "accountId": "acct_manual_cn", "assetId": "asset_161725", "type": "buy", "quantity": 15000, "price": 0.82, "fee": 0, "currency": "CNY", "executedAt": "2026-03-10T13:00:00+08:00", "note": ""},
    {"id": "txn_4", "accountId": "acct_okx", "assetId": "asset_cash_usdt", "type": "deposit", "quantity": 30000, "price": 1, "fee": 0, "currency": "USD", "executedAt": "2026-03-01T09:00:00+08:00", "note": "初始充值"},
    {"id": "txn_5", "accountId": "acct_okx", "assetId": "asset_btc", "type": "buy", "quantity": 0.32, "price": 81500, "fee": 35, "currency": "USD", "executedAt": "2026-03-12T20:00:00+08:00", "note": ""},
    {"id": "txn_6", "accountId": "acct_okx", "assetId": "asset_eth", "type": "buy", "quantity": 4.6, "price": 1820, "fee": 12, "currency": "USD", "executedAt": "2026-03-20T11:00:00+08:00", "note": ""},
    {"id": "txn_7", "accountId": "acct_okx", "assetId": "asset_btc", "type": "sell", "quantity": 0.05, "price": 86200, "fee": 8, "currency": "USD", "executedAt": "2026-04-01T16:05:00+08:00", "note": ""},
]

PRICES_SEED = [
    {"assetId": "asset_600519", "price": 1688, "currency": "CNY", "updatedAt": NOW, "source": "demo-cn-quote", "stale": False},
    {"assetId": "asset_161725", "price": 0.93, "currency": "CNY", "updatedAt": NOW, "source": "demo-cn-fund", "stale": False},
    {"assetId": "asset_btc", "price": 90120, "currency": "USD", "updatedAt": NOW, "source": "demo-okx-ticker", "stale": False},
    {"assetId": "asset_eth", "price": 2140, "currency": "USD", "updatedAt": NOW, "source": "demo-okx-ticker", "stale": False},
    {"assetId": "asset_cash_cny", "price": 1, "currency": "CNY", "updatedAt": NOW, "source": "fixed", "stale": False},
    {"assetId": "asset_cash_usdt", "price": 1, "currency": "USD", "updatedAt": NOW, "source": "stablecoin", "stale": False},
]

FX_RATES_SEED = [
    {"pair": "USD/CNY", "baseCurrency": "USD", "quoteCurrency": "CNY", "rate": 7.24, "updatedAt": NOW, "source": "demo-fx", "stale": False},
    {"pair": "CNY/USD", "baseCurrency": "CNY", "quoteCurrency": "USD", "rate": round(1 / 7.24, 6), "updatedAt": NOW, "source": "demo-fx", "stale": False},
]

CONNECTOR_CONFIGS_SEED = [
    {"id": "cfg_okx_1", "accountId": "acct_okx", "connector": "okx", "apiKey": "", "secretKey": "", "passphrase": "", "lastSyncedAt": "2026-04-10T10:30:00+08:00", "status": "configured"},
]

SYNC_LOGS_SEED = [
    {"id": "log_1", "accountId": "acct_okx", "connector": "okx", "status": "success", "message": "同步完成：2 个币种余额、3 条交易流水", "createdAt": "2026-04-10T10:30:00+08:00"},
]


def get_seed_store():
    return {
        "assets": copy.deepcopy(ASSETS_SEED),
        "accounts": copy.deepcopy(ACCOUNTS_SEED),
        "transactions": copy.deepcopy(TRANSACTIONS_SEED),
        "prices": copy.deepcopy(PRICES_SEED),
        "fxRates": copy.deepcopy(FX_RATES_SEED),
        "connectorConfigs": copy.deepcopy(CONNECTOR_CONFIGS_SEED),
        "syncLogs": copy.deepcopy(SYNC_LOGS_SEED),
    }

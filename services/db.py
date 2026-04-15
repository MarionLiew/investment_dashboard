import json
import copy
import uuid
import threading
from pathlib import Path
from datetime import datetime, timezone

DATA_FILE = Path(__file__).parent.parent / "data" / "store.json"

_lock = threading.Lock()


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def make_id(prefix=""):
    uid = uuid.uuid4().hex[:8]
    return f"{prefix}_{uid}" if prefix else uid


class DB:
    def _load(self):
        if DATA_FILE.exists():
            try:
                with open(DATA_FILE, encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        store = {
            "accounts": [], "assets": [], "transactions": [],
            "prices": [], "fxRates": [], "connectorConfigs": [], "syncLogs": [],
        }
        self._persist(store)
        return store

    def _persist(self, store):
        DATA_FILE.parent.mkdir(exist_ok=True)
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(store, f, indent=2, ensure_ascii=False)

    def _atomic(self, fn):
        """Read-modify-write under lock. fn(store) mutates store in place."""
        with _lock:
            store = self._load()
            fn(store)
            self._persist(store)

    # ── Reads (always fresh, under lock) ─────────────────────
    def _read(self, key):
        with _lock:
            return self._load().get(key, [])

    def get_accounts(self):          return self._read("accounts")
    def get_assets(self):            return self._read("assets")
    def get_transactions(self):      return self._read("transactions")
    def get_prices(self):            return self._read("prices")
    def get_fx_rates(self):          return self._read("fxRates")
    def get_connector_configs(self): return self._read("connectorConfigs")
    def get_sync_logs(self):         return self._read("syncLogs")

    # ── Account ──────────────────────────────────────────────
    def add_account(self, account):
        def fn(s): s["accounts"].insert(0, account)
        self._atomic(fn)

    def update_account(self, account_id, patch):
        def fn(s):
            for i, a in enumerate(s["accounts"]):
                if a["id"] == account_id:
                    s["accounts"][i] = {**a, **patch, "updatedAt": now_iso()}
                    break
        self._atomic(fn)

    def delete_account(self, account_id):
        def fn(s):
            s["accounts"] = [a for a in s["accounts"] if a["id"] != account_id]
            s["connectorConfigs"] = [c for c in s["connectorConfigs"] if c.get("accountId") != account_id]
        self._atomic(fn)

    # ── Transaction ──────────────────────────────────────────
    def add_transaction(self, txn):
        def fn(s): s["transactions"].insert(0, txn)
        self._atomic(fn)

    def delete_transaction(self, txn_id):
        def fn(s): s["transactions"] = [t for t in s["transactions"] if t["id"] != txn_id]
        self._atomic(fn)

    # ── Asset ────────────────────────────────────────────────
    def ensure_asset(self, asset_type, symbol, name, market, currency):
        with _lock:
            store = self._load()
            for a in store["assets"]:
                if a["symbol"] == symbol and a["market"] == market:
                    return a
            asset = {
                "id": f"asset_{symbol.lower()}_{make_id()}",
                "assetType": asset_type,
                "symbol": symbol,
                "name": name,
                "market": market,
                "currency": currency,
            }
            store["assets"].append(asset)
            self._persist(store)
            return asset

    # ── Prices ───────────────────────────────────────────────
    def upsert_price(self, price):
        def fn(s):
            for i, p in enumerate(s["prices"]):
                if p["assetId"] == price["assetId"]:
                    s["prices"][i] = price
                    return
            s["prices"].append(price)
        self._atomic(fn)

    def upsert_fx_rate(self, rate):
        def fn(s):
            for i, r in enumerate(s["fxRates"]):
                if r["pair"] == rate["pair"]:
                    s["fxRates"][i] = rate
                    return
            s["fxRates"].append(rate)
        self._atomic(fn)

    # ── Connector config ─────────────────────────────────────
    def upsert_connector_config(self, config):
        def fn(s):
            for i, c in enumerate(s["connectorConfigs"]):
                if c["id"] == config["id"]:
                    s["connectorConfigs"][i] = config
                    return
            s["connectorConfigs"].append(config)
        self._atomic(fn)

    # ── Sync log ─────────────────────────────────────────────
    def add_sync_log(self, log):
        def fn(s): s["syncLogs"].insert(0, log)
        self._atomic(fn)

    # ── Data management ──────────────────────────────────────
    def clear_all_data(self):
        def fn(s):
            s["transactions"] = []
            s["assets"] = []
            s["prices"] = []
            s["fxRates"] = []
            s["syncLogs"] = []
            # accounts + connectorConfigs preserved intentionally
        self._atomic(fn)

    def reset_to_sample_data(self):
        from data.sample_data import get_seed_store
        self._persist(get_seed_store())


db = DB()

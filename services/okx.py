import hmac
import hashlib
import base64
import requests
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def _load_env():
    env_file = Path(__file__).parent.parent / ".env.local"
    env = {}
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    return env


def _sign(secret_key: str, method: str, path: str, body: str = "") -> tuple:
    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"
    message = timestamp + method + path + body
    sign = base64.b64encode(
        hmac.new(secret_key.encode(), message.encode(), hashlib.sha256).digest()
    ).decode()
    return sign, timestamp


def okx_get(path: str, creds: Optional[dict] = None) -> dict:
    env = _load_env()
    api_key    = (creds or {}).get("apiKey")    or env.get("OKX_API_KEY", "")
    secret     = (creds or {}).get("secretKey") or env.get("OKX_SECRET_KEY", "")
    passphrase = (creds or {}).get("passphrase") or env.get("OKX_PASSPHRASE", "")

    sign, timestamp = _sign(secret, "GET", path)
    headers = {
        "OK-ACCESS-KEY": api_key,
        "OK-ACCESS-SIGN": sign,
        "OK-ACCESS-TIMESTAMP": timestamp,
        "OK-ACCESS-PASSPHRASE": passphrase,
        "Content-Type": "application/json",
    }
    resp = requests.get(f"https://www.okx.com{path}", headers=headers, timeout=15)
    return resp.json()


def fetch_public_price(inst_id: str) -> Optional[float]:
    """Fetch price from OKX public ticker endpoint (no auth needed)."""
    try:
        resp = requests.get(
            f"https://www.okx.com/api/v5/market/ticker?instId={inst_id}",
            timeout=10
        )
        data = resp.json()
        if data.get("code") == "0" and data.get("data"):
            price = float(data["data"][0].get("last", 0))
            return price if price > 0 else None
    except Exception:
        pass
    return None


_ct_val_cache: dict = {}


def _get_ct_val(inst_id: str, inst_type: str) -> float:
    """
    Fetch contract face value (ctVal) from OKX public instruments API.
    ctVal = how many base-currency units 1 contract represents.
    e.g. BTC-USDT-SWAP ctVal=0.01 → 1 contract = 0.01 BTC.
    SPOT and MARGIN use 1.0 (fillSz already in base units).
    """
    if inst_type in ("SPOT", "MARGIN"):
        return 1.0
    if inst_id in _ct_val_cache:
        return _ct_val_cache[inst_id]
    try:
        resp = requests.get(
            f"https://www.okx.com/api/v5/public/instruments?instType={inst_type}&instId={inst_id}",
            timeout=10
        )
        data = resp.json()
        if data.get("code") == "0" and data.get("data"):
            ct_val = float(data["data"][0].get("ctVal", 1.0) or 1.0)
            _ct_val_cache[inst_id] = ct_val if ct_val > 0 else 1.0
            return _ct_val_cache[inst_id]
    except Exception:
        pass
    _ct_val_cache[inst_id] = 1.0
    return 1.0


def _cache_price(ccy: str, creds=None):
    """Cache price for a currency. Returns 1 if successful, 0 if failed."""
    from services.db import db, now_iso
    if ccy in ("USDT", "USDC", "BUSD"):
        asset = db.ensure_asset("cash", ccy, ccy, "CRYPTO", "USD")
        db.upsert_price({"assetId": asset["id"], "price": 1.0, "currency": "USD",
                         "updatedAt": now_iso(), "source": "stablecoin", "stale": False})
        return 1

    # Try public ticker first (no auth needed)
    price = fetch_public_price(f"{ccy}-USDT")
    if price is None and creds:
        # Fallback to authenticated endpoint
        try:
            resp = okx_get(f"/api/v5/market/ticker?instId={ccy}-USDT", creds)
            if resp.get("code") == "0" and resp.get("data"):
                price = float(resp["data"][0].get("last", 0)) or None
        except Exception:
            pass

    if price and price > 0:
        asset = db.ensure_asset("crypto", ccy, ccy, "CRYPTO", "USD")
        db.upsert_price({"assetId": asset["id"], "price": price, "currency": "USD",
                         "updatedAt": now_iso(), "source": "okx-ticker", "stale": False})
        return 1
    return 0


def refresh_prices_for_open_positions(account_id: str, creds=None):
    """Refresh prices for all assets with open positions in this account."""
    from services.db import db
    assets = {a["id"]: a for a in db.get_assets()}
    transactions = [t for t in db.get_transactions() if t["accountId"] == account_id]

    # Compute net quantity per asset
    net_qty = {}
    for txn in transactions:
        aid = txn["assetId"]
        qty = float(txn["quantity"])
        t = txn["type"]
        if t == "buy":
            net_qty[aid] = net_qty.get(aid, 0) + qty
        elif t == "sell":
            net_qty[aid] = net_qty.get(aid, 0) - qty

    from services.db import now_iso
    updated = 0
    for aid, qty in net_qty.items():
        asset = assets.get(aid)
        if not asset:
            continue
        sym = asset["symbol"]
        if sym in ("USDT", "USDC"):
            continue
        if asset.get("market") == "OKX" and "." in sym:
            # SWAP/FUTURES/MARGIN: fetch price for base symbol (strip .SWAP etc.)
            base = sym.split(".")[0]
            inst_id = asset.get("name", "")  # e.g. "ARB-USDT-SWAP"
            # Try perp ticker first, fall back to spot
            price = fetch_public_price(inst_id) or fetch_public_price(f"{base}-USDT")
            if price and price > 0:
                db.upsert_price({
                    "assetId": aid,
                    "price": price,
                    "currency": "USD",
                    "updatedAt": now_iso(),
                    "source": "okx-ticker",
                    "stale": False,
                })
                updated += 1
        elif asset.get("market") in ("CRYPTO", "OKX"):
            updated += _cache_price(sym, creds)
    return updated


def sync_okx_account(account_id: str, creds: Optional[dict] = None) -> dict:
    from services.db import db, now_iso, make_id
    errors = []
    imported = 0
    updated_prices = 0

    # 0. Deposit history (入金记录)
    try:
        resp = okx_get("/api/v5/asset/deposit-history?limit=100", creds)
        if resp.get("code") == "0":
            existing = {t["id"] for t in db.get_transactions()}
            usdt_asset = db.ensure_asset("cash", "USDT", "USDT", "CRYPTO", "USD")
            for dep in resp.get("data", []):
                dep_id = f"okx_dep_{dep.get('depId', dep.get('txId', ''))}"
                if dep_id in existing:
                    continue
                amt = float(dep.get("amt", 0))
                ccy_dep = dep.get("ccy", "USDT")
                ts = int(dep.get("ts", 0))
                state = int(dep.get("state", 0))
                if state not in (1, 2) or amt <= 0:  # state 1=credited, 2=successful
                    continue
                # Use the asset matching the deposit currency
                dep_asset = db.ensure_asset("cash", ccy_dep, ccy_dep, "CRYPTO", "USD")
                db.add_transaction({
                    "id": dep_id,
                    "accountId": account_id,
                    "assetId": dep_asset["id"],
                    "type": "deposit",
                    "quantity": amt,
                    "price": 1.0,
                    "fee": 0.0,
                    "currency": "USD",
                    "executedAt": datetime.fromtimestamp(ts / 1000, timezone.utc).isoformat(),
                    "note": f"OKX入金 {ccy_dep}",
                })
                imported += 1
        else:
            msg_d = resp.get('msg', '')
            if '403' in str(resp.get('code', '')) or 'permission' in msg_d.lower():
                errors.append("deposits: API key 缺少 Funding 读取权限，请在 OKX 创建 API key 时勾选 Funding 权限")
            else:
                errors.append(f"deposits: {msg_d}")
    except Exception as e:
        errors.append(f"deposits: {e}")

    # 0b. Trading account bills-archive type=1 → capital flows (From/To Funding)
    # subType=11: From Funding → transfer_in (net inflow to trading account)
    # subType=12: To Funding   → transfer_out (net outflow from trading account)
    # Using account/bills-archive (not asset/bills) because it has longer history
    # and correctly captures the trading account perspective.
    try:
        existing_ids = {t["id"] for t in db.get_transactions()}
        for endpoint in [
            "/api/v5/account/bills?type=1&limit=100",
            "/api/v5/account/bills-archive?type=1&limit=100",
        ]:
            resp = okx_get(endpoint, creds)
            if resp.get("code") != "0":
                continue
            for bill in resp.get("data", []):
                sub_type = bill.get("subType", "")
                if sub_type not in ("11", "12"):
                    continue
                bill_id = bill.get("billId", "")
                txn_id = f"okx_tf_{bill_id}"
                if txn_id in existing_ids or not bill_id:
                    continue
                amt = abs(float(bill.get("balChg", 0)))
                if amt <= 0:
                    continue
                ccy = bill.get("ccy", "USDT")
                ts = int(bill.get("ts", 0))
                bill_asset = db.ensure_asset("cash", ccy, ccy, "CRYPTO", "USD")
                # subType=11 = From Funding = money entering trading account
                # subType=12 = To Funding   = money leaving trading account
                txn_type = "transfer_in" if sub_type == "11" else "transfer_out"
                db.add_transaction({
                    "id": txn_id,
                    "accountId": account_id,
                    "assetId": bill_asset["id"],
                    "type": txn_type,
                    "quantity": amt,
                    "price": 1.0,
                    "fee": 0.0,
                    "currency": "USD",
                    "executedAt": datetime.fromtimestamp(ts / 1000, timezone.utc).isoformat(),
                    "note": f"OKX资金{'转入' if txn_type == 'transfer_in' else '转出'}交易账户 {ccy}",
                })
                existing_ids.add(txn_id)
                imported += 1
    except Exception as e:
        errors.append(f"transfers: {e}")

    # 1. Trade fills — SPOT + SWAP + FUTURES + MARGIN, paginated
    inst_types = ["SPOT", "SWAP", "FUTURES", "MARGIN"]
    try:
        existing = {t["id"] for t in db.get_transactions()}
        for inst_type in inst_types:
            after = ""
            max_pages = 50
            page = 0
            stop_early = False
            while page < max_pages and not stop_early:
                url = f"/api/v5/trade/fills-history?instType={inst_type}&limit=100"
                if after:
                    url += f"&after={after}"
                resp = okx_get(url, creds)
                if resp.get("code") != "0":
                    errors.append(f"fills({inst_type}): {resp.get('msg')}")
                    break
                fills = resp.get("data", [])
                if not fills:
                    break
                for fill in fills:
                    trade_id = fill.get("tradeId", "")
                    bill_id = fill.get("billId", trade_id)
                    # SPOT uses old format for backward compat; others use instType prefix
                    txn_id = f"okx_{trade_id}" if inst_type == "SPOT" else f"okx_{inst_type.lower()}_{bill_id}"
                    if txn_id in existing:
                        stop_early = True
                        break
                    inst_id = fill.get("instId", "")
                    parts = inst_id.split("-")
                    # parts: [BASE, QUOTE] for SPOT/MARGIN
                    #        [BASE, QUOTE, SWAP] for SWAP
                    #        [BASE, QUOTE, YYMMDD] for FUTURES
                    base = parts[0] if parts else "UNKNOWN"
                    quote = parts[1] if len(parts) > 1 else "USDT"
                    # Asset label includes contract type for non-spot
                    asset_label = f"{base}.{inst_type}" if inst_type != "SPOT" else base
                    market = "CRYPTO" if inst_type == "SPOT" else "OKX"
                    asset = db.ensure_asset("crypto", asset_label, inst_id, market, "USD")
                    ts = int(fill.get("ts", 0))
                    side = fill.get("side", "buy")
                    fill_sz = float(fill.get("fillSz", 0))
                    fee_raw = abs(float(fill.get("fee", 0)))
                    fee_ccy = fill.get("feeCcy", quote)
                    # Apply contract multiplier: fillSz for SWAP/FUTURES is in contracts,
                    # ctVal converts to base-currency units (e.g. 0.01 BTC per contract)
                    ct_val = _get_ct_val(inst_id, inst_type)
                    fill_sz_base = fill_sz * ct_val  # actual base-unit quantity
                    if inst_type == "SPOT" and side == "buy" and fee_ccy == base:
                        net_qty = fill_sz_base - fee_raw
                        fee_usdt = 0.0
                    else:
                        net_qty = fill_sz_base
                        fee_usdt = fee_raw
                    db.add_transaction({
                        "id": txn_id,
                        "accountId": account_id,
                        "assetId": asset["id"],
                        "type": side,
                        "quantity": net_qty,
                        "price": float(fill.get("fillPx", 0)),
                        "fee": fee_usdt,
                        "currency": "USD",
                        "executedAt": datetime.fromtimestamp(ts / 1000, timezone.utc).isoformat(),
                        "note": f"OKX{inst_type}同步",
                    })
                    existing.add(txn_id)
                    imported += 1
                if stop_early or not fills:
                    break
                after = fills[-1].get("billId", "")
                if not after:
                    break
                page += 1
    except Exception as e:
        errors.append(f"fills: {e}")

    # 1b. Synthesize missing opening fills from positions-history
    # Positions opened >90 days ago won't appear in fills-history; only their closing fills
    # will be there. This causes the net qty to appear in the wrong direction (e.g., a closed
    # SHORT shows as a phantom LONG because we only captured the "buy to cover" closing fill).
    # Solution: for each closed position in positions-history where our fills show an inverted
    # net qty, synthesize the missing opening fill using openAvgPx + the imbalanced qty.
    try:
        existing_ids_synth = {t["id"] for t in db.get_transactions()}
        acct_txns_local = [t for t in db.get_transactions() if t["accountId"] == account_id]
        assets_map_by_name = {a["name"]: a for a in db.get_assets()}

        # Compute net qty per asset from current fills (buy=+, sell=-)
        net_qty_by_aid: dict = {}
        for txn in acct_txns_local:
            aid = txn["assetId"]
            qty = float(txn["quantity"])
            t = txn["type"]
            net_qty_by_aid.setdefault(aid, 0.0)
            if t == "buy":
                net_qty_by_aid[aid] += qty
            elif t == "sell":
                net_qty_by_aid[aid] -= qty

        for inst_type in ["SWAP", "FUTURES"]:
            resp = okx_get(
                f"/api/v5/account/positions-history?instType={inst_type}&limit=100", creds
            )
            if resp.get("code") != "0":
                continue
            for pos in resp.get("data", []):
                inst_id = pos.get("instId", "")
                direction = pos.get("direction", "")  # "long" or "short"
                open_avg_px = float(pos.get("openAvgPx", 0) or 0)
                # cTime = position creation (open) time; uTime = last update (close) time
                open_time = pos.get("cTime", "") or pos.get("openTime", "") or pos.get("uTime", "")
                u_time = pos.get("uTime", "")

                if open_avg_px <= 0 or not direction:
                    continue

                asset = assets_map_by_name.get(inst_id)
                if not asset:
                    continue  # no fills for this instrument, nothing to fix

                aid = asset["id"]
                net_qty = net_qty_by_aid.get(aid, 0.0)

                # Detect mismatch: closing fills without matching opening fills
                # direction=short → opened with SELL; if we only have closing BUYs, net_qty > 0
                # direction=long  → opened with BUY;  if we only have closing SELLs, net_qty < 0
                synth_type = None
                synth_qty = 0.0
                if direction == "short" and net_qty > 0.001:
                    synth_type = "sell"
                    synth_qty = net_qty       # sell this much → net becomes 0
                elif direction == "long" and net_qty < -0.001:
                    synth_type = "buy"
                    synth_qty = abs(net_qty)  # buy this much → net becomes 0

                if not synth_type:
                    continue

                synth_id = f"okx_synth_{inst_id}_{u_time}"
                if synth_id in existing_ids_synth:
                    continue

                exec_dt = (
                    datetime.fromtimestamp(int(open_time) / 1000, timezone.utc).isoformat()
                    if open_time
                    else "2025-10-01T00:00:00+00:00"  # before 90-day window as fallback
                )

                db.add_transaction({
                    "id": synth_id,
                    "accountId": account_id,
                    "assetId": aid,
                    "type": synth_type,
                    "quantity": round(synth_qty, 8),
                    "price": open_avg_px,
                    "fee": 0.0,
                    "currency": "USD",
                    "executedAt": exec_dt,
                    "note": f"OKX历史持仓补录({direction}开仓@{open_avg_px})",
                })
                existing_ids_synth.add(synth_id)
                imported += 1

                # Update local net so later positions in this loop see the corrected state
                if synth_type == "buy":
                    net_qty_by_aid[aid] = net_qty + synth_qty
                else:
                    net_qty_by_aid[aid] = net_qty - synth_qty

    except Exception as e:
        errors.append(f"positions_history: {e}")

    # 2. Account balance → total equity + prices + spot balance snapshot
    total_eq_usd = None
    spot_balances: dict = {}   # ccy -> qty (non-zero spot holdings)
    try:
        resp = okx_get("/api/v5/account/balance", creds)
        if resp.get("code") == "0" and resp.get("data"):
            acct_data = resp["data"][0]
            total_eq_usd = float(acct_data.get("totalEq", 0))
            for detail in acct_data.get("details", []):
                ccy = detail.get("ccy", "")
                eq = float(detail.get("eq", 0) or 0)
                bal = float(detail.get("eqUsd", eq) or 0)
                if eq > 0 and ccy:
                    spot_balances[ccy] = eq
                    updated_prices += _cache_price(ccy, creds)
        else:
            # Fallback: funding account balance
            resp2 = okx_get("/api/v5/asset/balances", creds)
            if resp2.get("code") == "0":
                for item in resp2.get("data", []):
                    if float(item.get("bal", 0)) > 0:
                        updated_prices += _cache_price(item.get("ccy", ""), creds)
    except Exception as e:
        errors.append(f"balances: {e}")

    # 3. Refresh prices for all open positions (using public API, no auth needed)
    try:
        updated_prices += refresh_prices_for_open_positions(account_id, creds)
    except Exception as e:
        errors.append(f"price_refresh: {e}")

    # 3b. Fetch open positions (leverage + margin) and cache prices for open SWAPs
    open_positions_margin = {}  # instId -> {lever, margin, notionalUsd}
    open_inst_ids: list = []    # authoritative list of instIds with non-zero OKX positions
    try:
        resp = okx_get("/api/v5/account/positions", creds)
        if resp.get("code") == "0":
            assets_map = {a["name"]: a for a in db.get_assets()}  # instId -> asset
            for pos in resp.get("data", []):
                inst_id = pos.get("instId", "")
                pos_qty = float(pos.get("pos", 0) or 0)
                lever = pos.get("lever")
                margin = pos.get("margin")
                notional = pos.get("notionalUsd")
                mark_px = pos.get("markPx")
                if abs(pos_qty) > 0:
                    open_inst_ids.append(inst_id)
                if lever and margin:
                    open_positions_margin[inst_id] = {
                        "lever": float(lever),
                        "margin": float(margin),
                        "notionalUsd": float(notional) if notional else None,
                    }
                # Cache mark price for SWAP assets
                if mark_px and inst_id in assets_map:
                    asset = assets_map[inst_id]
                    db.upsert_price({
                        "assetId": asset["id"],
                        "price": float(mark_px),
                        "currency": "USD",
                        "updatedAt": now_iso(),
                        "source": "okx-mark",
                        "stale": False,
                    })
                    updated_prices += 1
    except Exception as e:
        errors.append(f"positions: {e}")

    # 4. Store account equity + open position margins in connector config
    try:
        configs = db.get_connector_configs()
        config = next((c for c in configs if c.get("accountId") == account_id), None)
        if config:
            config["accountEquityUsd"] = total_eq_usd
            config["lastSyncedAt"] = now_iso()
            config["openPositionsMargin"] = open_positions_margin
            config["openInstIds"] = open_inst_ids   # authoritative derivative open positions
            config["spotBalances"] = spot_balances  # authoritative spot holdings (ccy -> qty)
            db.upsert_connector_config(config)
    except Exception as e:
        errors.append(f"config_update: {e}")

    # 4b. Build daily P&L history + chain-linked TWR from bills-archive
    # Uses realized P&L (closed trades + funding fees) — excludes unrealized swings.
    # TWR formula: chain-link sub-period returns cut at each capital transfer event.
    try:
        from datetime import date as _date, timedelta as _td

        # ── 1. Aggregate daily P&L from bills (realized trades + funding fees) ──
        daily_pnl: dict = {}   # date_str -> float (USD)
        seen_bill_ids: set = set()
        for endpoint in [
            "/api/v5/account/bills-archive?type=2&subType=5&limit=100",
            "/api/v5/account/bills?type=2&subType=5&limit=100",
            "/api/v5/account/bills-archive?type=8&limit=100",
            "/api/v5/account/bills?type=8&limit=100",
        ]:
            after_b = ""
            for _ in range(30):
                url_b = endpoint + (f"&after={after_b}" if after_b else "")
                r = okx_get(url_b, creds)
                rows = r.get("data", [])
                if not rows:
                    break
                for x in rows:
                    bid = x.get("billId", "")
                    if bid in seen_bill_ids:
                        continue
                    seen_bill_ids.add(bid)
                    ds = datetime.fromtimestamp(int(x["ts"]) / 1000, timezone.utc).strftime("%Y-%m-%d")
                    # type=2/subType=5: use "pnl" field; type=8: use "balChg"
                    pnl_val = float(x.get("pnl") or x.get("balChg") or 0)
                    daily_pnl[ds] = daily_pnl.get(ds, 0.0) + pnl_val
                if len(rows) < 100:
                    break
                after_b = rows[-1]["billId"]

        # ── 2. Get transfer events from DB ──
        acct_txns_h = sorted(
            [t for t in db.get_transactions() if t["accountId"] == account_id],
            key=lambda t: t["executedAt"],
        )
        transfers_by_date: dict = {}   # date_str -> net USD flow (+in / -out)
        for txn in acct_txns_h:
            if txn["type"] not in ("transfer_in", "transfer_out"):
                continue
            ds = txn["executedAt"][:10]
            amt = float(txn["quantity"]) * float(txn["price"])
            if txn["type"] == "transfer_out":
                amt = -amt
            transfers_by_date[ds] = transfers_by_date.get(ds, 0.0) + amt

        if transfers_by_date:
            all_ds = set(list(transfers_by_date) + list(daily_pnl))
            start_d = _date.fromisoformat(min(all_ds))
            end_d   = datetime.now(timezone.utc).date()

            # Build daily cumulative realized P&L series.
            # "已实现收益率" = cumulative_realized_pnl / net_invested
            # This cleanly avoids the chain-link sub-period problem with circular
            # sub-account transfers (which cause phantom -100% sub-periods).
            cum_pnl      = 0.0
            cum_deposits = 0.0
            cum_wd       = 0.0
            daily_values: list = []

            cur = start_d
            while cur <= end_d:
                ds = cur.isoformat()
                cum_pnl += daily_pnl.get(ds, 0.0)
                if ds in transfers_by_date:
                    tf = transfers_by_date[ds]
                    if tf > 0:
                        cum_deposits += tf
                    else:
                        cum_wd += abs(tf)
                net_inv  = cum_deposits - cum_wd
                ret_rate = round(cum_pnl / net_inv, 4) if net_inv > 0 else None
                if cum_deposits > 0 or daily_values:
                    daily_values.append({
                        "date": ds,
                        "cumulativePnl": round(cum_pnl, 2),
                        "returnRate": ret_rate,
                    })
                cur += _td(days=1)

            # Final "already realized" return rate
            net_inv_total = cum_deposits - cum_wd
            twr_val = round(cum_pnl / net_inv_total, 4) if net_inv_total > 0 else None

            # Persist (keep last 365 days to avoid bloat)
            configs2 = db.get_connector_configs()
            cfg2 = next((c for c in configs2 if c.get("accountId") == account_id), None)
            if cfg2:
                cfg2["dailyPortfolioValues"] = daily_values[-365:]
                cfg2["realizedTwr"] = twr_val
                db.upsert_connector_config(cfg2)

    except Exception as e:
        errors.append(f"pnl_history: {e}")

    # 5. Fetch USD/CNY FX rate (public free API, no auth needed)
    try:
        fx_resp = requests.get(
            "https://open.er-api.com/v6/latest/USD", timeout=10
        )
        fx_data = fx_resp.json()
        cny_rate = fx_data.get("rates", {}).get("CNY")
        if cny_rate:
            db.upsert_fx_rate({
                "pair": "USD/CNY",
                "baseCurrency": "USD",
                "quoteCurrency": "CNY",
                "rate": float(cny_rate),
                "updatedAt": now_iso(),
                "source": "open.er-api.com",
            })
    except Exception as e:
        errors.append(f"fx_rate: {e}")

    if errors:
        msg = f"同步部分完成（导入 {imported} 条交易）。错误: {'; '.join(errors)}"
    else:
        msg = f"OKX同步完成，导入 {imported} 条交易，更新 {updated_prices} 条行情。"

    return {"imported_transactions": imported, "updated_prices": updated_prices, "message": msg}

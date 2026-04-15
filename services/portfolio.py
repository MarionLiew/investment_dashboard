from datetime import datetime, timezone
from services.db import db
from services.fx import convert_amount


def _cash_impact(txn) -> float:
    """Cash impact of a transaction in txn['currency']. Positive = inflow, negative = outflow."""
    qty = float(txn["quantity"])
    price = float(txn["price"])
    fee = float(txn.get("fee", 0))
    gross = qty * price
    t = txn["type"]
    if t in ("deposit", "transfer_in", "dividend", "interest"):
        return gross
    if t in ("withdrawal", "transfer_out"):
        return -gross
    if t == "buy":
        return -(gross + fee)
    if t == "sell":
        return gross - fee
    if t == "fee":
        return -fee
    return 0.0


_DERIVATIVE_MARKETS = {"OKX"}  # SWAP / FUTURES / MARGIN assets


def build_positions(base_currency="CNY"):
    transactions = sorted(db.get_transactions(), key=lambda t: t["executedAt"])
    assets = {a["id"]: a for a in db.get_assets()}
    accounts = {a["id"]: a for a in db.get_accounts()}
    prices = {p["assetId"]: p for p in db.get_prices()}

    # Build OKX authoritative position snapshots (populated during sync).
    # openInstIds: derivative positions from /api/v5/account/positions
    # spotBalances: spot holdings from /api/v5/account/balance (ccy -> qty)
    # If snapshot exists, any computed position NOT in snapshot is treated as closed/dust.
    okx_open_inst: dict = {}    # accountId -> set[instId]  | None
    okx_spot_bal:  dict = {}    # accountId -> dict[ccy, qty] | None
    for cfg in db.get_connector_configs():
        aid = cfg.get("accountId", "")
        if cfg.get("openInstIds") is not None:
            okx_open_inst[aid] = set(cfg["openInstIds"])
        if cfg.get("spotBalances") is not None:
            okx_spot_bal[aid] = cfg["spotBalances"]


    acc_map = {}
    for txn in transactions:
        key = (txn["accountId"], txn["assetId"])
        asset = assets.get(txn["assetId"])
        is_derivative = asset and asset.get("market") in _DERIVATIVE_MARKETS

        acc = acc_map.setdefault(key, {
            "qty": 0.0, "avg_cost": 0.0,
            "sold_qty": 0.0, "realized_pnl": 0.0,
            # Derivative-only: track gross cash flows for net P&L
            "buy_cost": 0.0, "sell_proceeds": 0.0,
            "buy_qty": 0.0, "sell_qty": 0.0,
            "is_derivative": is_derivative,
        })
        qty = float(txn["quantity"])
        price = float(txn["price"])
        fee = float(txn.get("fee", 0))
        t = txn["type"]

        if is_derivative:
            # Derivatives (SWAP/FUTURES/MARGIN): allow short positions (qty can go negative)
            # P&L = net cash flow, matched to closed portion only
            if t == "buy":
                acc["buy_cost"] += qty * price + fee
                acc["buy_qty"] += qty
                acc["qty"] += qty          # can become less negative (covering short)
            elif t == "sell":
                acc["sell_proceeds"] += qty * price - fee
                acc["sell_qty"] += qty
                acc["qty"] -= qty          # can go negative (shorting)
                acc["sold_qty"] += qty
            # realized_pnl will be computed after all txns
        else:
            # Spot assets: long-only moving average cost
            if t == "buy":
                cost = qty * price + fee
                new_qty = acc["qty"] + qty
                acc["avg_cost"] = (acc["qty"] * acc["avg_cost"] + cost) / new_qty if new_qty > 0 else price
                acc["qty"] = new_qty
            elif t == "sell":
                acc["realized_pnl"] += qty * (price - acc["avg_cost"]) - fee
                acc["sold_qty"] += qty
                new_qty = acc["qty"] - qty
                acc["qty"] = 0.0 if new_qty < 1e-6 else max(0.0, new_qty)
            elif t in ("dividend", "interest"):
                acc["realized_pnl"] += qty * price
            elif t == "fee":
                acc["realized_pnl"] -= fee

    # Compute derivative realized P&L — only count closed (matched) portion
    for acc in acc_map.values():
        if acc["is_derivative"]:
            net_qty = acc["qty"]  # positive=net long, negative=net short
            buy_qty = acc["buy_qty"]
            sell_qty = acc["sell_qty"]

            if net_qty >= 0 and buy_qty > 0:
                # Net long: all sells are matched against portion of buys
                # realized_pnl = sell_proceeds - avg_buy_price × qty_sold
                avg_buy_per_unit = acc["buy_cost"] / buy_qty
                acc["realized_pnl"] = acc["sell_proceeds"] - avg_buy_per_unit * sell_qty
                # avg_cost for display (cost per unit of remaining open position)
                acc["avg_cost"] = avg_buy_per_unit
            elif net_qty < 0 and sell_qty > 0:
                # Net short: all buys (covers) are matched against portion of sells
                # realized_pnl = avg_sell_price × qty_covered - buy_cost
                avg_sell_per_unit = acc["sell_proceeds"] / sell_qty
                acc["realized_pnl"] = avg_sell_per_unit * buy_qty - acc["buy_cost"]
                acc["avg_cost"] = avg_sell_per_unit  # avg short entry price
            else:
                # Fully closed (net_qty ≈ 0) or no trades
                acc["realized_pnl"] = acc["sell_proceeds"] - acc["buy_cost"]
                acc["avg_cost"] = acc["buy_cost"] / buy_qty if buy_qty > 0 else 0.0

            # qty for display: show absolute net; negative = short
            acc["qty"] = abs(net_qty) if abs(net_qty) > 1e-6 else 0.0
            acc["is_short"] = net_qty < -1e-6

    result = []
    for (account_id, asset_id), acc in acc_map.items():
        if acc["qty"] <= 0 and acc["sold_qty"] <= 0 and acc["realized_pnl"] == 0:
            continue
        asset = assets.get(asset_id)
        account = accounts.get(account_id)
        if not asset or not account:
            continue

        # ── Filter 1: OKX authoritative position check ──────────────────────────
        # Two sub-checks, one per asset type:
        #   1a. Derivatives (SWAP/FUTURES/MARGIN): verify against openInstIds snapshot
        #   1b. Spot/CRYPTO: verify against spotBalances snapshot (account balance)
        # Both snapshots are written during sync; if absent (manual account / first sync),
        # skip the check so nothing is incorrectly zeroed.
        inst_id = asset.get("name", "")     # e.g. "XAUT-USDT-SWAP"
        symbol  = asset.get("symbol", "")   # e.g. "XAUT"
        is_okx_derivative = asset.get("market") in _DERIVATIVE_MARKETS

        if is_okx_derivative:
            open_set = okx_open_inst.get(account_id)
            if open_set is not None and acc["qty"] > 0 and inst_id not in open_set:
                acc = {**acc, "qty": 0.0, "is_short": False}
        else:
            spot_snap = okx_spot_bal.get(account_id)
            if spot_snap is not None and acc["qty"] > 0:
                # Strip contract suffix to get base currency (e.g. "XAUT.MARGIN" -> "XAUT")
                base_ccy = symbol.split(".")[0]
                live_qty = spot_snap.get(base_ccy, 0.0)
                if live_qty <= 0:
                    acc = {**acc, "qty": 0.0}

        is_derivative = acc["is_derivative"]
        # For derivatives, avg_cost is now set to avg buy/sell price for open positions
        avg_cost = acc["avg_cost"]
        cost_basis = avg_cost * acc["qty"]

        pi = prices.get(asset_id)
        latest_price = float(pi["price"]) if pi else None
        price_ccy = pi["currency"] if pi else asset["currency"]

        # For derivatives with open net position, show notional value if price available
        mv_orig = latest_price * acc["qty"] if latest_price is not None and acc["qty"] > 0 else None
        mv_base = convert_amount(mv_orig, price_ccy, base_currency) if mv_orig is not None else None
        cb_base = convert_amount(cost_basis, asset["currency"], base_currency)
        # Show unrealized P&L for open derivative positions if we have price and cost basis
        if mv_base is not None and cb_base > 0 and is_derivative and not acc.get("is_short"):
            upnl_base = round(mv_base - cb_base, 2)
        elif mv_base is not None and not is_derivative:
            upnl_base = round(mv_base - cb_base, 2)
        else:
            upnl_base = None
        upnl_rate = (upnl_base / cb_base) if upnl_base is not None and cb_base > 0 else None

        rpnl_orig = acc["realized_pnl"]
        rpnl_base = round(convert_amount(rpnl_orig, asset["currency"], base_currency), 2)

        total_pnl_base = round((upnl_base or 0) + rpnl_base, 2)

        result.append({
            "asset_id": asset_id,
            "symbol": asset["symbol"],
            "name": asset["name"],
            "asset_type": asset["assetType"],
            "market": asset["market"],
            "account_id": account_id,
            "account_name": account["name"],
            "currency": asset["currency"],
            "quantity": round(acc["qty"], 6),
            "avg_cost": round(avg_cost, 4),
            "cost_basis": round(cost_basis, 2),
            "latest_price": latest_price,
            "latest_price_currency": price_ccy,
            "market_value_original": round(mv_orig, 2) if mv_orig is not None else None,
            "market_value_base": round(mv_base, 2) if mv_base is not None else None,
            "cost_basis_base": round(cb_base, 2),
            "unrealized_pnl_base": upnl_base,
            "unrealized_pnl_rate": upnl_rate,
            "realized_pnl_base": rpnl_base,
            "total_pnl_base": total_pnl_base,
            "sold_quantity": round(acc["sold_qty"], 6),
            "price_updated_at": pi.get("updatedAt") if pi else None,
            "stale_price": pi.get("stale", True) if pi else True,
        })

    return sorted(result, key=lambda p: (p["market_value_base"] or 0), reverse=True)


def build_account_performance(base_currency="CNY"):
    accounts = db.get_accounts()
    positions = build_positions(base_currency)
    configs = db.get_connector_configs()
    transactions = db.get_transactions()

    result = []
    for account in accounts:
        aid = account["id"]
        pos_slice = [p for p in positions if p["account_id"] == aid]
        inv_value = sum(p["market_value_base"] or 0 for p in pos_slice)
        cb_base = sum(p["cost_basis_base"] for p in pos_slice)

        acct_txns = [t for t in transactions if t["accountId"] == aid]
        cash_balance = 0.0
        net_inflow = 0.0
        transferred_out = 0.0

        for txn in acct_txns:
            impact = _cash_impact(txn)
            cash_balance += convert_amount(impact, txn["currency"], base_currency)
            if txn["type"] in ("deposit", "transfer_in"):
                net_inflow += convert_amount(float(txn["quantity"]) * float(txn["price"]), txn["currency"], base_currency)
            elif txn["type"] in ("withdrawal", "transfer_out"):
                amt = convert_amount(float(txn["quantity"]) * float(txn["price"]), txn["currency"], base_currency)
                net_inflow -= amt
                transferred_out += amt

        config = next((c for c in configs if c.get("accountId") == aid), None)

        upnl = round(sum(p["unrealized_pnl_base"] or 0 for p in pos_slice), 2)
        rpnl = round(sum(p["realized_pnl_base"] for p in pos_slice), 2)
        total_pnl = round(upnl + rpnl, 2)

        # If OKX account has synced equity, use it directly for total market value
        if config and config.get("accountEquityUsd") is not None:
            mv_base = round(convert_amount(config["accountEquityUsd"], "USD", base_currency), 2)
            # Cash = total equity minus positions market value (actual USDT/cash in account)
            actual_cash = round(mv_base - inv_value, 2)
        else:
            mv_base = round(inv_value + cash_balance, 2)
            actual_cash = round(cash_balance, 2)

        # Cumulative return: profit on net capital deployed
        # cum_return = current_value - net_inflow  (net_inflow already deducts outflows)
        # cum_rate   = cum_return / net_inflow
        if net_inflow > 0:
            cum_return = round(mv_base - net_inflow, 2)
            cum_rate = round(cum_return / net_inflow, 4)
        else:
            cum_return = total_pnl
            cum_rate = None

        result.append({
            "account_id": aid,
            "account_name": account["name"],
            "source_type": account["sourceType"],
            "status": account["status"],
            "base_currency": base_currency,
            "market_value_base": mv_base,
            "cost_basis_base": round(cb_base, 2),
            "unrealized_pnl_base": upnl,
            "realized_pnl_base": rpnl,
            "total_pnl_base": total_pnl,
            "total_net_inflow_base": round(net_inflow, 2),
            "transferred_out_base": round(transferred_out, 2),
            "cumulative_return_base": cum_return,
            "cumulative_return_rate": cum_rate,
            "cash_balance_base": actual_cash,
            "last_synced_at": config.get("lastSyncedAt") if config else None,
            "has_equity_snapshot": config.get("accountEquityUsd") is not None if config else False,
        })
    return result


def build_portfolio_summary(base_currency="CNY"):
    positions = build_positions(base_currency)
    accounts = build_account_performance(base_currency)

    total_mv = round(sum(a["market_value_base"] for a in accounts), 2)
    total_cb = round(sum(p["cost_basis_base"] for p in positions if p["quantity"] > 0), 2)
    total_upnl = round(sum(p["unrealized_pnl_base"] or 0 for p in positions), 2)
    total_rpnl = round(sum(p["realized_pnl_base"] for p in positions), 2)
    total_pnl = round(total_upnl + total_rpnl, 2)
    total_inflow = round(sum(a["total_net_inflow_base"] for a in accounts), 2)
    total_out = round(sum(a["transferred_out_base"] for a in accounts), 2)
    total_cash = round(sum(a["cash_balance_base"] for a in accounts), 2)

    if total_inflow > 0:
        cum_return = round(total_mv - total_inflow, 2)
        cum_rate = round(cum_return / total_inflow, 4)
    else:
        cum_return = total_pnl
        cum_rate = None

    # Time-Weighted Return: read pre-computed value from connector config
    # (computed during OKX sync via bills-archive realized P&L chain-linking)
    twr_rate = None
    daily_portfolio_values = []
    try:
        _configs = db.get_connector_configs()
        for cfg in _configs:
            if cfg.get("accountId") in {a["account_id"] for a in accounts}:
                if twr_rate is None and cfg.get("realizedTwr") is not None:
                    twr_rate = cfg["realizedTwr"]
                dpv = cfg.get("dailyPortfolioValues", [])
                if dpv:
                    daily_portfolio_values = dpv
    except Exception:
        pass

    # Asset category breakdown (active positions only)
    cat_map = {}
    for p in positions:
        if p["quantity"] <= 0:
            continue
        at = p["asset_type"]
        cat = cat_map.setdefault(at, {"asset_type": at, "market_value_base": 0.0, "cost_basis_base": 0.0, "unrealized_pnl_base": 0.0})
        cat["market_value_base"] += p["market_value_base"] or 0
        cat["cost_basis_base"] += p["cost_basis_base"]
        cat["unrealized_pnl_base"] += p["unrealized_pnl_base"] or 0

    categories = sorted(
        [{"weight": round(c["market_value_base"] / total_mv, 4) if total_mv > 0 else 0, **c} for c in cat_map.values()],
        key=lambda c: c["market_value_base"], reverse=True
    )

    # Current open positions cost basis:
    # - SWAP/derivative: use actual margin from OKX positions API (not inflated notional)
    # - Spot: use avg_cost × qty (actual capital deployed)
    configs = db.get_connector_configs()
    margin_map = {}  # instId -> margin USD
    for cfg in configs:
        for inst_id, pos_data in (cfg.get("openPositionsMargin") or {}).items():
            margin_map[inst_id] = pos_data.get("margin", 0)

    assets_by_id = {a["id"]: a for a in db.get_assets()}
    cost_parts = []
    for p in positions:
        if p["quantity"] <= 0 or p["avg_cost"] <= 0:
            continue
        asset = assets_by_id.get(p["asset_id"])
        inst_id = asset.get("name", "") if asset else ""
        if inst_id in margin_map:
            # Use actual margin (real capital at risk) for open SWAP/leveraged positions
            cost_parts.append(convert_amount(margin_map[inst_id], "USD", base_currency))
        else:
            cost_parts.append(convert_amount(p["avg_cost"] * p["quantity"], p["currency"], base_currency))
    total_cost_all_base = round(sum(cost_parts), 2)

    prices = db.get_prices()
    price_ts = max((p["updatedAt"] for p in prices), default="") if prices else ""

    # All positions: active (qty>0) first, then closed; within each group sort by total P&L desc
    all_positions_by_pnl = sorted(
        positions,
        key=lambda p: (0 if p["quantity"] > 0 else 1, -p["total_pnl_base"])
    )

    return {
        "base_currency": base_currency,
        "total_market_value_base": total_mv,
        "total_cost_basis_base": total_cb,
        "total_cost_all_base": total_cost_all_base,
        "total_net_inflow_base": total_inflow,
        "cumulative_return_base": cum_return,
        "cumulative_return_rate": cum_rate,
        "twr_rate": twr_rate,
        "daily_portfolio_values": daily_portfolio_values,
        "unrealized_pnl_base": total_upnl,
        "realized_pnl_base": total_rpnl,
        "total_pnl_base": total_pnl,
        "total_cash_base": total_cash,
        "price_timestamp": price_ts,
        "categories": categories,
        "accounts": accounts,
        "all_positions": all_positions_by_pnl,
    }


def build_investment_timeline(base_currency="CNY", account_id=None):
    transactions = sorted(db.get_transactions(), key=lambda t: t["executedAt"])
    if account_id:
        transactions = [t for t in transactions if t["accountId"] == account_id]

    net_inflow = 0.0
    cost_basis = 0.0
    by_date = {}
    for txn in transactions:
        amount = convert_amount(float(txn["quantity"]) * float(txn["price"]), txn["currency"], base_currency)
        fee = convert_amount(float(txn.get("fee", 0)), txn["currency"], base_currency)
        t = txn["type"]
        if t in ("deposit", "transfer_in"):
            net_inflow += amount
        elif t in ("withdrawal", "transfer_out"):
            net_inflow -= amount
        elif t == "buy":
            cost_basis += amount + fee
        elif t == "sell":
            cost_basis -= amount - fee
        date = txn["executedAt"][:10]
        by_date[date] = {"date": date, "net_inflow": round(net_inflow, 2), "cost_basis": round(cost_basis, 2)}

    return list(by_date.values())


def build_pnl_for_period(base_currency="CNY", period_days=None):
    """
    Returns realized P&L from sells within the period + current unrealized P&L.
    period_days=None means all time.
    Definition: total_period_pnl = period_realized + current_unrealized (always current, no time filter)
    """
    from datetime import datetime, timezone, timedelta
    cutoff = None
    if period_days:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=period_days)).isoformat()

    transactions = sorted(db.get_transactions(), key=lambda t: t["executedAt"])
    assets = {a["id"]: a for a in db.get_assets()}
    prices = {p["assetId"]: p for p in db.get_prices()}

    acc_map = {}
    for txn in transactions:
        key = (txn["accountId"], txn["assetId"])
        asset_obj = assets.get(txn["assetId"])
        is_deriv = asset_obj and asset_obj.get("market") in _DERIVATIVE_MARKETS
        acc = acc_map.setdefault(key, {
            "qty": 0.0, "avg_cost": 0.0, "period_realized": 0.0,
            "buy_cost_period": 0.0, "sell_proc_period": 0.0,
            "buy_cost_all": 0.0, "sell_proc_all": 0.0,
            "buy_qty_all": 0.0, "sell_qty_all": 0.0,
            "sell_qty_period": 0.0,
            "is_derivative": is_deriv,
        })
        qty = float(txn["quantity"])
        price = float(txn["price"])
        fee = float(txn.get("fee", 0))
        t = txn["type"]
        in_period = cutoff is None or txn["executedAt"] >= cutoff
        if is_deriv:
            if t == "buy":
                acc["qty"] += qty
                acc["buy_cost_all"] += qty * price + fee
                acc["buy_qty_all"] += qty
                if in_period:
                    acc["buy_cost_period"] += qty * price + fee
            elif t == "sell":
                acc["qty"] -= qty
                acc["sell_proc_all"] += qty * price - fee
                acc["sell_qty_all"] += qty
                if in_period:
                    acc["sell_proc_period"] += qty * price - fee
                    acc["sell_qty_period"] += qty
        else:
            if t == "buy":
                cost = qty * price + fee
                new_qty = acc["qty"] + qty
                acc["avg_cost"] = (acc["qty"] * acc["avg_cost"] + cost) / new_qty if new_qty > 0 else price
                acc["qty"] = new_qty
            elif t == "sell":
                pnl = qty * (price - acc["avg_cost"]) - fee
                if in_period:
                    acc["period_realized"] += pnl
                new_qty = acc["qty"] - qty
                acc["qty"] = 0.0 if new_qty < 1e-6 else max(0.0, new_qty)
            elif t in ("dividend", "interest"):
                if in_period:
                    acc["period_realized"] += qty * price

    total_period_realized = 0.0
    total_current_unrealized = 0.0
    for (account_id, asset_id), acc in acc_map.items():
        asset = assets.get(asset_id)
        if not asset:
            continue
        if acc["is_derivative"]:
            # Period P&L: use avg buy price from ALL time to cost period sells
            # No sells in period → P&L is 0 (open position, nothing realized)
            sell_qty_p = acc["sell_qty_period"]
            if sell_qty_p <= 0:
                period_pnl = 0.0
            elif acc["buy_qty_all"] > 0:
                avg_buy_per_unit = acc["buy_cost_all"] / acc["buy_qty_all"]
                period_pnl = acc["sell_proc_period"] - avg_buy_per_unit * sell_qty_p
            else:
                # Net short: use avg sell price × matched buys in period
                period_pnl = acc["sell_proc_period"] - acc["buy_cost_period"]
            total_period_realized += convert_amount(period_pnl, asset["currency"], base_currency)
            # No unrealized for derivatives (no reliable price for SWAP assets)
        else:
            total_period_realized += convert_amount(acc["period_realized"], asset["currency"], base_currency)
            pi = prices.get(asset_id)
            net_qty = acc["qty"]
            if pi and net_qty > 0:
                mv = float(pi["price"]) * net_qty
                cb = acc["avg_cost"] * net_qty
                upnl = convert_amount(mv - cb, pi["currency"], base_currency)
                total_current_unrealized += upnl

    return {
        "period_realized_pnl": round(total_period_realized, 2),
        "current_unrealized_pnl": round(total_current_unrealized, 2),
        "total_period_pnl": round(total_period_realized + total_current_unrealized, 2),
    }

import dash
from dash import html, dcc, dash_table, callback, Input, Output, State, ctx
import dash_bootstrap_components as dbc
from datetime import datetime, timezone, timedelta
from services.db import db, make_id, now_iso
from services.portfolio import build_positions

dash.register_page(__name__, path="/transactions", name="流水")


def _to_cst(iso: str) -> str:
    """Convert UTC ISO timestamp to CST (UTC+8) string."""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        cst = dt.astimezone(timezone(timedelta(hours=8)))
        return cst.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return iso[:16].replace("T", " ")

TYPE_OPTIONS = [
    {"label": "买入", "value": "buy"},
    {"label": "卖出", "value": "sell"},
    {"label": "入金", "value": "deposit"},
    {"label": "出金", "value": "withdrawal"},
    {"label": "分红", "value": "dividend"},
    {"label": "利息", "value": "interest"},
    {"label": "手续费", "value": "fee"},
    {"label": "转入", "value": "transfer_in"},
    {"label": "转出", "value": "transfer_out"},
]
TYPE_LABELS = {o["value"]: o["label"] for o in TYPE_OPTIONS}


def _fmt(val, ccy="CNY"):
    if val is None:
        return "-"
    sym = "¥" if ccy == "CNY" else "$"
    return f"{sym}{float(val):,.4f}".rstrip("0").rstrip(".")


def layout(**kwargs):
    accounts = db.get_accounts()
    acct_options = [{"label": a["name"], "value": a["id"]} for a in accounts]

    return html.Div([
        dcc.Store(id="txn-version", data=0),

        html.Div([
            html.H4("交易流水", style={"fontWeight": 700, "margin": 0}),
            dbc.Button("+ 新增", id="open-add-txn", color="primary", size="sm"),
        ], style={"display": "flex", "justifyContent": "space-between", "alignItems": "center", "marginBottom": 16}),

        # Add transaction modal
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle("新增交易")),
            dbc.ModalBody([
                dbc.Row([
                    dbc.Col([
                        dbc.Label("账户"),
                        dbc.Select(id="txn-acct", options=acct_options,
                                   value=acct_options[0]["value"] if acct_options else None),
                    ], width=6, className="mb-3"),
                    dbc.Col([
                        dbc.Label("类型"),
                        dbc.Select(id="txn-type", options=TYPE_OPTIONS, value="buy"),
                    ], width=6, className="mb-3"),
                ]),
                dbc.Row([
                    dbc.Col([
                        dbc.Label("资产代码"),
                        dbc.Input(id="txn-symbol", placeholder="如 BTC, 600519"),
                    ], width=4, className="mb-3"),
                    dbc.Col([
                        dbc.Label("数量"),
                        dbc.Input(id="txn-qty", type="number", placeholder="0", min=0),
                    ], width=4, className="mb-3"),
                    dbc.Col([
                        dbc.Label("价格"),
                        dbc.Input(id="txn-price", type="number", placeholder="0", min=0),
                    ], width=4, className="mb-3"),
                ]),
                dbc.Row([
                    dbc.Col([
                        dbc.Label("手续费"),
                        dbc.Input(id="txn-fee", type="number", value=0, min=0),
                    ], width=4, className="mb-3"),
                    dbc.Col([
                        dbc.Label("货币"),
                        dbc.Select(id="txn-ccy", options=[
                            {"label": "CNY", "value": "CNY"},
                            {"label": "USD", "value": "USD"},
                        ], value="CNY"),
                    ], width=4, className="mb-3"),
                    dbc.Col([
                        dbc.Label("时间"),
                        dbc.Input(id="txn-time", type="datetime-local",
                                  value=datetime.now().strftime("%Y-%m-%dT%H:%M")),
                    ], width=4, className="mb-3"),
                ]),
                dbc.Row([
                    dbc.Col([
                        dbc.Label("备注（可选）"),
                        dbc.Input(id="txn-note", placeholder="备注说明"),
                    ], width=12, className="mb-1"),
                ]),
                html.Div(id="add-txn-error", style={"color": "var(--negative)", "fontSize": 12, "marginTop": 8}),
            ]),
            dbc.ModalFooter([
                dbc.Button("提交", id="submit-add-txn", color="primary"),
                dbc.Button("取消", id="cancel-add-txn", color="secondary", outline=True),
            ]),
        ], id="add-txn-modal", is_open=False),

        html.Div(id="txn-table-content"),
    ])


@callback(
    Output("add-txn-modal", "is_open"),
    Input("open-add-txn", "n_clicks"),
    Input("cancel-add-txn", "n_clicks"),
    Input("submit-add-txn", "n_clicks"),
    State("txn-symbol", "value"),
    State("txn-qty", "value"),
    State("txn-price", "value"),
    State("add-txn-modal", "is_open"),
    prevent_initial_call=True,
)
def toggle_txn_modal(open_c, cancel_c, submit_c, symbol, qty, price, is_open):
    trigger = ctx.triggered_id
    if trigger == "open-add-txn":
        return True
    if trigger == "cancel-add-txn":
        return False
    if trigger == "submit-add-txn":
        if symbol and qty is not None and price is not None:
            return False
    return is_open


@callback(
    Output("txn-version", "data"),
    Output("add-txn-error", "children"),
    Input("submit-add-txn", "n_clicks"),
    State("txn-acct", "value"),
    State("txn-type", "value"),
    State("txn-symbol", "value"),
    State("txn-qty", "value"),
    State("txn-price", "value"),
    State("txn-fee", "value"),
    State("txn-ccy", "value"),
    State("txn-time", "value"),
    State("txn-note", "value"),
    State("txn-version", "data"),
    prevent_initial_call=True,
)
def submit_transaction(n, acct_id, txn_type, symbol, qty, price, fee, ccy, time_str, note, version):
    if not all([acct_id, txn_type, symbol, qty is not None, price is not None]):
        return version, "请填写所有必填字段（账户、类型、代码、数量、价格）"
    if float(qty) < 0 or float(price) < 0:
        return version, "数量和价格不能为负数"

    # Find or create asset
    assets = db.get_assets()
    sym = symbol.strip().upper()
    asset = next((a for a in assets if a["symbol"] == sym), None)
    if not asset:
        # Infer type from txn type and symbol
        asset_type = "crypto" if ccy == "USD" else "stock"
        currency = ccy or "CNY"
        asset = db.ensure_asset(asset_type, sym, sym, "MANUAL", currency)

    # Parse time
    try:
        if time_str:
            dt = datetime.fromisoformat(time_str)
            executed_at = dt.astimezone(timezone.utc).isoformat()
        else:
            executed_at = now_iso()
    except Exception:
        executed_at = now_iso()

    db.add_transaction({
        "id": make_id("txn"),
        "accountId": acct_id,
        "assetId": asset["id"],
        "type": txn_type,
        "quantity": float(qty),
        "price": float(price),
        "fee": float(fee or 0),
        "currency": ccy or "CNY",
        "executedAt": executed_at,
        "note": note or "",
    })
    return (version or 0) + 1, ""


@callback(
    Output("txn-version", "data", allow_duplicate=True),
    Input({"type": "del-txn", "index": dash.ALL}, "n_clicks"),
    State("txn-version", "data"),
    prevent_initial_call=True,
)
def delete_txn(n_clicks_list, version):
    if not any(n for n in (n_clicks_list or []) if n):
        return version
    triggered = ctx.triggered_id
    if triggered and isinstance(triggered, dict):
        db.delete_transaction(triggered["index"])
    return (version or 0) + 1


@callback(
    Output("txn-table-content", "children"),
    Input("txn-version", "data"),
)
def refresh_txns(version):
    transactions = sorted(db.get_transactions(), key=lambda t: t["executedAt"], reverse=True)
    assets = {a["id"]: a for a in db.get_assets()}
    accounts = {a["id"]: a for a in db.get_accounts()}

    rows = []
    for txn in transactions:
        asset = assets.get(txn["assetId"])
        account = accounts.get(txn["accountId"])
        ccy = txn.get("currency", "CNY")
        rows.append({
            "id": txn["id"],
            "time": _to_cst(txn["executedAt"]),
            "account": account["name"] if account else txn["accountId"],
            "symbol": asset["symbol"] if asset else txn["assetId"],
            "type": TYPE_LABELS.get(txn["type"], txn["type"]),
            "qty": f"{float(txn['quantity']):,.4f}".rstrip("0").rstrip("."),
            "price": _fmt(txn["price"], ccy),
            "fee": _fmt(txn["fee"], ccy),
            "note": txn.get("note", ""),
        })

    # Build delete buttons outside the table
    delete_buttons = [
        html.Td(
            dbc.Button("删除", id={"type": "del-txn", "index": r["id"]},
                       color="danger", outline=True, size="sm",
                       style={"fontSize": 11, "padding": "2px 8px"}),
            style={"padding": "6px 8px", "verticalAlign": "middle"}
        )
        for r in rows
    ]

    table = html.Table([
        html.Thead(html.Tr([
            html.Th(h, style={"padding": "8px 12px", "fontSize": 11, "fontWeight": 600,
                               "textTransform": "uppercase", "letterSpacing": "0.3px",
                               "color": "var(--ink-2)", "borderBottom": "1px solid var(--line)",
                               "background": "var(--bg)", "whiteSpace": "nowrap"})
            for h in ["时间", "账户", "标的", "类型", "数量", "价格", "费用", "备注", ""]
        ])),
        html.Tbody([
            html.Tr([
                html.Td(r["time"], style={"padding": "8px 12px", "fontSize": 12, "borderBottom": "1px solid var(--line)", "whiteSpace": "nowrap"}),
                html.Td(r["account"], style={"padding": "8px 12px", "fontSize": 12, "borderBottom": "1px solid var(--line)"}),
                html.Td(r["symbol"], style={"padding": "8px 12px", "fontSize": 12, "borderBottom": "1px solid var(--line)", "fontWeight": 500}),
                html.Td(r["type"], style={"padding": "8px 12px", "fontSize": 12, "borderBottom": "1px solid var(--line)"}),
                html.Td(r["qty"], style={"padding": "8px 12px", "fontSize": 12, "borderBottom": "1px solid var(--line)"}),
                html.Td(r["price"], style={"padding": "8px 12px", "fontSize": 12, "borderBottom": "1px solid var(--line)"}),
                html.Td(r["fee"], style={"padding": "8px 12px", "fontSize": 12, "borderBottom": "1px solid var(--line)"}),
                html.Td(r["note"], style={"padding": "8px 12px", "fontSize": 12, "borderBottom": "1px solid var(--line)", "color": "var(--ink-2)"}),
                delete_buttons[i],
            ])
            for i, r in enumerate(rows)
        ]),
    ], style={"width": "100%", "borderCollapse": "collapse"})

    return html.Div([
        html.Div([
            html.Div([
                html.H6("交易记录", className="panel-title"),
                html.Span(f"{len(rows)} 条", className="panel-sub"),
            ], className="panel-heading"),
            html.Div(table, style={"overflowX": "auto"}),
        ], className="panel"),
    ])

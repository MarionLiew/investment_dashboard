import dash
from dash import html, dcc, callback, Input, Output, State, ctx
import dash_bootstrap_components as dbc
from services.portfolio import build_account_performance
from services.db import db, make_id, now_iso

dash.register_page(__name__, path="/accounts", name="账户")

SOURCE_LABELS = {"manual": "手动", "okx": "OKX", "broker": "券商", "fund_platform": "基金平台"}


def _fmt(val, ccy):
    if val is None:
        return "-"
    sym = "¥" if ccy == "CNY" else "$"
    return f"{sym}{val:,.2f}"


def _pct(rate):
    if rate is None:
        return "-"
    sign = "+" if rate >= 0 else ""
    return f"{sign}{rate * 100:.2f}%"


def _build_account_cards(accounts_perf):
    if not accounts_perf:
        return html.P("还没有账户，点击右上角新建。", style={"color": "var(--ink-2)", "fontSize": 13})
    cards = []
    for a in accounts_perf:
        ccy = a["base_currency"]
        is_pos = a["cumulative_return_base"] >= 0
        color = "var(--positive)" if is_pos else "var(--negative)"
        cards.append(
            dbc.Col(html.Div([
                html.Div([
                    html.Div([
                        html.P(SOURCE_LABELS.get(a["source_type"], a["source_type"]), className="account-eyebrow"),
                        html.P(a["account_name"], className="account-name"),
                    ]),
                    html.Div([
                        dbc.Button("删除", id={"type": "delete-acct", "index": a["account_id"]},
                                   color="danger", outline=True, size="sm"),
                    ]),
                ], style={"display": "flex", "justifyContent": "space-between"}),
                html.Dl([
                    html.Div([html.Dt("账户净值"), html.Dd(_fmt(a["market_value_base"], ccy))], className="account-stat"),
                    html.Div([
                        html.Dt("累计收益"),
                        html.Dd([
                            html.Span(_fmt(a["cumulative_return_base"], ccy), style={"color": color}),
                            html.Span(f" {_pct(a['cumulative_return_rate'])}", style={"color": color, "fontSize": 11}),
                        ]),
                    ], className="account-stat"),
                    html.Div([html.Dt("现金余额"), html.Dd(_fmt(a["cash_balance_base"], ccy))], className="account-stat"),
                    html.Div([html.Dt("累计净投入"), html.Dd(_fmt(a["total_net_inflow_base"], ccy))], className="account-stat"),
                    html.Div([html.Dt("浮盈亏"), html.Dd(
                        html.Span(_fmt(a["unrealized_pnl_base"], ccy),
                                  style={"color": "var(--positive)" if a["unrealized_pnl_base"] >= 0 else "var(--negative)"}),
                    )], className="account-stat"),
                    html.Div([
                        html.Dt("最近同步"),
                        html.Dd(a["last_synced_at"][:10] if a.get("last_synced_at") else "手动账户", style={"fontSize": 12}),
                    ], className="account-stat"),
                ], className="account-stats"),
            ], className="account-card"), width=6)
        )
    return dbc.Row(cards, className="g-3")


def layout(**kwargs):
    return html.Div([
        dcc.Store(id="acct-version", data=0),

        html.Div([
            html.H4("账户管理", style={"fontWeight": 700, "margin": 0}),
            dbc.Button("+ 新建账户", id="open-add-acct", color="primary", size="sm"),
        ], style={"display": "flex", "justifyContent": "space-between", "alignItems": "center", "marginBottom": 16}),

        # Add account modal
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle("新建账户")),
            dbc.ModalBody([
                dbc.Row([
                    dbc.Col([
                        dbc.Label("账户名称"),
                        dbc.Input(id="new-acct-name", placeholder="如：招商证券、长桥美股"),
                    ], width=12, className="mb-3"),
                    dbc.Col([
                        dbc.Label("账户类型"),
                        dbc.Select(id="new-acct-type", options=[
                            {"label": "手动", "value": "manual"},
                            {"label": "OKX", "value": "okx"},
                            {"label": "券商", "value": "broker"},
                            {"label": "基金平台", "value": "fund_platform"},
                        ], value="manual"),
                    ], width=6, className="mb-3"),
                    dbc.Col([
                        dbc.Label("计价货币"),
                        dbc.Select(id="new-acct-ccy", options=[
                            {"label": "CNY", "value": "CNY"},
                            {"label": "USD", "value": "USD"},
                        ], value="CNY"),
                    ], width=6, className="mb-3"),
                ]),
                html.Div(id="add-acct-error", style={"color": "var(--negative)", "fontSize": 12}),
            ]),
            dbc.ModalFooter([
                dbc.Button("创建", id="submit-add-acct", color="primary"),
                dbc.Button("取消", id="cancel-add-acct", color="secondary", outline=True),
            ]),
        ], id="add-acct-modal", is_open=False),

        html.Div(id="accounts-content"),
    ])


# Open / close modal
@callback(
    Output("add-acct-modal", "is_open"),
    Input("open-add-acct", "n_clicks"),
    Input("cancel-add-acct", "n_clicks"),
    Input("submit-add-acct", "n_clicks"),
    State("new-acct-name", "value"),
    State("add-acct-modal", "is_open"),
    prevent_initial_call=True,
)
def toggle_modal(open_c, cancel_c, submit_c, name, is_open):
    trigger = ctx.triggered_id
    if trigger == "open-add-acct":
        return True
    if trigger == "cancel-add-acct":
        return False
    if trigger == "submit-add-acct" and name and name.strip():
        return False
    return is_open


# Create account
@callback(
    Output("acct-version", "data"),
    Output("add-acct-error", "children"),
    Input("submit-add-acct", "n_clicks"),
    State("new-acct-name", "value"),
    State("new-acct-type", "value"),
    State("new-acct-ccy", "value"),
    State("acct-version", "data"),
    prevent_initial_call=True,
)
def create_account(n, name, source, ccy, version):
    if not name or not name.strip():
        return version, "请填写账户名称"
    db.add_account({
        "id": make_id("acct"),
        "sourceType": source or "manual",
        "name": name.strip(),
        "baseCurrency": ccy or "CNY",
        "status": "active",
        "updatedAt": now_iso(),
    })
    return (version or 0) + 1, ""


# Delete account
@callback(
    Output("acct-version", "data", allow_duplicate=True),
    Input({"type": "delete-acct", "index": dash.ALL}, "n_clicks"),
    State("acct-version", "data"),
    prevent_initial_call=True,
)
def delete_account(n_clicks_list, version):
    if not any(n for n in (n_clicks_list or []) if n):
        return version
    triggered = ctx.triggered_id
    if triggered and isinstance(triggered, dict):
        db.delete_account(triggered["index"])
    return (version or 0) + 1


# Refresh account list
@callback(
    Output("accounts-content", "children"),
    Input("acct-version", "data"),
)
def refresh_accounts(version):
    perfs = build_account_performance("CNY")
    return html.Div([
        html.Div([
            html.Div([
                html.H6("账户表现", className="panel-title"),
                html.Span(f"{len(perfs)} 个账户（均以 CNY 折算）", className="panel-sub"),
            ], className="panel-heading"),
            _build_account_cards(perfs),
        ], className="panel"),
    ])

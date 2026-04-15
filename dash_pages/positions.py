import dash
from dash import html, dcc, dash_table, callback, Input, Output
import dash_bootstrap_components as dbc
from services.portfolio import build_positions
from services.db import db

dash.register_page(__name__, path="/positions", name="持仓")

ASSET_LABELS = {"stock": "股票", "fund": "基金", "crypto": "加密", "cash": "现金"}
TYPE_COLORS = {"stock": "#0071e3", "fund": "#8e44ad", "crypto": "#f5a623", "cash": "#6e6e73"}


def _fmt(val, ccy="CNY"):
    if val is None:
        return "-"
    sym = "¥" if ccy == "CNY" else "$"
    return f"{sym}{val:,.2f}"


def _pct(rate):
    if rate is None:
        return "-"
    sign = "+" if rate >= 0 else ""
    return f"{sign}{rate * 100:.2f}%"


def _color(val):
    if val is None or val == 0:
        return "var(--ink)"
    return "var(--positive)" if val > 0 else "var(--negative)"


def layout(**kwargs):
    accounts = db.get_accounts()
    acct_options = [{"label": "全部账户", "value": "all"}] + [
        {"label": a["name"], "value": a["id"]} for a in accounts
    ]
    type_options = [{"label": "全部类型", "value": "all"},
                    {"label": "股票", "value": "stock"},
                    {"label": "基金", "value": "fund"},
                    {"label": "加密", "value": "crypto"},
                    {"label": "现金", "value": "cash"}]
    ccy_options = [{"label": "CNY", "value": "CNY"}, {"label": "USD", "value": "USD"}]

    return html.Div([
        html.Div([
            html.H4("持仓明细", style={"fontWeight": 700, "margin": 0}),
            html.Div([
                dcc.Dropdown(acct_options, "all", id="pos-acct-filter",
                             clearable=False, style={"width": 160, "fontSize": 13}),
                dcc.Dropdown(type_options, "all", id="pos-type-filter",
                             clearable=False, style={"width": 130, "fontSize": 13}),
                dcc.Dropdown(ccy_options, "CNY", id="pos-ccy",
                             clearable=False, style={"width": 90, "fontSize": 13}),
            ], style={"display": "flex", "gap": 8}),
        ], style={"display": "flex", "justifyContent": "space-between",
                  "alignItems": "center", "marginBottom": 16}),

        html.Div(id="positions-content"),
    ])


@callback(
    Output("positions-content", "children"),
    Input("pos-acct-filter", "value"),
    Input("pos-type-filter", "value"),
    Input("pos-ccy", "value"),
)
def update_positions(acct_filter, type_filter, ccy):
    positions = build_positions(ccy or "CNY")
    if acct_filter and acct_filter != "all":
        positions = [p for p in positions if p["account_id"] == acct_filter]
    if type_filter and type_filter != "all":
        positions = [p for p in positions if p["asset_type"] == type_filter]

    active = [p for p in positions if p["quantity"] > 0]
    closed = [p for p in positions if p["quantity"] <= 0 and p["sold_quantity"] > 0]

    # Summary stats
    total_mv = sum(p["market_value_base"] or 0 for p in active)
    total_upnl = sum(p["unrealized_pnl_base"] or 0 for p in active)
    total_rpnl = sum(p["realized_pnl_base"] for p in closed)
    total_pnl = sum(p["total_pnl_base"] for p in positions)

    winners = [p for p in closed if p["realized_pnl_base"] > 0]
    losers = [p for p in closed if p["realized_pnl_base"] < 0]
    win_rate = len(winners) / len(closed) if closed else None

    def _stat(label, val, color=None):
        return html.Div([
            html.Span(label, style={"fontSize": 11, "color": "var(--ink-2)", "display": "block"}),
            html.Span(val, style={"fontSize": 14, "fontWeight": 600,
                                   "color": color or "var(--ink)"}),
        ], style={"marginRight": 24})

    summary_bar = html.Div([
        _stat("持仓市值", _fmt(total_mv, ccy)),
        _stat("浮盈亏", _fmt(total_upnl, ccy), "var(--positive)" if total_upnl >= 0 else "var(--negative)"),
        _stat("已实现盈亏", _fmt(total_rpnl, ccy), "var(--positive)" if total_rpnl >= 0 else "var(--negative)"),
        _stat("综合盈亏", _fmt(total_pnl, ccy), "var(--positive)" if total_pnl >= 0 else "var(--negative)"),
        _stat("胜率（已清仓）", f"{win_rate * 100:.0f}%  ({len(winners)}胜{len(losers)}负)" if win_rate is not None else "-"),
    ], style={"display": "flex", "flexWrap": "wrap", "padding": "12px 0", "marginBottom": 8})

    def make_table(rows, show_closed=False):
        if not rows:
            return html.P("暂无数据", style={"color": "var(--ink-2)", "fontSize": 13})

        cols = [
            {"name": "标的", "id": "symbol"},
            {"name": "账户", "id": "account_name"},
        ]
        if not show_closed:
            cols += [
                {"name": "数量", "id": "quantity"},
                {"name": "均价", "id": "avg_cost"},
                {"name": "成本", "id": "cost_basis_base"},
                {"name": "现价", "id": "latest_price"},
                {"name": "市值", "id": "market_value_base"},
                {"name": "浮盈亏", "id": "unrealized_pnl"},
                {"name": "已实现", "id": "realized_pnl_base"},
                {"name": "综合盈亏", "id": "total_pnl_base"},
            ]
        else:
            cols += [
                {"name": "已卖数量", "id": "sold_quantity"},
                {"name": "已实现盈亏", "id": "realized_pnl_base"},
            ]

        data = []
        styles = []
        for i, p in enumerate(rows):
            row = {
                "symbol": f"{p['symbol']}  {p['name']}",
                "account_name": p["account_name"],
                "quantity": f"{p['quantity']:,.4f}",
                "avg_cost": _fmt(p["avg_cost"], p["currency"]),
                "cost_basis_base": _fmt(p["cost_basis_base"], ccy),
                "latest_price": _fmt(p["latest_price"], p["latest_price_currency"] or p["currency"]) if p["latest_price"] else "无行情",
                "market_value_base": _fmt(p["market_value_base"], ccy) if p["market_value_base"] is not None else "-",
                "unrealized_pnl": (
                    f"{_fmt(p['unrealized_pnl_base'], ccy)}  {_pct(p['unrealized_pnl_rate'])}"
                    if p["unrealized_pnl_base"] is not None else "-"
                ),
                "realized_pnl_base": _fmt(p["realized_pnl_base"], ccy),
                "total_pnl_base": _fmt(p["total_pnl_base"], ccy),
                "sold_quantity": f"{p['sold_quantity']:,.4f}",
            }
            data.append(row)

            upnl = p.get("unrealized_pnl_base")
            rpnl = p.get("realized_pnl_base", 0)
            tpnl = p.get("total_pnl_base", 0)

            for col_id, val in [("unrealized_pnl", upnl), ("realized_pnl_base", rpnl), ("total_pnl_base", tpnl)]:
                if val is not None and val > 0:
                    styles.append({"if": {"row_index": i, "column_id": col_id}, "color": "var(--positive)"})
                elif val is not None and val < 0:
                    styles.append({"if": {"row_index": i, "column_id": col_id}, "color": "var(--negative)"})

        return dash_table.DataTable(
            columns=cols,
            data=data,
            style_table={"overflowX": "auto"},
            style_cell={"textAlign": "left", "padding": "8px 12px",
                        "fontFamily": "inherit", "fontSize": 12, "border": "none"},
            style_header={"backgroundColor": "var(--bg)", "fontWeight": "600", "fontSize": 11,
                          "textTransform": "uppercase", "letterSpacing": "0.3px",
                          "border": "none", "borderBottom": "1px solid var(--line)"},
            style_data={"borderBottom": "1px solid var(--line)"},
            style_data_conditional=styles,
            page_size=50,
        )

    sections = [
        html.Div([
            html.Div(summary_bar),
        ], className="panel"),

        html.Div([
            html.Div([
                html.H6("活跃持仓", className="panel-title"),
                html.Span(f"{len(active)} 个标的", className="panel-sub"),
            ], className="panel-heading"),
            make_table(active),
        ], className="panel"),
    ]

    if closed:
        sections.append(
            html.Div([
                html.Div([
                    html.H6("已清仓", className="panel-title"),
                    html.Span(f"{len(closed)} 个标的  已实现盈亏 {_fmt(total_rpnl, ccy)}",
                              className="panel-sub",
                              style={"color": "var(--positive)" if total_rpnl >= 0 else "var(--negative)"}),
                ], className="panel-heading"),
                make_table(closed, show_closed=True),
            ], className="panel")
        )

    return html.Div(sections)

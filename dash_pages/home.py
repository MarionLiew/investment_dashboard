import dash
from dash import html, dcc, callback, Input, Output, ctx
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from datetime import datetime, timezone, timedelta
from services.portfolio import build_portfolio_summary, build_investment_timeline, build_pnl_for_period

dash.register_page(__name__, path="/", name="总览")

ASSET_LABELS = {"stock": "股票", "fund": "基金", "crypto": "加密", "cash": "现金"}

PERIODS = [
    ("1D", 1),
    ("1W", 7),
    ("1M", 30),
    ("6M", 180),
    ("1Y", 365),
    ("全部", None),
]
PERIOD_LABELS = {1: "近1日", 7: "近1周", 30: "近1月", 180: "近半年", 365: "近1年", None: "全部"}


def _fmt(amount, ccy):
    if amount is None:
        return "-"
    return f"¥{amount:,.2f}" if ccy == "CNY" else f"${amount:,.2f}"


def _pct(rate):
    if rate is None:
        return ""
    sign = "+" if rate >= 0 else ""
    return f"{sign}{rate * 100:.2f}%"


def _color(val):
    if val is None:
        return "var(--ink)"
    if val > 0:
        return "var(--positive)"
    if val < 0:
        return "var(--negative)"
    return "var(--ink)"


def _period_selector():
    buttons = []
    for label, days in PERIODS:
        btn_id = f"btn-period-{label.lower().replace('全部', 'all')}"
        buttons.append(
            dbc.Button(
                label,
                id=btn_id,
                size="sm",
                color="primary",
                outline=(days is not None),  # "全部" active by default
                style={"fontSize": 11, "padding": "2px 10px"},
            )
        )
    return html.Div(buttons, style={"display": "flex", "gap": 4})


def _build_metrics(s, pnl_data, period_days, ccy):
    # 入金合计 vs 买入成本
    has_inflow = s["total_net_inflow_base"] > 0
    inflow_val = s["total_net_inflow_base"] if has_inflow else s["total_cost_all_base"]
    inflow_label = "累计净投入" if has_inflow else "买入总成本"
    inflow_sub = "入金合计" if has_inflow else "无入金记录，显示历史买入成本"

    # 总盈亏（时段）
    total_pnl = pnl_data["total_period_pnl"]
    upnl = pnl_data["current_unrealized_pnl"]
    period_label = PERIOD_LABELS.get(period_days, "全部")
    all_time_rpnl = s.get("realized_pnl_base", pnl_data["period_realized_pnl"])
    pnl_sub = f"浮盈 {_fmt(upnl, ccy)}（持仓中）  全时段已实现 {_fmt(all_time_rpnl, ccy)}"

    all_pos = s.get("all_positions", [])
    active_pos = [p for p in all_pos if p["quantity"] > 0]
    closed_pos = [p for p in all_pos if p["quantity"] <= 0 and p["sold_quantity"] > 0]
    profitable = [p for p in all_pos if (p["total_pnl_base"] or 0) > 0]
    total_traded = len(active_pos) + len(closed_pos)
    win_rate = len(profitable) / total_traded if total_traded > 0 else None
    win_rate_sub = f"{len(profitable)} 盈 / {total_traded - len(profitable)} 亏（含清仓）" if total_traded > 0 else ""

    simple_rate = s["cumulative_return_rate"]
    twr_rate = s.get("twr_rate")
    simple_sub = "需有入金记录" if simple_rate is None else "净投入加权（绝对回报）"
    twr_sub = "需同步后计算" if twr_rate is None else "已实现盈亏链式计算（不含浮盈）"

    items = [
        ("总资产", s["total_market_value_base"], None,
         f"含现金 {_fmt(s['total_cash_base'], ccy)}", "var(--ink)"),
        (inflow_label, inflow_val, None, inflow_sub, "var(--ink)"),
        (f"总盈亏（{period_label}）", total_pnl, None, pnl_sub, _color(total_pnl)),
        ("累计收益率", None, simple_rate, simple_sub, _color(simple_rate)),
        ("时间加权收益率", None, twr_rate, twr_sub, _color(twr_rate)),
        ("持仓资产数", len(active_pos), None,
         f"已清仓 {len(closed_pos)} 个",
         "var(--ink)"),
        ("胜率", None, win_rate, win_rate_sub, _color(win_rate)),
    ]

    cards = []
    for label, val, rate, sub, color in items:
        if rate is not None:
            display = html.Div(_pct(rate), className="metric-value", style={"color": color})
        elif isinstance(val, int):
            display = html.Div(str(val), className="metric-value",
                               style={"color": color, "fontSize": 28})
        else:
            display = html.Div(_fmt(val, ccy), className="metric-value", style={"color": color})
        cards.append(
            html.Div([
                html.Div(label, className="metric-label"),
                display,
                html.Div(sub or "", className="metric-sub", style={"color": "var(--ink-2)"}),
            ], className="metric-card")
        )
    return html.Div(cards, className="metrics-row")


def _build_account_bars(accounts, ccy):
    if not accounts:
        return html.P("暂无账户", style={"color": "var(--ink-2)", "fontSize": 13})
    rows = []
    total_mv = sum(a["market_value_base"] for a in accounts) or 1
    for a in accounts:
        mv = a["market_value_base"]
        pnl = a["total_pnl_base"]
        rate = a["cumulative_return_rate"]
        is_pos = pnl >= 0
        bar_w = min(100, abs(mv) / total_mv * 100)
        color = "var(--positive)" if is_pos else "var(--negative)"
        rate_str = _pct(rate) if rate is not None else (("+" if is_pos else "") + _fmt(abs(pnl), ccy))
        rows.append(html.Div([
            html.Div([
                html.Span(a["account_name"], style={"fontWeight": 500}),
                html.Span([
                    html.Span(f"净值 {_fmt(mv, ccy)}", style={"color": "var(--ink-2)", "marginRight": 12}),
                    html.Span(rate_str, style={"color": color, "fontWeight": 600}),
                ]),
            ], className="return-bar-info"),
            html.Div(
                html.Div(style={"height": "100%", "width": f"{bar_w}%",
                                "background": color, "opacity": 0.7, "borderRadius": 4}),
                className="return-bar-track"
            ),
            html.Div([
                html.Span(f"浮盈亏 {_fmt(a['unrealized_pnl_base'], ccy)}",
                          style={"color": _color(a["unrealized_pnl_base"])}),
                html.Span(f"已实现 {_fmt(a['realized_pnl_base'], ccy)}",
                          style={"color": _color(a["realized_pnl_base"])}),
            ], className="return-bar-details"),
        ], className="return-bar-row"))
    return html.Div(rows)


def _build_positions_pnl_table(positions, ccy):
    if not positions:
        return html.P("暂无持仓数据", style={"color": "var(--ink-2)", "fontSize": 13})

    rows = []
    for p in positions:
        is_active = p["quantity"] > 0
        total_pnl = p["total_pnl_base"]
        upnl = p["unrealized_pnl_base"]
        rpnl = p["realized_pnl_base"]
        rate = p["unrealized_pnl_rate"]

        status_badge = html.Span(
            "持仓中" if is_active else "已清仓",
            style={
                "fontSize": 10, "padding": "1px 6px", "borderRadius": 10,
                "background": "var(--positive)" if is_active else "var(--line)",
                "color": "white" if is_active else "var(--ink-2)",
                "marginLeft": 6,
            }
        )

        rows.append(html.Tr([
            html.Td([
                html.Span(p["symbol"], style={"fontWeight": 600, "fontSize": 13}),
                status_badge,
                html.Div(p["account_name"],
                         style={"fontSize": 11, "color": "var(--ink-2)", "marginTop": 1}),
            ], style={"padding": "8px 12px", "borderBottom": "1px solid var(--line)"}),
            html.Td([
                _fmt(p["market_value_base"], ccy) if is_active else "-",
                *(
                    [html.Span(" ⚠", title="价格数据过时",
                               style={"color": "#f5a623", "fontSize": 11})]
                    if is_active and p.get("stale_price") else []
                ),
            ], style={"padding": "8px 12px", "fontSize": 12,
                      "borderBottom": "1px solid var(--line)", "textAlign": "right"}),
            html.Td([
                html.Div(_fmt(upnl, ccy) if upnl is not None else "-",
                         style={"color": _color(upnl), "fontSize": 12}),
                html.Div(_pct(rate) if rate is not None else "",
                         style={"color": _color(upnl), "fontSize": 11}),
            ], style={"padding": "8px 12px", "borderBottom": "1px solid var(--line)", "textAlign": "right"}),
            html.Td(
                _fmt(rpnl, ccy),
                style={"padding": "8px 12px", "fontSize": 12, "color": _color(rpnl),
                       "borderBottom": "1px solid var(--line)", "textAlign": "right"}
            ),
            html.Td([
                html.Div(_fmt(total_pnl, ccy),
                         style={"color": _color(total_pnl), "fontWeight": 600, "fontSize": 13}),
            ], style={"padding": "8px 12px", "borderBottom": "1px solid var(--line)", "textAlign": "right"}),
        ]))

    return html.Table([
        html.Thead(html.Tr([
            html.Th(h, style={"padding": "8px 12px", "fontSize": 11, "fontWeight": 600,
                               "textTransform": "uppercase", "letterSpacing": "0.3px",
                               "color": "var(--ink-2)", "borderBottom": "1px solid var(--line)",
                               "background": "var(--bg)", "whiteSpace": "nowrap",
                               "textAlign": "right" if h != "标的" else "left"})
            for h in ["标的", "市值", "浮盈亏", "已实现（全部）", "综合盈亏"]
        ])),
        html.Tbody(rows),
    ], style={"width": "100%", "borderCollapse": "collapse"})


def _build_allocation_chart(categories, ccy):
    if not categories:
        return None
    labels = [ASSET_LABELS.get(c["asset_type"], c["asset_type"]) for c in categories]
    values = [c["market_value_base"] for c in categories]
    colors = ["#0071e3", "#1c8a3e", "#f5a623", "#c0392b", "#8e44ad"]
    fig = go.Figure(go.Pie(
        labels=labels, values=values, hole=0.55,
        textinfo="label+percent", textfont={"size": 12},
        marker={"colors": colors[:len(labels)], "line": {"color": "white", "width": 2}},
    ))
    fig.update_layout(
        height=200, margin={"t": 8, "b": 8, "l": 8, "r": 8},
        paper_bgcolor="white", showlegend=False,
        font={"family": "-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"},
    )
    return dcc.Graph(figure=fig, config={"displayModeBar": False})


def _build_concentration_chart(positions, ccy):
    """Top 5 positions by market value as donut pie chart."""
    active = [p for p in positions if p["quantity"] > 0 and p.get("market_value_base")]
    if not active:
        return html.P("暂无持仓数据", style={"color": "var(--ink-2)", "fontSize": 13})
    top5 = sorted(active, key=lambda p: p["market_value_base"], reverse=True)[:5]
    labels = [p["symbol"] for p in top5]
    values = [p["market_value_base"] for p in top5]
    colors = ["#5b8df6", "#f5a623", "#8e44ad", "#1abc9c", "#e67e22"]
    hover = [
        f"{p['symbol']}<br>市值: {_fmt(p['market_value_base'], ccy)}<br>"
        f"浮盈率: {_pct(p.get('unrealized_pnl_rate'))}<br>账户: {p['account_name']}"
        for p in top5
    ]
    fig = go.Figure(go.Pie(
        labels=labels,
        values=values,
        hole=0.45,
        textinfo="label+percent",
        textfont={"size": 12},
        marker={"colors": colors[:len(labels)], "line": {"color": "white", "width": 2}},
        hovertext=hover,
        hoverinfo="text",
    ))
    fig.update_layout(
        height=220,
        margin={"t": 8, "b": 8, "l": 8, "r": 8},
        paper_bgcolor="white",
        showlegend=False,
        font={"family": "-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"},
    )
    return dcc.Graph(figure=fig, config={"displayModeBar": False})


def _build_pnl_breakdown_chart(positions, ccy):
    """Stacked bar: unrealized + realized P&L by asset type."""
    cat_map = {}
    for p in positions:
        if p["quantity"] <= 0 and p["sold_quantity"] <= 0 and (p.get("realized_pnl_base") or 0) == 0:
            continue
        at = ASSET_LABELS.get(p["asset_type"], p["asset_type"])
        c = cat_map.setdefault(at, {"upnl": 0.0, "rpnl": 0.0})
        c["upnl"] += p.get("unrealized_pnl_base") or 0
        c["rpnl"] += p.get("realized_pnl_base") or 0
    if not cat_map:
        return None
    cats = list(cat_map.keys())
    upnls = [cat_map[c]["upnl"] for c in cats]
    rpnls = [cat_map[c]["rpnl"] for c in cats]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="浮盈亏", x=cats, y=upnls,
        marker_color=["#1c8a3e" if v >= 0 else "#c0392b" for v in upnls],
        hovertemplate="%{x}<br>浮盈亏: %{y:,.2f}<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        name="已实现", x=cats, y=rpnls,
        marker_color=["rgba(28,138,62,0.45)" if v >= 0 else "rgba(192,57,43,0.45)" for v in rpnls],
        hovertemplate="%{x}<br>已实现: %{y:,.2f}<extra></extra>",
    ))
    fig.update_layout(
        barmode="group", height=200,
        margin={"t": 8, "b": 8, "l": 48, "r": 8},
        paper_bgcolor="white", plot_bgcolor="white",
        legend={"font": {"size": 11}, "orientation": "h", "y": -0.18},
        xaxis={"tickfont": {"size": 12}},
        yaxis={"showgrid": True, "gridcolor": "#e5e5ea", "tickfont": {"size": 11},
               "zeroline": True, "zerolinecolor": "#e5e5ea"},
        font={"family": "-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"},
    )
    return dcc.Graph(figure=fig, config={"displayModeBar": False})


def _build_return_history_chart(daily_values):
    """Line chart of cumulative return rate over time (from realized P&L)."""
    if not daily_values:
        return html.P("暂无历史数据（请先同步 OKX）",
                      style={"color": "var(--ink-2)", "fontSize": 13})
    pts = [d for d in daily_values if d.get("returnRate") is not None]
    if not pts:
        return html.P("暂无收益率数据", style={"color": "var(--ink-2)", "fontSize": 13})
    dates = [p["date"] for p in pts]
    rates = [round(p["returnRate"] * 100, 2) for p in pts]
    colors = ["#1c8a3e" if r >= 0 else "#c0392b" for r in rates]
    # Single color line; shade area positive/negative
    pos_fill = [r if r >= 0 else 0 for r in rates]
    neg_fill = [r if r < 0 else 0 for r in rates]
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates, y=pos_fill, name="盈利",
        mode="none", fill="tozeroy",
        fillcolor="rgba(28,138,62,0.15)", showlegend=False,
    ))
    fig.add_trace(go.Scatter(
        x=dates, y=neg_fill, name="亏损",
        mode="none", fill="tozeroy",
        fillcolor="rgba(192,57,43,0.15)", showlegend=False,
    ))
    fig.add_trace(go.Scatter(
        x=dates, y=rates, name="收益率",
        mode="lines",
        line={"color": "#0071e3", "width": 2},
        hovertemplate="%{x}<br>收益率: %{y:.2f}%<extra></extra>",
    ))
    fig.add_hline(y=0, line_dash="dot", line_color="#aaa", line_width=1)
    _rs_buttons = [
        {"count": 7,  "label": "1W", "step": "day",   "stepmode": "backward"},
        {"count": 1,  "label": "1M", "step": "month", "stepmode": "backward"},
        {"count": 3,  "label": "3M", "step": "month", "stepmode": "backward"},
        {"step": "all", "label": "全部"},
    ]
    fig.update_layout(
        height=240, margin={"t": 36, "b": 8, "l": 48, "r": 8},
        paper_bgcolor="white", plot_bgcolor="white",
        showlegend=False,
        dragmode=False,
        xaxis={
            "showgrid": True, "gridcolor": "#e5e5ea",
            "tickfont": {"size": 11}, "zeroline": False,
            "rangeselector": {
                "buttons": _rs_buttons,
                "bgcolor": "#f5f5f7", "activecolor": "#0071e3",
                "bordercolor": "#e5e5ea", "borderwidth": 1,
                "font": {"size": 11, "color": "#1d1d1f"},
                "x": 0, "y": 1.12,
            },
            "rangeslider": {"visible": False},
        },
        yaxis={"showgrid": True, "gridcolor": "#e5e5ea",
               "tickfont": {"size": 11}, "ticksuffix": "%", "zeroline": False},
        font={"family": "-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"},
        hovermode="x unified",
    )
    return dcc.Graph(figure=fig, config={"displayModeBar": False, "scrollZoom": False})


def _build_timeline_chart(points, ccy):
    if not points:
        return html.P("暂无交易数据（需要入金记录）",
                      style={"color": "var(--ink-2)", "fontSize": 13})
    dates = [p["date"] for p in points]
    inflow = [p["net_inflow"] for p in points]
    cost = [p["cost_basis"] for p in points]
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates, y=inflow, name="累计投入",
        mode="lines", line={"color": "#0071e3", "width": 2},
        fill="tozeroy", fillcolor="rgba(0,113,227,0.08)",
    ))
    fig.add_trace(go.Scatter(
        x=dates, y=cost, name="已买入成本",
        mode="lines", line={"color": "#1c8a3e", "width": 2},
        fill="tozeroy", fillcolor="rgba(28,138,62,0.08)",
    ))
    _rs_buttons = [
        {"count": 7,  "label": "1W", "step": "day",   "stepmode": "backward"},
        {"count": 1,  "label": "1M", "step": "month", "stepmode": "backward"},
        {"count": 3,  "label": "3M", "step": "month", "stepmode": "backward"},
        {"step": "all", "label": "全部"},
    ]
    fig.update_layout(
        height=220, margin={"t": 36, "b": 8, "l": 48, "r": 8},
        paper_bgcolor="white", plot_bgcolor="white",
        legend={"font": {"size": 11}, "orientation": "h", "y": -0.18},
        dragmode=False,
        xaxis={
            "showgrid": True, "gridcolor": "#e5e5ea",
            "tickfont": {"size": 11}, "zeroline": False,
            "rangeselector": {
                "buttons": _rs_buttons,
                "bgcolor": "#f5f5f7", "activecolor": "#0071e3",
                "bordercolor": "#e5e5ea", "borderwidth": 1,
                "font": {"size": 11, "color": "#1d1d1f"},
                "x": 0, "y": 1.12,
            },
            "rangeslider": {"visible": False},
        },
        yaxis={"showgrid": True, "gridcolor": "#e5e5ea", "tickfont": {"size": 11},
               "zeroline": False, "tickformat": ",.0f"},
        font={"family": "-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"},
        hovermode="x unified",
    )
    return dcc.Graph(figure=fig, config={"displayModeBar": False, "scrollZoom": False})


def _mins_to_str(minutes: float) -> str:
    h = int(minutes // 60)
    m = int(minutes % 60)
    s = int((minutes * 60) % 60)
    if h > 0:
        return f"{h}小时{m}分"
    if m > 0:
        return f"{m}分{s}秒"
    return f"{s}秒"


def _market_clock_card(now_utc: datetime, tz_name: str, market_name: str, flag: str,
                        sessions: list, pre_session=None, after_session=None,
                        always_open: bool = False) -> html.Div:
    tz = timezone(timedelta(hours=8 if tz_name == "CST" else -4 if tz_name == "EDT" else -5))
    # Use proper timezone from name string
    from zoneinfo import ZoneInfo
    tz_info = ZoneInfo("Asia/Shanghai") if tz_name == "CST" else ZoneInfo("America/New_York")
    now_local = now_utc.astimezone(tz_info)
    time_str = now_local.strftime("%H:%M:%S")
    date_str = now_local.strftime("%m月%d日 %a")
    dow = now_local.weekday()  # 0=Mon
    is_weekend = dow >= 5

    if always_open:
        status_label = "24/7"
        status_color = "#1c8a3e"
        countdown_text = "全天候交易"
    elif is_weekend:
        status_label = "休市（周末）"
        status_color = "#888"
        # days until Mon
        days_to_mon = (7 - dow) % 7 or 7
        next_open = now_local.replace(hour=sessions[0][0], minute=sessions[0][1], second=0, microsecond=0)
        next_open = next_open + timedelta(days=days_to_mon)
        mins = (next_open - now_local).total_seconds() / 60
        countdown_text = f"下次开盘 {_mins_to_str(mins)}"
    else:
        h = now_local.hour + now_local.minute / 60 + now_local.second / 3600
        status_label = None
        status_color = "#888"
        countdown_text = ""

        # Check regular sessions
        for open_h, open_m, close_h, close_m in sessions:
            s_open = open_h + open_m / 60
            s_close = close_h + close_m / 60
            if s_open <= h < s_close:
                status_label = "交易中"
                status_color = "#1c8a3e"
                countdown_text = f"距收盘 {_mins_to_str((s_close - h) * 60)}"
                break

        if status_label is None and pre_session:
            po, pm, pc, pcm = pre_session
            p_open = po + pm / 60
            p_close = pc + pcm / 60
            if p_open <= h < p_close:
                status_label = "盘前交易"
                status_color = "#b8860b"
                reg_open = sessions[0][0] + sessions[0][1] / 60
                countdown_text = f"距开盘 {_mins_to_str((reg_open - h) * 60)}"

        if status_label is None and after_session:
            ao, am, ac, acm = after_session
            a_open = ao + am / 60
            a_close = ac + acm / 60
            if a_open <= h < a_close:
                status_label = "盘后交易"
                status_color = "#b8860b"
                countdown_text = f"盘后结束 {_mins_to_str((a_close - h) * 60)}"

        if status_label is None:
            # Closed - check if before first session or between sessions or after
            first_open = sessions[0][0] + sessions[0][1] / 60
            if h < first_open:
                # Check for pre-market
                status_label = "未开盘"
                status_color = "#888"
                countdown_text = f"距开盘 {_mins_to_str((first_open - h) * 60)}"
            elif len(sessions) > 1:
                # Check lunch break
                lunch_close = sessions[0][2] + sessions[0][3] / 60
                lunch_open = sessions[1][0] + sessions[1][1] / 60
                if lunch_close <= h < lunch_open:
                    status_label = "午休"
                    status_color = "#b8860b"
                    countdown_text = f"距开盘 {_mins_to_str((lunch_open - h) * 60)}"

            if status_label is None:
                status_label = "已收盘"
                status_color = "#888"
                # Next open
                next_local = now_local.replace(
                    hour=sessions[0][0], minute=sessions[0][1], second=0, microsecond=0
                ) + timedelta(days=1)
                while next_local.weekday() >= 5:
                    next_local += timedelta(days=1)
                mins = (next_local - now_local).total_seconds() / 60
                countdown_text = f"下次开盘 {_mins_to_str(mins)}"

    badge = html.Span(
        status_label,
        style={
            "fontSize": 11, "fontWeight": 600, "padding": "2px 8px",
            "borderRadius": 20,
            "background": status_color + "22",
            "color": status_color,
        }
    )
    clock_block = [] if always_open else [
        html.Div([
            html.Div(time_str, style={
                "fontSize": 22, "fontWeight": 700,
                "fontVariantNumeric": "tabular-nums", "letterSpacing": "-0.5px",
            }),
            html.Div(date_str, style={
                "fontSize": 11, "color": "var(--ink-2)", "marginTop": 1,
            }),
        ]),
    ]
    return html.Div([
        html.Div([
            html.Span(f"{flag} {market_name}", style={"fontWeight": 600, "fontSize": 14}),
            badge,
        ], style={"display": "flex", "alignItems": "center", "justifyContent": "space-between"}),
        *clock_block,
        html.Div(countdown_text, style={"fontSize": 12, "color": "var(--ink-2)"}),
    ], style={
        "flex": "1 1 160px", "padding": "12px 16px",
        "borderRadius": "var(--radius)", "border": "1px solid var(--line)",
        "background": "var(--bg)", "display": "flex", "flexDirection": "column", "gap": 6,
    })


def _cme_clock_card(now_utc: datetime) -> html.Div:
    """CME Globex commodities: Sun 18:00 – Fri 17:00 ET, with 17:00-18:00 daily break Mon-Thu."""
    from zoneinfo import ZoneInfo
    now_et = now_utc.astimezone(ZoneInfo("America/New_York"))
    time_str = now_et.strftime("%H:%M:%S")
    date_str = now_et.strftime("%m月%d日 %a")
    dow = now_et.weekday()   # 0=Mon … 6=Sun
    h = now_et.hour + now_et.minute / 60 + now_et.second / 3600

    if dow == 5:  # Saturday — full day closed
        next_open = (now_et + timedelta(days=1)).replace(hour=18, minute=0, second=0, microsecond=0)
        mins = (next_open - now_et).total_seconds() / 60
        status_label, status_color = "休市（周末）", "#888"
        countdown_text = f"下次开盘 {_mins_to_str(mins)}"

    elif dow == 6:  # Sunday
        if h < 18:
            next_open = now_et.replace(hour=18, minute=0, second=0, microsecond=0)
            mins = (next_open - now_et).total_seconds() / 60
            status_label, status_color = "休市（周末）", "#888"
            countdown_text = f"下次开盘 {_mins_to_str(mins)}"
        else:
            next_close = (now_et + timedelta(days=1)).replace(hour=17, minute=0, second=0, microsecond=0)
            mins = (next_close - now_et).total_seconds() / 60
            status_label, status_color = "交易中", "#1c8a3e"
            countdown_text = f"距收盘 {_mins_to_str(mins)}"

    elif dow == 4:  # Friday
        if h < 17:
            next_close = now_et.replace(hour=17, minute=0, second=0, microsecond=0)
            mins = (next_close - now_et).total_seconds() / 60
            status_label, status_color = "交易中", "#1c8a3e"
            countdown_text = f"距收盘 {_mins_to_str(mins)}"
        else:
            next_open = (now_et + timedelta(days=2)).replace(hour=18, minute=0, second=0, microsecond=0)
            mins = (next_open - now_et).total_seconds() / 60
            status_label, status_color = "休市（周末）", "#888"
            countdown_text = f"下次开盘 {_mins_to_str(mins)}"

    else:  # Mon-Thu (dow 0-3)
        if 17 <= h < 18:
            next_open = now_et.replace(hour=18, minute=0, second=0, microsecond=0)
            mins = (next_open - now_et).total_seconds() / 60
            status_label, status_color = "盘中休市", "#b8860b"
            countdown_text = f"恢复交易 {_mins_to_str(mins)}"
        elif h < 17:
            next_close = now_et.replace(hour=17, minute=0, second=0, microsecond=0)
            mins = (next_close - now_et).total_seconds() / 60
            status_label, status_color = "交易中", "#1c8a3e"
            countdown_text = f"距收盘 {_mins_to_str(mins)}"
        else:  # h >= 18, after break — session continues to next day 17:00
            next_close = (now_et + timedelta(days=1)).replace(hour=17, minute=0, second=0, microsecond=0)
            mins = (next_close - now_et).total_seconds() / 60
            status_label, status_color = "交易中", "#1c8a3e"
            countdown_text = f"距收盘 {_mins_to_str(mins)}"

    badge = html.Span(status_label, style={
        "fontSize": 11, "fontWeight": 600, "padding": "2px 8px",
        "borderRadius": 20, "background": status_color + "22", "color": status_color,
    })
    return html.Div([
        html.Div([
            html.Span("🏭 大宗商品", style={"fontWeight": 600, "fontSize": 14}),
            badge,
        ], style={"display": "flex", "alignItems": "center", "justifyContent": "space-between"}),
        html.Div([
            html.Div(time_str, style={
                "fontSize": 22, "fontWeight": 700,
                "fontVariantNumeric": "tabular-nums", "letterSpacing": "-0.5px",
            }),
            html.Div(f"{date_str} · 纽约时间", style={
                "fontSize": 11, "color": "var(--ink-2)", "marginTop": 1,
            }),
        ]),
        html.Div(countdown_text, style={"fontSize": 12, "color": "var(--ink-2)"}),
        html.Div("XAU · BZ · CL · NG | CME Globex", style={
            "fontSize": 10, "color": "var(--ink-2)", "marginTop": 2,
            "opacity": 0.7,
        }),
    ], style={
        "flex": "1 1 160px", "padding": "12px 16px",
        "borderRadius": "var(--radius)", "border": "1px solid var(--line)",
        "background": "var(--bg)", "display": "flex", "flexDirection": "column", "gap": 6,
    })


def _build_market_clock() -> html.Div:
    now_utc = datetime.now(timezone.utc)
    # A股 sessions: (open_h, open_m, close_h, close_m)
    cn_sessions = [(9, 30, 11, 30), (13, 0, 15, 0)]
    cn_card = _market_clock_card(now_utc, "CST", "A股", "🇨🇳", cn_sessions)
    # 美股: pre 04:00-09:30, regular 09:30-16:00, after 16:00-20:00
    us_sessions = [(9, 30, 16, 0)]
    us_pre = (4, 0, 9, 30)
    us_after = (16, 0, 20, 0)
    us_card = _market_clock_card(now_utc, "ET", "美股", "🇺🇸", us_sessions,
                                  pre_session=us_pre, after_session=us_after)
    cme_card = _cme_clock_card(now_utc)
    return html.Div([cn_card, us_card, cme_card],
                    style={"display": "flex", "gap": 12, "flexWrap": "wrap"})


def layout(**kwargs):
    return html.Div([
        dcc.Store(id="home-ccy", data="USD"),
        dcc.Store(id="pnl-period", data=None),  # None = 全部
        dcc.Interval(id="clock-tick", interval=1000, n_intervals=0),

        html.Div([
            html.Div([
                html.P("Portfolio", style={"fontSize": 11, "color": "var(--ink-2)", "margin": 0}),
                html.H4("综合投资看板", style={"margin": "4px 0", "fontWeight": 700}),
            ]),
            html.Div([
                _period_selector(),
                dbc.ButtonGroup([
                    dbc.Button("CNY", id="btn-cny", color="primary", size="sm", outline=True),
                    dbc.Button("USD", id="btn-usd", color="primary", size="sm", outline=False),
                ], style={"height": 32}),
            ], style={"display": "flex", "gap": 12, "alignItems": "center"}),
        ], style={"display": "flex", "justifyContent": "space-between",
                  "alignItems": "center", "marginBottom": 20}),

        html.Div([
            html.Div([
                html.H6("市场时间", className="panel-title"),
                html.Span("实时时钟 · 每秒刷新", className="panel-sub"),
            ], className="panel-heading"),
            html.Div(id="market-clock"),
        ], className="panel", style={"marginBottom": 16}),

        html.Div(id="home-content"),
    ])


# Period selector callback
@callback(
    Output("pnl-period", "data"),
    Output("btn-period-1d", "outline"),
    Output("btn-period-1w", "outline"),
    Output("btn-period-1m", "outline"),
    Output("btn-period-6m", "outline"),
    Output("btn-period-1y", "outline"),
    Output("btn-period-all", "outline"),
    Input("btn-period-1d", "n_clicks"),
    Input("btn-period-1w", "n_clicks"),
    Input("btn-period-1m", "n_clicks"),
    Input("btn-period-6m", "n_clicks"),
    Input("btn-period-1y", "n_clicks"),
    Input("btn-period-all", "n_clicks"),
    prevent_initial_call=True,
)
def select_period(d, w, m, sm, y, all_):
    trigger = ctx.triggered_id
    mapping = {
        "btn-period-1d": 1,
        "btn-period-1w": 7,
        "btn-period-1m": 30,
        "btn-period-6m": 180,
        "btn-period-1y": 365,
        "btn-period-all": None,
    }
    selected = mapping.get(trigger)
    # outline=True means inactive, outline=False means active
    return (selected,) + tuple(
        (days != selected) for _, days in PERIODS
    )


# Market clock callback — fires every second
@callback(
    Output("market-clock", "children"),
    Input("clock-tick", "n_intervals"),
)
def update_market_clock(_):
    return _build_market_clock()


# Main dashboard callback
@callback(
    Output("home-content", "children"),
    Output("btn-cny", "outline"),
    Output("btn-usd", "outline"),
    Output("home-ccy", "data"),
    Input("btn-cny", "n_clicks"),
    Input("btn-usd", "n_clicks"),
    Input("home-ccy", "data"),
    Input("pnl-period", "data"),
    prevent_initial_call=False,
)
def update_dashboard(n_cny, n_usd, stored_ccy, period_days):
    trigger_ctx = dash.callback_context
    ccy = stored_ccy or "USD"
    if trigger_ctx.triggered:
        trigger = trigger_ctx.triggered[0]["prop_id"]
        if "btn-usd" in trigger:
            ccy = "USD"
        elif "btn-cny" in trigger:
            ccy = "CNY"

    s = build_portfolio_summary(ccy)
    timeline = build_investment_timeline(ccy)
    pnl_data = build_pnl_for_period(ccy, period_days)
    daily_values = s.get("daily_portfolio_values", [])

    all_positions = s.get("all_positions", [])
    active_count = len([p for p in all_positions if p["quantity"] > 0])
    closed_count = len([p for p in all_positions if p["quantity"] <= 0 and p["sold_quantity"] > 0])

    allocation_chart = _build_allocation_chart(s["categories"], ccy)
    pnl_breakdown_chart = _build_pnl_breakdown_chart(all_positions, ccy)

    content = html.Div([
        _build_metrics(s, pnl_data, period_days, ccy),

        # Four panels in a 2×2 auto-height grid — each row stretches to its tallest card
        html.Div([
            # Row 1 left: 账户表现
            html.Div([
                html.Div([
                    html.H6("账户表现", className="panel-title"),
                    html.Span(f"{len(s['accounts'])} 个账户", className="panel-sub"),
                ], className="panel-heading"),
                _build_account_bars(s["accounts"], ccy),
            ], className="panel"),

            # Row 1 right: 资产配置
            html.Div([
                html.Div([
                    html.H6("资产配置", className="panel-title"),
                    html.Span(
                        f"行情 {s['price_timestamp'][:10] if s['price_timestamp'] else '-'}",
                        className="panel-sub"
                    ),
                ], className="panel-heading"),
                allocation_chart if allocation_chart is not None
                else html.P("暂无持仓行情", style={"color": "var(--ink-2)", "fontSize": 13}),
            ], className="panel"),

            # Row 2 left: 持仓集中度
            html.Div([
                html.Div([
                    html.H6("持仓集中度", className="panel-title"),
                    html.Span("Top 5 持仓市值占比", className="panel-sub"),
                ], className="panel-heading"),
                _build_concentration_chart(all_positions, ccy),
            ], className="panel"),

            # Row 2 right: 盈亏分解
            html.Div([
                html.Div([
                    html.H6("盈亏分解", className="panel-title"),
                    html.Span("按资产类别（浮盈 + 已实现）", className="panel-sub"),
                ], className="panel-heading"),
                pnl_breakdown_chart if pnl_breakdown_chart is not None
                else html.P("暂无盈亏数据", style={"color": "var(--ink-2)", "fontSize": 13}),
            ], className="panel"),
        ], className="panels-grid", style={
            "display": "grid",
            "gridTemplateColumns": "3fr 2fr",
            "gap": "16px",
            "alignItems": "stretch",
        }),

        html.Div([
            html.Div([
                html.H6("全部持仓盈亏", className="panel-title"),
                html.Span(
                    f"持仓中 {active_count} 个  已清仓 {closed_count} 个，综合盈亏含已清仓已实现",
                    className="panel-sub"
                ),
            ], className="panel-heading"),
            html.Div(_build_positions_pnl_table(all_positions, ccy),
                     style={"overflowX": "auto"}),
        ], className="panel"),

        html.Div([
            html.Div([
                html.H6("收益率历史走势", className="panel-title"),
                html.Span("基于已实现盈亏（不含浮盈波动）", className="panel-sub"),
            ], className="panel-heading"),
            _build_return_history_chart(daily_values),
        ], className="panel"),

        html.Div([
            html.Div([
                html.H6("资金投入走势", className="panel-title"),
                html.Span("累计投入 vs 已买入成本", className="panel-sub"),
            ], className="panel-heading"),
            _build_timeline_chart(timeline, ccy),
        ], className="panel"),
    ])

    return content, ccy != "CNY", ccy != "USD", ccy

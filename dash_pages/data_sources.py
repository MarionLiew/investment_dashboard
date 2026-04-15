import dash
from dash import html, dcc, dash_table, callback, Input, Output, State, ctx
import dash_bootstrap_components as dbc
from services.db import db, make_id, now_iso
from services.okx import sync_okx_account

dash.register_page(__name__, path="/data-sources", name="数据源")

SOURCE_LABELS = {"manual": "手动", "okx": "OKX", "broker": "券商", "fund_platform": "基金平台"}


def _to_cst(iso: str) -> str:
    """Convert UTC ISO timestamp to CST (UTC+8) formatted string."""
    from datetime import datetime, timezone, timedelta
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        cst = dt.astimezone(timezone(timedelta(hours=8)))
        return cst.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return iso[:16].replace("T", " ")


def layout(**kwargs):
    return html.Div([
        dcc.Store(id="ds-version", data=0),
        dcc.Store(id="sync-result", data={}),

        html.H4("数据源", style={"fontWeight": 700, "marginBottom": 16}),

        # OKX Accounts Panel
        html.Div([
            html.Div([
                html.H6("OKX 实盘账户", className="panel-title"),
                dbc.Button("+ 新建账户", id="open-ds-modal", color="primary", size="sm"),
            ], className="panel-heading"),
            html.Div(id="okx-accounts-list"),
        ], className="panel"),

        # Add/Edit OKX account modal
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle(id="ds-modal-title")),
            dbc.ModalBody([
                dcc.Store(id="editing-account-id", data=""),
                dbc.Row([
                    dbc.Col([
                        dbc.Label("账户名称"),
                        dbc.Input(id="ds-acct-name", placeholder="如：欧易主账户"),
                    ], width=6, className="mb-3"),
                    dbc.Col([
                        dbc.Label("计价货币"),
                        dbc.Select(id="ds-acct-ccy", options=[
                            {"label": "USD", "value": "USD"},
                            {"label": "CNY", "value": "CNY"},
                        ], value="USD"),
                    ], width=6, className="mb-3"),
                ]),
                dbc.Row([
                    dbc.Col([
                        dbc.Label("API Key"),
                        dbc.Input(id="ds-api-key", placeholder="xxxxxxxx-xxxx-xxxx-xxxx"),
                    ], width=12, className="mb-3"),
                ]),
                dbc.Row([
                    dbc.Col([
                        dbc.Label("Secret Key"),
                        dbc.Input(id="ds-secret-key", type="password", placeholder="Secret Key"),
                    ], width=6, className="mb-3"),
                    dbc.Col([
                        dbc.Label("Passphrase"),
                        dbc.Input(id="ds-passphrase", type="password", placeholder="API 通行短语"),
                    ], width=6, className="mb-3"),
                ]),
                html.Div(id="ds-modal-error", style={"color": "var(--negative)", "fontSize": 12}),
            ]),
            dbc.ModalFooter([
                dbc.Button("保存", id="submit-ds-account", color="primary"),
                dbc.Button("取消", id="cancel-ds-modal", color="secondary", outline=True),
            ]),
        ], id="ds-account-modal", is_open=False),

        # Data management
        html.Div([
            html.Div([
                html.H6("数据管理", className="panel-title"),
                html.Span("清空本地所有数据", className="panel-sub"),
            ], className="panel-heading"),
            html.Div([
                dbc.Button("清空所有数据", id="btn-clear-data", color="danger", outline=True, size="sm"),
                dbc.Button("恢复示例数据", id="btn-reset-data", color="secondary", outline=True, size="sm", style={"display": "none"}),
            ], style={"display": "flex", "gap": 8}),
            dbc.Modal([
                dbc.ModalHeader(dbc.ModalTitle("确认操作")),
                dbc.ModalBody(id="confirm-body"),
                dbc.ModalFooter([
                    dbc.Button("确认", id="confirm-data-yes", color="danger"),
                    dbc.Button("取消", id="confirm-data-no", color="secondary", outline=True),
                ]),
            ], id="confirm-data-modal", is_open=False),
            dcc.Store(id="pending-data-action", data=""),
        ], className="panel"),

        # FX Rates
        html.Div([
            html.Div([
                html.H6("汇率", className="panel-title"),
                html.Span("用于 CNY 换算，随 OKX 同步自动更新", className="panel-sub"),
            ], className="panel-heading"),
            html.Div(id="fx-rates-content"),
        ], className="panel"),

        # Sync logs
        html.Div([
            html.Div([
                html.H6("同步日志", className="panel-title"),
            ], className="panel-heading"),
            html.Div(id="sync-logs-content"),
        ], className="panel"),
    ])


# Toggle add/edit modal
@callback(
    Output("ds-account-modal", "is_open"),
    Output("ds-modal-title", "children"),
    Output("editing-account-id", "data"),
    Output("ds-acct-name", "value"),
    Output("ds-api-key", "value"),
    Output("ds-secret-key", "value"),
    Output("ds-passphrase", "value"),
    Output("ds-acct-ccy", "value"),
    Input("open-ds-modal", "n_clicks"),
    Input({"type": "edit-okx-acct", "index": dash.ALL}, "n_clicks"),
    Input("cancel-ds-modal", "n_clicks"),
    Input("submit-ds-account", "n_clicks"),
    State("ds-acct-name", "value"),
    State("ds-account-modal", "is_open"),
    prevent_initial_call=True,
)
def toggle_ds_modal(open_c, edit_clicks, cancel_c, submit_c, name, is_open):
    trigger = ctx.triggered_id
    if trigger == "open-ds-modal":
        return True, "新建 OKX 账户", "", "", "", "", "", "USD"
    if trigger == "cancel-ds-modal":
        return False, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update
    if isinstance(trigger, dict) and trigger.get("type") == "edit-okx-acct":
        # Guard: only open if there was an actual click (not page re-render)
        triggered_value = ctx.triggered[0]["value"] if ctx.triggered else None
        if not triggered_value:
            return is_open, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update
        account_id = trigger["index"]
        account = next((a for a in db.get_accounts() if a["id"] == account_id), None)
        config = next((c for c in db.get_connector_configs() if c.get("accountId") == account_id), None)
        return (
            True, "编辑 OKX 账户", account_id,
            account["name"] if account else "",
            config.get("apiKey", "") if config else "",
            config.get("secretKey", "") if config else "",
            config.get("passphrase", "") if config else "",
            account.get("baseCurrency", "USD") if account else "USD",
        )
    if trigger == "submit-ds-account" and name and name.strip():
        return False, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update
    return is_open, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update


# Save OKX account
@callback(
    Output("ds-version", "data"),
    Output("ds-modal-error", "children"),
    Input("submit-ds-account", "n_clicks"),
    State("editing-account-id", "data"),
    State("ds-acct-name", "value"),
    State("ds-api-key", "value"),
    State("ds-secret-key", "value"),
    State("ds-passphrase", "value"),
    State("ds-acct-ccy", "value"),
    State("ds-version", "data"),
    prevent_initial_call=True,
)
def save_ds_account(n, editing_id, name, api_key, secret_key, passphrase, ccy, version):
    if not name or not name.strip():
        return version, "请填写账户名称"

    account_id = editing_id or make_id("acct")

    if editing_id:
        db.update_account(editing_id, {"name": name.strip(), "baseCurrency": ccy or "USD"})
    else:
        db.add_account({
            "id": account_id,
            "sourceType": "okx",
            "name": name.strip(),
            "baseCurrency": ccy or "USD",
            "status": "active",
            "updatedAt": now_iso(),
        })

    existing = next((c for c in db.get_connector_configs() if c.get("accountId") == account_id), None)
    db.upsert_connector_config({
        **(existing or {}),  # preserve existing fields (accountEquityUsd, lastSyncedAt, etc.)
        "id": existing["id"] if existing else make_id("cfg"),
        "accountId": account_id,
        "connector": "okx",
        "apiKey": (api_key or "").strip(),
        "secretKey": (secret_key or "").strip(),
        "passphrase": (passphrase or "").strip(),
        "status": "configured",
    })
    return (version or 0) + 1, ""


# Delete OKX account
@callback(
    Output("ds-version", "data", allow_duplicate=True),
    Input({"type": "delete-okx-acct", "index": dash.ALL}, "n_clicks"),
    State("ds-version", "data"),
    prevent_initial_call=True,
)
def delete_okx_account(n_clicks_list, version):
    if not any(n for n in (n_clicks_list or []) if n):
        return version
    triggered = ctx.triggered_id
    if triggered and isinstance(triggered, dict):
        db.delete_account(triggered["index"])
    return (version or 0) + 1


# Sync account
@callback(
    Output("ds-version", "data", allow_duplicate=True),
    Output("sync-result", "data"),
    Input({"type": "sync-okx-acct", "index": dash.ALL}, "n_clicks"),
    State("ds-version", "data"),
    prevent_initial_call=True,
)
def sync_account(n_clicks_list, version):
    if not any(n for n in (n_clicks_list or []) if n):
        return version, {}
    triggered = ctx.triggered_id
    if not (triggered and isinstance(triggered, dict)):
        return version, {}

    account_id = triggered["index"]
    config = next((c for c in db.get_connector_configs() if c.get("accountId") == account_id), None)
    creds = None
    if config and config.get("apiKey"):
        creds = {"apiKey": config["apiKey"], "secretKey": config["secretKey"], "passphrase": config["passphrase"]}

    result = sync_okx_account(account_id, creds)

    db.add_sync_log({
        "id": make_id("log"),
        "accountId": account_id,
        "connector": "okx",
        "status": "error" if "错误" in result["message"] or "失败" in result["message"] else "success",
        "message": result["message"],
        "createdAt": now_iso(),
    })
    # Re-read config after sync (sync may have written accountEquityUsd into it)
    updated_config = next((c for c in db.get_connector_configs() if c.get("accountId") == account_id), config)
    if updated_config:
        db.upsert_connector_config({**updated_config, "lastSyncedAt": now_iso(), "status": "configured"})

    return (version or 0) + 1, {"account_id": account_id, "message": result["message"]}


# Render OKX accounts list
@callback(
    Output("okx-accounts-list", "children"),
    Output("sync-logs-content", "children"),
    Output("fx-rates-content", "children"),
    Input("ds-version", "data"),
    Input("sync-result", "data"),
)
def refresh_ds_content(version, sync_result):
    # Auto-recover accounts from connectorConfigs if accounts are missing
    all_accounts = db.get_accounts()
    all_account_ids = {a["id"] for a in all_accounts}
    for cfg in db.get_connector_configs():
        aid = cfg.get("accountId")
        if aid and aid not in all_account_ids:
            db.add_account({
                "id": aid,
                "sourceType": cfg.get("connector", "okx"),
                "name": f"OKX 实盘",
                "baseCurrency": "USD",
                "status": "active",
                "createdAt": now_iso(),
                "updatedAt": now_iso(),
            })
            all_account_ids.add(aid)

    accounts = [a for a in db.get_accounts() if a.get("sourceType") == "okx"]
    configs = {c["accountId"]: c for c in db.get_connector_configs()}
    sync_msgs = {}
    if sync_result and sync_result.get("account_id"):
        sync_msgs[sync_result["account_id"]] = sync_result["message"]

    if not accounts:
        acct_list = html.P("还没有 OKX 账户，点击右上角新建并配置 API 密钥。",
                           style={"color": "var(--ink-2)", "fontSize": 13})
    else:
        rows = []
        for a in accounts:
            config = configs.get(a["id"])
            has_key = bool(config and config.get("apiKey"))
            msg = sync_msgs.get(a["id"])
            is_error = msg and ("错误" in msg or "失败" in msg)
            rows.append(html.Div([
                html.Div([
                    html.Div([
                        html.Span(a["name"], style={"fontWeight": 600, "fontSize": 14}),
                        html.Span(a.get("baseCurrency", "USD"), style={"marginLeft": 8, "fontSize": 12, "color": "var(--ink-2)"}),
                        html.Span("API 已配置" if has_key else "未配置 API",
                                  style={"marginLeft": 8, "fontSize": 11,
                                         "color": "var(--positive)" if has_key else "var(--ink-3)"}),
                        *(
                            [html.Span(f"上次: {config['lastSyncedAt'][:10]}",
                                       style={"marginLeft": 8, "fontSize": 11, "color": "var(--ink-3)"})]
                            if config and config.get("lastSyncedAt") else []
                        ),
                    ]),
                    html.Div([
                        dbc.Button("编辑", id={"type": "edit-okx-acct", "index": a["id"]},
                                   color="secondary", outline=True, size="sm"),
                        dbc.Button("立即同步", id={"type": "sync-okx-acct", "index": a["id"]},
                                   color="primary", size="sm"),
                        dbc.Button("删除", id={"type": "delete-okx-acct", "index": a["id"]},
                                   color="danger", outline=True, size="sm"),
                    ], style={"display": "flex", "gap": 8}),
                ], style={"display": "flex", "justifyContent": "space-between", "alignItems": "center", "flexWrap": "wrap", "gap": 8}),
                *(
                    [html.Div(msg, style={
                        "marginTop": 10, "padding": "6px 12px", "borderRadius": 8, "fontSize": 12,
                        "background": "rgba(192,57,43,0.08)" if is_error else "rgba(28,138,62,0.08)",
                        "color": "var(--negative)" if is_error else "var(--positive)",
                    })]
                    if msg else []
                ),
            ], style={"border": "1px solid var(--line)", "borderRadius": 8, "padding": "12px 14px", "marginBottom": 10}))
        acct_list = html.Div(rows)

    # Sync logs
    logs = db.get_sync_logs()
    accounts_map = {a["id"]: a["name"] for a in db.get_accounts()}
    if not logs:
        log_table = html.P("暂无同步日志", style={"color": "var(--ink-2)", "fontSize": 13})
    else:
        log_table = html.Table([
            html.Thead(html.Tr([
                html.Th(h, style={"padding": "8px 12px", "fontSize": 11, "fontWeight": 600,
                                   "textTransform": "uppercase", "letterSpacing": "0.3px",
                                   "color": "var(--ink-2)", "borderBottom": "1px solid var(--line)",
                                   "background": "var(--bg)"})
                for h in ["时间", "账户", "状态", "说明"]
            ])),
            html.Tbody([
                html.Tr([
                    html.Td(_to_cst(log["createdAt"]),
                            style={"padding": "8px 12px", "fontSize": 12, "borderBottom": "1px solid var(--line)", "whiteSpace": "nowrap"}),
                    html.Td(accounts_map.get(log["accountId"], log["accountId"]),
                            style={"padding": "8px 12px", "fontSize": 12, "borderBottom": "1px solid var(--line)"}),
                    html.Td(
                        html.Span("成功" if log["status"] == "success" else "失败",
                                  className="positive" if log["status"] == "success" else "negative"),
                        style={"padding": "8px 12px", "fontSize": 12, "borderBottom": "1px solid var(--line)"}),
                    html.Td(log["message"],
                            style={"padding": "8px 12px", "fontSize": 12, "borderBottom": "1px solid var(--line)",
                                   "color": "var(--ink-2)"}),
                ])
                for log in logs[:20]
            ]),
        ], style={"width": "100%", "borderCollapse": "collapse"})

    # FX rates
    fx_rates = db.get_fx_rates()
    if not fx_rates:
        fx_content = html.P(
            "暂无汇率数据。请同步 OKX 账户，系统将自动获取 USD/CNY 汇率。",
            style={"color": "var(--ink-2)", "fontSize": 13}
        )
    else:
        fx_rows = []
        for r in fx_rates:
            fx_rows.append(html.Div([
                html.Span(f"{r['baseCurrency']} / {r['quoteCurrency']}",
                          style={"fontWeight": 600, "fontSize": 13}),
                html.Span(f"  {float(r['rate']):.4f}",
                          style={"fontSize": 14, "color": "var(--ink)", "marginLeft": 8}),
                html.Span(f"  来源: {r.get('source', '-')}",
                          style={"fontSize": 11, "color": "var(--ink-3)", "marginLeft": 12}),
                html.Span(f"  更新: {_to_cst(r.get('updatedAt', ''))}",
                          style={"fontSize": 11, "color": "var(--ink-3)", "marginLeft": 12}),
            ], style={"marginBottom": 6}))
        fx_content = html.Div(fx_rows)

    return acct_list, html.Div(log_table, style={"overflowX": "auto"}), fx_content


# Data management confirm
@callback(
    Output("confirm-data-modal", "is_open"),
    Output("confirm-body", "children"),
    Output("pending-data-action", "data"),
    Input("btn-clear-data", "n_clicks"),
    Input("btn-reset-data", "n_clicks"),
    Input("confirm-data-no", "n_clicks"),
    Input("confirm-data-yes", "n_clicks"),
    State("pending-data-action", "data"),
    prevent_initial_call=True,
)
def handle_data_confirm(clear_c, reset_c, no_c, yes_c, pending):
    trigger = ctx.triggered_id
    if trigger == "btn-clear-data":
        return True, "确定要清空所有交易记录和价格数据吗？账户配置和 API 密钥将保留，此操作不可撤销。", "clear"
    if trigger == "btn-reset-data":
        return True, "将覆盖当前所有数据，恢复为内置示例数据，确认继续？", "reset"
    if trigger == "confirm-data-no":
        return False, dash.no_update, ""
    if trigger == "confirm-data-yes":
        if pending == "clear":
            db.clear_all_data()
        elif pending == "reset":
            db.reset_to_sample_data()
        return False, dash.no_update, ""
    return False, dash.no_update, ""

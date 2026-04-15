import dash
from dash import Dash, html, dcc
import dash_bootstrap_components as dbc

app = Dash(
    __name__,
    use_pages=True,
    pages_folder="dash_pages",
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True,
    title="投资看板",
)

sidebar = html.Div([
    html.Div([
        html.Div("投", className="brand-icon"),
        html.Span("投资看板", className="brand-name"),
    ], className="sidebar-brand"),
    html.Hr(style={"borderColor": "var(--line)", "margin": "0 0 8px 0"}),
    dbc.Nav([
        dbc.NavLink("总览", href="/", active="exact"),
        dbc.NavLink("持仓", href="/positions", active="exact"),
        dbc.NavLink("账户", href="/accounts", active="exact"),
        dbc.NavLink("流水", href="/transactions", active="exact"),
        dbc.NavLink("数据源", href="/data-sources", active="exact"),
    ], vertical=True, pills=True),
], id="sidebar")

app.layout = dbc.Container(
    dbc.Row([
        dbc.Col(sidebar, width=2, style={"padding": 0}),
        dbc.Col(dash.page_container, id="page-content", width=10),
    ], style={"minHeight": "100vh"}),
    fluid=True,
    style={"padding": 0},
)

if __name__ == "__main__":
    app.run(debug=True, port=8050, host="0.0.0.0")

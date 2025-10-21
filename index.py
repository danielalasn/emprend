import dash_bootstrap_components as dbc
from dash import html, dcc
from dash.dependencies import Input, Output, State
from flask_login import logout_user, current_user
import dash

# Importar la app, server y layouts/callbacks
from app import app, server
from auth import User, login_manager
from database import record_first_login # Importamos esto aquí por si acaso, aunque se usa en login.py
from dashboard import get_layout as get_dashboard_layout, register_callbacks as register_dashboard_callbacks
from finances import get_layout as get_finanzas_layout, register_callbacks as register_finanzas_callbacks
from sales import get_layout as get_sales_layout, register_callbacks as register_sales_callbacks
from expenses import get_layout as get_expenses_layout, register_callbacks as register_expenses_callbacks
from products import get_layout as get_products_layout, register_callbacks as register_products_callbacks
# Importamos los nuevos layouts y callbacks de login.py
from login import get_login_layout, get_change_password_layout, register_login_callbacks

# --- Configuración de Flask-Login ---
login_manager.init_app(server)
login_manager.login_view = '/login'

@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)

# --- Layout de la Aplicación Principal ---
app_layout = dbc.Container([
    dcc.Store(id='store-data-signal'),
    dcc.Download(id="download-sales-excel"),
    dcc.Download(id="download-expenses-excel"),
    
    dbc.Row([
        dbc.Col(html.H1("Empren-D", className="text-center my-4"), width=10),
        dbc.Col(html.A("Cerrar Sesión", href="/logout", className="btn btn-danger mt-4"), width=2, className="text-end")
    ]),

    dbc.Tabs(id="main-tabs", active_tab="tab-dashboard", children=[
        dbc.Tab(label="Dashboard", tab_id="tab-dashboard"),
        dbc.Tab(label="Finanzas", tab_id="tab-finances"),
        dbc.Tab(label="Ventas", tab_id="tab-sales"),
        dbc.Tab(label="Gastos", tab_id="tab-expenses"),
        dbc.Tab(label="Productos", tab_id="tab-products"),
    ]),
    html.Div(id="tab-content", className="p-4")
], fluid=True)

# Layout principal que decide qué mostrar
app.layout = html.Div([
    dcc.Location(id='url', refresh=True),
    html.Div(id='page-content')
])

# --- Callbacks de Renderizado ---

@app.callback(
    Output('page-content', 'children'),
    Input('url', 'pathname')
)
def display_page(pathname):
    if pathname == '/logout':
        if current_user.is_authenticated:
            logout_user()
        return get_login_layout()
    
    if not current_user.is_authenticated:
        return get_login_layout()

    if current_user.must_change_password:
        if pathname == '/change-password':
            return get_change_password_layout()
        else:
            return dcc.Location(pathname="/change-password", id="redirect-force-change")

    if pathname == '/login' or pathname == '/change-password':
        return dcc.Location(pathname="/", id="redirect-to-home")

    return app_layout

@app.callback(Output('tab-content', 'children'), Input('main-tabs', 'active_tab'))
def render_tab_content(active_tab):
    if not current_user.is_authenticated:
        return
    if active_tab == 'tab-dashboard':
        return get_dashboard_layout()
    elif active_tab == 'tab-finances':
        return get_finanzas_layout()
    elif active_tab == 'tab-sales':
        return get_sales_layout()
    elif active_tab == 'tab-expenses':
        return get_expenses_layout()
    elif active_tab == 'tab-products':
        return get_products_layout()
    return html.P("Esta es una pestaña desconocida.")

# --- Registrar TODOS los Callbacks ---
register_dashboard_callbacks(app)
register_finanzas_callbacks(app)
register_sales_callbacks(app)
register_expenses_callbacks(app)
register_products_callbacks(app)
register_login_callbacks(app) # Se añaden los callbacks de login

if __name__ == '__main__':
    app.run(debug=True)
import dash_bootstrap_components as dbc
from dash import html, dcc
from dash.dependencies import Input, Output, State
from flask_login import login_user, logout_user, current_user

# Importar la app, server y layouts/callbacks
from app import app, server
from auth import User, check_password, login_manager
from dashboard import get_layout as get_dashboard_layout, register_callbacks as register_dashboard_callbacks
from finances import get_layout as get_finances_layout, register_callbacks as register_finances_callbacks
from sales import get_layout as get_sales_layout, register_callbacks as register_sales_callbacks
from expenses import get_layout as get_expenses_layout, register_callbacks as register_expenses_callbacks
from products import get_layout as get_products_layout, register_callbacks as register_products_callbacks

# --- Configuración de Flask-Login ---
login_manager.init_app(server)
login_manager.login_view = '/login'

@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)

# --- Layouts (Login y App Principal) ---

# Layout para la página de inicio de sesión
login_layout = dbc.Container([
    dbc.Row(
        dbc.Col(
            dbc.Card([
                html.H3("Iniciar Sesión", className="card-title text-center mt-3"),
                dbc.CardBody([
                    html.Div(id='login-alert'),
                    dbc.Input(id="username", type="text", placeholder="Usuario", className="mb-3"),
                    dbc.Input(id="password", type="password", placeholder="Contraseña", className="mb-3"),
                    dbc.Button("Ingresar", id="login-button", color="primary", n_clicks=0, className="w-100"),
                ]),
            ], className="shadow-sm"),
            width=10, lg=4, className="mx-auto mt-5"
        )
    )
], fluid=True)

# Layout de la aplicación principal
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
    dcc.Location(id='url', refresh=False),
    html.Div(id='page-content')
])


# --- Callbacks de Autenticación y Renderizado ---

@app.callback(
    Output('page-content', 'children'),
    Input('url', 'pathname')
)
def display_page(pathname):
    if pathname == '/logout':
        if current_user.is_authenticated:
            logout_user()
        return login_layout
    
    if current_user.is_authenticated:
        return app_layout
    else:
        return login_layout

@app.callback(
    Output('url', 'pathname'),
    Output('login-alert', 'children'),
    Input('login-button', 'n_clicks'),
    [State('username', 'value'),
     State('password', 'value')],
    prevent_initial_call=True
)
def login_callback(n_clicks, username, password):
    user = User.find(username)
    if user and check_password(user.password, password):
        login_user(user)
        return '/', None
    else:
        return '/login', dbc.Alert("Usuario o contraseña incorrectos.", color="danger", dismissable=True)


@app.callback(Output('tab-content', 'children'), Input('main-tabs', 'active_tab'))
def render_tab_content(active_tab):
    if not current_user.is_authenticated:
        return
    if active_tab == 'tab-dashboard':
        return get_dashboard_layout()
    elif active_tab == 'tab-finances':
        return get_finances_layout()
    elif active_tab == 'tab-sales':
        return get_sales_layout()
    elif active_tab == 'tab-expenses':
        return get_expenses_layout()
    elif active_tab == 'tab-products':
        return get_products_layout()
    return html.P("Esta es una pestaña desconocida.")

# --- Registrar Callbacks de las Pestañas ---
register_dashboard_callbacks(app)
register_finances_callbacks(app)
register_sales_callbacks(app)
register_expenses_callbacks(app)
register_products_callbacks(app)

if __name__ == '__main__':
    app.run(debug=True)
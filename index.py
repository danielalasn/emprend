import dash_bootstrap_components as dbc
from dash import html, dcc
from dash.dependencies import Input, Output, State
from flask_login import login_user, logout_user, current_user
import dash

from app import app, server
from auth import User, check_password, login_manager, set_password
from database import update_user_password
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

# --- Layouts (Login, Cambiar Contraseña y App Principal) ---

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

change_password_layout = dbc.Container([
    dcc.Location(id='change-pass-redirector', refresh=True),
    dbc.Row(
        dbc.Col(
            dbc.Card([
                html.H3("Cambiar Contraseña", className="card-title text-center mt-3"),
                html.P("Es tu primer inicio de sesión. Por favor, crea una nueva contraseña.", className="text-center text-muted"),
                dbc.CardBody([
                    html.Div(id='change-password-alert'),
                    dbc.Input(id="new-password", type="password", placeholder="Nueva Contraseña", className="mb-3"),
                    dbc.Input(id="confirm-password", type="password", placeholder="Confirmar Contraseña", className="mb-3"),
                    dbc.Button("Guardar Contraseña", id="change-password-button", color="primary", n_clicks=0, className="w-100"),
                ]),
            ], className="shadow-sm"),
            width=10, lg=4, className="mx-auto mt-5"
        )
    )
], fluid=True)

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

app.layout = html.Div([
    dcc.Location(id='url', refresh=True),
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
    
    if not current_user.is_authenticated:
        return login_layout

    if current_user.must_change_password:
        if pathname == '/change-password':
            return change_password_layout
        else:
            return dcc.Location(pathname="/change-password", id="redirect-force-change")

    if pathname == '/login' or pathname == '/change-password':
        return dcc.Location(pathname="/", id="redirect-to-home")

    return app_layout

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
        if user.must_change_password:
            return '/change-password', None
        return '/', None
    else:
        return '/login', dbc.Alert("Usuario o contraseña incorrectos.", color="danger", dismissable=True)

@app.callback(
    Output('change-password-alert', 'children'),
    Output('change-pass-redirector', 'pathname'),
    Input('change-password-button', 'n_clicks'),
    [State('new-password', 'value'),
     State('confirm-password', 'value')],
    prevent_initial_call=True
)
def update_password_callback(n_clicks, new_pass, confirm_pass):
    if not new_pass or not confirm_pass:
        return dbc.Alert("Ambos campos son obligatorios.", color="warning"), dash.no_update
    if new_pass != confirm_pass:
        return dbc.Alert("Las contraseñas no coinciden.", color="danger"), dash.no_update
    
    hashed_password = set_password(new_pass)
    update_user_password(current_user.id, hashed_password)
    
    return dbc.Alert("¡Contraseña actualizada! Redirigiendo...", color="success"), "/"


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
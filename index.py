import dash_bootstrap_components as dbc
from dash import html, dcc
from dash.dependencies import Input, Output, State
from flask_login import logout_user, current_user
import dash
from datetime import date, timedelta # <-- AÑADIR ESTA LÍNEA

# Importar la app, server y layouts/callbacks
from app import app, server
from auth import User, login_manager
from database import record_first_login
from dashboard import get_layout as get_dashboard_layout, register_callbacks as register_dashboard_callbacks
from finances import get_layout as get_finanzas_layout, register_callbacks as register_finanzas_callbacks
from sales import get_layout as get_sales_layout, register_callbacks as register_sales_callbacks
from expenses import get_layout as get_expenses_layout, register_callbacks as register_expenses_callbacks
from products import get_layout as get_products_layout, register_callbacks as register_products_callbacks
from login import get_login_layout, get_change_password_layout, register_login_callbacks
from admin import get_layout as get_admin_layout, register_callbacks as register_admin_callbacks
from materia_prima import get_layout as get_material_layout, register_callbacks as register_material_callbacks 

# --- Configuración de Flask-Login ---
login_manager.init_app(server)
login_manager.login_view = '/login'

@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)

# --- Layout de la Aplicación Principal (Función) ---
def get_main_app_layout():
    """Genera el layout principal de la aplicación."""

    tabs = [
        dbc.Tab(label="Dashboard", tab_id="tab-dashboard"),
        dbc.Tab(label="Finanzas", tab_id="tab-finances"),
        dbc.Tab(label="Ventas", tab_id="tab-sales"),
        dbc.Tab(label="Gastos", tab_id="tab-expenses"),
        dbc.Tab(label="Productos", tab_id="tab-products"),
        dbc.Tab(label="Insumos", tab_id="tab-material"),
    ]
    if current_user.is_authenticated and current_user.is_admin:
        admin_tab = dbc.Tab(label="Administrar", tab_id="tab-admin", tab_style={"backgroundColor": "#ffc107"})
        tabs.append(admin_tab)

    return dbc.Container([
        dcc.Store(id='store-data-signal'),
        dcc.Download(id="download-sales-excel"),
        dcc.Download(id="download-expenses-excel"),

        dbc.Row([
            dbc.Col(html.H1("Empren-D", className="text-center my-4"), width=10),
            dbc.Col(html.A("Cerrar Sesión", href="/logout", className="btn btn-danger mt-4"), width=2, className="text-end")
        ]),

        # Alerta para suscripción
        html.Div(id='subscription-alert', className="m-3"),

        dbc.Tabs(id="main-tabs", active_tab="tab-dashboard", children=tabs),
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

    return get_main_app_layout()

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
    elif active_tab == 'tab-material':
        return get_material_layout()
    elif active_tab == 'tab-admin':
        return get_admin_layout()
    return html.P("Esta es una pestaña desconocida.")


# --- NUEVO CALLBACK: Mostrar Alerta de Suscripción ---
@app.callback(
    Output('subscription-alert', 'children'),
    Input('url', 'pathname') # Triggered whenever the page changes
)
def display_subscription_warning(pathname):
    # Only show if user is logged in, not admin, and on a main app page
    if current_user.is_authenticated and not current_user.is_admin and pathname not in ['/login', '/logout', '/change-password']:
        today = date.today()
        # Check if the user object has the date attribute (it should after login)
        if hasattr(current_user, 'subscription_end_date') and current_user.subscription_end_date:
            # Check if it expires within 5 days (and hasn't already expired)
            # Asegurarse de que current_user.subscription_end_date es un objeto date
            sub_end_date_obj = current_user.subscription_end_date
            if isinstance(sub_end_date_obj, str): # Convertir si es string
                 try:
                     sub_end_date_obj = date.fromisoformat(sub_end_date_obj)
                 except ValueError:
                     return None # No mostrar alerta si la fecha no es válida

            if isinstance(sub_end_date_obj, date): # Proceder solo si es un objeto date
                if today <= sub_end_date_obj <= today + timedelta(days=5):
                    days_left = (sub_end_date_obj - today).days
                    day_str = "día" if days_left == 1 else "días"
                    expire_str = "hoy" if days_left == 0 else f"en {days_left} {day_str}"
                    return dbc.Alert(f"⚠️ Tu suscripción vence {expire_str} ({sub_end_date_obj.strftime('%Y-%m-%d')}).", color="warning", dismissable=True) # Show for 10 secs

    # In all other cases, show nothing
    return None

# --- Registrar TODOS los Callbacks ---
register_dashboard_callbacks(app)
register_finanzas_callbacks(app)
register_sales_callbacks(app)
register_expenses_callbacks(app)
register_products_callbacks(app)
register_login_callbacks(app)
register_admin_callbacks(app)
register_material_callbacks(app)

if __name__ == '__main__':
    app.run(debug=True)
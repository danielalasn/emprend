# index.py
import dash_bootstrap_components as dbc
from dash import html, dcc
from dash.dependencies import Input, Output, State
from flask_login import logout_user, current_user
import dash
from datetime import date, timedelta

# Importar la app, server y layouts/callbacks
from app import app, server
from auth import User, login_manager
from database import record_first_login
# Importar la función generadora y el layout del resumen
from resumen_excel import generate_excel_summary, get_summary_layout 

# Importar layouts de módulos
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

# --- Layout de la Aplicación Principal ---
def get_main_app_layout():
    """Genera el layout principal de la aplicación."""

    tabs = [
        dbc.Tab(label="Dashboard", tab_id="tab-dashboard"),
        dbc.Tab(label="Finanzas", tab_id="tab-finances"),
        dbc.Tab(label="Ventas", tab_id="tab-sales"),
        dbc.Tab(label="Gastos", tab_id="tab-expenses"),
        dbc.Tab(label="Productos", tab_id="tab-products"),
        dbc.Tab(label="Insumos", tab_id="tab-material"),
        dbc.Tab(label="Reportes", tab_id="tab-summary"), 
    ]
    
    if current_user.is_authenticated and current_user.is_admin:
        admin_tab = dbc.Tab(label="Admin", tab_id="tab-admin")
        tabs.append(admin_tab)

    username_display = current_user.username if current_user.is_authenticated else "Usuario"

    return html.Div([ # Contenedor principal sin márgenes para el navbar
        dcc.Store(id='store-data-signal'),
        dcc.Download(id="download-sales-excel"),
        dcc.Download(id="download-expenses-excel"),
        dcc.Download(id="download-summary-excel"), 

        # --- NAVBAR MODERNO ---
        dbc.Navbar(
            dbc.Container([
                # Marca / Logo
                html.A(
                    dbc.Row([
                        dbc.Col(html.I(className="fas fa-chart-line", style={"fontSize": "1.5rem", "color": "white"})),
                        dbc.Col(dbc.NavbarBrand("Empren-D", className="ms-2 fw-bold", style={"fontSize": "1.5rem"})),
                    ], align="center", className="g-0"),
                    href="/",
                    style={"textDecoration": "none"},
                ),
                
                # Saludo y Logout a la derecha
                dbc.Nav([
                    dbc.NavItem(html.Span(f"Hola, {username_display}", className="text-white me-3 align-middle", style={"lineHeight": "40px"})),
                    dbc.NavItem(dbc.Button("Salir", href="/logout", color="light", size="sm", outline=True, className="mt-1")),
                ], className="ms-auto", navbar=True),
            ], fluid=True),
            color="#32a852", # Tu color de marca
            dark=True,
            className="mb-4 shadow-sm",
            style={"height": "70px"}
        ),

        # --- CONTENIDO PRINCIPAL ---
        dbc.Container([
            # Alerta para suscripción
            html.Div(id='subscription-alert', className="mb-3"),

            # Tabs estilizados por CSS
            dbc.Tabs(id="main-tabs", active_tab="tab-dashboard", children=tabs, className="nav-tabs"),
            
            # Contenido de la pestaña
            html.Div(id="tab-content", className="p-0") # Padding controlado por las vistas internas
        ], fluid=True, className="px-4") # Un poco de padding lateral en la pantalla
    ], style={"backgroundColor": "#f4f6f8", "minHeight": "100vh"})
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
    elif active_tab == 'tab-summary': 
        return get_summary_layout() 
    elif active_tab == 'tab-admin':
        return get_admin_layout()
    return html.P("Esta es una pestaña desconocida.")


# --- Callback: Mostrar Alerta de Suscripción ---
@app.callback(
    Output('subscription-alert', 'children'),
    Input('url', 'pathname') 
)
def display_subscription_warning(pathname):
    if current_user.is_authenticated and not current_user.is_admin and pathname not in ['/login', '/logout', '/change-password']:
        today = date.today()
        if hasattr(current_user, 'subscription_end_date') and current_user.subscription_end_date:
            sub_end_date_obj = current_user.subscription_end_date
            if isinstance(sub_end_date_obj, str):
                 try:
                     sub_end_date_obj = date.fromisoformat(sub_end_date_obj)
                 except ValueError:
                     return None 

            if isinstance(sub_end_date_obj, date):
                if today <= sub_end_date_obj <= today + timedelta(days=5):
                    days_left = (sub_end_date_obj - today).days
                    day_str = "día" if days_left == 1 else "días"
                    expire_str = "hoy" if days_left == 0 else f"en {days_left} {day_str}"
                    return dbc.Alert(f"⚠️ Tu suscripción vence {expire_str} ({sub_end_date_obj.strftime('%Y-%m-%d')}).", color="warning", dismissable=True) 
    return None

# --- NUEVO CALLBACK: Deshabilitar DatePicker si Switch está ON ---
@app.callback(
    Output('summary-date-picker', 'disabled'),
    Input('summary-see-all-switch', 'value')
)
def toggle_summary_date_picker(see_all):
    return see_all

# --- Callback: Descargar Resumen Completo ---
@app.callback(
    Output('download-summary-excel', 'data'),
    Input('btn-download-summary-excel', 'n_clicks'),
    [State('summary-date-picker', 'start_date'),
     State('summary-date-picker', 'end_date'),
     State('summary-see-all-switch', 'value')],
    prevent_initial_call=True
)
def download_full_summary(n_clicks, start_date, end_date, see_all):
    if n_clicks is None or not current_user.is_authenticated:
        raise dash.exceptions.PreventUpdate
    
    user_id = int(current_user.id)
    
    # Lógica del Switch: Si está ON, pasamos None para traer todo
    if see_all:
        final_start = None
        final_end = None
        date_str = "HISTORICO"
    else:
        final_start = start_date
        final_end = end_date
        date_str = date.today().strftime("%Y-%m-%d")
    
    # Generar Excel
    excel_bytes_io = generate_excel_summary(user_id, final_start, final_end)
    
    filename = f"Resumen_Empren-D_{date_str}.xlsx"
    
    return dcc.send_bytes(excel_bytes_io.getvalue(), filename)

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
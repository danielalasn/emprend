import dash_bootstrap_components as dbc
from dash import html, dcc
from dash.dependencies import Input, Output, State
from flask_login import login_user, current_user
import dash
from dash.exceptions import PreventUpdate
from datetime import date, timedelta # <-- Añadido

from app import app
from auth import User, check_password, set_password
from database import update_user_password, record_first_login

# --- LAYOUTS DE AUTENTICACIÓN ---
# (get_login_layout, get_change_password_layout sin cambios)
def get_login_layout():
    return dbc.Container([
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

def get_change_password_layout():
    return dbc.Container([
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

# --- CALLBACKS DE AUTENTICACIÓN ---

def register_login_callbacks(app):

    # --- CORREGIDO: Añadido Output para alerta de suscripción ---
    @app.callback(
        Output('url', 'pathname', allow_duplicate=True),
        Output('login-alert', 'children'),
        # Output('subscription-alert', 'children'), # <-- NUEVO OUTPUT
        Input('login-button', 'n_clicks'),
        [State('username', 'value'),
         State('password', 'value')],
        prevent_initial_call=True
    )
    def login_callback(n_clicks, username, password):
        if n_clicks is None or n_clicks < 1:
            raise PreventUpdate

        user = User.find(username) # Esto ahora incluye subscription_end_date

        # Retornamos 3 valores (url, login_alert, subscription_alert)
        no_url_update = dash.no_update

        if not user:
            return no_url_update, dbc.Alert("Usuario o contraseña incorrectos.", color="danger", dismissable=True)

        if user.is_blocked:
            return no_url_update, dbc.Alert("Tu cuenta ha sido bloqueada. Contacta al administrador.", color="danger", dismissable=True)

        if user and check_password(user.password, password):

            # --- INICIO LÓGICA DE SUSCRIPCIÓN ---
            today = date.today()
            subscription_alert_message = None

            # 1. Verificar si tiene fecha de suscripción (ignoramos si es admin)
            if not user.is_admin and user.subscription_end_date:
                # 2. Verificar si está expirada
                if today > user.subscription_end_date:
                    return no_url_update, dbc.Alert("Tu suscripción ha expirado. Contacta al administrador.", color="warning", dismissable=True)
                # 3. Verificar si expira pronto (en 5 días o menos)
                elif user.subscription_end_date <= today + timedelta(days=5):
                    days_left = (user.subscription_end_date - today).days
                    day_str = "día" if days_left == 1 else "días"
                    expire_str = "hoy" if days_left == 0 else f"en {days_left} {day_str}"
                    subscription_alert_message = dbc.Alert(f"⚠️ Tu suscripción vence {expire_str} ({user.subscription_end_date.strftime('%Y-%m-%d')}).", color="warning", dismissable=True)
            # --- FIN LÓGICA DE SUSCRIPCIÓN ---

            login_user(user)

            if user.first_login is None:
                record_first_login(user.id)

            if user.must_change_password:
                # CORRECTION: Only return 2 values (url, login_alert)
                return '/change-password', None
            # Al redirigir a la app principal, mostramos la alerta de suscripción
            return '/', None
        else:
            return no_url_update, dbc.Alert("Usuario o contraseña incorrectos.", color="danger", dismissable=True)


    # (update_password_callback sin cambios)
    @app.callback(
        Output('change-password-alert', 'children'),
        Output('url', 'pathname', allow_duplicate=True),
        Output('change-password-button', 'disabled'),
        Input('change-password-button', 'n_clicks'),
        [State('new-password', 'value'),
         State('confirm-password', 'value')],
        prevent_initial_call=True
    )
    def update_password_callback(n_clicks, new_pass, confirm_pass):
        if n_clicks is None or n_clicks < 1:
            raise PreventUpdate

        if not new_pass or not confirm_pass:
            return dbc.Alert("Ambos campos son obligatorios.", color="warning"), dash.no_update, False
        if new_pass != confirm_pass:
            return dbc.Alert("Las contraseñas no coinciden.", color="danger"), dash.no_update, False

        hashed_password = set_password(new_pass)
        update_user_password(current_user.id, hashed_password)

        return dbc.Alert("¡Contraseña actualizada! Redirigiendo...", color="success"), "/", True
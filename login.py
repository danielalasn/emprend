import dash_bootstrap_components as dbc
from dash import html, dcc
from dash.dependencies import Input, Output, State
from flask_login import login_user, current_user
import dash
from dash.exceptions import PreventUpdate

from app import app
from auth import User, check_password, set_password
from database import update_user_password, record_first_login

# --- LAYOUTS DE AUTENTICACIÓN ---

def get_login_layout():
    """Devuelve el layout de la página de inicio de sesión."""
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
    """Devuelve el layout de la página de cambio de contraseña."""
    return dbc.Container([
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


# --- CALLBACKS DE AUTENTICACIÓN ---

def register_login_callbacks(app):
    @app.callback(
        Output('url', 'pathname'),
        Output('login-alert', 'children'),
        Input('login-button', 'n_clicks'),
        [State('username', 'value'),
         State('password', 'value')],
        prevent_initial_call=True  # <-- CAMBIO: Se asegura que no se ejecute al inicio
    )
    def login_callback(n_clicks, username, password):
        # La guarda 'if n_clicks is None' ya no es necesaria gracias a prevent_initial_call
        
        user = User.find(username)
        
        if not user:
            return '/login', dbc.Alert("Usuario o contraseña incorrectos.", color="danger", dismissable=True)
        
        if user.is_blocked:
            return '/login', dbc.Alert("Tu cuenta ha sido bloqueada. Contacta al administrador.", color="danger", dismissable=True)

        if user and check_password(user.password, password):
            login_user(user)
            
            if user.first_login is None:
                record_first_login(user.id)
                
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
        if n_clicks is None:
            raise PreventUpdate
            
        if not new_pass or not confirm_pass:
            return dbc.Alert("Ambos campos son obligatorios.", color="warning"), dash.no_update
        if new_pass != confirm_pass:
            return dbc.Alert("Las contraseñas no coinciden.", color="danger"), dash.no_update
        
        hashed_password = set_password(new_pass)
        update_user_password(current_user.id, hashed_password)
        
        return dbc.Alert("¡Contraseña actualizada! Redirigiendo...", color="success"), "/"
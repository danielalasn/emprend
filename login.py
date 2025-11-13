import dash_bootstrap_components as dbc
from dash import html, dcc
from dash.dependencies import Input, Output, State
from flask_login import login_user, current_user
import dash
from dash.exceptions import PreventUpdate
from datetime import date, timedelta
import random

from app import app
from auth import User, check_password, set_password
from database import update_user_password, record_first_login

# --- TUS FRASES SELECCIONADAS ---
SLOGANS = [
    "Administra menos, crece más.",
    "Tus números claros, tu mente en el negocio.",
    "Donde los pequeños negocios se hacen grandes.",
    "Números claros, mente clara."
]

# --- ESTILOS PERSONALIZADOS ---
BACKGROUND_STYLE = {
    "background": "linear-gradient(135deg, #32a852 0%, #2c3e50 100%)",
    "minHeight": "100vh",
    "display": "flex",
    "alignItems": "center",
    "justifyContent": "center"
}

CARD_STYLE = {
    "border": "none",
    "borderRadius": "15px",
    "overflow": "hidden"
}

# --- LAYOUTS DE AUTENTICACIÓN ---

def get_login_layout():
    selected_slogan = random.choice(SLOGANS)

    return html.Div(style=BACKGROUND_STYLE, children=[
        dbc.Container([
            dbc.Row(
                dbc.Col(
                    dbc.Card([
                        # Cabecera
                        html.Div(
                            className="bg-white text-center pt-4 pb-2",
                            children=[
                                html.Div(
                                    html.I(className="fas fa-chart-line", style={"fontSize": "4rem", "color": "#32a852"}),
                                    className="mb-2"
                                ),
                                html.H2("Empren-D", className="fw-bold text-dark", style={"letterSpacing": "1px"}),
                                html.P(selected_slogan, className="text-muted small text-uppercase fw-bold px-3")
                            ]
                        ),
                        
                        dbc.CardBody([
                            html.H5("Iniciar Sesión", className="text-center mb-4 fw-normal"),
                            html.Div(id='login-alert'),
                            
                            dbc.InputGroup([
                                dbc.InputGroupText(html.I(className="fas fa-user")),
                                dbc.Input(id="username", type="text", placeholder="Nombre de usuario", autoFocus=True)
                            ], className="mb-3"),
                            
                            dbc.InputGroup([
                                dbc.InputGroupText(html.I(className="fas fa-lock")),
                                dbc.Input(id="password", type="password", placeholder="Contraseña")
                            ], className="mb-4"),
                            
                            dbc.Button(
                                "INGRESAR", 
                                id="login-button", 
                                color="success", 
                                size="lg", 
                                n_clicks=0, 
                                className="w-100 fw-bold shadow-sm",
                                style={"borderRadius": "30px"}
                            ),

                            # --- NUEVO: LINK PARA RECUPERAR CONTRASEÑA ---
                            html.Div(
                                html.A("¿Olvidaste tu contraseña?", id="open-forgot-password", href="#", className="text-muted small", style={"textDecoration": "none"}),
                                className="text-center mt-3"
                            )
                        ], className="p-4"),
                        
                        # Pie de tarjeta (Crear Usuario)
                        dbc.CardFooter(
                            html.Div([
                                html.A("¿No tienes cuenta? Crear Usuario", id="open-contact-modal", href="#", className="text-muted small", style={"textDecoration": "none"}),
                            ], className="text-center"),
                            className="bg-light py-3 border-0"
                        )
                    ], className="shadow-lg", style=CARD_STYLE),
                    width=10, sm=8, md=6, lg=4
                ),
                justify="center"
            ),

            # --- MODAL DE CONTACTO (Soporte General) ---
            dbc.Modal([
                dbc.ModalHeader(dbc.ModalTitle("Ayuda y Soporte")), # Título genérico
                dbc.ModalBody([
                    html.P("La gestión de cuentas (registro y recuperación) se realiza manualmente por el equipo de Empren-D.", className="text-muted"),
                    html.P("Por favor, contacta al administrador con tu solicitud:", className="fw-bold"),
                    html.Hr(),
                    html.Div([
                        html.H5("Soporte Empren-D", className="text-success mb-3"),
                        
                        html.Div([
                            html.I(className="fas fa-envelope me-3 text-secondary"),
                            html.Span("infoemprend.sv@gmail.com", className="fw-bold") 
                        ], className="mb-2"),
                        
                        html.Div([
                            html.I(className="fas fa-phone me-3 text-secondary"),
                            html.Span("+503 7600 3378", className="fw-bold")     
                        ]),
                        
                    ], className="p-3 bg-light rounded")
                ]),
                dbc.ModalFooter(
                    dbc.Button("Cerrar", id="close-contact-modal", className="ms-auto", n_clicks=0)
                )
            ], id="contact-modal", is_open=False, centered=True),

        ], fluid=True)
    ])

def get_change_password_layout():
    return html.Div(style=BACKGROUND_STYLE, children=[
        dbc.Container([
            dbc.Row(
                dbc.Col(
                    dbc.Card([
                        html.Div(
                            className="text-center pt-4",
                            children=[
                                html.I(className="fas fa-key", style={"fontSize": "3rem", "color": "#f0ad4e"}),
                                html.H3("Cambiar Contraseña", className="mt-3 fw-bold")
                            ]
                        ),
                        dbc.CardBody([
                            dbc.Alert("Es tu primer inicio de sesión. Por seguridad, crea una nueva contraseña.", color="info", className="small mb-4"),
                            html.Div(id='change-password-alert'),
                            
                            dbc.Label("Nueva Contraseña", className="fw-bold small"),
                            dbc.InputGroup([
                                dbc.InputGroupText(html.I(className="fas fa-lock")),
                                dbc.Input(id="new-password", type="password", placeholder="Mínimo 6 caracteres")
                            ], className="mb-3"),

                            dbc.Label("Confirmar Contraseña", className="fw-bold small"),
                            dbc.InputGroup([
                                dbc.InputGroupText(html.I(className="fas fa-check-circle")),
                                dbc.Input(id="confirm-password", type="password", placeholder="Repite la contraseña")
                            ], className="mb-4"),

                            dbc.Button(
                                "GUARDAR Y CONTINUAR", 
                                id="change-password-button", 
                                color="primary", 
                                size="lg",
                                n_clicks=0, 
                                className="w-100 fw-bold shadow-sm",
                                style={"borderRadius": "30px"}
                            ),
                        ], className="p-4")
                    ], className="shadow-lg", style=CARD_STYLE),
                    width=10, sm=8, md=6, lg=4
                ),
                justify="center"
            )
        ], fluid=True)
    ])

# --- CALLBACKS DE AUTENTICACIÓN ---

def register_login_callbacks(app):

    # --- CALLBACK UNIFICADO: Maneja ambos enlaces (Crear cuenta y Olvidé contraseña) ---
    @app.callback(
        Output("contact-modal", "is_open"),
        [Input("open-contact-modal", "n_clicks"), 
         Input("open-forgot-password", "n_clicks"), # Nuevo Input
         Input("close-contact-modal", "n_clicks")],
        [State("contact-modal", "is_open")],
    )
    def toggle_contact_modal(n1, n2, n3, is_open):
        # Si cualquiera de los 3 botones es presionado, cambiamos el estado
        if n1 or n2 or n3:
            return not is_open
        return is_open

    # Callback de Login
    @app.callback(
        Output('url', 'pathname', allow_duplicate=True),
        Output('login-alert', 'children'),
        Input('login-button', 'n_clicks'),
        [State('username', 'value'),
         State('password', 'value')],
        prevent_initial_call=True
    )
    def login_callback(n_clicks, username, password):
        if n_clicks is None or n_clicks < 1:
            raise PreventUpdate

        user = User.find(username) 
        no_url_update = dash.no_update

        if not user:
            return no_url_update, dbc.Alert("Usuario o contraseña incorrectos.", color="danger", dismissable=True)

        if user.is_blocked:
            return no_url_update, dbc.Alert("Tu cuenta ha sido bloqueada. Contacta al administrador.", color="danger", dismissable=True)

        if user and check_password(user.password, password):
            today = date.today()
            if not user.is_admin and user.subscription_end_date:
                if today > user.subscription_end_date:
                    return no_url_update, dbc.Alert("Tu suscripción ha expirado. Contacta al administrador.", color="warning", dismissable=True)
            
            login_user(user)

            if user.first_login is None:
                record_first_login(user.id)

            if user.must_change_password:
                return '/change-password', None
            
            return '/', None
        else:
            return no_url_update, dbc.Alert("Usuario o contraseña incorrectos.", color="danger", dismissable=True)

    # Callback de Cambio de Contraseña
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
        if len(new_pass) < 4:
             return dbc.Alert("La contraseña es muy corta.", color="warning"), dash.no_update, False

        hashed_password = set_password(new_pass)
        update_user_password(current_user.id, hashed_password)

        return dbc.Alert("¡Contraseña actualizada! Redirigiendo...", color="success"), "/", True
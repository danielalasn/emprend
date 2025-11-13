import dash_bootstrap_components as dbc
from dash import html, dcc
from dash.dependencies import Input, Output, State, ClientsideFunction
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
    "Donde los pequeños negocios se hacen grandes.",
    "Números claros, mente clara.",
    "El único fracaso real es no intentarlo.",
    "Si puedes soñarlo, puedes lograrlo.",
    "La acción vence a la procrastinación.",
    "Convierte tu pasión en tu proyecto.",
    "Sé tan bueno que no puedan ignorarte.",
    "Empieza donde estás, usa lo que tienes."
]


# --- ESTILOS PERSONALIZADOS ---
BACKGROUND_STYLE = {
    "background": "linear-gradient(135deg, #32a852 0%, #2c3e50 100%)",
    "height": "100vh",      
    "width": "100vw",      
    "display": "flex",
    "alignItems": "center",
    "justifyContent": "center",
    "padding": "0.5rem",
    "overflow": "hidden", 
    "position": "fixed",      
    "top": "0",
    "left": "0"
}

CARD_STYLE = {
    "border": "none",
    "borderRadius": "15px",
    "overflow": "hidden"
}

# Estilo para la alerta flotante (Ghost)
FLOAT_ALERT_STYLE = {
    "position": "absolute",
    "bottom": "100%",      # Se sitúa justo encima del elemento padre (la columna)
    "left": "0",
    "width": "100%",       # Ocupa el mismo ancho que la tarjeta
    "marginBottom": "10px", # Un pequeño espacio de separación
    "zIndex": "1000"       # Asegura que quede encima de todo
}

# --- LAYOUTS DE AUTENTICACIÓN ---

def get_login_layout():
    selected_slogan = random.choice(SLOGANS)

    return html.Div(style=BACKGROUND_STYLE, children=[
        dbc.Container([
            dbc.Row(
                dbc.Col([
                    # --- ALERTA FLOTANTE (GHOST) ---
                    # Al tener position:absolute y bottom:100%, aparece arriba sin empujar la card
                    html.Div(id='login-alert', style=FLOAT_ALERT_STYLE),

                    dbc.Card([
                        # CABECERA
                        html.Div(
                            className="bg-white text-center pt-3 pb-1",
                            children=[
                                html.Div(
                                    html.I(className="fas fa-chart-line", style={"fontSize": "2.5rem", "color": "#32a852"}),
                                    className="mb-1"
                                ),
                                html.H2("Empren-D", className="fw-bold text-dark h4 mb-0", style={"letterSpacing": "1px"}), 
                                html.P(selected_slogan, className="text-muted small text-uppercase fw-bold px-2 m-0", style={"fontSize": "0.75rem"})
                            ]
                        ),
                        
                        # CUERPO
                        dbc.CardBody([
                            html.H5("Iniciar Sesión", className="text-center mb-3 fw-normal small"), 
                            
                            dbc.InputGroup([
                                dbc.InputGroupText(html.I(className="fas fa-user")),
                                dbc.Input(id="username", type="text", placeholder="Usuario", autoFocus=True, className="form-control-sm")
                            ], className="mb-2"),
                            
                            dbc.InputGroup([
                                dbc.InputGroupText(html.I(className="fas fa-lock")),
                                dbc.Input(id="password", type="password", placeholder="Contraseña", className="form-control-sm")
                            ], className="mb-2"),
                            
                            dbc.Button(
                                "INGRESAR", 
                                id="login-button", 
                                color="success", 
                                size="md", 
                                n_clicks=0, 
                                className="w-100 fw-bold shadow-sm mt-1",
                                style={"borderRadius": "30px"}
                            ),

                            html.Div(
                                html.A("¿Olvidaste tu contraseña?", id="open-forgot-password", href="#", className="text-muted small", style={"textDecoration": "none", "fontSize": "0.8rem"}),
                                className="text-center mt-2"
                            )
                        ], className="p-3 p-md-5"),
                        
                        # PIE DE TARJETA
                        dbc.CardFooter(
                            html.Div([
                                html.A("¿No tienes cuenta? Crear Usuario", id="open-contact-modal", href="#", className="text-muted small", style={"textDecoration": "none"}),
                            ], className="text-center"),
                            className="bg-light py-2 border-0"
                        )
                    ], className="shadow-lg", style=CARD_STYLE)
                # AQUI AGREGAMOS 'position-relative' PARA QUE LA ALERTA SEPA DONDE POSICIONARSE
                ], xs=12, sm=10, md=8, lg=5, xl=4, className="position-relative"), 
                
                justify="center"
            ),

            # MODAL DE CONTACTO
            dbc.Modal([
                dbc.ModalHeader(dbc.ModalTitle("Ayuda y Soporte")),
                dbc.ModalBody([
                    html.P("La gestión de cuentas se realiza manualmente por seguridad.", className="text-muted"),
                    html.P("Por favor, contacta al administrador:", className="fw-bold"),
                    html.Hr(),
                    html.Div([
                        html.H5("Soporte Empren-D", className="text-success mb-3"),
                        html.Div([
                            html.I(className="fas fa-envelope me-3 text-secondary"),
                            html.Span("soporte@emprend.com", className="fw-bold") 
                        ], className="mb-2"),
                        html.Div([
                            html.I(className="fas fa-phone me-3 text-secondary"),
                            html.Span("+503 7000 0000", className="fw-bold")     
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
                dbc.Col([
                    # ALERTA FLOTANTE TAMBIEN AQUI
                    html.Div(id='change-password-alert', style=FLOAT_ALERT_STYLE),

                    dbc.Card([
                        html.Div(
                            className="text-center pt-3 pb-1",
                            children=[
                                html.I(className="fas fa-key", style={"fontSize": "2.5rem", "color": "#f0ad4e"}),
                                html.H3("Cambiar Contraseña", className="mt-1 fw-bold h5")
                            ]
                        ),
                        dbc.CardBody([
                            dbc.Alert("Por seguridad, crea una nueva contraseña.", color="info", className="small mb-2 py-1"),
                            
                            dbc.Label("Nueva Contraseña", className="fw-bold small mb-0"),
                            dbc.InputGroup([
                                dbc.InputGroupText(html.I(className="fas fa-lock")),
                                dbc.Input(id="new-password", type="password", placeholder="Mínimo 6 caracteres", className="form-control-sm")
                            ], className="mb-2"),

                            dbc.Label("Confirmar Contraseña", className="fw-bold small mb-0"),
                            dbc.InputGroup([
                                dbc.InputGroupText(html.I(className="fas fa-check-circle")),
                                dbc.Input(id="confirm-password", type="password", placeholder="Repite la contraseña", className="form-control-sm")
                            ], className="mb-3"),

                            dbc.Button("GUARDAR Y CONTINUAR", id="change-password-button", color="primary", size="md", n_clicks=0, className="w-100 fw-bold shadow-sm", style={"borderRadius": "30px"}),
                        ], className="p-3 p-md-5")
                    ], className="shadow-lg", style=CARD_STYLE)
                ], xs=12, sm=10, md=8, lg=5, xl=4, className="position-relative"),
                justify="center"
            )
        ], fluid=True)
    ])

# --- CALLBACKS ---

def register_login_callbacks(app):

    @app.callback(
        Output("contact-modal", "is_open"),
        [Input("open-contact-modal", "n_clicks"), 
         Input("open-forgot-password", "n_clicks"),
         Input("close-contact-modal", "n_clicks")],
        [State("contact-modal", "is_open")],
    )
    def toggle_contact_modal(n1, n2, n3, is_open):
        if n1 or n2 or n3: return not is_open
        return is_open

    @app.callback(
        Output('url', 'pathname', allow_duplicate=True),
        Output('login-alert', 'children'),
        Input('login-button', 'n_clicks'),
        [State('username', 'value'), State('password', 'value')],
        prevent_initial_call=True
    )
    def login_callback(n_clicks, username, password):
        if n_clicks is None or n_clicks < 1: raise PreventUpdate
        user = User.find(username) 
        no_url_update = dash.no_update
        if not user: return no_url_update, dbc.Alert("Usuario o contraseña incorrectos.", color="danger", dismissable=True, className="shadow-sm") 
        if user.is_blocked: return no_url_update, dbc.Alert("Tu cuenta ha sido bloqueada.", color="danger", dismissable=True, className="shadow-sm")
        if user and check_password(user.password, password):
            today = date.today()
            if not user.is_admin and user.subscription_end_date and today > user.subscription_end_date:
                return no_url_update, dbc.Alert("Tu suscripción ha expirado.", color="warning", dismissable=True, className="shadow-sm")
            login_user(user)
            if user.first_login is None: record_first_login(user.id)
            if user.must_change_password: return '/change-password', None
            return '/', None
        else: return no_url_update, dbc.Alert("Usuario o contraseña incorrectos.", color="danger", dismissable=True, className="shadow-sm")

    @app.callback(
        Output('change-password-alert', 'children'),
        Output('url', 'pathname', allow_duplicate=True),
        Output('change-password-button', 'disabled'),
        Input('change-password-button', 'n_clicks'),
        [State('new-password', 'value'), State('confirm-password', 'value')],
        prevent_initial_call=True
    )
    def update_password_callback(n_clicks, new_pass, confirm_pass):
        if n_clicks is None or n_clicks < 1: raise PreventUpdate
        if not new_pass or not confirm_pass: return dbc.Alert("Campos obligatorios.", color="warning", dismissable=True, className="shadow-sm"), dash.no_update, False
        if new_pass != confirm_pass: return dbc.Alert("Las contraseñas no coinciden.", color="danger", dismissable=True, className="shadow-sm"), dash.no_update, False
        if len(new_pass) < 4: return dbc.Alert("Contraseña muy corta.", color="warning", dismissable=True, className="shadow-sm"), dash.no_update, False
        hashed_password = set_password(new_pass)
        update_user_password(current_user.id, hashed_password)
        return dbc.Alert("¡Listo! Redirigiendo...", color="success", className="shadow-sm"), "/", True
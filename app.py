import dash
import dash_bootstrap_components as dbc
import os

# Define la instancia de la app aquí para que otros módulos puedan importarla
FONT_AWESOME = "https://use.fontawesome.com/releases/v5.15.4/css/all.css"
app = dash.Dash(
    __name__, 
    external_stylesheets=[dbc.themes.BOOTSTRAP, FONT_AWESOME]
)
server = app.server
app.config.suppress_callback_exceptions = True

# --- INICIO CORRECCIÓN ---
# Establece una llave secreta ESTÁTICA para las sesiones de usuario.
SECRET_KEY = os.environ.get('FLASK_SECRET_KEY')
if not SECRET_KEY:
    raise ValueError("No FLASK_SECRET_KEY set for Flask application")

server.secret_key = SECRET_KEY
# --- FIN CORRECCIÓN ---
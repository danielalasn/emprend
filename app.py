import dash
import dash_bootstrap_components as dbc
import os
from dotenv import load_dotenv # <--- IMPORTANTE: Importar esto

# 1. Cargar las variables del archivo .env inmediatamente
load_dotenv()

# Define la instancia de la app
FONT_AWESOME = "https://use.fontawesome.com/releases/v5.15.4/css/all.css"
app = dash.Dash(
    __name__, 
    external_stylesheets=[dbc.themes.BOOTSTRAP, FONT_AWESOME],
    title="Empren-D"
)
server = app.server
app.config.suppress_callback_exceptions = True

# 2. Ahora sí encontrará la clave
SECRET_KEY = os.environ.get('FLASK_SECRET_KEY')

if not SECRET_KEY:
    raise ValueError("No FLASK_SECRET_KEY set for Flask application. Revisa tu archivo .env")

server.secret_key = SECRET_KEY
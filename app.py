import dash
import dash_bootstrap_components as dbc
import os

# Define la instancia de la app aquí para que otros módulos puedan importarla
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
server = app.server
app.config.suppress_callback_exceptions = True

# Establece una llave secreta para las sesiones de usuario.
server.secret_key = os.urandom(24)
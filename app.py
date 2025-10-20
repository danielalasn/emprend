import dash
import dash_bootstrap_components as dbc

# Define la instancia de la app aquí para que otros módulos puedan importarla
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
server = app.server
# Permite que los callbacks se definan en archivos separados
app.config.suppress_callback_exceptions = True
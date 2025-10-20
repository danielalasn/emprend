import dash_bootstrap_components as dbc
from dash import html, dcc
from app import app, server

# Importar layouts y callbacks de cada archivo
from dashboard import get_layout as get_dashboard_layout, register_callbacks as register_dashboard_callbacks
from finances import get_layout as get_finances_layout, register_callbacks as register_finances_callbacks
from sales import get_layout as get_sales_layout, register_callbacks as register_sales_callbacks
from expenses import get_layout as get_expenses_layout, register_callbacks as register_expenses_callbacks
from products import get_layout as get_products_layout, register_callbacks as register_products_callbacks

# Registrar todos los callbacks en la app principal
register_dashboard_callbacks(app)
register_finances_callbacks(app)
register_sales_callbacks(app)
register_expenses_callbacks(app)
register_products_callbacks(app)

# Definir el layout principal de la aplicación con las pestañas
app.layout = dbc.Container([
    # ### LÍNEA AÑADIDA: El "avisador" invisible ###
    dcc.Store(id='store-data-signal'),

    dcc.Download(id="download-sales-excel"),
    dcc.Download(id="download-expenses-excel"),
    html.H1("Empren-D", className="text-center my-4"),
    dbc.Tabs(id="main-tabs", active_tab="tab-dashboard", children=[
        dbc.Tab(label="Dashboard", tab_id="tab-dashboard", children=get_dashboard_layout()),
        dbc.Tab(label="Finanzas", tab_id="tab-finances", children=get_finances_layout()),
        dbc.Tab(label="Ventas", tab_id="tab-sales", children=get_sales_layout()),
        dbc.Tab(label="Gastos", tab_id="tab-expenses", children=get_expenses_layout()),
        dbc.Tab(label="Productos", tab_id="tab-products", children=get_products_layout()),
    ])
], fluid=True)


if __name__ == '__main__':
    app.run(debug=True)
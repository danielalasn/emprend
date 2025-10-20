from dash import dcc, html, dash_table
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
import pandas as pd
from dash.dash_table.Format import Format, Scheme

from app import app
from database import load_products, load_categories, get_product_options, get_category_options, update_stock

def get_layout():
    return dbc.Tabs(id="product-sub-tabs", active_tab="sub-tab-inventory", children=[
        dbc.Tab(label="Inventario", tab_id="sub-tab-inventory", children=[
            html.Div(className="p-4", children=[
                html.H3("Inventario de Productos"),
                dash_table.DataTable(
                    id='products-table',
                    columns=[
                        {"name": "Nombre", "id": "Nombre"},
                        {"name": "Categoría", "id": "Categoría"},
                        {"name": "Descripción", "id": "description"},
                        {"name": "Costo", "id": "cost", 'type': 'numeric', 'format': Format(precision=2, scheme=Scheme.fixed)},
                        {"name": "Precio", "id": "price", 'type': 'numeric', 'format': Format(precision=2, scheme=Scheme.fixed)},
                        {"name": "Stock", "id": "stock"},
                        {"name": "Umbral Alerta", "id": "alert_threshold"}
                    ],
                    page_size=15,          # Muestra 15 filas por página
                    sort_action='native',  # Permite ordenar por cualquier columna
                )
            ])
        ]),
        dbc.Tab(label="Añadir Producto", tab_id="sub-tab-add-product", children=[
            dbc.Card(className="m-4", children=[
                dbc.CardBody([
                    html.H3("Añadir un Nuevo Producto"),
                    html.Div(id="add-product-alert"),
                    dbc.Row([
                        dbc.Col(html.Div([html.Label("Nombre del Producto"), dbc.Input(id="product-name-input", type="text")]), width=6),
                        dbc.Col(html.Div([html.Label("Categoría"), dcc.Dropdown(id="product-category-dropdown", placeholder="Crea o selecciona una categoría") ]), width=6),
                    ], className="mb-3"),
                    dbc.Row([dbc.Col(html.Div([html.Label("Descripción (Opcional)"), dbc.Textarea(id="product-desc-input")]), width=12)], className="mb-3"),
                    dbc.Row([
                        dbc.Col(html.Div([html.Label("Costo por Unidad"), dbc.Input(id="product-cost-input", type="number", min=0)]), width=3),
                        dbc.Col(html.Div([html.Label("Precio de Venta"), dbc.Input(id="product-price-input", type="number", min=0)]), width=3),
                        dbc.Col(html.Div([html.Label("Stock Inicial"), dbc.Input(id="product-stock-input", type="number", min=0, step=1)]), width=3),
                        dbc.Col(html.Div([html.Label("Alertar si stock baja de:"), dbc.Input(id="product-alert-input", type="number", min=0, step=1, value=5)]), width=3),
                    ], className="mb-3"),
                    dbc.Button("Guardar Producto", id="save-product-button", color="success", n_clicks=0, className="mt-3")
                ])
            ])
        ]),
        dbc.Tab(label="Añadir Stock", tab_id="sub-tab-add-stock", children=[
            dbc.Card(className="m-4", children=[
                dbc.CardBody([
                    html.H3("Añadir Stock a un Producto Existente", className="card-title"),
                    html.Div(id="add-stock-alert"),
                    dbc.Row([
                        dbc.Col([html.Label("Selecciona un Producto"), dcc.Dropdown(id='add-stock-product-dropdown', placeholder="Selecciona un producto...")], width=6),
                        dbc.Col([html.Label("Cantidad a Añadir"), dbc.Input(id='add-stock-quantity-input', type='number', min=1, step=1)], width=6),
                    ], className="mb-3"),
                    dbc.Button("Añadir Stock", id="submit-add-stock-button", color="info", n_clicks=0, className="mt-3")
                ])
            ])
        ]),
        dbc.Tab(label="Gestionar Categorías", tab_id="sub-tab-categories", children=[
            dbc.Row([
                dbc.Col([
                    dbc.Card(className="m-4", children=[
                        dbc.CardBody([
                            html.H3("Crear Nueva Categoría"),
                            html.Div(id="add-category-alert"),
                            dbc.Input(id="category-name-input", placeholder="Nombre de la nueva categoría", className="mb-2"),
                            dbc.Button("Guardar Categoría", id="save-category-button", color="primary")
                        ])
                    ])
                ], width=4),
                dbc.Col([
                    html.Div(className="p-4", children=[
                        html.H3("Categorías Existentes"),
                        dash_table.DataTable(id='categories-table', columns=[{"name": "ID Categoría", "id": "category_id"}, {"name": "Nombre", "id": "name"}])
                    ])
                ], width=8)
            ])
        ]),
    ])

def register_callbacks(app):
    @app.callback(
        Output('add-product-alert', 'children'),
        Input('save-product-button', 'n_clicks'),
        [State('product-name-input', 'value'), State('product-desc-input', 'value'), State('product-category-dropdown', 'value'),
         State('product-price-input', 'value'), State('product-cost-input', 'value'), State('product-stock-input', 'value'),
         State('product-alert-input', 'value')],
        prevent_initial_call=True
    )
    def add_product(n, name, desc, cat_id, price, cost, stock, alert):
        if not all([name, cat_id, price, cost, stock, alert]):
            return dbc.Alert("Todos los campos (excepto descripción) son obligatorios.", color="danger")
        
        from database import engine
        pd.DataFrame([{'name': name, 'description': desc, 'category_id': cat_id, 'price': price, 'cost': cost, 'stock': stock, 'alert_threshold': alert}]).to_sql('products', engine, if_exists='append', index=False)
        return dbc.Alert(f"¡Producto '{name}' guardado!", color="success", dismissable=True, duration=4000)

    @app.callback(
        Output('add-stock-alert', 'children'),
        Input('submit-add-stock-button', 'n_clicks'),
        [State('add-stock-product-dropdown', 'value'), State('add-stock-quantity-input', 'value')],
        prevent_initial_call=True
    )
    def add_stock(n, prod_id, qty):
        if not all([prod_id, qty]):
            return dbc.Alert("Debes seleccionar un producto y cantidad.", color="warning", dismissable=True)
        
        df = load_products()
        stock, name = df.loc[df['product_id'] == prod_id, 'stock'].iloc[0], df.loc[df['product_id'] == prod_id, 'name'].iloc[0]
        update_stock(prod_id, stock + qty)
        return dbc.Alert(f"¡Stock de '{name}' actualizado!", color="success", dismissable=True, duration=4000)

    @app.callback(
        Output('add-category-alert', 'children'),
        Input('save-category-button', 'n_clicks'),
        State('category-name-input', 'value'),
        prevent_initial_call=True
    )
    def add_category(n_clicks, name):
        if not name:
            return dbc.Alert("El nombre no puede estar vacío.", color="warning")
        
        from database import engine
        existing_cats = load_categories()
        if name.lower() in existing_cats['name'].str.lower().tolist():
            return dbc.Alert(f"La categoría '{name}' ya existe.", color="danger")
        pd.DataFrame([{'name': name.title()}]).to_sql('categories', engine, if_exists='append', index=False)
        return dbc.Alert(f"Categoría '{name.title()}' guardada.", color="success")

    @app.callback(
        Output('products-table', 'data'),
        Output('add-stock-product-dropdown', 'options'),
        Output('categories-table', 'data'),
        Output('product-category-dropdown', 'options'),
        [Input('main-tabs', 'active_tab'), Input('product-sub-tabs', 'active_tab')]
    )
    def refresh_products_components(main_tab, sub_tab):
        if main_tab != 'tab-products':
            raise PreventUpdate
        
        products_df = load_products()
        categories_df = load_categories()

        if not products_df.empty:
            display_df = pd.merge(products_df, categories_df, on='category_id', how='left').fillna("Sin Categoría")
            display_df = display_df.rename(columns={'name_x': 'Nombre', 'name_y': 'Categoría'})
            display_df = display_df[['Nombre', 'Categoría', 'description', 'cost', 'price', 'stock', 'alert_threshold']]
        else:
            display_df = pd.DataFrame(columns=['Nombre', 'Categoría', 'description', 'cost', 'price', 'stock', 'alert_threshold'])
        
        return display_df.to_dict('records'), get_product_options(), categories_df.to_dict('records'), get_category_options()
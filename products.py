from dash import dcc, html, dash_table
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
from dash.dash_table.Format import Format, Scheme
import pandas as pd
from flask_login import current_user
import dash

from app import app
from database import (
    load_products, load_categories, get_product_options, get_category_options, 
    update_stock, update_product, delete_product, update_category, delete_category,
    reactivate_product_category # Importamos la nueva función
)

def get_layout():
    return html.Div([
        dcc.Store(id='store-product-id-to-edit'),
        dcc.Store(id='store-product-id-to-delete'),
        dcc.Store(id='store-category-id-to-edit'),
        dcc.Store(id='store-category-id-to-delete'),

        dbc.Modal([
            dbc.ModalHeader("Editar Producto"),
            dbc.ModalBody(dbc.Form([
                dbc.Row([
                    dbc.Col([dbc.Label("Nombre"), dbc.Input(id='edit-product-name')]),
                    dbc.Col([dbc.Label("Categoría"), dcc.Dropdown(id='edit-product-category', options=[])]),
                ]),
                dbc.Label("Descripción", className="mt-2"),
                dbc.Textarea(id='edit-product-desc'),
                dbc.Row([
                    dbc.Col([dbc.Label("Costo"), dbc.Input(id='edit-product-cost', type='number')]),
                    dbc.Col([dbc.Label("Precio"), dbc.Input(id='edit-product-price', type='number')]),
                    dbc.Col([dbc.Label("Stock"), dbc.Input(id='edit-product-stock', type='number')]),
                    dbc.Col([dbc.Label("Umbral"), dbc.Input(id='edit-product-alert', type='number')]),
                ], className="mt-2"),
            ])),
            dbc.ModalFooter([
                dbc.Button("Cancelar", id="cancel-edit-product-button", color="secondary", className="ms-auto"),
                dbc.Button("Guardar Cambios", id="save-edited-product-button", color="primary"),
            ]),
        ], id="product-edit-modal", is_open=False),

        dbc.Modal([
            dbc.ModalHeader("Confirmar Eliminación"),
            dbc.ModalBody("¿Estás seguro de que quieres eliminar este producto? El producto se ocultará de las listas, pero se mantendrá en los reportes históricos."),
            dbc.ModalFooter([
                dbc.Button("Cancelar", id="cancel-delete-product-button", color="secondary", className="ms-auto"),
                dbc.Button("Eliminar", id="confirm-delete-product-button", color="danger"),
            ]),
        ], id="product-delete-confirm-modal", is_open=False),
        
        dbc.Modal([
            dbc.ModalHeader("Editar Categoría"),
            dbc.ModalBody(dbc.Form([
                dbc.Label("Nombre de la Categoría"),
                dbc.Input(id='edit-category-name', type='text')
            ])),
            dbc.ModalFooter([
                dbc.Button("Cancelar", id="cancel-edit-category-button", color="secondary", className="ms-auto"),
                dbc.Button("Guardar Cambios", id="save-edited-category-button", color="primary"),
            ]),
        ], id="category-edit-modal", is_open=False),

        dbc.Modal([
            dbc.ModalHeader("Confirmar Eliminación"),
            dbc.ModalBody("¿Estás seguro de que quieres eliminar esta categoría? Se ocultará de las listas y se desasignará de todos los productos."),
            dbc.ModalFooter([
                dbc.Button("Cancelar", id="cancel-delete-category-button", color="secondary", className="ms-auto"),
                dbc.Button("Eliminar", id="confirm-delete-category-button", color="danger"),
            ]),
        ], id="category-delete-confirm-modal", is_open=False),

        dbc.Tabs(id="product-sub-tabs", active_tab="sub-tab-inventory", children=[
            dbc.Tab(label="Inventario", tab_id="sub-tab-inventory", children=[
                html.Div(className="p-4", children=[
                    html.H3("Inventario de Productos"),
                    html.Div(id="products-table-container")
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
                            html.Div(id='categories-table-container')
                        ])
                    ], width=8)
                ])
            ]),
        ])
    ])

def register_callbacks(app):
    @app.callback(
        Output('add-product-alert', 'children'),
        Output('store-data-signal', 'data', allow_duplicate=True),
        Input('save-product-button', 'n_clicks'),
        [State('product-name-input', 'value'), State('product-desc-input', 'value'), State('product-category-dropdown', 'value'),
         State('product-price-input', 'value'), State('product-cost-input', 'value'), State('product-stock-input', 'value'),
         State('product-alert-input', 'value'), State('store-data-signal', 'data')],
        prevent_initial_call=True
    )
    def add_product(n, name, desc, cat_id, price, cost, stock, alert, signal_data):
        if n is None or n < 1:
            raise PreventUpdate
        if not current_user.is_authenticated:
            raise PreventUpdate
        
        user_id = current_user.id
        if not all([name, cat_id, price is not None, cost is not None, stock is not None, alert is not None]):
            return dbc.Alert("Todos los campos (excepto descripción) son obligatorios.", color="danger"), dash.no_update

        from database import engine
        pd.DataFrame([{'name': name, 'description': desc or "", 'category_id': cat_id, 
                       'price': price, 'cost': cost, 'stock': stock, 
                       'alert_threshold': alert, 'user_id': user_id, 'is_active': True}]).to_sql('products', engine, if_exists='append', index=False)
        
        new_signal = (signal_data or 0) + 1
        return dbc.Alert(f"¡Producto '{name}' guardado!", color="success", dismissable=True, duration=4000), new_signal

    @app.callback(
        Output('add-stock-alert', 'children'),
        Output('store-data-signal', 'data', allow_duplicate=True),
        Input('submit-add-stock-button', 'n_clicks'),
        [State('add-stock-product-dropdown', 'value'), State('add-stock-quantity-input', 'value'),
         State('store-data-signal', 'data')],
        prevent_initial_call=True
    )
    def add_stock(n, prod_id, qty, signal_data):
        if n is None or n < 1:
            raise PreventUpdate
        if not current_user.is_authenticated:
            raise PreventUpdate
        
        user_id = current_user.id
        if not all([prod_id, qty]):
            return dbc.Alert("Debes seleccionar un producto y cantidad.", color="warning", dismissable=True), dash.no_update
        
        df = load_products(user_id)
        stock, name = df.loc[df['product_id'] == prod_id, 'stock'].iloc[0], df.loc[df['product_id'] == prod_id, 'name'].iloc[0]
        update_stock(prod_id, stock + qty, user_id)
        
        new_signal = (signal_data or 0) + 1
        return dbc.Alert(f"¡Stock de '{name}' actualizado!", color="success", dismissable=True, duration=4000), new_signal

    # --- CALLBACK CORREGIDO: AÑADIR CATEGORÍA (CON REACTIVACIÓN) ---
    @app.callback(
        Output('add-category-alert', 'children'),
        Output('store-data-signal', 'data', allow_duplicate=True),
        Input('save-category-button', 'n_clicks'),
        [State('category-name-input', 'value'),
         State('store-data-signal', 'data')],
        prevent_initial_call=True
    )
    def add_category(n_clicks, name, signal_data):
        if n_clicks is None or n_clicks < 1:
            raise PreventUpdate
        if not current_user.is_authenticated:
            raise PreventUpdate
        
        user_id = current_user.id
        if not name:
            return dbc.Alert("El nombre no puede estar vacío.", color="warning"), dash.no_update
        
        from database import engine
        
        # Cargamos TODAS las categorías (activas e inactivas)
        existing_cats = load_categories(user_id)
        
        if not existing_cats.empty and 'is_active' in existing_cats.columns:
            match = existing_cats[existing_cats['name'].str.lower() == name.lower()]
            if not match.empty:
                category_data = match.iloc[0]
                
                # Si existe Y está activa, mostrar error
                if category_data['is_active']:
                    return dbc.Alert(f"La categoría '{name}' ya existe.", color="danger"), dash.no_update
                
                # Si existe PERO está inactiva, reactivarla
                else:
                    reactivate_product_category(category_data['category_id'], user_id)
                    new_signal = (signal_data or 0) + 1
                    return dbc.Alert(f"Categoría '{category_data['name']}' reactivada.", color="success"), new_signal
        
        # Si no existe (o si la columna 'is_active' aún no existe), crearla nueva
        pd.DataFrame([{'name': name.title(), 'user_id': user_id, 'is_active': True}]).to_sql('categories', engine, if_exists='append', index=False)
        
        new_signal = (signal_data or 0) + 1
        return dbc.Alert(f"Categoría '{name.title()}' guardada.", color="success"), new_signal

    # --- CALLBACK CORREGIDO: REFRESCAR COMPONENTES (PARA LÓGICA DE PESTAÑAS Y FILTROS) ---
    @app.callback(
        Output('products-table-container', 'children'),
        Output('categories-table-container', 'children'),
        Output('add-stock-product-dropdown', 'options'),
        Output('product-category-dropdown', 'options'),
        [Input('product-sub-tabs', 'active_tab'), # Trigger 1
         Input('store-data-signal', 'data')] # Trigger 2
    )
    def refresh_products_components(sub_tab, signal_data):
        # --- START OPTIMIZATION ---
        if not current_user.is_authenticated:
            raise PreventUpdate

        # Check triggers: Only proceed if the signal changed,
        # OR if the sub_tab input triggered.
        # (We assume this callback should always run when the sub_tab changes
        # within the Products main tab, so no extra check needed here like in Sales)
        triggered_id = dash.callback_context.triggered_id
        if not triggered_id: # Initial load
             pass # Allow initial load
        # No specific PreventUpdate needed here based only on trigger,
        # as changing the sub-tab *should* trigger this refresh.
        # --- END OPTIMIZATION ---

        user_id = current_user.id
        products_df = load_products(user_id)
        # ... rest of the function (including the logic that uses sub_tab
        #     to decide whether to render products_table or categories_table)...
        user_id = current_user.id
        # Cargamos todos los productos y categorías una vez
        products_df = load_products(user_id)
        categories_df = load_categories(user_id)

        # --- Generar opciones para Dropdowns (usando las funciones de DB que ya filtran) ---
        product_options = get_product_options(user_id)
        category_options = get_category_options(user_id)

        # --- Lógica de Pestañas ---
        products_table_content = dash.no_update
        categories_table_content = dash.no_update

        # Solo genera la tabla de productos si la pestaña 'Inventario' está activa
        if sub_tab == 'sub-tab-inventory':
            display_df = pd.DataFrame()
            if not products_df.empty:
                # Filtrar solo productos activos para la tabla
                df_active = products_df
                if 'is_active' in products_df.columns:
                    df_active = products_df[products_df['is_active'] == True].copy()
                
                df = pd.merge(df_active, categories_df, on='category_id', how='left').fillna("Sin Categoría")
                df = df.rename(columns={'name_x': 'Nombre', 'name_y': 'Categoría'})
                df['editar'] = "✏️"
                df['eliminar'] = "🗑️"
                display_df = df
            
            products_table_content = dash_table.DataTable(
                id='products-table',
                columns=[
                    {"name": "Nombre", "id": "Nombre"}, {"name": "Categoría", "id": "Categoría"},
                    {"name": "Descripción", "id": "description"},
                    {"name": "Costo", "id": "cost", 'type': 'numeric', 'format': Format(precision=2, scheme=Scheme.fixed)},
                    {"name": "Precio", "id": "price", 'type': 'numeric', 'format': Format(precision=2, scheme=Scheme.fixed)},
                    {"name": "Stock", "id": "stock"}, {"name": "Umbral Alerta", "id": "alert_threshold"},
                    {"name": "Editar", "id": "editar"}, {"name": "Eliminar", "id": "eliminar"}
                ],
                data=display_df.to_dict('records'),
                page_size=15, sort_action='native', filter_action='native',
                style_cell_conditional=[{'if': {'column_id': 'editar'}, 'cursor': 'pointer'}, {'if': {'column_id': 'eliminar'}, 'cursor': 'pointer'}]
            )
        
        # Solo genera la tabla de categorías si la pestaña 'Categorías' está activa
        elif sub_tab == 'sub-tab-categories':
            categories_df_display = pd.DataFrame()
            if not categories_df.empty:
                # Filtrar solo categorías activas para la tabla
                categories_df_active = categories_df
                if 'is_active' in categories_df.columns:
                     categories_df_active = categories_df[categories_df['is_active'] == True].copy()
                
                categories_df_display = categories_df_active
                categories_df_display['editar'] = "✏️"
                categories_df_display['eliminar'] = "🗑️"

            categories_table_content = dash_table.DataTable(
                id='categories-table', 
                columns=[
                    {"name": "ID", "id": "category_id"}, {"name": "Nombre", "id": "name"},
                    {"name": "Editar", "id": "editar"}, {"name": "Eliminar", "id": "eliminar"}
                ],
                data=categories_df_display.to_dict('records'),
                style_cell_conditional=[{'if': {'column_id': 'editar'}, 'cursor': 'pointer'}, {'if': {'column_id': 'eliminar'}, 'cursor': 'pointer'}]
            )
        
        return products_table_content, categories_table_content, product_options, category_options

    @app.callback(
        Output('product-edit-modal', 'is_open'),
        Output('product-delete-confirm-modal', 'is_open'),
        Output('store-product-id-to-edit', 'data'),
        Output('store-product-id-to-delete', 'data'),
        Output('edit-product-name', 'value'),
        Output('edit-product-category', 'value'),
        Output('edit-product-desc', 'value'),
        Output('edit-product-cost', 'value'),
        Output('edit-product-price', 'value'),
        Output('edit-product-stock', 'value'),
        Output('edit-product-alert', 'value'),
        Output('edit-product-category', 'options'), # <-- Añadido para poblar dropdown
        Input('products-table', 'active_cell'),
        State('products-table', 'derived_virtual_data'),
        prevent_initial_call=True
    )
    def open_product_modals(active_cell, data):
        if not current_user.is_authenticated or not active_cell or 'row' not in active_cell: 
            raise PreventUpdate

        user_id = current_user.id
        row_idx = active_cell['row']
        col_id = active_cell['column_id']

        if not data or row_idx >= len(data):
            raise PreventUpdate
        
        product_name_clicked = data[row_idx]['Nombre']
        products_df = load_products(user_id)
        product_info = products_df[products_df['name'] == product_name_clicked].iloc[0]
        product_id = int(product_info['product_id'])

        # Preparamos las opciones del dropdown para el modal
        category_options = get_category_options(user_id)
        no_update_list = [dash.no_update] * 8

        if col_id == "editar":
            cat_val = int(product_info['category_id']) if pd.notna(product_info['category_id']) else None
            return True, False, product_id, None, product_info['name'], cat_val, product_info['description'], product_info['cost'], product_info['price'], product_info['stock'], product_info['alert_threshold'], category_options
        
        elif col_id == "eliminar":
            return False, True, None, product_id, *no_update_list

        return False, False, None, None, *no_update_list

    @app.callback(
        Output('product-edit-modal', 'is_open', allow_duplicate=True),
        Output('store-data-signal', 'data', allow_duplicate=True),
        Input('save-edited-product-button', 'n_clicks'),
        [State('store-product-id-to-edit', 'data'),
         State('edit-product-name', 'value'), State('edit-product-desc', 'value'),
         State('edit-product-category', 'value'), State('edit-product-price', 'value'),
         State('edit-product-cost', 'value'), State('edit-product-stock', 'value'),
         State('edit-product-alert', 'value'), State('store-data-signal', 'data')],
        prevent_initial_call=True
    )
    def save_edited_product(n, product_id, name, desc, cat_id, price, cost, stock, alert, signal):
        if n is None: raise PreventUpdate
        if not product_id: raise PreventUpdate
        
        new_data = {
            "name": name, "description": desc, "category_id": cat_id, "price": float(price),
            "cost": float(cost), "stock": int(stock), "alert_threshold": int(alert)
        }
        update_product(product_id, new_data, current_user.id)
        
        return False, (signal or 0) + 1

    @app.callback(
        Output('product-delete-confirm-modal', 'is_open', allow_duplicate=True),
        Output('store-data-signal', 'data', allow_duplicate=True),
        Input('confirm-delete-product-button', 'n_clicks'),
        [State('store-product-id-to-delete', 'data'), State('store-data-signal', 'data')],
        prevent_initial_call=True
    )
    def confirm_delete_product(n, product_id, signal):
        if n is None: raise PreventUpdate
        if not product_id: raise PreventUpdate
        # Llama a la función de borrado suave
        delete_product(product_id, current_user.id)
        return False, (signal or 0) + 1

    @app.callback(
        Output('product-edit-modal', 'is_open', allow_duplicate=True),
        Output('product-delete-confirm-modal', 'is_open', allow_duplicate=True),
        [Input('cancel-edit-product-button', 'n_clicks'), Input('cancel-delete-product-button', 'n_clicks')],
        prevent_initial_call=True
    )
    def close_product_modals(n_cancel_edit, n_cancel_delete):
        return False, False

    @app.callback(
        Output('category-edit-modal', 'is_open'),
        Output('category-delete-confirm-modal', 'is_open'),
        Output('store-category-id-to-edit', 'data'),
        Output('store-category-id-to-delete', 'data'),
        Output('edit-category-name', 'value'),
        Input('categories-table', 'active_cell'),
        State('categories-table', 'derived_virtual_data'),
        prevent_initial_call=True
    )
    def open_category_modals(active_cell, data):
        if not current_user.is_authenticated or not active_cell or 'row' not in active_cell:
            raise PreventUpdate

        row_idx = active_cell['row']
        col_id = active_cell['column_id']

        if not data or row_idx >= len(data):
            raise PreventUpdate
            
        category_id = data[row_idx]['category_id']
        category_info = data[row_idx]
        
        if col_id == 'editar':
            return True, False, category_id, None, category_info['name']
        
        elif col_id == 'eliminar':
            return False, True, None, category_id, dash.no_update

        return False, False, None, None, dash.no_update

    @app.callback(
        Output('category-edit-modal', 'is_open', allow_duplicate=True),
        Output('store-data-signal', 'data', allow_duplicate=True),
        Input('save-edited-category-button', 'n_clicks'),
        [State('store-category-id-to-edit', 'data'), State('edit-category-name', 'value'), State('store-data-signal', 'data')],
        prevent_initial_call=True
    )
    def save_edited_category(n, category_id, name, signal):
        if n is None: raise PreventUpdate
        if not category_id: raise PreventUpdate
        update_category(category_id, {"name": name}, current_user.id)
        return False, (signal or 0) + 1

    @app.callback(
        Output('category-delete-confirm-modal', 'is_open', allow_duplicate=True),
        Output('store-data-signal', 'data', allow_duplicate=True),
        Input('confirm-delete-category-button', 'n_clicks'),
        [State('store-category-id-to-delete', 'data'), State('store-data-signal', 'data')],
        prevent_initial_call=True
    )
    def confirm_delete_category(n, category_id, signal):
        if n is None: raise PreventUpdate
        if not category_id: raise PreventUpdate
        # Llama a la función de borrado suave
        delete_category(category_id, current_user.id)
        return False, (signal or 0) + 1

    @app.callback(
        Output('category-edit-modal', 'is_open', allow_duplicate=True),
        Output('category-delete-confirm-modal', 'is_open', allow_duplicate=True),
        [Input('cancel-edit-category-button', 'n_clicks'), Input('cancel-delete-category-button', 'n_clicks')],
        prevent_initial_call=True
    )
    def close_category_modals(n_cancel_edit, n_cancel_delete):
        return False, False
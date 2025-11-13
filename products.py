# products.py
from dash import dcc, html, dash_table
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output, State, ALL
from dash.exceptions import PreventUpdate
from dash.dash_table.Format import Format, Scheme, Symbol
import pandas as pd
from flask_login import current_user
import dash
from sqlalchemy import text

from app import app
from database import (
    load_products, load_categories, get_product_options, get_category_options,
    update_stock, update_product, delete_product, update_category, delete_category,
    reactivate_product_category, get_raw_material_options, get_linked_material_quantities,
    save_product_materials, get_material_costs_map, engine, deduct_materials_for_production,
    delete_products_bulk, add_product_category_strict
)

def get_layout():
    try:
        user_id = int(current_user.id) if current_user.is_authenticated else None
        category_opts = get_category_options(user_id) if user_id else []
        material_opts = get_raw_material_options(user_id) if user_id else []
    except Exception as e:
        category_opts = []
        material_opts = []

    return html.Div([
        dcc.Store(id='store-product-id-to-edit'),
        dcc.Store(id='store-product-id-to-delete'),
        dcc.Store(id='store-category-id-to-edit'),
        dcc.Store(id='store-category-id-to-delete'),
        dcc.Store(id='store-edit-material-quantities', storage_type='memory'),

        # --- MODALES ---
        dbc.Modal([
            dbc.ModalHeader("Editar Producto"),
            dbc.ModalBody(dbc.Form([
                html.Div(id='edit-product-alert'),
                dbc.Row([
                    dbc.Col([dbc.Label("Nombre"), dbc.Input(id='edit-product-name')], xs=12, md=6, className="mb-2"),
                    dbc.Col([dbc.Label("Categoría"), dcc.Dropdown(id='edit-product-category', options=category_opts)], xs=12, md=6, className="mb-2"),
                ]),
                dbc.Label("Descripción", className="mt-2"),
                dbc.Textarea(id='edit-product-desc', className="mb-2"),
                dbc.Row([
                    dbc.Col([dbc.Label("Costo Base"), dbc.Input(id='edit-product-cost', type='number', min=0, step=0.01)], xs=6, md=3),
                    dbc.Col([dbc.Label("Precio Venta"), dbc.Input(id='edit-product-price', type='number', min=0, step=0.01)], xs=6, md=3),
                    dbc.Col([dbc.Label("Stock"), dbc.Input(id='edit-product-stock', type='number', min=0, step=1)], xs=6, md=3),
                    dbc.Col([dbc.Label("Alerta"), dbc.Input(id='edit-product-alert', type='number', min=0, step=1)], xs=6, md=3),
                ], className="mt-2"),
                html.Hr(),
                html.H5("Insumos Utilizados", className="mt-3 mb-3"),
                 dbc.Row([
                    dbc.Col(html.Div([
                        dbc.Label("Selecciona los insumos:", html_for="edit-product-materials-dropdown"),
                        dcc.Dropdown(id="edit-product-materials-dropdown", options=material_opts, multi=True, placeholder="Selecciona insumos...")
                    ]), width=12)
                ], className="mb-3"),
                html.Div(id='edit-product-material-quantities-container', children=[]),
            ])),
            dbc.ModalFooter([
                dbc.Button("Cancelar", id="cancel-edit-product-button", color="secondary", className="ms-auto"),
                dbc.Button("Guardar Cambios", id="save-edited-product-button", color="primary"),
            ]),
        ], id="product-edit-modal", is_open=False, size="lg"),

        dbc.Modal([
            dbc.ModalHeader("Confirmar Eliminación"),
            dbc.ModalBody("¿Estás seguro de que quieres eliminar este producto?"),
            dbc.ModalFooter([
                dbc.Button("Cancelar", id="cancel-delete-product-button", color="secondary", className="ms-auto"),
                dbc.Button("Eliminar", id="confirm-delete-product-button", color="danger"),
            ]),
        ], id="product-delete-confirm-modal", is_open=False),

        dbc.Modal([
            dbc.ModalHeader("Editar Categoría"),
            dbc.ModalBody(dbc.Form([dbc.Label("Nombre de la Categoría"), dbc.Input(id='edit-category-name', type='text')])),
            dbc.ModalFooter([
                dbc.Button("Cancelar", id="cancel-edit-category-button", color="secondary", className="ms-auto"),
                dbc.Button("Guardar Cambios", id="save-edited-category-button", color="primary"),
            ]),
        ], id="category-edit-modal", is_open=False),

        dbc.Modal([
            dbc.ModalHeader("Confirmar Eliminación"),
            dbc.ModalBody("¿Estás seguro de que quieres eliminar esta categoría?"),
            dbc.ModalFooter([
                dbc.Button("Cancelar", id="cancel-delete-category-button", color="secondary", className="ms-auto"),
                dbc.Button("Eliminar", id="confirm-delete-category-button", color="danger"),
            ]),
        ], id="category-delete-confirm-modal", is_open=False),

        # --- TABS PRINCIPALES ---
        dbc.Tabs(id="product-sub-tabs", active_tab="sub-tab-inventory", children=[
            
            # --- Tab: Inventario ---
            dbc.Tab(label="Inventario", tab_id="sub-tab-inventory", children=[
                html.Div(className="p-2 p-md-4", children=[
                    html.H3("Inventario de Productos", className="mb-3"),
                    dbc.Button("Borrar Seleccionados", id="delete-selected-products-btn", color="danger", n_clicks=0, className="mb-3"),
                    html.Div(id='bulk-delete-products-output'),
                    
                    dash_table.DataTable(
                        id='products-table',
                        columns=[
                            {"name": "ID", "id": "product_id"},
                            {"name": "Nombre", "id": "Nombre"}, {"name": "Categoría", "id": "Categoría"},
                            {"name": "Descripción", "id": "description"},
                            {"name": "Costo Base", "id": "cost", 'type': 'numeric', 'format': Format(precision=2, scheme=Scheme.fixed, symbol=Symbol.yes)},
                            {"name": "Precio", "id": "price", 'type': 'numeric', 'format': Format(precision=2, scheme=Scheme.fixed, symbol=Symbol.yes)},
                            {"name": "Stock", "id": "stock"}, {"name": "Alerta", "id": "alert_threshold"},
                            {"name": "Editar", "id": "editar"}, {"name": "Eliminar", "id": "eliminar"}
                        ],
                        data=[], 
                        hidden_columns=['product_id'], 
                        css=[{"selector": ".show-hide", "rule": "display: none"}],
                        page_size=15, 
                        sort_action='native', 
                        filter_action='native',
                        row_selectable='multi',
                        selected_rows=[],
                        selected_row_ids=[],
                        style_table={'overflowX': 'auto'}, 
                        style_cell={'textAlign': 'left'}, 
                        style_cell_conditional=[{'if': {'column_id': c}, 'cursor': 'pointer', 'textAlign': 'center'} for c in ['editar', 'eliminar']]
                    )
                ])
            ]),

            # --- Tab: Añadir Producto ---
            dbc.Tab(label="Añadir Producto", tab_id="sub-tab-add-product", children=[
                dbc.Card(className="m-2 m-md-4 shadow-sm", children=[ 
                    dbc.CardBody([
                        html.H3("Añadir un Nuevo Producto", className="card-title mb-4"), 
                        html.Div(id="add-product-alert"),
                        
                        dbc.Row([
                            dbc.Col(html.Div([html.Label("Nombre", className="fw-bold small"), dbc.Input(id="product-name-input", placeholder="Nombre del producto")]), xs=12, md=6, className="mb-3 mb-md-0"),
                            dbc.Col(html.Div([html.Label("Categoría", className="fw-bold small"), dcc.Dropdown(id="product-category-dropdown", options=category_opts, placeholder="Selecciona...") ]), xs=12, md=6),
                        ], className="mb-3"),
                        
                        dbc.Row([dbc.Col(html.Div([html.Label("Descripción (Opcional)", className="fw-bold small"), dbc.Textarea(id="product-desc-input", placeholder="Descripción breve")]), width=12)], className="mb-3"),
                        
                        dbc.Row([
                            dbc.Col(html.Div([html.Label("Costo Base", className="fw-bold small"), dbc.Input(id="product-cost-input", type="number", min=0, step=0.01, placeholder="0.00")]), xs=6, md=3),
                            dbc.Col(html.Div([html.Label("Precio Venta", className="fw-bold small"), dbc.Input(id="product-price-input", type="number", min=0, step=0.01, placeholder="0.00")]), xs=6, md=3),
                            dbc.Col(html.Div([html.Label("Stock Inicial", className="fw-bold small"), dbc.Input(id="product-stock-input", type="number", min=0, step=1, placeholder="0")]), xs=6, md=3),
                            dbc.Col(html.Div([html.Label("Alerta Stock", className="fw-bold small"), dbc.Input(id="product-alert-input", type="number", min=0, step=1, placeholder="5" )]), xs=6, md=3),
                        ], className="mb-3"),
                        
                        html.Hr(), html.H4("Insumos Utilizados", className="mt-4 mb-3"),
                        dbc.Row([
                            dbc.Col(html.Div([
                                dbc.Label("Selecciona Insumos:", html_for="add-product-materials-dropdown", className="fw-bold small"),
                                dcc.Dropdown(id="add-product-materials-dropdown", options=material_opts, multi=True, placeholder="Selecciona...")
                            ]), width=12)
                        ], className="mb-3"),
                        html.Div(id='add-product-material-quantities-container', children=[]),
                        
                        dbc.Button("Guardar Producto", id="save-product-button", color="success", n_clicks=0, className="mt-3 w-100 w-md-auto")
                    ])
                ])
            ]),

            # --- Tab: Añadir Stock ---
            dbc.Tab(label="Añadir Stock", tab_id="sub-tab-add-stock", children=[
                dbc.Card(className="m-2 m-md-4 shadow-sm", children=[
                    dbc.CardBody([
                        html.H3("Añadir Stock Producto Existente", className="card-title mb-4"), 
                        html.Div(id="add-stock-alert"),
                        
                        dbc.Row([
                            dbc.Col([html.Label("Producto", className="fw-bold small"), dcc.Dropdown(id='add-stock-product-dropdown', placeholder="Selecciona...")], xs=12, md=6, className="mb-3 mb-md-0"),
                            dbc.Col([html.Label("Cantidad a Añadir", className="fw-bold small"), dbc.Input(id='add-stock-quantity-input', type='number', min=1, step=1, placeholder="0")], xs=12, md=6),
                        ], className="mb-3"),
                        
                        dbc.Button("Añadir Stock", id="submit-add-stock-button", color="info", n_clicks=0, className="mt-3 w-100 w-md-auto")
                    ])
                ])
            ]),

            # --- Tab: Gestionar Categorías ---
            dbc.Tab(label="Gestionar Categorías", tab_id="sub-tab-categories", children=[
                dbc.Row([
                    dbc.Col([
                        dbc.Card(className="m-2 m-md-4 shadow-sm", children=[ 
                            dbc.CardBody([
                                html.H3("Crear Nueva Categoría", className="card-title h4 mb-3"), 
                                html.Div(id="add-category-alert"),
                                dbc.Input(id="category-name-input", placeholder="Nombre...", className="mb-3"),
                                dbc.Button("Guardar Categoría", id="save-category-button", color="primary", className="w-100")
                            ])
                        ])
                    ], xs=12, md=4, className="mb-4 mb-md-0"), 
                    
                    dbc.Col([
                        html.Div(className="p-2 p-md-4", children=[
                            html.H3("Categorías Existentes", className="mb-3"), 
                            html.Div(id='categories-table-container', style={'overflowX': 'auto'}) 
                        ])
                    ], xs=12, md=8)
                ])
            ]),
        ]) 
    ])

# --- Callbacks ---
def register_callbacks(app):

    # 1. AÑADIR PRODUCTO
    @app.callback(
        Output('add-product-alert', 'children'),
        Output('store-data-signal', 'data', allow_duplicate=True),
        Input('save-product-button', 'n_clicks'),
        [State('product-name-input', 'value'), State('product-desc-input', 'value'),
         State('product-category-dropdown', 'value'), State('product-price-input', 'value'),
         State('product-cost-input', 'value'), State('product-stock-input', 'value'),
         State('product-alert-input', 'value'),
         State('add-product-materials-dropdown', 'value'),
         State('add-product-materials-dropdown', 'options'),
         State({'type': 'add-material-quantity', 'index': ALL}, 'value'),
         State({'type': 'add-material-quantity', 'index': ALL}, 'id'),
         State('store-data-signal', 'data')],
        prevent_initial_call=True
    )
    def add_product(n, name, desc, cat_id, price, cost, stock, alert,
                    selected_material_ids, all_material_options,
                    material_quantities, material_input_ids,
                    signal_data):
        if n is None or n < 1: raise PreventUpdate
        if not current_user.is_authenticated: raise PreventUpdate

        user_id = int(current_user.id)
        
        if not all([name, cat_id, price is not None]):
            return dbc.Alert("Nombre, Categoría y Precio son obligatorios.", color="danger"), dash.no_update
        
        try:
            price_f = float(price); cost_f = float(cost) if cost is not None else 0
            stock_i = int(stock) if stock is not None else 0; alert_i = int(alert) if alert is not None else 0
            if price_f <= 0 or cost_f < 0 or stock_i < 0 or alert_i < 0: raise ValueError("Inv Num")
        except (ValueError, TypeError):
             return dbc.Alert("Precio, Costo Base, Stock y Alerta deben ser números válidos (Precio > 0).", color="danger"), dash.no_update

        material_data_to_save = {}
        error_messages = []
        options_map = {opt['value']: opt['label'] for opt in all_material_options}
        quantities_map = {inp_id['index']: qty for inp_id, qty in zip(material_input_ids, material_quantities)}

        if selected_material_ids:
            for mat_id in selected_material_ids:
                material_label = options_map.get(mat_id, f"ID {mat_id}")
                qty_input = quantities_map.get(mat_id)
                if qty_input is None or str(qty_input).strip() == "":
                    error_messages.append(f"Falta la cantidad para '{material_label}'.")
                    continue
                try:
                    qty_float = float(qty_input)
                    if qty_float <= 0: error_messages.append(f"La cantidad para '{material_label}' debe ser positiva.")
                    else: material_data_to_save[mat_id] = qty_float
                except: error_messages.append(f"La cantidad para '{material_label}' no es válida.")

        if error_messages:
             error_list_items = [html.Li(msg) for msg in error_messages]
             return dbc.Alert([html.P("Errores en insumos:"), html.Ul(error_list_items)], color="danger"), dash.no_update
        
        total_material_cost = 0.0
        if material_data_to_save:
            material_costs_map = get_material_costs_map(user_id, material_data_to_save.keys())
            for mat_id, qty in material_data_to_save.items():
                total_material_cost += material_costs_map.get(mat_id, 0.0) * qty
        total_product_cost = cost_f + total_material_cost

        clean_name = " ".join(name.strip().split())

        product_data = {
            'name': clean_name, 'description': desc or "", 'category_id': cat_id,
            'price': price_f, 'cost': total_product_cost, 'stock': stock_i,
            'alert_threshold': alert_i, 'user_id': user_id, 'is_active': True
        }

        try:
            with engine.connect() as connection:
                with connection.begin(): 
                    check_query = text("""
                        SELECT product_id FROM products 
                        WHERE user_id = :uid AND category_id = :cid 
                        AND LOWER(name) = LOWER(:name) AND is_active = TRUE
                    """)
                    existing_prod = connection.execute(check_query, {"uid": user_id, "cid": cat_id, "name": clean_name}).fetchone()
                    
                    if existing_prod:
                        return dbc.Alert(f"Error: El producto '{clean_name}' ya existe en esta categoría.", color="danger"), dash.no_update

                    insert_prod_query = text("""
                        INSERT INTO products (name, description, category_id, price, cost, stock, alert_threshold, user_id, is_active)
                        VALUES (:name, :description, :category_id, :price, :cost, :stock, :alert_threshold, :user_id, :is_active)
                        RETURNING product_id
                    """)
                    result = connection.execute(insert_prod_query, product_data)
                    new_product_id = result.scalar_one_or_none()
                    
                    if material_data_to_save:
                        success, msg = save_product_materials(connection, new_product_id, material_data_to_save, user_id)
                        if not success: raise Exception(msg)

                    if stock_i > 0:
                        success, msg = deduct_materials_for_production(connection, new_product_id, stock_i, user_id)
                        if not success: raise Exception(msg)
                
        except Exception as e:
            return dbc.Alert(f"Error al guardar: {e}", color="danger"), dash.no_update

        return dbc.Alert(f"¡Producto '{clean_name}' guardado!", color="success", dismissable=True), (signal_data or 0) + 1

    # 2. AÑADIR STOCK
    @app.callback(
        Output('add-stock-alert', 'children'),
        Output('store-data-signal', 'data', allow_duplicate=True),
        Input('submit-add-stock-button', 'n_clicks'),
        [State('add-stock-product-dropdown', 'value'), State('add-stock-quantity-input', 'value'),
        State('store-data-signal', 'data')],
        prevent_initial_call=True
    )
    def add_stock(n, prod_id, qty, signal_data):
        if n is None or n < 1: raise PreventUpdate
        if not current_user.is_authenticated: raise PreventUpdate
        user_id = int(current_user.id)
        if not all([prod_id, qty]): return dbc.Alert("Faltan datos.", color="warning"), dash.no_update
        
        try:
            qty_int = int(qty)
            if qty_int <= 0: raise ValueError
        except: return dbc.Alert("Cantidad inválida.", color="danger"), dash.no_update

        try:
            with engine.connect() as connection:
                with connection.begin():
                    success, msg = deduct_materials_for_production(connection, prod_id, qty_int, user_id)
                    if not success: raise Exception(msg)
                    
                    connection.execute(text("UPDATE products SET stock = stock + :q WHERE product_id = :pid AND user_id = :uid"), 
                                       {"q": qty_int, "pid": prod_id, "uid": user_id})
            
            return dbc.Alert(f"¡Stock actualizado! Insumos descontados.", color="success", dismissable=True), (signal_data or 0) + 1
        except Exception as e:
             return dbc.Alert(f"Error: {e}", color="danger", dismissable=True), dash.no_update

    # 3. AÑADIR CATEGORÍA
    @app.callback(
        Output('add-category-alert', 'children'),
        Output('store-data-signal', 'data', allow_duplicate=True),
        Input('save-category-button', 'n_clicks'),
        [State('category-name-input', 'value'), State('store-data-signal', 'data')],
        prevent_initial_call=True
    )
    def add_category(n, name, signal_data):
        if n is None or n < 1: raise PreventUpdate
        if not current_user.is_authenticated: raise PreventUpdate
        user_id = int(current_user.id)
        if not name or not name.strip(): return dbc.Alert("Nombre vacío.", color="warning"), dash.no_update

        try:
            success, msg = add_product_category_strict(name, user_id)
            return dbc.Alert(msg, color="success" if success else "danger"), (signal_data or 0) + 1
        except Exception as e:
            return dbc.Alert(f"Error: {e}", color="danger"), dash.no_update

    # 4. REFRESCAR COMPONENTES
    @app.callback(
        Output('products-table', 'data'), 
        Output('categories-table-container', 'children'),
        Output('add-stock-product-dropdown', 'options'), 
        Output('product-category-dropdown', 'options'),
        Output('add-product-materials-dropdown', 'options'),
        [Input('product-sub-tabs', 'active_tab'), Input('store-data-signal', 'data')]
    )
    def refresh_products_components(sub_tab, signal_data):
        if not current_user.is_authenticated: raise PreventUpdate
        user_id = int(current_user.id) 
        products_df = load_products(user_id); categories_df = load_categories(user_id)
        category_options = get_category_options(user_id)
        material_options = get_raw_material_options(user_id)
        
        products_table_data = dash.no_update
        categories_table_content = dash.no_update
        
        add_stock_options = []
        if not products_df.empty:
            active_prods = products_df[products_df['is_active'] == True].copy() if 'is_active' in products_df.columns else products_df.copy()
            if not active_prods.empty:
                merged = pd.merge(active_prods, categories_df, on='category_id', how='left')
                merged['cat_name'] = merged['name_y'].fillna('Sin Categoría')
                merged['prod_name'] = merged['name_x']
                add_stock_options = [{'label': f"{row['cat_name']} - {row['prod_name']} (Actual: {row['stock']})", 'value': row['product_id']} for _, row in merged.iterrows()]

        display_df = pd.DataFrame()
        if not products_df.empty:
            df_active = products_df[products_df['is_active'] == True].copy() if 'is_active' in products_df.columns else products_df.copy()
            for col in ['cost', 'price']: df_active[col] = pd.to_numeric(df_active[col], errors='coerce')
            df = pd.merge(df_active, categories_df, on='category_id', how='left').fillna("Sin Categoría")
            df = df.rename(columns={'name_x': 'Nombre', 'name_y': 'Categoría'})
            df['editar'] = "✏️"; df['eliminar'] = "🗑️"; df['id'] = df['product_id']
            display_df = df
        products_table_data = display_df.to_dict('records')

        if sub_tab == 'sub-tab-categories':
            categories_df_display = pd.DataFrame()
            if not categories_df.empty:
                cats_active = categories_df[categories_df['is_active'] == True].copy() if 'is_active' in categories_df.columns else categories_df.copy()
                categories_df_display = cats_active; categories_df_display['editar'] = "✏️"; categories_df_display['eliminar'] = "🗑️"
            categories_table_content = dash_table.DataTable(id='categories-table',
                columns=[{"name": "ID", "id": "category_id"}, {"name": "Nombre", "id": "name"}, {"name": "Editar", "id": "editar"}, {"name": "Eliminar", "id": "eliminar"}],
                data=categories_df_display.to_dict('records'), page_size=10, style_cell={'textAlign': 'left'},
                style_cell_conditional=[{'if': {'column_id': c}, 'cursor': 'pointer', 'textAlign': 'center'} for c in ['editar', 'eliminar']])

        return (products_table_data, categories_table_content, add_stock_options, category_options, material_options)

    # Inputs Cantidad Insumos
    @app.callback(Output('add-product-material-quantities-container', 'children'), Input('add-product-materials-dropdown', 'value'), State('add-product-materials-dropdown', 'options'))
    def update_add_q(ids, opts):
        if not ids: return []
        om = {o['value']: o['label'] for o in opts}
        return [dbc.Row([dbc.Col(dbc.Label(f"{om.get(i, i)}:"), width=6), dbc.Col(dcc.Input(id={'type': 'add-material-quantity', 'index': i}, type='number', placeholder="Cantidad"), width=6)], className="mb-2") for i in ids]

    @app.callback(Output('edit-product-material-quantities-container', 'children'), Input('edit-product-materials-dropdown', 'value'), [State('edit-product-materials-dropdown', 'options'), State('store-edit-material-quantities', 'data')])
    def update_edit_q(ids, opts, saved):
        if not ids: return []
        om = {o['value']: o['label'] for o in opts}; s = saved or {}
        return [dbc.Row([dbc.Col(dbc.Label(f"{om.get(i, i)}:"), width=6), dbc.Col(dcc.Input(id={'type': 'edit-material-quantity', 'index': i}, type='number', value=s.get(str(i)) or s.get(int(i)), placeholder="Cantidad"), width=6)], className="mb-2") for i in ids]

    # Modales Acciones
    @app.callback(
        Output('product-edit-modal', 'is_open'), Output('product-delete-confirm-modal', 'is_open'),
        Output('store-product-id-to-edit', 'data'), Output('store-product-id-to-delete', 'data'),
        Output('edit-product-name', 'value'), Output('edit-product-category', 'value'),
        Output('edit-product-desc', 'value'), Output('edit-product-cost', 'value'),
        Output('edit-product-price', 'value'), Output('edit-product-stock', 'value'),
        Output('edit-product-alert', 'value'), Output('edit-product-materials-dropdown', 'value'),
        Output('store-edit-material-quantities', 'data'),
        Input('products-table', 'active_cell'), State('products-table', 'derived_virtual_data'), prevent_initial_call=True
    )
    def open_prod_modals(cell, data):
        if not cell or 'row_id' not in cell: raise PreventUpdate
        pid = cell['row_id']; col = cell['column_id']
        user_id = int(current_user.id)
        
        prods = load_products(user_id); p_info = prods[prods['product_id'] == pid].iloc[0]
        
        if col == "editar":
            linked = {}; linked_ids = []
            try:
                with engine.connect() as conn: linked = get_linked_material_quantities(conn, pid, user_id)
                linked_ids = list(linked.keys())
            except: pass
            
            return (True, False, pid, None, p_info['name'], int(p_info['category_id']) if pd.notna(p_info['category_id']) else None,
                    p_info['description'], p_info['cost'], p_info['price'], p_info['stock'], p_info['alert_threshold'],
                    linked_ids, linked)
        elif col == "eliminar":
            return (False, True, None, pid, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update)
        raise PreventUpdate

    # Guardar Edición (CORREGIDO: 14 ARGUMENTOS)
    @app.callback(
        Output('product-edit-modal', 'is_open', allow_duplicate=True),
        Output('store-data-signal', 'data', allow_duplicate=True),
        Output('edit-product-alert', 'children', allow_duplicate=True),
        Input('save-edited-product-button', 'n_clicks'),
        [State('store-product-id-to-edit', 'data'),
         State('edit-product-name', 'value'), State('edit-product-desc', 'value'),
         State('edit-product-category', 'value'), State('edit-product-price', 'value'),
         State('edit-product-cost', 'value'), State('edit-product-stock', 'value'),
         State('edit-product-alert', 'value'),
         State('edit-product-materials-dropdown', 'value'),
         State('edit-product-materials-dropdown', 'options'),
         State({'type': 'edit-material-quantity', 'index': ALL}, 'value'),
         State({'type': 'edit-material-quantity', 'index': ALL}, 'id'),
         State('store-data-signal', 'data')],
        prevent_initial_call=True
    )
    def save_edit(n, pid, name, desc, cat, price, cost, stock, alert, mids, mopts, mquants, mids_ids, sig):
        if not n or not pid: raise PreventUpdate
        user_id = int(current_user.id)
        if not all([name, cat, price is not None]): return True, dash.no_update, dbc.Alert("Faltan datos.", color="danger")
        
        mat_data = {}; om = {o['value']: o['label'] for o in mopts}
        qm = {i['index']: q for i, q in zip(mids_ids, mquants)}
        if mids:
            for m in mids:
                q = qm.get(m)
                if not q or float(q)<=0: return True, dash.no_update, dbc.Alert(f"Cantidad inválida para {om.get(m)}", color="danger")
                mat_data[m] = float(q)

        mat_cost = 0
        if mat_data:
            cmap = get_material_costs_map(user_id, mat_data.keys())
            mat_cost = sum(cmap.get(m, 0)*q for m, q in mat_data.items())
        
        try:
            with engine.connect() as conn:
                with conn.begin():
                    update_product(conn, pid, {"name": name.strip(), "description": desc, "category_id": cat, "price": float(price), "cost": float(cost)+mat_cost, "stock": int(stock), "alert_threshold": int(alert)}, user_id)
                    save_product_materials(conn, pid, mat_data, user_id)
            return False, (sig or 0)+1, None
        except Exception as e: return True, dash.no_update, dbc.Alert(f"Error: {e}", color="danger")

    # Eliminar Producto
    @app.callback(Output('product-delete-confirm-modal', 'is_open', allow_duplicate=True), Output('store-data-signal', 'data', allow_duplicate=True), Input('confirm-delete-product-button', 'n_clicks'), State('store-product-id-to-delete', 'data'), State('store-data-signal', 'data'), prevent_initial_call=True)
    def del_prod(n, pid, sig):
        if n and pid: delete_product(pid, int(current_user.id)); return False, (sig or 0)+1
        raise PreventUpdate

    # Categorías Modales
    @app.callback(Output('category-edit-modal', 'is_open'), Output('category-delete-confirm-modal', 'is_open'), Output('store-category-id-to-edit', 'data'), Output('store-category-id-to-delete', 'data'), Output('edit-category-name', 'value'), Input('categories-table', 'active_cell'), State('categories-table', 'derived_virtual_data'), prevent_initial_call=True)
    def cat_modals(cell, data):
        if not cell or 'row_id' not in cell: raise PreventUpdate
        cid = cell['row_id']; col = cell['column_id']
        row = next((r for r in data if r['id'] == cid), None)
        if col == "editar": return True, False, cid, None, row['name']
        elif col == "eliminar": return False, True, None, cid, dash.no_update
        raise PreventUpdate

    @app.callback(Output('category-edit-modal', 'is_open', allow_duplicate=True), Output('store-data-signal', 'data', allow_duplicate=True), Input('save-edited-category-button', 'n_clicks'), [State('store-category-id-to-edit', 'data'), State('edit-category-name', 'value'), State('store-data-signal', 'data')], prevent_initial_call=True)
    def save_cat_edit(n, cid, name, sig):
        if n and cid and name: update_category(cid, {"name": name.strip()}, int(current_user.id)); return False, (sig or 0)+1
        raise PreventUpdate

    @app.callback(Output('category-delete-confirm-modal', 'is_open', allow_duplicate=True), Output('store-data-signal', 'data', allow_duplicate=True), Input('confirm-delete-category-button', 'n_clicks'), State('store-category-id-to-delete', 'data'), State('store-data-signal', 'data'), prevent_initial_call=True)
    def del_cat(n, cid, sig):
        if n and cid: delete_category(cid, int(current_user.id)); return False, (sig or 0)+1
        raise PreventUpdate

    # Cerrar todos
    @app.callback(Output('product-edit-modal', 'is_open', allow_duplicate=True), Input('cancel-edit-product-button', 'n_clicks'), prevent_initial_call=True)
    def c1(n): return False
    @app.callback(Output('product-delete-confirm-modal', 'is_open', allow_duplicate=True), Input('cancel-delete-product-button', 'n_clicks'), prevent_initial_call=True)
    def c2(n): return False
    @app.callback(Output('category-edit-modal', 'is_open', allow_duplicate=True), Input('cancel-edit-category-button', 'n_clicks'), prevent_initial_call=True)
    def c3(n): return False
    @app.callback(Output('category-delete-confirm-modal', 'is_open', allow_duplicate=True), Input('cancel-delete-category-button', 'n_clicks'), prevent_initial_call=True)
    def c4(n): return False

    # Borrado Masivo
    @app.callback(Output('bulk-delete-products-output', 'children'), Output('store-data-signal', 'data', allow_duplicate=True), Output('products-table', 'selected_rows'), Output('products-table', 'selected_row_ids'), Input('delete-selected-products-btn', 'n_clicks'), [State('products-table', 'selected_row_ids'), State('store-data-signal', 'data')], prevent_initial_call=True)
    def bulk_del(n, ids, sig):
        if not n or not ids: raise PreventUpdate
        success, msg = delete_products_bulk(ids, int(current_user.id))
        return dbc.Alert(msg, color="success" if success else "danger", dismissable=True), (sig or 0)+1, [], []
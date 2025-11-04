# products.py
from dash import dcc, html, dash_table
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output, State, ALL
from dash.exceptions import PreventUpdate
from dash.dash_table.Format import Format, Scheme, Symbol # <-- Importado Symbol
import pandas as pd
from flask_login import current_user
import dash
from sqlalchemy import text # <-- Importar text

from app import app
# Importar todas las funciones necesarias de la base de datos
from database import (
    load_products, load_categories, get_product_options, get_category_options,
    update_stock, update_product, delete_product, update_category, delete_category,
    reactivate_product_category,
    get_raw_material_options,
    get_linked_material_quantities,
    save_product_materials,
    get_material_costs_map,
    engine,
    deduct_materials_for_production
)

def get_layout():
    # Obtener opciones para poblar dropdowns en el layout inicial
    try:
        user_id = int(current_user.id) if current_user.is_authenticated else None # <-- FIX numpy.int64
        category_opts = get_category_options(user_id) if user_id else []
        material_opts = get_raw_material_options(user_id) if user_id else []
    except Exception as e:
        print(f"Error cargando opciones iniciales en products.py: {e}")
        category_opts = []
        material_opts = []

    unit_options = [ # Re-added unit options for edit modal consistency
        {'label': 'Unidad(es)', 'value': 'unidad'}, {'label': 'Metro(s)', 'value': 'metro'},
        {'label': 'Centímetro(s)', 'value': 'cm'}, {'label': 'Litro(s)', 'value': 'litro'},
        {'label': 'Mililitro(s)', 'value': 'ml'}, {'label': 'Kilogramo(s)', 'value': 'kg'},
        {'label': 'Gramo(s)', 'value': 'g'}, {'label': 'Par(es)', 'value': 'par'},
    ]


    return html.Div([
        dcc.Store(id='store-product-id-to-edit'),
        dcc.Store(id='store-product-id-to-delete'),
        dcc.Store(id='store-category-id-to-edit'),
        dcc.Store(id='store-category-id-to-delete'),
        dcc.Store(id='store-edit-material-quantities', storage_type='memory'),

        # --- Modal Editar Producto ---
        dbc.Modal([
            dbc.ModalHeader("Editar Producto"),
            dbc.ModalBody(dbc.Form([
                html.Div(id='edit-product-alert'), # Alerta interna
                dbc.Row([
                    dbc.Col([dbc.Label("Nombre"), dbc.Input(id='edit-product-name')]),
                    dbc.Col([dbc.Label("Categoría"), dcc.Dropdown(id='edit-product-category', options=category_opts)]),
                ]),
                dbc.Label("Descripción", className="mt-2"),
                dbc.Textarea(id='edit-product-desc'),
                dbc.Row([
                    dbc.Col([dbc.Label("Costo Base (Sin Insumos)"), dbc.Input(id='edit-product-cost', type='number', min=0, step="any", placeholder="0.00")]),
                    dbc.Col([dbc.Label("Precio Venta"), dbc.Input(id='edit-product-price', type='number', min=0, step="any", placeholder="0.00")]),
                    dbc.Col([dbc.Label("Stock Actual"), dbc.Input(id='edit-product-stock', type='number', min=0, step="any", placeholder="0.00")]),
                    dbc.Col([dbc.Label("Alerta Stock Bajo"), dbc.Input(id='edit-product-alert', type='number', min=0, step="any", placeholder="0.00")]),
                ], className="mt-2"),
                html.Hr(),
                html.H5("Insumos Utilizados", className="mt-3 mb-3"),
                 dbc.Row([
                    dbc.Col(html.Div([
                        dbc.Label("Selecciona los insumos:", html_for="edit-product-materials-dropdown"),
                        dcc.Dropdown(
                            id="edit-product-materials-dropdown",
                            options=material_opts,
                            multi=True,
                            placeholder="Selecciona insumos..."
                        )
                    ]), width=12)
                ], className="mb-3"),
                html.Div(id='edit-product-material-quantities-container', children=[]), # Container for dynamic inputs
            ])),
            dbc.ModalFooter([
                dbc.Button("Cancelar", id="cancel-edit-product-button", color="secondary", className="ms-auto"),
                dbc.Button("Guardar Cambios", id="save-edited-product-button", color="primary"),
            ]),
        ], id="product-edit-modal", is_open=False, size="lg"),

        # --- Modal Confirmar Eliminación Producto ---
        dbc.Modal([
            dbc.ModalHeader("Confirmar Eliminación"),
            dbc.ModalBody("¿Estás seguro de que quieres eliminar este producto? Se ocultará de las listas, pero se mantendrá en los reportes históricos."),
            dbc.ModalFooter([
                dbc.Button("Cancelar", id="cancel-delete-product-button", color="secondary", className="ms-auto"),
                dbc.Button("Eliminar", id="confirm-delete-product-button", color="danger"),
            ]),
        ], id="product-delete-confirm-modal", is_open=False),

        # --- Modal Editar Categoría ---
        dbc.Modal([
            dbc.ModalHeader("Editar Categoría"),
            dbc.ModalBody(dbc.Form([dbc.Label("Nombre de la Categoría"), dbc.Input(id='edit-category-name', type='text')])),
            dbc.ModalFooter([
                dbc.Button("Cancelar", id="cancel-edit-category-button", color="secondary", className="ms-auto"),
                dbc.Button("Guardar Cambios", id="save-edited-category-button", color="primary"),
            ]),
        ], id="category-edit-modal", is_open=False),

        # --- Modal Confirmar Eliminación Categoría ---
        dbc.Modal([
            dbc.ModalHeader("Confirmar Eliminación"),
            dbc.ModalBody("¿Estás seguro de que quieres eliminar esta categoría? Se ocultará de las listas y se desasignará de todos los productos."),
            dbc.ModalFooter([
                dbc.Button("Cancelar", id="cancel-delete-category-button", color="secondary", className="ms-auto"),
                dbc.Button("Eliminar", id="confirm-delete-category-button", color="danger"),
            ]),
        ], id="category-delete-confirm-modal", is_open=False),

        # --- Tabs Principales ---
        dbc.Tabs(id="product-sub-tabs", active_tab="sub-tab-inventory", children=[
            # --- Tab: Inventario ---
            dbc.Tab(label="Inventario", tab_id="sub-tab-inventory", children=[
                html.Div(className="p-4", children=[html.H3("Inventario de Productos"), html.Div(id="products-table-container")])
            ]),

            # --- Tab: Añadir Producto ---
            dbc.Tab(label="Añadir Producto", tab_id="sub-tab-add-product", children=[
                dbc.Card(className="m-4", children=[
                    dbc.CardBody([
                        html.H3("Añadir un Nuevo Producto"), html.Div(id="add-product-alert"),
                        dbc.Row([
                            dbc.Col(html.Div([html.Label("Nombre"), dbc.Input(id="product-name-input")]), width=6),
                            dbc.Col(html.Div([html.Label("Categoría"), dcc.Dropdown(id="product-category-dropdown", options=category_opts, placeholder="Selecciona...") ]), width=6),
                        ], className="mb-3"),
                        dbc.Row([dbc.Col(html.Div([html.Label("Descripción (Opcional)"), dbc.Textarea(id="product-desc-input")]), width=12)], className="mb-3"),
                        dbc.Row([
                            dbc.Col(html.Div([html.Label("Costo Base"), dbc.Input(id="product-cost-input", type="number", min=0, step="any", placeholder="0.00")]), width=3),
                            dbc.Col(html.Div([html.Label("Precio Venta"), dbc.Input(id="product-price-input", type="number", min=0, step="any", placeholder="0.00")]), width=3),
                            dbc.Col(html.Div([html.Label("Stock Inicial"), dbc.Input(id="product-stock-input", type="number", min=0, step="any", placeholder="0.00")]), width=3),
                            dbc.Col(html.Div([html.Label("Alerta Stock"), dbc.Input(id="product-alert-input", type="number", min=0, step="any", placeholder="0.00" )]), width=3),
                        ], className="mb-3"),
                        html.Hr(), html.H4("Insumos Utilizados", className="mt-4 mb-3"),
                        dbc.Row([
                            dbc.Col(html.Div([
                                dbc.Label("Selecciona Insumos:", html_for="add-product-materials-dropdown"),
                                dcc.Dropdown(id="add-product-materials-dropdown", options=material_opts, multi=True, placeholder="Selecciona...")
                            ]), width=12)
                        ], className="mb-3"),
                        html.Div(id='add-product-material-quantities-container', children=[]),
                        html.Hr(),
                        dbc.Button("Guardar Producto", id="save-product-button", color="success", n_clicks=0, className="mt-3")
                    ])
                ])
            ]),

            # --- Tab: Añadir Stock ---
            dbc.Tab(label="Añadir Stock", tab_id="sub-tab-add-stock", children=[
                dbc.Card(className="m-4", children=[
                    dbc.CardBody([
                        html.H3("Añadir Stock Producto Existente"), html.Div(id="add-stock-alert"),
                        dbc.Row([
                            dbc.Col([html.Label("Producto"), dcc.Dropdown(id='add-stock-product-dropdown', placeholder="Selecciona...")], width=6),
                            dbc.Col([html.Label("Cantidad a Añadir"), dbc.Input(id='add-stock-quantity-input', type='number', min=1, step="any", placeholder="0.00")], width=6),
                        ], className="mb-3"),
                        dbc.Button("Añadir Stock", id="submit-add-stock-button", color="info", n_clicks=0, className="mt-3")
                    ])
                ])
            ]),

            # --- Tab: Gestionar Categorías ---
            dbc.Tab(label="Gestionar Categorías", tab_id="sub-tab-categories", children=[
                dbc.Row([
                    dbc.Col([
                        dbc.Card(className="m-4", children=[
                            dbc.CardBody([
                                html.H3("Crear Nueva Categoría"), html.Div(id="add-category-alert"),
                                dbc.Input(id="category-name-input", placeholder="Nombre...", className="mb-2"),
                                dbc.Button("Guardar Categoría", id="save-category-button", color="primary")
                            ])
                        ])
                    ], width=4),
                    dbc.Col([
                        html.Div(className="p-4", children=[html.H3("Categorías Existentes"), html.Div(id='categories-table-container')])
                    ], width=8)
                ])
            ]),
        ]) # Fin Tabs
    ]) # Fin Div Principal

# --- Callbacks ---
def register_callbacks(app):

    # Callback Añadir Producto
    @app.callback(
        Output('add-product-alert', 'children'),
        Output('store-data-signal', 'data', allow_duplicate=True),
        # PENDIENTE: Limpiar campos en éxito
        Input('save-product-button', 'n_clicks'),
        [State('product-name-input', 'value'), State('product-desc-input', 'value'),
         State('product-category-dropdown', 'value'), State('product-price-input', 'value'),
         State('product-cost-input', 'value'), State('product-stock-input', 'value'),
         State('product-alert-input', 'value'),
         State('add-product-materials-dropdown', 'value'),
         State('add-product-materials-dropdown', 'options'), # <-- Para nombres
         State({'type': 'add-material-quantity', 'index': ALL}, 'value'), # Valores
         State({'type': 'add-material-quantity', 'index': ALL}, 'id'),    # <-- IDs de inputs
         State('store-data-signal', 'data')],
        prevent_initial_call=True
    )
    def add_product(n, name, desc, cat_id, price, cost, stock, alert,
                    selected_material_ids, all_material_options,
                    material_quantities, material_input_ids,
                    signal_data):
        if n is None or n < 1: raise PreventUpdate
        if not current_user.is_authenticated: raise PreventUpdate

        # --- FIX numpy.int64 ---
        user_id = int(current_user.id)
        # --- FIN FIX ---

        if not all([name, cat_id, price is not None]):
            return dbc.Alert("Nombre, Categoría y Precio son obligatorios.", color="danger"), dash.no_update
        try:
            price_f = float(price); cost_f = float(cost) if cost is not None else 0
            stock_i = int(stock) if stock is not None else 0; alert_i = int(alert) if alert is not None else 0
            if price_f <= 0 or cost_f < 0 or stock_i < 0 or alert_i < 0: raise ValueError("Inv Num")
        except (ValueError, TypeError):
             return dbc.Alert("Precio, Costo Base, Stock y Alerta deben ser números válidos (Precio > 0).", color="danger"), dash.no_update

        # --- RECOGER CANTIDADES Y VALIDAR (LÓGICA MEJORADA) ---
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
                    if qty_float <= 0:
                        error_messages.append(f"La cantidad para '{material_label}' debe ser positiva.")
                    else:
                        material_data_to_save[mat_id] = qty_float
                except (ValueError, TypeError):
                    error_messages.append(f"La cantidad '{qty_input}' para '{material_label}' no es un número válido.")

        # Si hubo algún error durante la validación
        if error_messages:
             error_list_items = [html.Li(msg) for msg in error_messages]
             alert_content = html.Div([html.P("Corrige los errores en las cantidades de insumos:"), html.Ul(error_list_items)])
             # --- FIX AttributeError: Retornar 2 valores ---
             return dbc.Alert(alert_content, color="danger"), dash.no_update
        # --- FIN RECOGER CANTIDADES Y VALIDAR ---

    # ... (justo después del bloque "FIN RECOGER CANTIDADES Y VALIDAR") ...

        # --- CÁLCULO DE COSTO TOTAL ---
        total_material_cost = 0.0
        if material_data_to_save:
            # Usar la nueva función para obtener los costos
            material_costs_map = get_material_costs_map(user_id, material_data_to_save.keys())
            for mat_id, qty in material_data_to_save.items():
                total_material_cost += material_costs_map.get(mat_id, 0.0) * qty

        # Sumar el costo base + costo de materiales
        total_product_cost = cost_f + total_material_cost
        # --- FIN CÁLCULO ---

        from database import engine, text # Importar text
        product_data = {'name': name, 'description': desc or "", 'category_id': cat_id,
                    'price': price_f, 
                    'cost': total_product_cost, # <-- MODIFICADO (antes era cost_f)
                    'stock': stock_i,
                    'alert_threshold': alert_i, 'user_id': user_id, 'is_active': True}

        # ... (el resto del bloque try/except/finally sigue igual) ...

    # --- REEMPLAZA CON ESTE BLOQUE ---
        new_product_id = None
        try:
            with engine.connect() as connection:
                with connection.begin(): # Usar transacción
                    
                    # --- INICIO DE LÍNEAS FALTANTES ---
                    # 1. Definir la consulta
                    insert_prod_query = text("""
                        INSERT INTO products (name, description, category_id, price, cost, stock, alert_threshold, user_id, is_active)
                        VALUES (:name, :description, :category_id, :price, :cost, :stock, :alert_threshold, :user_id, :is_active)
                        RETURNING product_id
                    """)
                    
                    # 2. Ejecutar la consulta y guardar en 'result' (singular)
                    result = connection.execute(insert_prod_query, product_data)
                    # --- FIN DE LÍNEAS FALTANTES ---

                    # 3. Esta línea ahora funcionará
                    new_product_id = result.scalar_one_or_none()
                    
                    if new_product_id is None:
                        raise Exception("No se pudo obtener el ID del nuevo producto.")

                    if material_data_to_save:
                        success_save_mats, msg_save_mats = save_product_materials(connection, new_product_id, material_data_to_save, user_id)
                        if not success_save_mats:
                            raise Exception(f"Error al guardar insumos: {msg_save_mats}")

                    # --- INICIO DEL NUEVO BLOQUE (Deducción de stock) ---
                    # Si se añadió stock inicial, deducir los insumos
                    if stock_i > 0:
                        success_deduct, msg_deduct = deduct_materials_for_production(connection, new_product_id, stock_i, user_id)
                        if not success_deduct:
                            # Esto cancelará toda la transacción
                            raise Exception(msg_deduct)
                    # --- FIN DEL NUEVO BLOQUE ---

                # Commit automático
        except Exception as e:
            print(f"Error al guardar producto o insumos: {e}")
            return dbc.Alert(f"Error al guardar: {e}", color="danger"), dash.no_update
    # --- FIN DEL REEMPLAZO ---

        new_signal = (signal_data or 0) + 1
        # PENDIENTE: Limpiar campos
        return dbc.Alert(f"¡Producto '{name}' guardado exitosamente!", color="success", dismissable=True, duration=4000), new_signal

    # Callback Añadir Stock
# EN products.py: REEMPLAZA EL CALLBACK add_stock COMPLETO

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
        if not all([prod_id, qty]):
            return dbc.Alert("Debes seleccionar un producto y cantidad.", color="warning", dismissable=True), dash.no_update
        
        try:
            qty_int = int(qty)
            if qty_int <= 0: raise ValueError("Cantidad debe ser positiva.")
        except (ValueError, TypeError):
            return dbc.Alert("Cantidad inválida.", color="danger", dismissable=True), dash.no_update

        # --- LÓGICA TRANSACCIONAL ---
        try:
            with engine.connect() as connection:
                with connection.begin(): # Iniciar transacción
                    
                    # 1. Deducir los insumos primero
                    success_deduct, msg_deduct = deduct_materials_for_production(connection, prod_id, qty_int, user_id)
                    if not success_deduct:
                        raise Exception(msg_deduct) # Cancela la transacción
                    
                    # 2. Si la deducción fue exitosa, añadir stock al producto
                    update_prod_query = text("""
                        UPDATE products SET stock = stock + :quantity 
                        WHERE product_id = :product_id AND user_id = :user_id
                    """)
                    connection.execute(update_prod_query, {"quantity": qty_int, "product_id": prod_id, "user_id": user_id})
            
            # 3. Si la transacción fue exitosa, cargar nombre para alerta
            df = load_products(user_id)
            name = df.loc[df['product_id'] == prod_id, 'name'].iloc[0]
            
            new_signal = (signal_data or 0) + 1
            return dbc.Alert(f"¡Stock de '{name}' actualizado! Insumos deducidos.", color="success", dismissable=True, duration=4000), new_signal

        except IndexError:
            return dbc.Alert("Error: Producto no encontrado.", color="danger", dismissable=True), dash.no_update
        except Exception as e:
            print(f"Error en add_stock: {e}")
            # Muestra el error específico (ej: "Stock insuficiente...")
            return dbc.Alert(f"Error al actualizar stock: {e}", color="danger", dismissable=True), dash.no_update
    # Callback Añadir Categoría
    @app.callback(
        Output('add-category-alert', 'children'),
        Output('store-data-signal', 'data', allow_duplicate=True),
        Input('save-category-button', 'n_clicks'),
        [State('category-name-input', 'value'), State('store-data-signal', 'data')],
        prevent_initial_call=True
    )
    def add_category(n_clicks, name, signal_data):
        if n_clicks is None or n_clicks < 1: raise PreventUpdate
        if not current_user.is_authenticated: raise PreventUpdate
        user_id = int(current_user.id) # <-- FIX numpy.int64
        if not name:
            return dbc.Alert("El nombre no puede estar vacío.", color="warning"), dash.no_update

        from database import engine, text # Importar text
        existing_cats = load_categories(user_id)
        if not existing_cats.empty and 'is_active' in existing_cats.columns:
            match = existing_cats[existing_cats['name'].str.lower() == name.lower()]
            if not match.empty:
                category_data = match.iloc[0]
                if category_data['is_active']:
                    return dbc.Alert(f"La categoría '{name}' ya existe.", color="danger"), dash.no_update
                else:
                    reactivate_product_category(category_data['category_id'], user_id)
                    new_signal = (signal_data or 0) + 1
                    return dbc.Alert(f"Categoría '{category_data['name']}' reactivada.", color="success"), new_signal
        try:
            pd.DataFrame([{'name': name.title(), 'user_id': user_id, 'is_active': True}]).to_sql('categories', engine, if_exists='append', index=False)
            new_signal = (signal_data or 0) + 1
            return dbc.Alert(f"Categoría '{name.title()}' guardada.", color="success"), new_signal
        except Exception as e:
            print(f"Error al guardar categoría: {e}")
            return dbc.Alert(f"Error al guardar categoría. ¿Quizás ya existe?", color="danger"), dash.no_update

    # Callback Refrescar Componentes
    @app.callback(
        Output('products-table-container', 'children'), Output('categories-table-container', 'children'),
        Output('add-stock-product-dropdown', 'options'), Output('product-category-dropdown', 'options'),
        Output('add-product-materials-dropdown', 'options'),
        [Input('product-sub-tabs', 'active_tab'), Input('store-data-signal', 'data')]
    )
    def refresh_products_components(sub_tab, signal_data):
        if not current_user.is_authenticated: raise PreventUpdate
        user_id = int(current_user.id) # <-- FIX numpy.int64
        products_df = load_products(user_id); categories_df = load_categories(user_id)
        product_options = get_product_options(user_id); category_options = get_category_options(user_id)
        material_options = get_raw_material_options(user_id)
        products_table_content = dash.no_update; categories_table_content = dash.no_update

        if sub_tab == 'sub-tab-inventory':
            display_df = pd.DataFrame()
            if not products_df.empty:
                df_active = products_df[products_df['is_active'] == True].copy() if 'is_active' in products_df.columns else products_df.copy()
                for col in ['cost', 'price']: df_active[col] = pd.to_numeric(df_active[col], errors='coerce')
                df = pd.merge(df_active, categories_df, on='category_id', how='left').fillna("Sin Categoría")
                df = df.rename(columns={'name_x': 'Nombre', 'name_y': 'Categoría'})
                df['editar'] = "✏️"; df['eliminar'] = "🗑️"; display_df = df
            products_table_content = dash_table.DataTable(id='products-table',
                columns=[
                    {"name": "ID", "id": "product_id"},
                    {"name": "Nombre", "id": "Nombre"}, {"name": "Categoría", "id": "Categoría"},
                    {"name": "Descripción", "id": "description"},
                    {"name": "Costo Base", "id": "cost", 'type': 'numeric', 'format': Format(precision=2, scheme=Scheme.fixed, symbol=Symbol.yes)},
                    {"name": "Precio", "id": "price", 'type': 'numeric', 'format': Format(precision=2, scheme=Scheme.fixed, symbol=Symbol.yes)},
                    {"name": "Stock", "id": "stock"}, {"name": "Alerta", "id": "alert_threshold"},
                    {"name": "Editar", "id": "editar"}, {"name": "Eliminar", "id": "eliminar"}],
                data=display_df.to_dict('records'), hidden_columns=['product_id'], page_size=15, sort_action='native', filter_action='native',
                
                style_cell={'textAlign': 'left'}, style_cell_conditional=[{'if': {'column_id': c}, 'cursor': 'pointer', 'textAlign': 'center'} for c in ['editar', 'eliminar']])
        elif sub_tab == 'sub-tab-categories':
            categories_df_display = pd.DataFrame()
            if not categories_df.empty:
                cats_active = categories_df[categories_df['is_active'] == True].copy() if 'is_active' in categories_df.columns else categories_df.copy()
                categories_df_display = cats_active; categories_df_display['editar'] = "✏️"; categories_df_display['eliminar'] = "🗑️"
            categories_table_content = dash_table.DataTable(id='categories-table',
                columns=[{"name": "ID", "id": "category_id"}, {"name": "Nombre", "id": "name"},
                         {"name": "Editar", "id": "editar"}, {"name": "Eliminar", "id": "eliminar"}],
                data=categories_df_display.to_dict('records'), page_size=10, style_cell={'textAlign': 'left'},
                style_cell_conditional=[{'if': {'column_id': c}, 'cursor': 'pointer', 'textAlign': 'center'} for c in ['editar', 'eliminar']])

        return (products_table_content, categories_table_content, product_options, category_options, material_options)

    # Callback Generar Inputs Cantidad (Añadir)
    @app.callback(
        Output('add-product-material-quantities-container', 'children'),
        Input('add-product-materials-dropdown', 'value'),
        State('add-product-materials-dropdown', 'options')
    )
    def update_add_material_quantities(selected_material_ids, all_material_options):
        if not selected_material_ids: return []
        inputs = []
        options_map = {opt['value']: opt['label'] for opt in all_material_options}
        for material_id in selected_material_ids:
            material_label = options_map.get(material_id, f"Insumo ID {material_id}")
            input_id = {'type': 'add-material-quantity', 'index': material_id}
            inputs.append(dbc.Row([dbc.Col(dbc.Label(f"Cantidad de '{material_label}':"), width=6),
                                   dbc.Col(dcc.Input(id=input_id, type='number', step="any", placeholder="Cantidad usada", debounce=True, style={'width': '100%'} ), width=6)],
                                  className="mb-2 align-items-center"))
        return inputs

    # Callback Generar Inputs Cantidad (Editar)
    @app.callback(
        Output('edit-product-material-quantities-container', 'children'),
        Input('edit-product-materials-dropdown', 'value'),
        [State('edit-product-materials-dropdown', 'options'),
         State('store-edit-material-quantities', 'data')] # Leer cantidades del Store
    )
    def update_edit_material_quantities(selected_material_ids, all_material_options,
                                        saved_quantities_data):
        if not selected_material_ids: return []
        inputs = []; options_map = {opt['value']: opt['label'] for opt in all_material_options}
        saved_quantities = saved_quantities_data if saved_quantities_data else {}
        for material_id in selected_material_ids:
             material_label = options_map.get(material_id, f"Insumo ID {material_id}")
             input_id = {'type': 'edit-material-quantity', 'index': material_id}
             # Intentar matchear con int y string
             saved_qty = saved_quantities.get(str(material_id))
             if saved_qty is None: saved_qty = saved_quantities.get(int(material_id))

             inputs.append(dbc.Row([dbc.Col(dbc.Label(f"Cantidad de '{material_label}':"), width=6),
                                    dbc.Col(dcc.Input(id=input_id, type='number', step="any", placeholder="Cantidad usada", value=saved_qty, debounce=True, style={'width': '100%'}), width=6)],
                                   className="mb-2 align-items-center"))
        return inputs


    # Callback Abrir Modales Producto (Edit/Delete)
    @app.callback(
        # 15 Outputs
        Output('product-edit-modal', 'is_open'), Output('product-delete-confirm-modal', 'is_open'),
        Output('store-product-id-to-edit', 'data'), Output('store-product-id-to-delete', 'data'),
        Output('edit-product-name', 'value'), Output('edit-product-category', 'value'),
        Output('edit-product-desc', 'value'), Output('edit-product-cost', 'value'),
        Output('edit-product-price', 'value'), Output('edit-product-stock', 'value'),
        Output('edit-product-alert', 'value'),
        Output('edit-product-category', 'options'), Output('edit-product-materials-dropdown', 'options'),
        Output('edit-product-materials-dropdown', 'value'),
        Output('store-edit-material-quantities', 'data'),
        Input('products-table', 'active_cell'), State('products-table', 'derived_virtual_data'),
        prevent_initial_call=True
    )
    def open_product_modals(active_cell, data):
        if not current_user.is_authenticated: raise PreventUpdate
        if not active_cell or 'row' not in active_cell: raise PreventUpdate
        user_id = int(current_user.id) # <-- FIX numpy.int64
        row_idx, col_id = active_cell['row'], active_cell['column_id']
        if not data or row_idx >= len(data): raise PreventUpdate
        product_id = int(data[row_idx]['product_id']) # <-- Obtiene el ID directo de la fila
        products_df = load_products(user_id)
        try:
            product_info = products_df[products_df['product_id'] == product_id].iloc[0]
        except IndexError: raise PreventUpdate
        category_options = get_category_options(user_id); material_options = get_raw_material_options(user_id)
        # ... (código existente) ...
# --- INICIO DEL NUEVO BLOQUE (EL CORRECTO) ---
        linked_material_quantities = {}; linked_material_ids = []
        calculated_base_cost = 0.0
        # Obtener el Costo TOTAL de la BD
        total_cost_from_db = float(product_info['cost']) 

        try:
            # 1. Obtener los insumos vinculados
            with engine.connect() as connection:
                linked_material_quantities = get_linked_material_quantities(connection, product_id, user_id) # Devuelve {int: float}
            
            linked_material_ids = list(linked_material_quantities.keys())
            
            total_insumos_cost = 0.0
            if linked_material_ids:
                # 2. Obtener el costo actual de esos insumos
                costs_map = get_material_costs_map(user_id, linked_material_ids) # Devuelve {int: float}
                
                # 3. Calcular el costo total de los insumos
                for mat_id, qty in linked_material_quantities.items():
                    total_insumos_cost += costs_map.get(mat_id, 0.0) * qty
            
            # 4. Calcular el Costo Base restando
            calculated_base_cost = total_cost_from_db - total_insumos_cost
            # Asegurarse de que no sea negativo si los costos de insumos han subido
            if calculated_base_cost < 0:
                calculated_base_cost = 0.0 

        except Exception as e: 
            print(f"Error al calcular costos de materiales vinculados para {product_id}: {e}")
            # Si falla, mostrar el costo total como fallback
            calculated_base_cost = total_cost_from_db 

        no_update_list = [dash.no_update] * 11
        # --- FIN DEL NUEVO BLOQUE ---

        if col_id == "editar":
            cat_val = int(product_info['category_id']) if pd.notna(product_info['category_id']) else None
            return (True, False, product_id, None, product_info['name'], cat_val,
                    product_info['description'], 
                    round(calculated_base_cost, 2), # <-- ESTA ES LA LÍNEA MODIFICADA
                    product_info['price'],
                    # ... (el resto de la línea sigue igual)
                    product_info['stock'], product_info['alert_threshold'],
                    category_options, material_options, linked_material_ids,
                    linked_material_quantities) # 15 outputs
        elif col_id == "eliminar":
            return (False, True, None, product_id, *no_update_list)
        return (False, False, None, None, *no_update_list)


    # Callback Guardar Edición Producto
    @app.callback(
        Output('product-edit-modal', 'is_open', allow_duplicate=True),
        Output('store-data-signal', 'data', allow_duplicate=True),
        Output('edit-product-alert', 'children', allow_duplicate=True), # Alerta interna
        Input('save-edited-product-button', 'n_clicks'),
        [State('store-product-id-to-edit', 'data'), State('edit-product-name', 'value'), State('edit-product-desc', 'value'),
         State('edit-product-category', 'value'), State('edit-product-price', 'value'), State('edit-product-cost', 'value'),
         State('edit-product-stock', 'value'), State('edit-product-alert', 'value'),
         State('edit-product-materials-dropdown', 'value'),
         State('edit-product-materials-dropdown', 'options'), # Para nombres
         State({'type': 'edit-material-quantity', 'index': ALL}, 'value'), # Cantidades
         State({'type': 'edit-material-quantity', 'index': ALL}, 'id'), # Para IDs
         State('store-data-signal', 'data')],
        prevent_initial_call=True
    )
    def save_edited_product(n, product_id, name, desc, cat_id, price, cost, stock, alert,
                            selected_material_ids, all_material_options,
                            material_quantities, material_input_ids,
                            signal):
        if n is None: raise PreventUpdate
        if not product_id: raise PreventUpdate
        if not current_user.is_authenticated: raise PreventUpdate
        user_id = int(current_user.id) # <-- FIX numpy.int64

        if not all([name, cat_id, price is not None]):
             return True, dash.no_update, dbc.Alert("Nombre, Categoría y Precio son obligatorios.", color="danger")
        try:
            price_f = float(price); cost_f = float(cost) if cost is not None else 0
            stock_i = int(stock) if stock is not None else 0; alert_i = int(alert) if alert is not None else 0
            if price_f <= 0 or cost_f < 0 or stock_i < 0 or alert_i < 0: raise ValueError("Inv Num")
        except (ValueError, TypeError):
             return True, dash.no_update, dbc.Alert("Precio, Costo Base, Stock o Alerta inválidos.", color="danger")

        # Recoger cantidades validadas
        material_data_to_save = {}
        error_messages = []
        options_map = {opt['value']: opt['label'] for opt in all_material_options}
        quantities_map = {inp_id['index']: qty for inp_id, qty in zip(material_input_ids, material_quantities)}
        if selected_material_ids:
            for mat_id in selected_material_ids:
                material_label = options_map.get(mat_id, f"ID {mat_id}")
                qty_input = quantities_map.get(mat_id)
                if qty_input is None or str(qty_input).strip() == "": error_messages.append(f"Falta cantidad para '{material_label}'."); continue
                try:
                    qty_float = float(qty_input)
                    if qty_float <= 0: error_messages.append(f"Cantidad para '{material_label}' debe ser positiva.")
                    else: material_data_to_save[mat_id] = qty_float
                except (ValueError, TypeError): error_messages.append(f"Cantidad '{qty_input}' para '{material_label}' no válida.")
        if error_messages:
            error_list_items = [html.Li(msg) for msg in error_messages]
            alert_content = html.Div([html.P("Corrige errores en cantidades:"), html.Ul(error_list_items)])
            return True, dash.no_update, dbc.Alert(alert_content, color="danger")

        # --- CÁLCULO DE COSTO TOTAL ---
        total_material_cost = 0.0
        if material_data_to_save:
            # Usar la nueva función para obtener los costos
            material_costs_map = get_material_costs_map(user_id, material_data_to_save.keys())
            for mat_id, qty in material_data_to_save.items():
                total_material_cost += material_costs_map.get(mat_id, 0.0) * qty

        # Sumar el costo base + costo de materiales
        total_product_cost = cost_f + total_material_cost
        # --- FIN CÁLCULO ---
    
        print(f"Producto {product_id} a actualizar."); print("Materiales y cantidades:", material_data_to_save)
        new_data = {"name": name, "description": desc, "category_id": cat_id, 
                    "price": price_f, 
                    "cost": total_product_cost, # <-- Costo total (de la corrección anterior)
                    "stock": stock_i, "alert_threshold": alert_i}
        
        # --- REEMPLAZA EL BLOQUE try/except CON ESTO ---
        try:
            with engine.connect() as connection:
                with connection.begin(): # <-- INICIAR TRANSACCIÓN ÚNICA
                    
                    # 1. Actualizar el producto
                    update_product(connection, product_id, new_data, user_id)
                    
                    # 2. Actualizar los materiales
                    success_mats, msg_mats = save_product_materials(connection, product_id, material_data_to_save, user_id)
                    
                    if not success_mats:
                        # Si save_product_materials falla, lanza una excepción
                        # para que la transacción haga rollback
                        raise Exception(msg_mats)
                # <-- COMMIT AUTOMÁTICO SI TODO FUE BIEN

        except Exception as e:
            print(f"Error al guardar edición producto {product_id}: {e}")
            return True, dash.no_update, dbc.Alert(f"Error al guardar: {e}", color="danger")
        # --- FIN DEL REEMPLAZO ---

        return False, (signal or 0) + 1, None # Éxito

    # Callback Confirmar Eliminar Producto
    @app.callback(
        Output('product-delete-confirm-modal', 'is_open', allow_duplicate=True),
        Output('store-data-signal', 'data', allow_duplicate=True),
        Input('confirm-delete-product-button', 'n_clicks'),
        [State('store-product-id-to-delete', 'data'), State('store-data-signal', 'data')],
        prevent_initial_call=True
    )
    def confirm_delete_product(n, product_id, signal):
        if n is None or n < 1: raise PreventUpdate
        if not current_user.is_authenticated: return False, dash.no_update
        if not product_id: return False, dash.no_update
        try:
            delete_product(product_id, int(current_user.id)) # <-- FIX numpy.int64
            return False, (signal or 0) + 1
        except Exception as e:
             print(f"Error al eliminar producto {product_id}: {e}")
             return False, dash.no_update

    # Callback Cerrar Modales Producto
    @app.callback(
        Output('product-edit-modal', 'is_open', allow_duplicate=True),
        Output('product-delete-confirm-modal', 'is_open', allow_duplicate=True),
        [Input('cancel-edit-product-button', 'n_clicks'), Input('cancel-delete-product-button', 'n_clicks')],
        prevent_initial_call=True
    )
    def close_product_modals(n_cancel_edit, n_cancel_delete):
        triggered_id = dash.callback_context.triggered_id
        if triggered_id in ['cancel-edit-product-button', 'cancel-delete-product-button']: return False, False
        raise PreventUpdate

    # --- Callbacks para Categorías ---
    # Callback Abrir Modales Categoría (Edit/Delete)
    @app.callback(
        Output('category-edit-modal', 'is_open'), Output('category-delete-confirm-modal', 'is_open'),
        Output('store-category-id-to-edit', 'data'), Output('store-category-id-to-delete', 'data'),
        Output('edit-category-name', 'value'),
        Input('categories-table', 'active_cell'), State('categories-table', 'derived_virtual_data'),
        prevent_initial_call=True
    )
    def open_category_modals(active_cell, data):
        if not current_user.is_authenticated: raise PreventUpdate
        if not active_cell or 'row' not in active_cell: raise PreventUpdate
        row_idx, col_id = active_cell['row'], active_cell['column_id']
        if not data or row_idx >= len(data): raise PreventUpdate
        category_id = data[row_idx]['category_id']; category_info = data[row_idx]
        if col_id == 'editar': return True, False, category_id, None, category_info['name']
        elif col_id == 'eliminar': return False, True, None, category_id, dash.no_update
        return False, False, None, None, dash.no_update

    # Callback Guardar Edición Categoría
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
        if not current_user.is_authenticated: raise PreventUpdate
        if not name: raise PreventUpdate # PENDIENTE: Alerta modal
        try:
            update_category(category_id, {"name": name.strip()}, int(current_user.id)) # <-- FIX numpy.int64
            return False, (signal or 0) + 1
        except Exception as e:
            print(f"Error al guardar categoría {category_id}: {e}")
            return True, dash.no_update # Mantener modal abierto

    # Callback Confirmar Eliminar Categoría
    @app.callback(
        Output('category-delete-confirm-modal', 'is_open', allow_duplicate=True),
        Output('store-data-signal', 'data', allow_duplicate=True),
        Input('confirm-delete-category-button', 'n_clicks'),
        [State('store-category-id-to-delete', 'data'), State('store-data-signal', 'data')],
        prevent_initial_call=True
    )
    def confirm_delete_category(n, category_id, signal):
        if n is None or n < 1: raise PreventUpdate
        if not category_id: raise PreventUpdate
        if not current_user.is_authenticated: raise PreventUpdate
        try:
            delete_category(category_id, int(current_user.id)) # <-- FIX numpy.int64
            return False, (signal or 0) + 1
        except Exception as e:
            print(f"Error al eliminar categoría {category_id}: {e}")
            return False, dash.no_update

    # Callback Cerrar Modales Categoría
    @app.callback(
        Output('category-edit-modal', 'is_open', allow_duplicate=True),
        Output('category-delete-confirm-modal', 'is_open', allow_duplicate=True),
        [Input('cancel-edit-category-button', 'n_clicks'), Input('cancel-delete-category-button', 'n_clicks')],
        prevent_initial_call=True
    )
    def close_category_modals(n_cancel_edit, n_cancel_delete):
         triggered_id = dash.callback_context.triggered_id
         if triggered_id in ['cancel-edit-category-button', 'cancel-delete-category-button']: return False, False
         raise PreventUpdate
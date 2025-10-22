from dash import dcc, html, dash_table
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
from dash.dash_table.Format import Format, Scheme
import pandas as pd
import base64
import io
import dash
from flask_login import current_user

from app import app
from database import load_sales, get_product_options, load_products, load_categories, update_stock, update_sale, delete_sale

def get_layout():
    return html.Div([
        dcc.Store(id='store-sale-id-to-edit'),
        dcc.Store(id='store-sale-id-to-delete'),
        
        dbc.Modal([
            dbc.ModalHeader("Editar Venta"),
            dbc.ModalBody(dbc.Form([
                # CORRECCIÓN: Div para mostrar errores (ej. stock)
                html.Div(id='edit-sale-alert'), 
                dbc.Row([
                    dbc.Col([dbc.Label("Producto"), dcc.Dropdown(id='edit-sale-product', options=[])]),
                    dbc.Col([dbc.Label("Cantidad"), dbc.Input(id='edit-sale-quantity', type='number')]),
                ]),
                dbc.Label("Fecha de Venta", className="mt-2"),
                dcc.DatePickerSingle(id='edit-sale-date')
            ])),
            dbc.ModalFooter([
                dbc.Button("Cancelar", id="cancel-edit-sale-button", color="secondary", className="ms-auto"),
                dbc.Button("Guardar Cambios", id="save-edited-sale-button", color="primary"),
            ]),
        ], id="sale-edit-modal", is_open=False),

        dbc.Modal([
            dbc.ModalHeader("Confirmar Eliminación"),
            dbc.ModalBody("¿Estás seguro de que quieres eliminar esta venta? El stock del producto será restaurado."),
            dbc.ModalFooter([
                dbc.Button("Cancelar", id="cancel-delete-sale-button", color="secondary", className="ms-auto"),
                dbc.Button("Eliminar", id="confirm-delete-sale-button", color="danger"),
            ]),
        ], id="sale-delete-confirm-modal", is_open=False),

        dbc.Card(className="m-4", children=[
            dbc.CardBody([
                html.H3("Registrar una Nueva Venta", className="card-title"),
                html.Div(id="sale-validation-alert"),
                dbc.Row([
                    dbc.Col([html.Label("Selecciona un Producto"), dcc.Dropdown(id='product-dropdown', placeholder="Selecciona un producto...")], width=6),
                    dbc.Col([html.Label("Cantidad Vendida"), dbc.Input(id='quantity-input', type='number', min=1, step=1, value=1)], width=6),
                ], className="mb-3"),
                dbc.Button("Registrar Venta", id="submit-sale-button", color="primary", n_clicks=0, className="mt-3")
            ])
        ]),
        
        dbc.Accordion([
            dbc.AccordionItem(
                [
                    dcc.Upload(
                        id='upload-sales-data',
                        children=html.Div(['Arrastra y suelta o ', html.A('Selecciona un Archivo')]),
                        style={'width': '100%', 'height': '60px', 'lineHeight': '60px', 'borderWidth': '1px', 'borderStyle': 'dashed', 'borderRadius': '5px', 'textAlign': 'center', 'margin': '10px 0'},
                        multiple=False
                    ),
                    
                    # CORRECCIÓN: Switch para decidir si se actualiza el stock
                    dbc.Switch(
                        id="upload-sales-update-stock",
                        label="Descontar stock del inventario actual (Marcar solo para ventas nuevas)",
                        value=False, # Por defecto, NO afectará el stock (para ventas pasadas)
                        className="my-2"
                    ),
                    
                    html.Div(id='upload-sales-output')
                ],
                title="Importar Historial de Ventas desde Excel"
            )
        ], start_collapsed=True, className="m-4"),
        
        dbc.Accordion([
            dbc.AccordionItem([
                dbc.Button("Descargar Excel", id="btn-download-sales-excel", color="success", className="mb-3"),
                html.Div(id='history-table-container')
            ], title="Ver Historial de Ventas")
        ], start_collapsed=True, className="m-4")
    ])

def register_callbacks(app):
    @app.callback(
        Output('sale-validation-alert', 'children'),
        Output('store-data-signal', 'data', allow_duplicate=True),
        Input('submit-sale-button', 'n_clicks'),
        [State('product-dropdown', 'value'), State('quantity-input', 'value'),
         State('store-data-signal', 'data')],
        prevent_initial_call=True
    )
    def register_sale(n, prod_id, qty, signal_data):
        if not current_user.is_authenticated or not all([prod_id, qty]):
            raise PreventUpdate
        
        user_id = current_user.id
        
        # --- INICIO DE CORRECCIÓN ---
        
        # 1. Validar cantidad
        try:
            qty = int(qty)
            if qty <= 0:
                return dbc.Alert("Error: La cantidad debe ser mayor a cero.", color="danger", dismissable=True), dash.no_update
        except (ValueError, TypeError):
             return dbc.Alert("Error: Cantidad no válida.", color="danger", dismissable=True), dash.no_update

        # 2. Importar la nueva función atómica
        from database import attempt_stock_deduction 

        # 3. Intentar deducir el stock de forma atómica
        success = attempt_stock_deduction(prod_id, qty, user_id)

        # 4. Si la deducción falló (no había stock o producto no existe)
        if not success:
            # Para dar un mensaje más útil, cargamos el stock actual (esto ya no causa race condition)
            products_df = load_products(user_id)
            try:
                current_stock = products_df.loc[products_df['product_id'] == prod_id, 'stock'].iloc[0]
                return dbc.Alert(f"Error: Stock insuficiente. Solo quedan {current_stock}.", color="danger", dismissable=True), dash.no_update
            except IndexError:
                 return dbc.Alert(f"Error: Producto no encontrado.", color="danger", dismissable=True), dash.no_update

        # 5. Si la deducción fue exitosa, OBTENER precio/costo y REGISTRAR la venta
        try:
            products_df = load_products(user_id) # Volver a cargar para obtener datos actualizados (opcional pero seguro)
            info = products_df.loc[products_df['product_id'] == prod_id].iloc[0]
            
            from database import engine
            pd.DataFrame([{
                'product_id': prod_id, 
                'quantity': qty, 
                'total_amount': info['price'] * qty,
                'cogs_total': info['cost'] * qty,
                'sale_date': pd.to_datetime('now').strftime('%Y-%m-%d %H:%M:%S'),
                'user_id': user_id
            }]).to_sql('sales', engine, if_exists='append', index=False)
            
            # NO necesitamos llamar a update_stock aquí, ya se hizo atómicamente

            new_signal = (signal_data or 0) + 1
            return dbc.Alert("¡Venta registrada!", color="success", dismissable=True, duration=4000), new_signal

        except Exception as e:
            # Error inesperado después de deducir stock (raro, pero posible)
            # Idealmente, aquí se debería revertir la deducción de stock,
            # pero por simplicidad, mostramos un error.
            print(f"Error al registrar venta después de deducir stock: {e}")
            # Intentamos restaurar stock (puede fallar si el producto ya no existe)
            try: 
                update_stock(prod_id, info['stock'] + qty, user_id) 
            except: pass
            return dbc.Alert("Error al registrar la venta. Stock restaurado si fue posible.", color="danger"), dash.no_update
        # --- FIN DE CORRECCIÓN ---

    @app.callback(
        Output('history-table-container', 'children'),
        Output('product-dropdown', 'options'),
        Output('edit-sale-product', 'options'), # <-- Añadido para poblar dropdown del modal
        [Input('main-tabs', 'active_tab'),
         Input('store-data-signal', 'data')]
    )
    def refresh_sales_components(active_tab, signal_data):
        if not current_user.is_authenticated or active_tab != 'tab-sales':
            raise PreventUpdate
        
        user_id = current_user.id
        sales_df = load_sales(user_id)
        products_df = load_products(user_id) # Carga todos (incl. inactivos)
        categories_df = load_categories(user_id) # Carga todas (incl. inactivas)

        df_show = pd.DataFrame()
        if not sales_df.empty:
            # Merge con TODOS los productos para reportes históricos
            df_show = pd.merge(sales_df, products_df, on='product_id', how='left')
            if not categories_df.empty and not df_show.empty:
                df_show = pd.merge(df_show, categories_df, on='category_id', how='left')
            
            df_show = df_show.rename(columns={'name_x': 'product_name', 'name_y': 'category_name'})
            
            # Rellenar nombres de productos/categorías eliminados
            df_show['product_name'] = df_show['product_name'].fillna('Producto Eliminado')
            df_show['category_name'] = df_show['category_name'].fillna('Sin Categoría')

            df_show['sale_date'] = pd.to_datetime(df_show['sale_date'], format='mixed').dt.strftime('%Y-%m-%d %H:%M')
            df_show['editar'] = "✏️"
            df_show['eliminar'] = "🗑️"

        table = dash_table.DataTable(
            id='history-table',
            columns=[
                {"name": "ID Venta", "id": "sale_id"},
                {"name": "Producto", "id": "product_name"},
                {"name": "Categoría", "id": "category_name"},
                {"name": "Cantidad", "id": "quantity"},
                {"name": "Monto Total", "id": "total_amount", 'type': 'numeric', 'format': Format(precision=2, scheme=Scheme.fixed)},
                {"name": "Fecha", "id": "sale_date"},
                {"name": "Editar", "id": "editar"},
                {"name": "Eliminar", "id": "eliminar"}
            ],
            data=df_show.to_dict('records'),
            page_size=10,
            sort_action='native',
            sort_by=[{'column_id': 'sale_date', 'direction': 'desc'}],
            style_cell_conditional=[{'if': {'column_id': 'editar'}, 'cursor': 'pointer'}, {'if': {'column_id': 'eliminar'}, 'cursor': 'pointer'}]
        )
        
        # Dropdowns solo deben mostrar productos ACTIVOS
        product_options = get_product_options(user_id)
        return table, product_options, product_options

    @app.callback(
        Output("download-sales-excel", "data"),
        Input("btn-download-sales-excel", "n_clicks"),
        prevent_initial_call=True
    )
    def download_sales(n_clicks):
        if n_clicks is None:
            raise PreventUpdate

        if not current_user.is_authenticated:
            raise PreventUpdate
            
        user_id = current_user.id
        sales_df = load_sales(user_id)
        products_df = load_products(user_id)
        categories_df = load_categories(user_id)
        
        df = pd.merge(sales_df, products_df, on='product_id', how='left')
        if not categories_df.empty and not df.empty:
            df = pd.merge(df, categories_df, on='category_id', how='left')
        df = df.rename(columns={'name_x': 'product_name', 'name_y': 'category_name'})
        
        return dcc.send_data_frame(df.to_excel, "historial_ventas.xlsx", sheet_name="Ventas", index=False)

    # --- CALLBACK CORREGIDO: IMPORTAR VENTAS (EXCEL) ---
    @app.callback(
        Output('upload-sales-output', 'children'),
        Output('store-data-signal', 'data', allow_duplicate=True),
        Input('upload-sales-data', 'contents'),
        [State('upload-sales-data', 'filename'),
         State('store-data-signal', 'data'),
         State('upload-sales-update-stock', 'value')], # <-- Añadido State del switch
        prevent_initial_call=True
    )
    def upload_sales_data(contents, filename, signal_data, update_stock_enabled): #<-- Añadido parámetro
        if not current_user.is_authenticated or contents is None:
            raise PreventUpdate
        
        user_id = current_user.id
        content_type, content_string = contents.split(',')
        decoded = base64.b64decode(content_string)
        
        try:
            if 'xls' in filename:
                df = pd.read_excel(io.BytesIO(decoded))
            else:
                return dbc.Alert("El archivo debe ser un .xlsx o .xls", color="danger"), dash.no_update
        except Exception as e:
            return dbc.Alert(f"Error al procesar el archivo: {e}", color="danger"), dash.no_update

        required_columns = ['Nombre del Producto', 'Cantidad', 'Fecha de Venta']
        errors = []
        if not all(col in df.columns for col in required_columns):
            return dbc.Alert(f"El archivo debe contener las columnas: {', '.join(required_columns)}", color="danger"), dash.no_update

        # Cargamos solo productos ACTIVOS para la importación
        products_db = pd.DataFrame(get_product_options(user_id))
        if products_db.empty:
            return dbc.Alert("No hay productos activos en la base de datos para importar ventas.", color="danger"), dash.no_update
            
        # Renombramos 'label' a 'name' para el lookup
        products_db['name'] = products_db['label'].apply(lambda x: x.split(' (Stock:')[0])
        products_db = products_db.set_index('name')
        
        products_lookup = products_db['value'].to_dict()
        
        # Necesitamos cargar todos los productos para precios y costos
        all_products_db = load_products(user_id)
        prices_lookup = all_products_db.set_index('product_id')['price'].to_dict()
        costs_lookup = all_products_db.set_index('product_id')['cost'].to_dict()
        stock_lookup = all_products_db.set_index('product_id')['stock'].to_dict()


        sales_to_insert = []
        for index, row in df.iterrows():
            product_name = row['Nombre del Producto']
            quantity = row['Cantidad']
            sale_date = row['Fecha de Venta']

            if product_name not in products_lookup:
                errors.append(f"Fila {index + 2}: El producto '{product_name}' no existe o está inactivo.")
                continue
            
            product_id = products_lookup[product_name]
            
            try:
                quantity = int(quantity)
                if quantity <= 0:
                     errors.append(f"Fila {index + 2}: La cantidad debe ser un número positivo.")
                     continue
            except (ValueError, TypeError):
                errors.append(f"Fila {index + 2}: La cantidad '{quantity}' no es un número válido.")
                continue

            try:
                sale_date = pd.to_datetime(sale_date)
            except (ValueError, TypeError):
                errors.append(f"Fila {index + 2}: La fecha '{sale_date}' no tiene un formato válido.")
                continue

            # Solo verificar y descontar stock SI el switch está activado
            if update_stock_enabled:
                current_stock = stock_lookup.get(product_id, 0)
                if quantity > current_stock:
                    errors.append(f"Fila {index + 2}: Stock insuficiente para '{product_name}'. Stock: {current_stock}, Pedido: {quantity}")
                    continue
                
                # Actualizar el stock en memoria para la siguiente fila
                stock_lookup[product_id] -= quantity

            price = prices_lookup.get(product_id, 0)
            cost = costs_lookup.get(product_id, 0)
            total_amount = price * quantity
            cogs_total = cost * quantity

            sales_to_insert.append({
                'product_id': product_id,
                'quantity': quantity,
                'total_amount': total_amount,
                'cogs_total': cogs_total,
                'sale_date': sale_date.strftime('%Y-%m-%d %H:%M:%S'),
                'user_id': user_id
            })

        if errors:
            error_messages = [html.P(e) for e in errors]
            return dbc.Alert([html.H5("Se encontraron errores. No se importó nada:")] + error_messages, color="danger"), dash.no_update

        if sales_to_insert:
            from database import engine
            sales_df = pd.DataFrame(sales_to_insert)
            sales_df.to_sql('sales', engine, if_exists='append', index=False)
            
            alert_message = f"¡Éxito! Se importaron {len(sales_to_insert)} registros de ventas."
            
            if update_stock_enabled:
                # Actualizar el stock en la BD
                for product_id, new_stock in stock_lookup.items():
                    if new_stock != all_products_db.set_index('product_id')['stock'].to_dict().get(product_id): 
                        update_stock(product_id, new_stock, user_id)
                alert_message += " Stock actualizado."
                    
            new_signal = (signal_data or 0) + 1
            return dbc.Alert(alert_message, color="success"), new_signal
        
        return dbc.Alert("No se encontraron registros válidos para importar.", color="warning"), dash.no_update

    @app.callback(
        Output('sale-edit-modal', 'is_open'),
        Output('sale-delete-confirm-modal', 'is_open'),
        Output('store-sale-id-to-edit', 'data'),
        Output('store-sale-id-to-delete', 'data'),
        Output('edit-sale-product', 'value'),
        Output('edit-sale-quantity', 'value'),
        Output('edit-sale-date', 'date'),
        Input('history-table', 'active_cell'),
        State('history-table', 'derived_virtual_data'),
        prevent_initial_call=True
    )
    def open_sale_modals(active_cell, data):
        if not current_user.is_authenticated or not active_cell or 'row' not in active_cell: 
            raise PreventUpdate
        
        user_id = current_user.id
        row_idx = active_cell['row']
        column_id = active_cell['column_id']
        
        if not data or row_idx >= len(data):
            raise PreventUpdate
        sale_id = data[row_idx]['sale_id']

        sales_df = load_sales(user_id)
        sale_info = sales_df[sales_df['sale_id'] == sale_id].iloc[0]

        if column_id == "editar":
            product_value = int(sale_info['product_id']) if pd.notna(sale_info['product_id']) else None
            quantity_value = sale_info['quantity']
            date_value = pd.to_datetime(sale_info['sale_date']).date()
            return True, False, sale_id, None, product_value, quantity_value, date_value
        
        elif column_id == "eliminar":
            return False, True, None, sale_id, dash.no_update, dash.no_update, dash.no_update

        return False, False, None, None, dash.no_update, dash.no_update, dash.no_update

    # --- CALLBACK CORREGIDO: EDITAR VENTA ---
    @app.callback(
        Output('sale-edit-modal', 'is_open', allow_duplicate=True),
        Output('store-data-signal', 'data', allow_duplicate=True),
        Output('edit-sale-alert', 'children'), # <-- Nuevo Output para alertas
        Input('save-edited-sale-button', 'n_clicks'),
        [State('store-sale-id-to-edit', 'data'),
         State('edit-sale-product', 'value'),
         State('edit-sale-quantity', 'value'),
         State('edit-sale-date', 'date'),
         State('store-data-signal', 'data')],
        prevent_initial_call=True
    )
    def save_edited_sale(n, sale_id, new_product_id, new_quantity, sale_date, signal):
        if not n or not sale_id: 
            raise PreventUpdate
        
        user_id = current_user.id
        
        # Validaciones
        if not all([new_product_id, new_quantity, sale_date]):
             return True, dash.no_update, dbc.Alert("Todos los campos son obligatorios.", color="danger")
        try:
            new_product_id = int(new_product_id)
            new_quantity = int(new_quantity)
            if new_quantity <= 0:
                 return True, dash.no_update, dbc.Alert("La cantidad debe ser positiva.", color="danger")
        except (ValueError, TypeError):
             return True, dash.no_update, dbc.Alert("Producto o cantidad no válida.", color="danger")

        # --- INICIO DE LÓGICA DE STOCK ---
        
        # 1. Obtener datos de la venta ORIGINAL
        try:
            sales_df = load_sales(user_id)
            original_sale_info = sales_df[sales_df['sale_id'] == sale_id].iloc[0]
            original_product_id = original_sale_info['product_id']
            original_quantity = original_sale_info['quantity']
        except (IndexError, KeyError):
            return True, dash.no_update, dbc.Alert("Error: No se encontró la venta original.", color="danger")
            
        products_df = load_products(user_id)
        
        # 3. Caso: El producto NO cambió (solo cambió la cantidad)
        if original_product_id == new_product_id:
            quantity_diff = new_quantity - original_quantity
            
            if quantity_diff != 0: # Solo si la cantidad cambió
                try:
                    current_stock = products_df[products_df['product_id'] == new_product_id]['stock'].iloc[0]
                    # Si la cantidad nueva es MAYOR, verificar stock
                    if quantity_diff > 0 and quantity_diff > current_stock:
                        return True, dash.no_update, dbc.Alert(f"Stock insuficiente. Solo quedan {current_stock} unidades.", color="danger")
                    
                    new_stock_val = current_stock - quantity_diff
                    update_stock(new_product_id, new_stock_val, user_id)
                except (IndexError, KeyError):
                     return True, dash.no_update, dbc.Alert("Error: El producto ya no existe. No se puede ajustar stock.", color="danger")

        # 4. Caso: El producto SÍ cambió
        else:
            # 4a. Restaurar stock del producto ORIGINAL
            if pd.notna(original_product_id):
                try:
                    original_stock = products_df[products_df['product_id'] == original_product_id]['stock'].iloc[0]
                    restored_stock = original_stock + original_quantity
                    update_stock(original_product_id, restored_stock, user_id)
                except (IndexError, KeyError):
                    pass # El producto original ya no existe

            # 4b. Descontar stock del producto NUEVO
            try:
                new_product_stock = products_df[products_df['product_id'] == new_product_id]['stock'].iloc[0]
                if new_quantity > new_product_stock:
                    # NOTA: El stock del producto original ya fue restaurado.
                    # El usuario deberá cerrar y re-editar para arreglarlo.
                    return True, dash.no_update, dbc.Alert(f"Stock insuficiente para el nuevo producto. Solo quedan {new_product_stock}.", color="danger")
                
                new_stock_val = new_product_stock - new_quantity
                update_stock(new_product_id, new_stock_val, user_id)
            except (IndexError, KeyError):
                 return True, dash.no_update, dbc.Alert("Error: El nuevo producto seleccionado no existe.", color="danger")

        # --- FIN DE LÓGICA DE STOCK ---

        # 5. Actualizar los datos de la venta
        product_info = products_df[products_df['product_id'] == new_product_id].iloc[0]
        formatted_date = pd.to_datetime(sale_date).strftime('%Y-%m-%d %H:%M:%S')

        new_data = {
            "product_id": new_product_id,
            "quantity": new_quantity,
            "total_amount": float(product_info['price'] * new_quantity),
            "cogs_total": float(product_info['cost'] * new_quantity),
            "sale_date": formatted_date
        }
        update_sale(sale_id, new_data, user_id)
        
        # 6. Éxito: Cerrar modal, actualizar señal, limpiar alerta
        return False, (signal or 0) + 1, None

    # --- CALLBACK CORREGIDO: ELIMINAR VENTA ---
    @app.callback(
        Output('sale-delete-confirm-modal', 'is_open', allow_duplicate=True),
        Output('store-data-signal', 'data', allow_duplicate=True),
        Input('confirm-delete-sale-button', 'n_clicks'),
        [State('store-sale-id-to-delete', 'data'), State('store-data-signal', 'data')],
        prevent_initial_call=True
    )
    def confirm_delete_sale(n, sale_id, signal):
        if not n or not sale_id: raise PreventUpdate
        
        user_id = current_user.id
        
        # 1. Obtener la información de la venta ANTES de borrarla
        try:
            sales_df = load_sales(user_id)
            sale_info = sales_df[sales_df['sale_id'] == sale_id].iloc[0]
            product_id = sale_info['product_id']
            quantity_sold = sale_info['quantity']
        except (IndexError, KeyError):
            product_id = None # La venta no se encontró o ya no tiene producto
        
        # 2. Obtener el stock actual del producto
        if pd.notna(product_id):
            try:
                products_df = load_products(user_id)
                current_stock = products_df[products_df['product_id'] == product_id]['stock'].iloc[0]
                
                # 3. Calcular y actualizar el nuevo stock (restaurarlo)
                new_stock = current_stock + quantity_sold
                update_stock(product_id, new_stock, user_id)
            except (IndexError, KeyError):
                pass # El producto ya no existe, no se puede restaurar stock

        # 4. Borrar la venta (lógica original)
        delete_sale(sale_id, current_user.id)
        return False, (signal or 0) + 1

    @app.callback(
        Output('sale-edit-modal', 'is_open', allow_duplicate=True),
        Output('sale-delete-confirm-modal', 'is_open', allow_duplicate=True),
        [Input('cancel-edit-sale-button', 'n_clicks'),
         Input('cancel-delete-sale-button', 'n_clicks')],
        prevent_initial_call=True
    )
    def close_sale_modals(n_edit, n_delete):
        return False, False
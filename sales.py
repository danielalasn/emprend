# sales.py
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
from datetime import datetime # Added for datetime objects

from app import app
from database import (
    load_sales, get_product_options, load_products, load_categories,
    update_stock, update_sale, delete_sale, attempt_stock_deduction,
    delete_sales_bulk # <-- Importación añadida
)

def get_layout():
    return html.Div([
        dcc.Store(id='store-sale-id-to-edit'),
        dcc.Store(id='store-sale-id-to-delete'),

        dbc.Modal([ # Edit Sale Modal
            dbc.ModalHeader("Editar Venta"),
            dbc.ModalBody(dbc.Form([
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

        dbc.Modal([ # Delete Sale Modal
             dbc.ModalHeader("Confirmar Eliminación"),
             dbc.ModalBody("¿Estás seguro de que quieres eliminar esta venta? El stock del producto será restaurado."),
             dbc.ModalFooter([
                 dbc.Button("Cancelar", id="cancel-delete-sale-button", color="secondary", className="ms-auto"),
                 dbc.Button("Eliminar", id="confirm-delete-sale-button", color="danger"),
             ]),
         ], id="sale-delete-confirm-modal", is_open=False),

         dbc.Card(className="m-4", children=[ # Register Sale Card
             dbc.CardBody([
                 html.H3("Registrar una Nueva Venta", className="card-title"),
                 html.Div(id="sale-validation-alert"),
                 dbc.Row([
                     dbc.Col([html.Label("Selecciona un Producto"), dcc.Dropdown(id='product-dropdown', placeholder="Selecciona un producto...")], width=6),
                     # SIN PLACEHOLDER: 'value=1' se usa por defecto
                     dbc.Col([html.Label("Cantidad Vendida"), dbc.Input(id='quantity-input', type='number', min=1, step=1, value=1)], width=6),
                 ], className="mb-3"),
                 dbc.Button("Registrar Venta", id="submit-sale-button", color="primary", n_clicks=0, className="mt-3")
             ])
         ]),

         dbc.Accordion([ # Import Sales Accordion
             dbc.AccordionItem(
                 children=[ # <-- Corregido para envolver en lista
                     dcc.Upload(
                         id='upload-sales-data',
                         children=html.Div(['Arrastra y suelta o ', html.A('Selecciona un Archivo')]),
                         style={'width': '100%', 'height': '60px', 'lineHeight': '60px', 'borderWidth': '1px', 'borderStyle': 'dashed', 'borderRadius': '5px', 'textAlign': 'center', 'margin': '10px 0'},
                         multiple=False
                     ),
                     dbc.Alert([
                         html.H5("Formato Requerido:", className="alert-heading"),
                         html.P("El archivo Excel debe tener las siguientes columnas (exactamente como se escriben):"),
                         html.Ul([
                            html.Li([html.B("nombre"), " (El 'Nombre del Producto' ya debe existir en tus productos)"]),
                            html.Li([html.B("cantidad"), " (El número de unidades vendidas)"]),
                            html.Li([html.B("fecha"), " (Formato AAAA-MM-DD o similar)"]),
                            ])
                     ], color="info", className="mt-2"),

                     dbc.Switch(
                         id="upload-sales-update-stock",
                         label="Descontar stock del inventario actual (Marcar solo para ventas nuevas)",
                         value=False,
                         className="my-2"
                     ),
                     html.Div(id='upload-sales-output')
                 ],
                 title="Importar Historial de Ventas desde Excel"
             )
         ], start_collapsed=True, className="m-4"),

         dbc.Accordion([ # Sales History Accordion
             # EN sales.py, DENTRO DE get_layout()
            dbc.AccordionItem(
                children=[ 
                    dbc.Button("Descargar Excel", id="btn-download-sales-excel", color="success", className="mb-3 me-2"),
                    dbc.Button("Borrar Seleccionados", id="delete-selected-sales-btn", color="danger", n_clicks=0, className="mb-3"),
                    html.Div(id='bulk-delete-sales-output'),

                    # --- INICIO DE LA CORRECCIÓN ---
                    # Definimos la tabla aquí, en el layout, con data vacía
                    dash_table.DataTable(
                        id='history-table', # <-- El ID ahora existe en el layout
                        columns=[
                            {"name": "ID Venta", "id": "sale_id"},
                            {"name": "Producto", "id": "product_name"},
                            {"name": "Categoría", "id": "category_name"},
                            {"name": "Cantidad", "id": "quantity"},
                            {"name": "Monto Total", "id": "total_amount", 'type': 'numeric', 'format': Format(precision=2, scheme=Scheme.fixed)},
                            {"name": "Fecha", "id": "sale_date_display"}, 
                            {"name": "Editar", "id": "editar"},
                            {"name": "Eliminar", "id": "eliminar"}
                        ],
                        data=[], # <-- Se inicializa vacía
                        page_size=10,
                        sort_action='native',
                        row_selectable='multi',
                        selected_rows=[],
                        selected_row_ids=[],
                        sort_by=[{'column_id': 'sale_date_display', 'direction': 'desc'}],
                        style_cell_conditional=[
                            {'if': {'column_id': 'editar'}, 'cursor': 'pointer'},
                            {'if': {'column_id': 'eliminar'}, 'cursor': 'pointer'}
                        ]
                    )
                    # --- FIN DE LA CORRECCIÓN ---
                ], 
                title="Ver Historial de Ventas"
             )
         ], start_collapsed=True, className="m-4")
     ])


def register_callbacks(app):

    # --- CALLBACK: Registrar Venta (con deducción atómica) ---
    @app.callback(
        Output('sale-validation-alert', 'children'),
        Output('store-data-signal', 'data', allow_duplicate=True), # <-- CORREGIDO: allow_duplicate añadido
        Input('submit-sale-button', 'n_clicks'),
        [State('product-dropdown', 'value'), State('quantity-input', 'value'),
         State('store-data-signal', 'data')],
        prevent_initial_call=True
    )
    def register_sale(n, prod_id, qty, signal_data):
        if not current_user.is_authenticated or not all([prod_id, qty]):
            raise PreventUpdate

        user_id = int(current_user.id) # Fix numpy.int64
        try:
            qty = int(qty)
            if qty <= 0:
                return dbc.Alert("Error: La cantidad debe ser mayor a cero.", color="danger", dismissable=True), dash.no_update
        except (ValueError, TypeError):
             return dbc.Alert("Error: Cantidad no válida.", color="danger", dismissable=True), dash.no_update

        # Intentar deducir stock atómicamente
        success = attempt_stock_deduction(prod_id, qty, user_id)

        if not success:
            # Si falló, obtener stock actual para mensaje
            products_df = load_products(user_id)
            try:
                current_stock = products_df.loc[products_df['product_id'] == prod_id, 'stock'].iloc[0]
                return dbc.Alert(f"Error: Stock insuficiente. Solo quedan {current_stock}.", color="danger", dismissable=True), dash.no_update
            except IndexError:
                 return dbc.Alert(f"Error: Producto no encontrado.", color="danger", dismissable=True), dash.no_update

        # Si la deducción tuvo éxito, registrar la venta
        try:
            products_df = load_products(user_id) # Cargar datos del producto
            info = products_df.loc[products_df['product_id'] == prod_id].iloc[0]

            from database import engine
            sale_time = datetime.now() # Usar objeto datetime
            pd.DataFrame([{
                'product_id': prod_id,
                'quantity': qty,
                'total_amount': info['price'] * qty,
                'cogs_total': info['cost'] * qty,
                'sale_date': sale_time, # Guardar como datetime
                'user_id': user_id
            }]).to_sql('sales', engine, if_exists='append', index=False)

            new_signal = (signal_data or 0) + 1
            return dbc.Alert("¡Venta registrada!", color="success", dismissable=True, duration=4000), new_signal

        except Exception as e:
            # Error después de deducir stock (raro)
            print(f"Error al registrar venta después de deducir stock: {e}")
            try:
                 # Intentar restaurar stock
                 products_df = load_products(user_id)
                 info = products_df.loc[products_df['product_id'] == prod_id].iloc[0]
                 update_stock(prod_id, info['stock'] + qty, user_id)
            except: pass
            return dbc.Alert("Error al registrar la venta. Stock restaurado si fue posible.", color="danger"), dash.no_update


    # --- CALLBACK: Refrescar Tabla y Dropdowns ---
    @app.callback(
        Output('history-table', 'data'),
        Output('product-dropdown', 'options'),
        Output('edit-sale-product', 'options'),
        [Input('main-tabs', 'active_tab'), # Trigger 1
         Input('store-data-signal', 'data')] # Trigger 2
    )
    def refresh_sales_components(active_tab, signal_data):
        if not current_user.is_authenticated:
             raise PreventUpdate
        triggered_id = dash.callback_context.triggered_id
        if triggered_id == 'main-tabs' and active_tab != 'tab-sales':
            raise PreventUpdate
        if active_tab != 'tab-sales':
             raise PreventUpdate

        user_id = int(current_user.id) # Fix numpy.int64
        sales_df = load_sales(user_id)
        products_df = load_products(user_id)
        categories_df = load_categories(user_id)

        df_show = pd.DataFrame()
        if not sales_df.empty:
            df_show = pd.merge(sales_df, products_df, on='product_id', how='left')
            if not categories_df.empty and not df_show.empty:
                df_show = pd.merge(df_show, categories_df, on='category_id', how='left')

            df_show = df_show.rename(columns={'name_x': 'product_name', 'name_y': 'category_name'})
            df_show['product_name'] = df_show['product_name'].fillna('Producto Eliminado')
            df_show['category_name'] = df_show['category_name'].fillna('Sin Categoría')
            df_show['sale_date_display'] = df_show['sale_date'].dt.strftime('%Y-%m-%d %H:%M')
            df_show['editar'] = "✏️"
            df_show['eliminar'] = "🗑️"
            df_show['id'] = df_show['sale_id'] # <-- AÑADIDO PARA BORRADO MASIVO

        product_options = get_product_options(user_id)

        # Simplemente devolvemos los datos para la tabla, no el componente
        return df_show.to_dict('records'), product_options, product_options

    # --- CALLBACK: Descargar Excel ---
    @app.callback(
        Output("download-sales-excel", "data"),
        Input("btn-download-sales-excel", "n_clicks"),
        prevent_initial_call=True
    )
    def download_sales(n_clicks):
        if n_clicks is None: raise PreventUpdate
        if not current_user.is_authenticated: raise PreventUpdate

        user_id = int(current_user.id) # Fix numpy.int64
        sales_df = load_sales(user_id)
        products_df = load_products(user_id)
        categories_df = load_categories(user_id)

        df = pd.merge(sales_df, products_df, on='product_id', how='left')
        if not categories_df.empty and not df.empty:
            df = pd.merge(df, categories_df, on='category_id', how='left')
        df = df.rename(columns={'name_x': 'product_name', 'name_y': 'category_name'})

        return dcc.send_data_frame(df.to_excel, "historial_ventas.xlsx", sheet_name="Ventas", index=False)

    # --- CALLBACK: Importar Ventas (Excel) ---
    @app.callback(
        Output('upload-sales-output', 'children'),
        Output('store-data-signal', 'data', allow_duplicate=True),
        Input('upload-sales-data', 'contents'),
        [State('upload-sales-data', 'filename'),
         State('store-data-signal', 'data'),
         State('upload-sales-update-stock', 'value')],
        prevent_initial_call=True
    )
    def upload_sales_data(contents, filename, signal_data, update_stock_enabled):
        if not current_user.is_authenticated or contents is None: raise PreventUpdate

        user_id = int(current_user.id) # Fix numpy.int64
        content_type, content_string = contents.split(',')
        decoded = base64.b64decode(content_string)

        try:
            if 'xls' in filename:
                df = pd.read_excel(io.BytesIO(decoded))
            else:
                return dbc.Alert("El archivo debe ser un .xlsx o .xls", color="danger"), dash.no_update
        except Exception as e:
            return dbc.Alert(f"Error al procesar el archivo: {e}", color="danger"), dash.no_update

        required_columns = ['nombre', 'cantidad', 'fecha'] 
        errors = []
        if not all(col in df.columns for col in required_columns):
            return dbc.Alert(f"El archivo debe contener las columnas: {', '.join(required_columns)}", color="danger"), dash.no_update
        
        products_active_df = pd.DataFrame(get_product_options(user_id))
        if products_active_df.empty:
            return dbc.Alert("No hay productos activos para importar ventas.", color="warning"), dash.no_update
        products_active_df['name'] = products_active_df['label'].apply(lambda x: x.split(' (Stock:')[0])
        products_lookup = products_active_df.set_index('name')['value'].to_dict()

        all_products_db = load_products(user_id)
        prices_lookup = all_products_db.set_index('product_id')['price'].to_dict()
        costs_lookup = all_products_db.set_index('product_id')['cost'].to_dict()
        stock_lookup = all_products_db.set_index('product_id')['stock'].to_dict() 

        sales_to_insert = []
        stock_updates_needed = {} 

        for index, row in df.iterrows():
            product_name = row['nombre']
            quantity = row['cantidad']
            sale_date = row['fecha']

            if product_name not in products_lookup:
                errors.append(f"Fila {index + 2}: El producto '{product_name}' no existe o está inactivo.")
                continue

            product_id = products_lookup[product_name]

            try:
                quantity = int(quantity)
                if quantity <= 0:
                     errors.append(f"Fila {index + 2}: La cantidad debe ser positiva.")
                     continue
            except (ValueError, TypeError):
                errors.append(f"Fila {index + 2}: La cantidad '{quantity}' no es un número válido.")
                continue

            try:
                sale_date_dt = pd.to_datetime(sale_date)
                sale_date_to_save = sale_date_dt.to_pydatetime()
            except (ValueError, TypeError):
                errors.append(f"Fila {index + 2}: La fecha '{sale_date}' no tiene un formato válido.")
                continue

            if update_stock_enabled:
                current_stock = stock_updates_needed.get(product_id, stock_lookup.get(product_id, 0))
                if quantity > current_stock:
                    errors.append(f"Fila {index + 2}: Stock insuficiente para '{product_name}'. Stock: {current_stock}, Pedido: {quantity}")
                    continue
                stock_updates_needed[product_id] = current_stock - quantity

            price = prices_lookup.get(product_id, 0)
            cost = costs_lookup.get(product_id, 0)
            total_amount = price * quantity
            cogs_total = cost * quantity

            sales_to_insert.append({
                'product_id': product_id,
                'quantity': quantity,
                'total_amount': total_amount,
                'cogs_total': cogs_total,
                'sale_date': sale_date_to_save,
                'user_id': user_id
            })

        if errors:
            return dbc.Alert([html.H5("Se encontraron errores. No se importó nada:")] + [html.P(e) for e in errors], color="danger"), dash.no_update

        if sales_to_insert:
            from database import engine
            sales_df_to_insert = pd.DataFrame(sales_to_insert)
            sales_df_to_insert.to_sql('sales', engine, if_exists='append', index=False)

            alert_message = f"¡Éxito! Se importaron {len(sales_to_insert)} registros de ventas."

            if update_stock_enabled and stock_updates_needed:
                for product_id, new_stock in stock_updates_needed.items():
                    update_stock(product_id, new_stock, user_id)
                alert_message += " Stock actualizado."

            new_signal = (signal_data or 0) + 1
            return dbc.Alert(alert_message, color="success"), new_signal

        return dbc.Alert("No se encontraron registros válidos para importar.", color="warning"), dash.no_update


    # --- CALLBACK: Abrir Modales Editar/Eliminar ---
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

        user_id = int(current_user.id) # Fix numpy.int64
        row_idx = active_cell['row']
        column_id = active_cell['column_id']

        if not data or row_idx >= len(data): raise PreventUpdate
        sale_id = data[row_idx]['sale_id']

        sales_df = load_sales(user_id) 
        try:
            sale_info = sales_df[sales_df['sale_id'] == sale_id].iloc[0]
        except IndexError:
             return False, False, None, None, dash.no_update, dash.no_update, dash.no_update

        if column_id == "editar":
            product_value = int(sale_info['product_id']) if pd.notna(sale_info['product_id']) else None
            quantity_value = sale_info['quantity']
            date_value = sale_info['sale_date'].date() if pd.notna(sale_info['sale_date']) else None
            return True, False, sale_id, None, product_value, quantity_value, date_value

        elif column_id == "eliminar":
            return False, True, None, sale_id, dash.no_update, dash.no_update, dash.no_update

        return False, False, None, None, dash.no_update, dash.no_update, dash.no_update

    # --- CALLBACK: Guardar Edición de Venta ---
    @app.callback(
        Output('sale-edit-modal', 'is_open', allow_duplicate=True),
        Output('store-data-signal', 'data', allow_duplicate=True),
        Output('edit-sale-alert', 'children'),
        Input('save-edited-sale-button', 'n_clicks'),
        [State('store-sale-id-to-edit', 'data'),
         State('edit-sale-product', 'value'),
         State('edit-sale-quantity', 'value'),
         State('edit-sale-date', 'date'), 
         State('store-data-signal', 'data')],
        prevent_initial_call=True
    )
    def save_edited_sale(n, sale_id, new_product_id, new_quantity, sale_date_str, signal):
        if not n or not sale_id: raise PreventUpdate

        user_id = int(current_user.id) # Fix numpy.int64

        if not all([new_product_id, new_quantity, sale_date_str]):
             return True, dash.no_update, dbc.Alert("Todos los campos son obligatorios.", color="danger")
        try:
            new_product_id = int(new_product_id)
            new_quantity = int(new_quantity)
            if new_quantity <= 0:
                 return True, dash.no_update, dbc.Alert("La cantidad debe ser positiva.", color="danger")
            sale_date_dt = datetime.strptime(sale_date_str, '%Y-%m-%d')
        except (ValueError, TypeError):
             return True, dash.no_update, dbc.Alert("Producto, cantidad o fecha no válida.", color="danger")

        try:
            sales_df = load_sales(user_id)
            original_sale_info = sales_df[sales_df['sale_id'] == sale_id].iloc[0]
            original_product_id = original_sale_info['product_id']
            original_quantity = original_sale_info['quantity']
        except (IndexError, KeyError):
            return True, dash.no_update, dbc.Alert("Error: No se encontró la venta original.", color="danger")

        products_df = load_products(user_id) 

        if original_product_id == new_product_id:
            quantity_diff = new_quantity - original_quantity
            if quantity_diff != 0:
                try:
                    current_stock = products_df.loc[products_df['product_id'] == new_product_id, 'stock'].iloc[0]
                    if quantity_diff > 0 and quantity_diff > current_stock:
                        return True, dash.no_update, dbc.Alert(f"Stock insuficiente. Solo quedan {current_stock}.", color="danger")
                    new_stock_val = current_stock - quantity_diff
                    update_stock(new_product_id, new_stock_val, user_id)
                except (IndexError, KeyError):
                     return True, dash.no_update, dbc.Alert("Error: El producto ya no existe.", color="danger")

        else:
            if pd.notna(original_product_id):
                try:
                    original_stock = products_df.loc[products_df['product_id'] == original_product_id, 'stock'].iloc[0]
                    restored_stock = original_stock + original_quantity
                    update_stock(original_product_id, restored_stock, user_id)
                except (IndexError, KeyError): pass 

            try:
                new_product_stock = products_df.loc[products_df['product_id'] == new_product_id, 'stock'].iloc[0]
                if new_quantity > new_product_stock:
                    return True, dash.no_update, dbc.Alert(f"Stock insuficiente para nuevo producto ({new_product_stock}). Stock original restaurado.", color="danger")
                new_stock_val = new_product_stock - new_quantity
                update_stock(new_product_id, new_stock_val, user_id)
            except (IndexError, KeyError):
                 return True, dash.no_update, dbc.Alert("Error: El nuevo producto seleccionado no existe.", color="danger")

        try:
            product_info = products_df.loc[products_df['product_id'] == new_product_id].iloc[0]
        except IndexError:
             return True, dash.no_update, dbc.Alert("Error: No se encontraron datos del nuevo producto.", color="danger")

        new_data = {
            "product_id": new_product_id,
            "quantity": new_quantity,
            "total_amount": float(product_info['price'] * new_quantity),
            "cogs_total": float(product_info['cost'] * new_quantity),
            "sale_date": sale_date_dt
        }
        update_sale(sale_id, new_data, user_id)

        return False, (signal or 0) + 1, None # Éxito

    # --- CALLBACK: Confirmar Eliminar Venta ---
    @app.callback(
        Output('sale-delete-confirm-modal', 'is_open', allow_duplicate=True),
        Output('store-data-signal', 'data', allow_duplicate=True),
        Input('confirm-delete-sale-button', 'n_clicks'),
        [State('store-sale-id-to-delete', 'data'), State('store-data-signal', 'data')],
        prevent_initial_call=True
    )
    def confirm_delete_sale(n, sale_id, signal):
        if not n or not sale_id: raise PreventUpdate

        user_id = int(current_user.id) # Fix numpy.int64
        product_id_to_restore = None
        quantity_to_restore = 0

        try:
            sales_df = load_sales(user_id)
            sale_info = sales_df[sales_df['sale_id'] == sale_id].iloc[0]
            product_id_to_restore = sale_info['product_id']
            quantity_to_restore = sale_info['quantity']
        except (IndexError, KeyError):
            print(f"Advertencia: No se encontró la venta {sale_id} para restaurar stock.")

        delete_sale(sale_id, user_id)

        if pd.notna(product_id_to_restore) and quantity_to_restore > 0:
            try:
                products_df = load_products(user_id)
                current_stock = products_df.loc[products_df['product_id'] == product_id_to_restore, 'stock'].iloc[0]
                new_stock = current_stock + quantity_to_restore
                update_stock(product_id_to_restore, new_stock, user_id)
            except (IndexError, KeyError):
                print(f"Advertencia: No se pudo restaurar stock para producto {product_id_to_restore} (quizás ya no existe).")
            except Exception as e:
                 print(f"Error inesperado al restaurar stock para producto {product_id_to_restore}: {e}")

        return False, (signal or 0) + 1

    # --- CALLBACK: Cerrar Modales ---
    @app.callback(
        Output('sale-edit-modal', 'is_open', allow_duplicate=True),
        Output('sale-delete-confirm-modal', 'is_open', allow_duplicate=True),
        [Input('cancel-edit-sale-button', 'n_clicks'),
         Input('cancel-delete-sale-button', 'n_clicks')],
        prevent_initial_call=True
    )
    def close_sale_modals(n_edit, n_delete):
        triggered_id = dash.callback_context.triggered_id
        if triggered_id in ['cancel-edit-sale-button', 'cancel-delete-sale-button']:
            return False, False
        raise PreventUpdate

    # --- NUEVO CALLBACK: BORRADO MASIVO DE VENTAS ---
    @app.callback(
        Output('bulk-delete-sales-output', 'children'),
        Output('store-data-signal', 'data', allow_duplicate=True),
        Input('delete-selected-sales-btn', 'n_clicks'),
        [State('history-table', 'selected_row_ids'),
         State('store-data-signal', 'data')],
        prevent_initial_call=True
    )
    def delete_selected_sales(n_clicks, selected_ids, signal_data):
        if n_clicks is None or n_clicks < 1 or not selected_ids:
            raise PreventUpdate
        
        if not current_user.is_authenticated:
            raise PreventUpdate
        
        user_id = int(current_user.id)
        
        try:
            success, message = delete_sales_bulk(selected_ids, user_id)
            if success:
                new_signal = (signal_data or 0) + 1
                return dbc.Alert(message, color="success", dismissable=True, duration=4000), new_signal
            else:
                return dbc.Alert(message, color="danger", dismissable=True), dash.no_update
        except Exception as e:
            print(f"Error en borrado masivo de ventas: {e}")
            return dbc.Alert("Ocurrió un error al intentar borrar las ventas.", color="danger", dismissable=True), dash.no_update
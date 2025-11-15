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
from datetime import datetime
from sqlalchemy import text 

from app import app
from database import (
    load_sales, load_products, load_categories,
    update_stock, update_sale, delete_sale, attempt_stock_deduction,
    delete_sales_bulk, engine
)

def get_layout():
    return html.Div([
        dcc.Store(id='store-sale-id-to-edit'),
        dcc.Store(id='store-sale-id-to-delete'),
        # Eliminamos el dcc.Store('client-timestamp-store')

        # --- MODAL EDITAR VENTA ---
        dbc.Modal([ 
            dbc.ModalHeader("Editar Venta"),
            dbc.ModalBody(dbc.Form([
                html.Div(id='edit-sale-alert'),
                dbc.Row([
                    dbc.Col([
                        dbc.Label("Producto", className="fw-bold small"),
                        dcc.Dropdown(id='edit-sale-product', placeholder="Busca el producto...", options=[])
                    ], xs=12, className="mb-2"),
                    dbc.Col([
                        dbc.Label("Cantidad", className="fw-bold small"),
                        dbc.Input(id='edit-sale-quantity', type='number')
                    ], xs=12, className="mb-2"),
                ]),
                dbc.Label("Fecha de Venta", className="mt-2 fw-bold small"),
                html.Div(dcc.DatePickerSingle(id='edit-sale-date', className="w-100")) 
            ])),
            dbc.ModalFooter([
                dbc.Button("Cancelar", id="cancel-edit-sale-button", color="secondary", className="ms-auto"),
                dbc.Button("Guardar Cambios", id="save-edited-sale-button", color="primary"),
            ]),
        ], id="sale-edit-modal", is_open=False),

        # --- MODAL ELIMINAR VENTA ---
        dbc.Modal([ 
             dbc.ModalHeader("Confirmar Eliminación"),
             dbc.ModalBody("¿Estás seguro de que quieres eliminar esta venta? El stock del producto será restaurado."),
             dbc.ModalFooter([
                 dbc.Button("Cancelar", id="cancel-delete-sale-button", color="secondary", className="ms-auto"),
                 dbc.Button("Eliminar", id="confirm-delete-sale-button", color="danger"),
             ]),
         ], id="sale-delete-confirm-modal", is_open=False),

         # --- PESTAÑAS ---
         dbc.Tabs(id="sales-tabs", active_tab="tab-register-sale", children=[
             
             # TAB 1: REGISTRAR VENTA
             dbc.Tab(label="Registrar Venta", tab_id="tab-register-sale", children=[
                 
                 dbc.Card(className="m-2 m-md-4 shadow-sm", children=[ 
                     dbc.CardBody([
                         html.H3("Registrar una Nueva Venta", className="card-title mb-4"),
                         html.Div(id="sale-validation-alert"),
                         
                         dbc.Row([
                             dbc.Col([
                                 html.Label("Selecciona un Producto", className="fw-bold small"), 
                                 dcc.Dropdown(id='product-dropdown', placeholder="Busca por categoría o nombre...")
                             ], xs=12, md=6, className="mb-3 mb-md-0"),
                             
                             dbc.Col([
                                 html.Label("Cantidad Vendida", className="fw-bold small"), 
                                 dbc.Input(id='quantity-input', type='number', min=1, step=1, value=1)
                             ], xs=12, md=6),
                         ], className="mb-3"),
                         
                         dbc.Button("Registrar Venta", id="submit-sale-button", color="primary", n_clicks=0, className="mt-3 w-100 w-md-auto")
                     ])
                 ]),

                 dbc.Accordion([ 
                     dbc.AccordionItem(
                         children=[ 
                             dcc.Upload(
                                 id='upload-sales-data',
                                 children=html.Div(['Arrastra y suelta o ', html.A('Selecciona un Archivo')]),
                                 style={'width': '100%', 'height': '60px', 'lineHeight': '60px', 'borderWidth': '1px', 'borderStyle': 'dashed', 'borderRadius': '5px', 'textAlign': 'center', 'margin': '10px 0'},
                                 multiple=False
                             ),
                             dbc.Alert([
                                 html.H5("Formato Requerido:", className="alert-heading"),
                                 html.P("El archivo Excel debe tener las siguientes columnas:"),
                                 html.Ul([
                                    html.Li([html.B("categoria"), " (Ej: 'Ropa')"]),
                                    html.Li([html.B("nombre"), " (Ej: 'Camiseta Negra')"]),
                                    html.Li([html.B("cantidad"), " (Número de unidades)"]),
                                    html.Li([html.B("fecha"), " (Formato AAAA-MM-DD)"]),
                                    ]),
                                 html.P("Nota: La combinación Categoría + Nombre debe coincidir exactamente.", className="small text-muted")
                             ], color="info", className="mt-2 small"),

                             dbc.Switch(
                                 id="upload-sales-update-stock",
                                 label="Descontar stock del inventario actual",
                                 value=False,
                                 className="my-2"
                             ),
                             html.Div(id='upload-sales-output')
                         ],
                         title="Importar Historial de Ventas desde Excel"
                     )
                 ], start_collapsed=True, className="m-2 m-md-4"),
             ]),

             # TAB 2: HISTORIAL
             dbc.Tab(label="Historial", tab_id="tab-sales-history", children=[
                 html.Div(className="p-2 p-md-4", children=[ 
                     dbc.Row([
                        dbc.Col(html.H4("Historial de Ventas"), width="auto"),
                        dbc.Col([
                            dbc.Button("Descargar Excel", id="btn-download-sales-excel", color="success", size="sm", className="me-2"),
                            dbc.Button("Borrar Seleccionados", id="delete-selected-sales-btn", color="danger", size="sm")
                        ], width="auto", className="ms-auto")
                     ], className="mb-3 align-items-center"),
                     
                     html.Div(id='bulk-delete-sales-output'), 
                     
                     dash_table.DataTable(
                        id='history-table',
                        columns=[
                            {"name": "ID Venta", "id": "sale_id"},
                            {"name": "Categoría", "id": "category_name"},
                            {"name": "Producto", "id": "product_name"},
                            {"name": "Cantidad", "id": "quantity"},
                            {"name": "Monto Total", "id": "total_amount", 'type': 'numeric', 'format': Format(precision=2, scheme=Scheme.fixed)},
                            {"name": "Fecha", "id": "sale_date_display"}, 
                            {"name": "Editar", "id": "editar"},
                            {"name": "Eliminar", "id": "eliminar"}
                        ],
                        data=[], 
                        page_size=15,
                        sort_action='native',
                        row_selectable='multi',
                        selected_rows=[],
                        selected_row_ids=[],
                        sort_by=[{'column_id': 'sale_date_display', 'direction': 'desc'}],
                        style_table={'overflowX': 'auto'},
                        style_cell={'textAlign': 'left', 'minWidth': '100px'},
                        style_cell_conditional=[
                            {'if': {'column_id': 'editar'}, 'cursor': 'pointer', 'textAlign': 'center', 'width': '80px'},
                            {'if': {'column_id': 'eliminar'}, 'cursor': 'pointer', 'textAlign': 'center', 'width': '80px'}
                        ]
                    )
                 ])
             ])
         ])
     ])


def register_callbacks(app):

    # --- 1. REGISTRAR VENTA (SERVER-SIDE, USA HORA LOCAL) ---
    @app.callback(
        Output('sale-validation-alert', 'children'),
        Output('store-data-signal', 'data', allow_duplicate=True), 
        Input('submit-sale-button', 'n_clicks'), # <-- Disparador es el botón
        [State('product-dropdown', 'value'), 
         State('quantity-input', 'value'),
         State('store-data-signal', 'data')],
        prevent_initial_call=True
    )
    def register_sale(n_clicks, prod_id, qty, signal_data):
        if not current_user.is_authenticated or not all([prod_id, qty, n_clicks]):
            raise PreventUpdate

        user_id = int(current_user.id) 
        try:
            qty = int(qty)
            if qty <= 0: return dbc.Alert("Error: La cantidad debe ser mayor a cero.", color="danger", dismissable=True), dash.no_update
        except (ValueError, TypeError):
             return dbc.Alert("Error: Cantidad no válida.", color="danger", dismissable=True), dash.no_update

        success = attempt_stock_deduction(prod_id, qty, user_id)

        if not success:
            products_df = load_products(user_id)
            try:
                current_stock = products_df.loc[products_df['product_id'] == prod_id, 'stock'].iloc[0]
                return dbc.Alert(f"Error: Stock insuficiente. Solo quedan {current_stock}.", color="danger", dismissable=True), dash.no_update
            except IndexError:
                 return dbc.Alert(f"Error: Producto no encontrado.", color="danger", dismissable=True), dash.no_update

        try:
            products_df = load_products(user_id) 
            info = products_df.loc[products_df['product_id'] == prod_id].iloc[0]

            # Obtenemos la hora del servidor (que será tu hora local al correr en tu PC)
            sale_time = datetime.now() 

            pd.DataFrame([{
                'product_id': prod_id,
                'quantity': qty,
                'total_amount': info['price'] * qty,
                'cogs_total': info['cost'] * qty,
                'sale_date': sale_time, # <-- Usamos la hora local del servidor
                'user_id': user_id
            }]).to_sql('sales', engine, if_exists='append', index=False)

            new_signal = (signal_data or 0) + 1
            return dbc.Alert("¡Venta registrada!", color="success", dismissable=True, duration=4000), new_signal

        except Exception as e:
            try:
                 products_df = load_products(user_id)
                 info = products_df.loc[products_df['product_id'] == prod_id].iloc[0]
                 update_stock(prod_id, info['stock'] + qty, user_id)
            except: pass
            return dbc.Alert(f"Error al registrar la venta: {e}", color="danger"), dash.no_update


    # --- 2. REFRESCAR TABLA Y DROPDOWNS ---
    @app.callback(
        Output('history-table', 'data'), 
        Output('product-dropdown', 'options'),
        Output('edit-sale-product', 'options'),
        [Input('sales-tabs', 'active_tab'), 
         Input('store-data-signal', 'data')] 
    )
    def refresh_sales_components(active_tab, signal_data):
        if not current_user.is_authenticated: raise PreventUpdate
        
        user_id = int(current_user.id) 
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
            df_show['id'] = df_show['sale_id'] 

        # Dropdowns (Categoria - Producto)
        product_options = []
        if not products_df.empty:
            merged_prods = pd.merge(products_df, categories_df, on='category_id', how='left')
            merged_prods['cat_name'] = merged_prods['name_y'].fillna('Sin Categoría')
            active_prods = merged_prods[merged_prods['is_active'] == True] if 'is_active' in merged_prods.columns else merged_prods
            
            product_options = [
                {
                    'label': f"{row['cat_name']} - {row['name_x']} (Stock: {row['stock']})",
                    'value': row['product_id']
                } for _, row in active_prods.iterrows()
            ]

        return df_show.to_dict('records'), product_options, product_options

    # --- 3. IMPORTAR VENTAS (CON VALIDACIÓN DE CATEGORÍA) ---
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

        user_id = int(current_user.id) 
        content_type, content_string = contents.split(',')
        decoded = base64.b64decode(content_string)

        try:
            if 'xls' in filename: df = pd.read_excel(io.BytesIO(decoded))
            else: return dbc.Alert("Formato incorrecto. Usa .xlsx", color="danger"), dash.no_update
        except Exception as e: return dbc.Alert(f"Error leyendo archivo: {e}", color="danger"), dash.no_update

        df.columns = [c.lower().strip() for c in df.columns]
        required_columns = ['categoria', 'nombre', 'cantidad', 'fecha']
        missing = [col for col in required_columns if col not in df.columns]
        
        if missing:
            return dbc.Alert(f"Faltan columnas: {', '.join(missing)}.", color="danger"), dash.no_update
        
        products_db = load_products(user_id)
        cats_db = load_categories(user_id)
        if products_db.empty: return dbc.Alert("No hay productos registrados.", color="warning"), dash.no_update

        merged_db = pd.merge(products_db, cats_db, on='category_id', how='left')
        merged_db['cat_clean'] = merged_db['name_y'].fillna('').str.strip().str.lower()
        merged_db['prod_clean'] = merged_db['name_x'].str.strip().str.lower()
        
        product_map = {}
        prices_lookup = products_db.set_index('product_id')['price'].to_dict()
        costs_lookup = products_db.set_index('product_id')['cost'].to_dict()
        stock_lookup = products_db.set_index('product_id')['stock'].to_dict()

        for _, row in merged_db.iterrows():
            key = (row['cat_clean'], row['prod_clean'])
            product_map[key] = row['product_id']

        sales_to_insert = []
        stock_updates_needed = {} 
        errors = []

        for index, row in df.iterrows():
            cat_in = str(row['categoria']).strip().lower()
            prod_in = str(row['nombre']).strip().lower()
            key = (cat_in, prod_in)

            if key not in product_map:
                errors.append(f"Fila {index+2}: Producto '{row['nombre']}' en categoría '{row['categoria']}' no existe.")
                continue

            product_id = product_map[key]

            try:
                quantity = int(row['cantidad'])
                if quantity <= 0: raise ValueError
                sale_date_dt = pd.to_datetime(row['fecha']).to_pydatetime()
            except:
                errors.append(f"Fila {index+2}: Cantidad o fecha inválidos.")
                continue

            if update_stock_enabled:
                current_stock = stock_updates_needed.get(product_id, stock_lookup.get(product_id, 0))
                if quantity > current_stock:
                    errors.append(f"Fila {index+2}: Stock insuficiente para '{row['nombre']}'. Stock: {current_stock}, Pedido: {quantity}")
                    continue
                stock_updates_needed[product_id] = current_stock - quantity

            total_amount = prices_lookup.get(product_id, 0) * quantity
            cogs_total = costs_lookup.get(product_id, 0) * quantity

            sales_to_insert.append({
                'product_id': product_id, 'quantity': quantity,
                'total_amount': total_amount, 'cogs_total': cogs_total,
                'sale_date': sale_date_dt, 'user_id': user_id
            })

        if errors:
            return dbc.Alert([html.H5("Errores encontrados:")] + [html.P(e) for e in errors[:10]], color="danger"), dash.no_update

        if sales_to_insert:
            pd.DataFrame(sales_to_insert).to_sql('sales', engine, if_exists='append', index=False)
            
            alert_msg = f"¡Éxito! {len(sales_to_insert)} ventas importadas."
            if update_stock_enabled and stock_updates_needed:
                for pid, new_stk in stock_updates_needed.items():
                    update_stock(pid, new_stk, user_id)
                alert_msg += " Stock actualizado."

            return dbc.Alert(alert_msg, color="success"), (signal_data or 0) + 1

        return dbc.Alert("No hay datos válidos.", color="warning"), dash.no_update

    # --- 4. MODALES (EDITAR/ELIMINAR) ---
    @app.callback(
        Output('sale-edit-modal', 'is_open'), Output('sale-delete-confirm-modal', 'is_open'),
        Output('store-sale-id-to-edit', 'data'), Output('store-sale-id-to-delete', 'data'),
        Output('edit-sale-product', 'value'), Output('edit-sale-quantity', 'value'), Output('edit-sale-date', 'date'),
        Input('history-table', 'active_cell'), State('history-table', 'derived_virtual_data'),
        prevent_initial_call=True
    )
    def open_sale_modals(cell, data):
        if not current_user.is_authenticated or not cell or 'row_id' not in cell:
            raise PreventUpdate
            
        sale_id = cell['row_id']; column_id = cell['column_id']
        user_id = int(current_user.id); sales_df = load_sales(user_id) 
        
        try: sale_info = sales_df[sales_df['sale_id'] == sale_id].iloc[0]
        except IndexError: raise PreventUpdate

        if column_id == "editar":
            product_value = int(sale_info['product_id']) if pd.notna(sale_info['product_id']) else None
            quantity_value = sale_info['quantity']
            date_value = sale_info['sale_date'].date() if pd.notna(sale_info['sale_date']) else None
            return True, False, sale_id, None, product_value, quantity_value, date_value

        elif column_id == "eliminar":
            return False, True, None, sale_id, dash.no_update, dash.no_update, dash.no_update

        raise PreventUpdate

    # --- 5. GUARDAR EDICIÓN (LÓGICA DE STOCK CORREGIDA) ---
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
    def save_edited_sale(n, sale_id, new_prod_id, new_qty, date_str, signal):
        if not n or not sale_id: raise PreventUpdate
        uid = int(current_user.id)

        if not all([new_prod_id, new_qty, date_str]):
            return True, dash.no_update, dbc.Alert("Datos incompletos.", color="danger")
        try:
            new_qty = int(new_qty)
            if new_qty <= 0: raise ValueError("Cantidad debe ser positiva")
            dt = datetime.strptime(date_str, '%Y-%m-%d')
        except (ValueError, TypeError):
            return True, dash.no_update, dbc.Alert("Datos inválidos (Cantidad o Fecha).", color="danger")
        
        try:
            with engine.connect() as conn:
                with conn.begin(): # Inicia Transacción
                    
                    orig_sale = conn.execute(text("SELECT product_id, quantity FROM sales WHERE sale_id=:sid AND user_id=:uid"), 
                                             {"sid": sale_id, "uid": uid}).fetchone()
                    if not orig_sale:
                        raise Exception("Venta original no encontrada.")
                    
                    orig_pid = orig_sale.product_id
                    orig_qty = orig_sale.quantity

                    prods_df = pd.read_sql(text("SELECT product_id, stock, price, cost FROM products WHERE user_id=:uid AND product_id = ANY(:pids) FOR UPDATE"), 
                                           conn, params={"uid": uid, "pids": [int(orig_pid), int(new_prod_id)]})
                    
                    stock_map = prods_df.set_index('product_id')['stock'].to_dict()
                    
                    if int(orig_pid) == int(new_prod_id):
                        diff = new_qty - orig_qty
                        if diff > 0: 
                            if stock_map.get(new_prod_id, 0) < diff:
                                raise Exception(f"Stock insuficiente. Solo quedan {stock_map.get(new_prod_id, 0)}.")
                            conn.execute(text("UPDATE products SET stock = stock - :d WHERE product_id=:pid"), {"d": diff, "pid": new_prod_id})
                        elif diff < 0: 
                            conn.execute(text("UPDATE products SET stock = stock + :d WHERE product_id=:pid"), {"d": abs(diff), "pid": new_prod_id})
                    
                    else:
                        conn.execute(text("UPDATE products SET stock = stock + :q WHERE product_id=:pid"), {"q": orig_qty, "pid": orig_pid})
                        if stock_map.get(new_prod_id, 0) < new_qty:
                            raise Exception(f"Stock insuficiente para el nuevo producto. (Stock original restaurado).")
                        conn.execute(text("UPDATE products SET stock = stock - :q WHERE product_id=:pid"), {"q": new_qty, "pid": new_prod_id})
                    
                    p_info = prods_df.loc[prods_df['product_id'] == new_prod_id].iloc[0]
                    new_data = {
                        "product_id": new_prod_id, "quantity": new_qty,
                        "total_amount": float(p_info['price'] * new_qty),
                        "cogs_total": float(p_info['cost'] * new_qty),
                        "sale_date": dt
                    }
                    conn.execute(text("UPDATE sales SET product_id=:product_id, quantity=:quantity, total_amount=:total_amount, sale_date=:sale_date, cogs_total=:cogs_total WHERE sale_id=:sale_id AND user_id=:user_id"),
                                 {**new_data, "sale_id": int(sale_id), "user_id": uid})
            
            return False, (signal or 0)+1, None 
        
        except Exception as e:
            return True, dash.no_update, dbc.Alert(f"Error: {e}", color="danger")

    # --- 6. CONFIRMAR ELIMINACIÓN (LÓGICA CORREGIDA) ---
    @app.callback(
        Output('sale-delete-confirm-modal', 'is_open', allow_duplicate=True),
        Output('store-data-signal', 'data', allow_duplicate=True),
        Input('confirm-delete-sale-button', 'n_clicks'),
        [State('store-sale-id-to-delete', 'data'), State('store-data-signal', 'data')],
        prevent_initial_call=True
    )
    def confirm_del(n, sid, sig):
        if not n or not sid: raise PreventUpdate
        
        # Usamos delete_sales_bulk porque ya tiene la lógica de restauración de stock
        success, msg = delete_sales_bulk([sid], int(current_user.id)) 
        
        new_sig = (sig or 0) + 1
        if not success:
            # Fallback (sin restauración) si delete_sales_bulk falla
            delete_sale(sid, int(current_user.id))
        
        return False, new_sig

    # --- 7. CERRAR MODALES ---
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

    # --- 8. DESCARGAR EXCEL ---
    @app.callback(
        Output("download-sales-excel", "data"), Input("btn-download-sales-excel", "n_clicks"), prevent_initial_call=True
    )
    def download(n):
        if not n: raise PreventUpdate
        uid = int(current_user.id)
        df = load_sales(uid); prods = load_products(uid); cats = load_categories(uid)
        if not df.empty:
            m = pd.merge(df, prods, on='product_id', how='left')
            m = pd.merge(m, cats, on='category_id', how='left')
            m = m[['sale_date', 'name_y', 'name_x', 'quantity', 'total_amount']]
            m.columns = ['Fecha', 'Categoría', 'Producto', 'Cantidad', 'Total']
            return dcc.send_data_frame(m.to_excel, "ventas.xlsx", index=False)
        return dash.no_update

    # --- 9. BORRADO MASIVO (CON LIMPIEZA) ---
    @app.callback(
        Output('bulk-delete-sales-output', 'children'),
        Output('store-data-signal', 'data', allow_duplicate=True),
        Output('history-table', 'selected_rows'),
        Output('history-table', 'selected_row_ids'),
        Input('delete-selected-sales-btn', 'n_clicks'),
        [State('history-table', 'selected_row_ids'), State('store-data-signal', 'data')],
        prevent_initial_call=True
    )
    def bulk_del(n, ids, sig):
        if not n or not ids: raise PreventUpdate
        success, msg = delete_sales_bulk(ids, int(current_user.id))
        return dbc.Alert(msg, color="success" if success else "danger", dismissable=True), (sig or 0)+1, [], []
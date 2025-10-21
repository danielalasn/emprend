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
            dbc.ModalBody("¿Estás seguro de que quieres eliminar esta venta? Esta acción no se puede deshacer."),
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
        df, info = load_products(user_id), None
        
        try:
            info = df.loc[df['product_id'] == prod_id].iloc[0]
        except IndexError:
            return dbc.Alert("Error: Producto no válido.", color="danger", dismissable=True), dash.no_update
        
        if qty > info['stock']:
            return dbc.Alert(f"Error: Stock insuficiente. Solo quedan {info['stock']}.", color="danger", dismissable=True), dash.no_update
        
        from database import engine
        pd.DataFrame([{
            'product_id': prod_id, 
            'quantity': qty, 
            'total_amount': info['price'] * qty,
            'cogs_total': info['cost'] * qty,
            'sale_date': pd.to_datetime('now').strftime('%Y-%m-%d %H:%M:%S'),
            'user_id': user_id
        }]).to_sql('sales', engine, if_exists='append', index=False)
        
        update_stock(prod_id, info['stock'] - qty, user_id)
        
        new_signal = (signal_data or 0) + 1
        return dbc.Alert("¡Venta registrada!", color="success", dismissable=True, duration=4000), new_signal

    @app.callback(
        Output('history-table-container', 'children'),
        Output('product-dropdown', 'options'),
        [Input('main-tabs', 'active_tab'),
         Input('store-data-signal', 'data')]
    )
    def refresh_sales_components(active_tab, signal_data):
        if not current_user.is_authenticated or active_tab != 'tab-sales':
            raise PreventUpdate
        
        user_id = current_user.id
        sales_df = load_sales(user_id)
        products_df = load_products(user_id)
        categories_df = load_categories(user_id)

        df_show = pd.DataFrame()
        if not sales_df.empty:
            df_show = pd.merge(sales_df, products_df, on='product_id', how='left')
            if not categories_df.empty and not df_show.empty:
                df_show = pd.merge(df_show, categories_df, on='category_id', how='left')
            
            df_show = df_show.rename(columns={'name_x': 'product_name', 'name_y': 'category_name'})
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
        return table, get_product_options(user_id)

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

    @app.callback(
        Output('upload-sales-output', 'children'),
        Output('store-data-signal', 'data', allow_duplicate=True),
        Input('upload-sales-data', 'contents'),
        [State('upload-sales-data', 'filename'),
         State('store-data-signal', 'data')],
        prevent_initial_call=True
    )
    def upload_sales_data(contents, filename, signal_data):
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

        products_db = load_products(user_id)
        products_lookup = products_db.set_index('name')['product_id'].to_dict()
        prices_lookup = products_db.set_index('name')['price'].to_dict()
        costs_lookup = products_db.set_index('name')['cost'].to_dict()

        sales_to_insert = []
        for index, row in df.iterrows():
            product_name = row['Nombre del Producto']
            quantity = row['Cantidad']
            sale_date = row['Fecha de Venta']

            if product_name not in products_lookup:
                errors.append(f"Fila {index + 2}: El producto '{product_name}' no existe en la base de datos.")
                continue
            
            try:
                quantity = int(quantity)
            except (ValueError, TypeError):
                errors.append(f"Fila {index + 2}: La cantidad '{quantity}' no es un número válido.")
                continue

            try:
                sale_date = pd.to_datetime(sale_date)
            except (ValueError, TypeError):
                errors.append(f"Fila {index + 2}: La fecha '{sale_date}' no tiene un formato válido.")
                continue

            product_id = products_lookup[product_name]
            price = prices_lookup[product_name]
            cost = costs_lookup[product_name]
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
            return dbc.Alert([html.H5("Se encontraron errores. Por favor, corrígelos y vuelve a subir el archivo:")] + error_messages, color="danger"), dash.no_update

        if sales_to_insert:
            from database import engine
            sales_df = pd.DataFrame(sales_to_insert)
            sales_df.to_sql('sales', engine, if_exists='append', index=False)
            new_signal = (signal_data or 0) + 1
            return dbc.Alert(f"¡Éxito! Se importaron {len(sales_to_insert)} registros de ventas.", color="success"), new_signal
        
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
            product_value = int(sale_info['product_id'])
            quantity_value = sale_info['quantity']
            date_value = pd.to_datetime(sale_info['sale_date']).date()
            return True, False, sale_id, None, product_value, quantity_value, date_value
        
        elif column_id == "eliminar":
            return False, True, None, sale_id, dash.no_update, dash.no_update, dash.no_update

        return False, False, None, None, dash.no_update, dash.no_update, dash.no_update

    @app.callback(
        Output('sale-edit-modal', 'is_open', allow_duplicate=True),
        Output('store-data-signal', 'data', allow_duplicate=True),
        Input('save-edited-sale-button', 'n_clicks'),
        [State('store-sale-id-to-edit', 'data'),
         State('edit-sale-product', 'value'),
         State('edit-sale-quantity', 'value'),
         State('edit-sale-date', 'date'),
         State('store-data-signal', 'data')],
        prevent_initial_call=True
    )
    def save_edited_sale(n, sale_id, product_id, quantity, sale_date, signal):
        if not n or not sale_id: raise PreventUpdate
        
        user_id = current_user.id
        products_df = load_products(user_id)
        product_info = products_df[products_df['product_id'] == product_id].iloc[0]
        
        formatted_date = pd.to_datetime(sale_date).strftime('%Y-%m-%d %H:%M:%S')

        new_data = {
            "product_id": int(product_id),
            "quantity": int(quantity),
            "total_amount": float(product_info['price'] * quantity),
            "cogs_total": float(product_info['cost'] * quantity),
            "sale_date": formatted_date
        }
        update_sale(sale_id, new_data, user_id)
        return False, (signal or 0) + 1

    @app.callback(
        Output('sale-delete-confirm-modal', 'is_open', allow_duplicate=True),
        Output('store-data-signal', 'data', allow_duplicate=True),
        Input('confirm-delete-sale-button', 'n_clicks'),
        [State('store-sale-id-to-delete', 'data'), State('store-data-signal', 'data')],
        prevent_initial_call=True
    )
    def confirm_delete_sale(n, sale_id, signal):
        if not n or not sale_id: raise PreventUpdate
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
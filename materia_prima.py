# materia_prima.py
from dash import dcc, html, dash_table
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
from dash.dash_table.Format import Format, Scheme, Symbol
import pandas as pd
from flask_login import current_user
import dash
from datetime import date, datetime

# --- Importar funciones reales de database ---
from database import (
    load_raw_materials, add_raw_material, get_raw_material_options,
    add_material_purchase, update_raw_material, delete_raw_material,
    delete_materials_bulk
)

# --- Layout ---
def get_layout():
    """Returns the layout for the Raw Materials section."""
    today_date = date.today()

    unit_options = [
        {'label': 'Unidad(es)', 'value': 'unidad'}, {'label': 'Metro(s)', 'value': 'metro'},
        {'label': 'Centímetro(s)', 'value': 'cm'}, {'label': 'Litro(s)', 'value': 'litro'},
        {'label': 'Mililitro(s)', 'value': 'ml'}, {'label': 'Kilogramo(s)', 'value': 'kg'},
        {'label': 'Gramo(s)', 'value': 'g'}, {'label': 'Par(es)', 'value': 'par'},
    ]

    return html.Div([
        dcc.Store(id='store-material-id-to-edit'),
        dcc.Store(id='store-material-id-to-delete'),

        # --- Modal Editar Insumo (CORREGIDO) ---
        dbc.Modal([
            dbc.ModalHeader("Editar Insumo"),
            dbc.ModalBody(dbc.Form([
                html.Div(id='edit-material-alert'),
                dbc.Label("Nombre del Insumo:", html_for="edit-material-name-input"),
                dbc.Input(id="edit-material-name-input", type="text", className="mb-2"),
                dbc.Label("Unidad de Medida:", html_for="edit-material-unit-dropdown"),
                dcc.Dropdown(id="edit-material-unit-dropdown", options=unit_options, className="mb-2"),

                html.Hr(),
                dbc.Label("Ajuste Manual (¡Cuidado!):", className="fw-bold text-danger"),
                dbc.Row([
                    dbc.Col([
                        dbc.Label("Stock Actual Manual:", html_for="edit-material-stock-input"),
                        # CORREGIDO: step="any" para permitir decimales infinitos
                        dbc.Input(id="edit-material-stock-input", type="number", min=0, step="any", placeholder=0)
                    ]),
                    dbc.Col([
                        dbc.Label("Costo Promedio Manual:", html_for="edit-material-cost-input"),
                        # CORREGIDO: step="any" para aceptar 0.006
                        dbc.Input(id="edit-material-cost-input", type="number", min=0, step="any", placeholder=0)
                    ])
                ], className="mb-2"),
                html.Hr(),

                dbc.Label("Alertar si Stock baja de:", html_for="edit-material-alert-input"),
                dbc.Input(id="edit-material-alert-input", type="number", min=0, step="any", className="mt-2", placeholder=0),
                dbc.Alert("Nota: Ajustar el stock o costo manualmente anula el promedio ponderado. Úsalo solo para corregir errores.", color="warning", className="mt-3 fs-sm")
            ])),
            dbc.ModalFooter([
                dbc.Button("Cancelar", id="cancel-edit-material-button", color="secondary"),
                dbc.Button("Guardar Cambios", id="save-edited-material-button", color="primary"),
            ]),
        ], id="material-edit-modal", is_open=False),

        # Modal Confirmar Eliminación
        dbc.Modal([
            dbc.ModalHeader("Confirmar Eliminación"),
            dbc.ModalBody("¿Estás seguro de que quieres eliminar este insumo?"),
            dbc.ModalFooter([
                dbc.Button("Cancelar", id="cancel-delete-material-button", color="secondary"),
                dbc.Button("Eliminar", id="confirm-delete-material-button", color="danger"),
            ]),
        ], id="material-delete-confirm-modal", is_open=False),

        # Tabs Principales
        dbc.Tabs(id="material-sub-tabs", active_tab="sub-tab-material-inventory", children=[
            # --- Tab: Ver Inventario ---
            dbc.Tab(label="Inventario de Insumos", tab_id="sub-tab-material-inventory", children=[
                html.Div(className="p-4", children=[
                    html.H3("Inventario Actual de Materia Prima"),
                    dbc.Button("Borrar Seleccionados", id="delete-selected-materials-btn", color="danger", n_clicks=0, className="mb-2"),
                    html.Div(id='bulk-delete-materials-output'),

                    dash_table.DataTable(
                        id='material-inventory-table',
                        columns=[
                            {"name": "ID", "id": "material_id"}, 
                            {"name": "Nombre Insumo", "id": "name"},
                            {"name": "Unidad", "id": "unit_measure"},
                            # Stock con 4 decimales
                            {"name": "Stock Actual", "id": "current_stock", 'type': 'numeric', 'format': Format(precision=2, scheme=Scheme.fixed)},
                            # CORREGIDO: Costo Promedio con 4 decimales como pediste (acepta 0.0060)
                            {"name": "Costo Promedio", "id": "average_cost", 'type': 'numeric', 'format': Format(precision=4, scheme=Scheme.fixed, symbol=Symbol.yes)},
                            {"name": "Valor Inventario", "id": "valor_inventario", 'type': 'numeric', 'format': Format(precision=2, scheme=Scheme.fixed, symbol=Symbol.yes)},
                            {"name": "Umbral Alerta", "id": "alert_threshold", 'type': 'numeric', 'format': Format(precision=2, scheme=Scheme.fixed)},
                            {"name": "Editar", "id": "editar"}, 
                            {"name": "Eliminar", "id": "eliminar"},
                        ],
                        data=[], 
                        page_size=15, 
                        sort_action='native', 
                        filter_action='native',
                        row_selectable='multi',
                        selected_rows=[],
                        selected_row_ids=[],
                        style_table={'overflowX': 'auto'},
                        style_cell={'textAlign': 'left'},
                        style_data_conditional=[
                            {'if': { 'filter_query': '{current_stock} <= {alert_threshold} && {alert_threshold} > 0', 'column_id': 'current_stock'}, 'backgroundColor': '#FFCCCB', 'color': 'black'}
                        ],
                        style_cell_conditional=[
                            {'if': {'column_id': 'editar'}, 'cursor': 'pointer', 'textAlign': 'center'},
                            {'if': {'column_id': 'eliminar'}, 'cursor': 'pointer', 'textAlign': 'center'}
                        ]
                    )
                ])
            ]), 

            # --- Tab: Añadir Insumo ---
            dbc.Tab(label="Añadir Insumo", tab_id="sub-tab-add-material", children=[
                dbc.Card(className="m-4", children=[
                    dbc.CardBody([
                        html.H3("Definir Nuevo Insumo"),
                        html.Div(id="add-material-alert"),
                        dbc.Row([
                            dbc.Col(html.Div([
                                dbc.Label("Nombre del Insumo:", html_for="material-name-input"),
                                dbc.Input(id="material-name-input", type="text", placeholder="Ej: Ajo en Polvo")
                            ]), width=6),
                            dbc.Col(html.Div([
                                dbc.Label("Unidad de Medida:", html_for="material-unit-dropdown"),
                                dcc.Dropdown(id="material-unit-dropdown", options=unit_options, placeholder="Selecciona unidad...")
                            ]), width=6),
                        ], className="mb-3"),
                         dbc.Row([
                             dbc.Col(html.Div([
                                 dbc.Label("Stock Actual (Si ya tienes):", html_for="material-stock-input"),
                                 dbc.Input(id="material-stock-input", type="number", min=0, step="any", placeholder=0)
                             ]), width=4),
                             dbc.Col(html.Div([
                                 dbc.Label("Costo Total (De ese stock inicial):", html_for="material-cost-input"),
                                 dbc.Input(id="material-cost-input", type="number", min=0, step="any", placeholder=0)
                             ]), width=4),
                             dbc.Col(html.Div([
                                dbc.Label("Alertar si Stock baja de:", html_for="material-alert-input"),
                                dbc.Input(id="material-alert-input", type="number", min=0, step="any", placeholder=0)
                             ]), width=4),
                         ], className="mb-3"),
                        dbc.Button("Guardar Nuevo Insumo", id="save-material-button", color="success", n_clicks=0, className="mt-3")
                    ])
                ])
            ]), 

            # --- Tab: Registrar Compra ---
            dbc.Tab(label="Registrar Compra", tab_id="sub-tab-add-purchase", children=[
                 dbc.Card(className="m-4", children=[
                     dbc.CardBody([
                         html.H3("Registrar Compra de Insumos"),
                         html.Div(id="add-purchase-alert"),
                         dbc.Row([
                             dbc.Col(html.Div([
                                 dbc.Label("Selecciona el Insumo:", html_for="purchase-material-dropdown"),
                                 dcc.Dropdown(id='purchase-material-dropdown', placeholder="Selecciona insumo...", options=[])
                             ]), width=12)
                         ], className="mb-3"),
                         dbc.Row([
                             dbc.Col(html.Div([
                                 dbc.Label("Cantidad Comprada:", html_for="purchase-quantity-input"),
                                 dbc.Input(id="purchase-quantity-input", type="number", min=0.000001, step="any", placeholder=0)
                             ]), width=6),
                              dbc.Col(html.Div([
                                 dbc.Label("Costo Total de la Compra:", html_for="purchase-cost-input"),
                                 dbc.Input(id="purchase-cost-input", type="number", min=0, step="any", placeholder=0)
                             ]), width=6),
                         ], className="mb-3"),
                         dbc.Row([
                              dbc.Col(html.Div([
                                 dbc.Label("Fecha de Compra:", html_for="purchase-date-picker"),
                                 dcc.DatePickerSingle(
                                     id='purchase-date-picker',
                                     date=today_date,
                                     display_format='YYYY-MM-DD',
                                     className="w-100"
                                 )
                             ]), width=6),
                              dbc.Col(html.Div([
                                 dbc.Label("Proveedor (Opcional):", html_for="purchase-supplier-input"),
                                 dbc.Input(id="purchase-supplier-input", type="text")
                             ]), width=6),
                         ], className="mb-3"),
                         dbc.Row([
                             dbc.Col(html.Div([
                                 dbc.Label("Notas (Opcional):", html_for="purchase-notes-input"),
                                 dbc.Textarea(id="purchase-notes-input", rows=2)
                             ]), width=12)
                         ], className="mb-3"),
                         dbc.Button("Guardar Compra", id="save-purchase-button", color="info", n_clicks=0, className="mt-3")
                     ])
                 ])
            ]), 
        ]) 
    ]) 

# --- Callbacks ---
def register_callbacks(app):

    @app.callback(
        Output('add-material-alert', 'children'),
        Output('store-data-signal', 'data', allow_duplicate=True),
        Output('material-name-input', 'value'),
        Output('material-unit-dropdown', 'value'),
        Output('material-stock-input', 'value'),
        Output('material-cost-input', 'value'),
        Output('material-alert-input', 'value'),
        Input('save-material-button', 'n_clicks'),
        [State('material-name-input', 'value'),
         State('material-unit-dropdown', 'value'),
         State('material-stock-input', 'value'),
         State('material-cost-input', 'value'),
         State('material-alert-input', 'value'),
         State('store-data-signal', 'data')],
        prevent_initial_call=True
    )
    def handle_add_material(n_clicks, name, unit, stock, cost, alert, signal_data):
        if n_clicks is None or n_clicks < 1: raise PreventUpdate
        if not current_user.is_authenticated: raise PreventUpdate

        user_id = int(current_user.id)
        if not name or not unit:
            return dbc.Alert("Nombre y Unidad de Medida son obligatorios.", color="warning"), dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update

        try:
            stock_f = float(stock) if stock is not None else 0
            total_cost_f = float(cost) if cost is not None else 0 
            alert_f = float(alert) if alert is not None else 0
            
            # Calcular promedio
            avg_cost_f = (total_cost_f / stock_f) if stock_f > 0 else 0
            
            if stock_f < 0 or total_cost_f < 0 or alert_f < 0:
                raise ValueError("Valores numéricos no pueden ser negativos.")
        except (ValueError, TypeError):
             return dbc.Alert("Valores numéricos inválidos.", color="danger"), dash.no_update, name, unit, stock, cost, alert

        material_data = {
            'name': name.strip(),
            'unit_measure': unit,
            'current_stock': stock_f,
            'average_cost': avg_cost_f,
            'alert_threshold': alert_f,
            'is_active': True
        }
        
        success, message = add_raw_material(material_data, user_id)

        if success:
            new_signal = (signal_data or 0) + 1
            return dbc.Alert(message, color="success", dismissable=True, duration=4000), new_signal, "", None, 0, 0, 0
        else:
            return dbc.Alert(message, color="danger"), dash.no_update, name, unit, stock, cost, alert

    @app.callback(
        Output('material-inventory-table', 'data'), 
        [Input('material-sub-tabs', 'active_tab'),
         Input('store-data-signal', 'data')]
    )
    def update_material_inventory_table(active_sub_tab, signal_data):
        if not current_user.is_authenticated: raise PreventUpdate
        if active_sub_tab != 'sub-tab-material-inventory' and dash.callback_context.triggered_id != 'store-data-signal':
             raise PreventUpdate

        user_id = int(current_user.id)
        materials_df = load_raw_materials(user_id, include_inactive=False)

        if not materials_df.empty:
             numeric_cols = ['current_stock', 'average_cost', 'alert_threshold']
             for col in numeric_cols:
                  materials_df[col] = pd.to_numeric(materials_df[col], errors='coerce').fillna(0)
             materials_df['valor_inventario'] = materials_df['current_stock'] * materials_df['average_cost']
             materials_df['editar'] = "✏️"
             materials_df['eliminar'] = "🗑️"
             materials_df['id'] = materials_df['material_id'] 
        else:
             materials_df = pd.DataFrame(columns=['material_id', 'name', 'unit_measure', 'current_stock', 'average_cost', 'alert_threshold', 'valor_inventario', 'editar', 'eliminar', 'id'])

        return materials_df.to_dict('records')

    @app.callback(
        Output('purchase-material-dropdown', 'options'),
        [Input('material-sub-tabs', 'active_tab'),
         Input('store-data-signal', 'data')]
    )
    def update_purchase_dropdown(active_sub_tab, signal_data):
        if not current_user.is_authenticated: raise PreventUpdate
        if active_sub_tab != 'sub-tab-add-purchase' and dash.callback_context.triggered_id != 'store-data-signal':
             raise PreventUpdate

        user_id = int(current_user.id)
        try:
            return get_raw_material_options(user_id)
        except:
            return []

    @app.callback(
        Output('add-purchase-alert', 'children', allow_duplicate=True),
        Output('store-data-signal', 'data', allow_duplicate=True),
        Output('purchase-material-dropdown', 'value', allow_duplicate=True), 
        Output('purchase-quantity-input', 'value', allow_duplicate=True),
        Output('purchase-cost-input', 'value', allow_duplicate=True), 
        Output('purchase-supplier-input', 'value', allow_duplicate=True),
        Output('purchase-notes-input', 'value', allow_duplicate=True),
        Input('save-purchase-button', 'n_clicks'),
        [State('purchase-material-dropdown', 'value'), State('purchase-quantity-input', 'value'),
         State('purchase-cost-input', 'value'), State('purchase-date-picker', 'date'),
         State('purchase-supplier-input', 'value'), State('purchase-notes-input', 'value'),
         State('store-data-signal', 'data')],
        prevent_initial_call=True
    )
    def handle_add_purchase(n_clicks, material_id, quantity, cost, date_str, supplier, notes, signal_data):
        if n_clicks is None or n_clicks < 1: raise PreventUpdate
        if not current_user.is_authenticated: raise PreventUpdate

        user_id = int(current_user.id)

        if material_id is None or quantity is None or cost is None or date_str is None:
             return dbc.Alert("Insumo, Cantidad, Costo Total y Fecha son obligatorios.", color="warning"), dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update

        try:
            quantity_float = float(quantity)
            cost_total_float = float(cost) 
            purchase_datetime = datetime.strptime(date_str, '%Y-%m-%d')
            
            if quantity_float <= 0 or cost_total_float < 0:
                 raise ValueError
        except:
              return dbc.Alert("Datos inválidos.", color="danger"), dash.no_update, material_id, quantity, cost, supplier, notes

        purchase_data = {
            "material_id": material_id, "quantity_purchased": quantity_float,
            "total_cost": cost_total_float, 
            "purchase_date": purchase_datetime,
            "supplier": supplier.strip() if supplier else None,
            "notes": notes.strip() if notes else None
        }

        success, message = add_material_purchase(purchase_data, user_id)

        if success:
            new_signal = (signal_data or 0) + 1
            return dbc.Alert(message, color="success", dismissable=True, duration=4000), new_signal, None, 0, 0, None, None
        else:
             return dbc.Alert(message, color="danger"), dash.no_update, material_id, quantity, cost, supplier, notes

    @app.callback(
        Output('material-edit-modal', 'is_open'), Output('material-delete-confirm-modal', 'is_open'),
        Output('store-material-id-to-edit', 'data'), Output('store-material-id-to-delete', 'data'),
        Output('edit-material-name-input', 'value'), Output('edit-material-unit-dropdown', 'value'),
        Output('edit-material-alert-input', 'value'), Output('edit-material-alert', 'children'),
        Output('edit-material-stock-input', 'value'), Output('edit-material-cost-input', 'value'),
        Input('material-inventory-table', 'active_cell'),
        State('material-inventory-table', 'derived_virtual_data'),
        prevent_initial_call=True
    )
    def open_material_modals(active_cell, data):
        if not active_cell or 'row' not in active_cell: raise PreventUpdate
        if not current_user.is_authenticated: raise PreventUpdate

        row_idx = active_cell['row']; col_id = active_cell['column_id']
        if not data or row_idx >= len(data): raise PreventUpdate

        material_id = data[row_idx]['id']
        material_info = data[row_idx]

        open_edit, open_delete = False, False
        edit_id, delete_id = None, None
        edit_name, edit_unit, edit_alert = dash.no_update, dash.no_update, dash.no_update
        edit_stock, edit_cost = dash.no_update, dash.no_update
        edit_alert_msg = None

        if col_id == 'editar':
            open_edit, edit_id = True, material_id
            edit_name = material_info.get('name')
            edit_unit = material_info.get('unit_measure')
            edit_alert = material_info.get('alert_threshold')
            edit_stock = material_info.get('current_stock') 
            edit_cost = material_info.get('average_cost') 
        elif col_id == 'eliminar':
            open_delete, delete_id = True, material_id

        return open_edit, open_delete, edit_id, delete_id, edit_name, edit_unit, edit_alert, edit_alert_msg, edit_stock, edit_cost

    @app.callback(
        Output('material-edit-modal', 'is_open', allow_duplicate=True),
        Output('store-data-signal', 'data', allow_duplicate=True),
        Output('edit-material-alert', 'children', allow_duplicate=True),
        Input('save-edited-material-button', 'n_clicks'),
        [State('store-material-id-to-edit', 'data'), 
         State('edit-material-name-input', 'value'),  
         State('edit-material-unit-dropdown', 'value'),
         State('edit-material-alert-input', 'value'),  
         State('edit-material-stock-input', 'value'),  
         State('edit-material-cost-input', 'value'),   
         State('store-data-signal', 'data')],           
        prevent_initial_call=True
    )
    def save_edited_material(n_clicks, material_id, name, unit, alert, stock, cost, signal_data):
        if n_clicks is None or not material_id: raise PreventUpdate
        if not current_user.is_authenticated: raise PreventUpdate

        user_id = int(current_user.id)
        if not name or not unit:
             return True, dash.no_update, dbc.Alert("Nombre obligatorio.", color="danger")

        try:
             alert_f = float(alert) if alert is not None else 0
             stock_f = float(stock) if stock is not None else 0
             cost_f = float(cost) if cost is not None else 0
             if alert_f < 0 or stock_f < 0 or cost_f < 0: raise ValueError
        except:
             return True, dash.no_update, dbc.Alert("Valores inválidos.", color="danger")

        update_data = {
            "name": name.strip(), 
            "unit_measure": unit, 
            "alert_threshold": alert_f,
            "current_stock": stock_f,
            "average_cost": cost_f
        }

        try:
            update_raw_material(material_id, update_data, user_id)
            new_signal = (signal_data or 0) + 1
            return False, new_signal, None
        except ValueError as ve:
            return True, dash.no_update, dbc.Alert(str(ve), color="danger")
        except Exception as e:
            print(f"Error: {e}")
            return True, dash.no_update, dbc.Alert("Error al guardar.", color="danger")

    @app.callback(
        Output('material-delete-confirm-modal', 'is_open', allow_duplicate=True),
        Output('store-data-signal', 'data', allow_duplicate=True),
        Input('confirm-delete-material-button', 'n_clicks'),
        [State('store-material-id-to-delete', 'data'), State('store-data-signal', 'data')],
        prevent_initial_call=True
    )
    def confirm_delete_material(n_clicks, material_id, signal_data):
        if n_clicks is None or not material_id: raise PreventUpdate
        if not current_user.is_authenticated: raise PreventUpdate

        try:
            delete_raw_material(material_id, current_user.id) 
            new_signal = (signal_data or 0) + 1
            return False, new_signal
        except:
            return False, dash.no_update

    @app.callback(
        Output('material-edit-modal', 'is_open', allow_duplicate=True),
        Output('material-delete-confirm-modal', 'is_open', allow_duplicate=True),
        [Input('cancel-edit-material-button', 'n_clicks'),
         Input('cancel-delete-material-button', 'n_clicks')],
        prevent_initial_call=True
    )
    def close_material_modals(n_edit, n_delete):
        triggered_id = dash.callback_context.triggered_id
        if triggered_id in ['cancel-edit-material-button', 'cancel-delete-material-button']:
            return False, False
        raise PreventUpdate

    # Borrado Masivo
    @app.callback(
        Output('bulk-delete-materials-output', 'children'),
        Output('store-data-signal', 'data', allow_duplicate=True),
        Input('delete-selected-materials-btn', 'n_clicks'),
        [State('material-inventory-table', 'selected_row_ids'),
         State('store-data-signal', 'data')],
        prevent_initial_call=True
    )
    def delete_selected_materials(n_clicks, selected_ids, signal_data):
        if n_clicks is None or n_clicks < 1 or not selected_ids: raise PreventUpdate
        if not current_user.is_authenticated: raise PreventUpdate
        
        user_id = int(current_user.id)
        try:
            success, message = delete_materials_bulk(selected_ids, user_id)
            if success:
                new_signal = (signal_data or 0) + 1
                return dbc.Alert(message, color="success", dismissable=True, duration=4000), new_signal
            else:
                return dbc.Alert(message, color="danger", dismissable=True), dash.no_update
        except Exception as e:
            print(f"Error: {e}")
            return dbc.Alert("Error al borrar.", color="danger", dismissable=True), dash.no_update
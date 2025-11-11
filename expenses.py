# expenses.py
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

from app import app
from database import (
    load_expenses, load_expense_categories, get_expense_category_options,
    update_expense, delete_expense, delete_expense_category,
    reactivate_expense_category, update_expense_category,
    delete_expenses_bulk # <-- Importación añadida
)

def get_layout():
    return html.Div([
        dcc.Store(id='store-expense-id-to-edit'),
        dcc.Store(id='store-expense-id-to-delete'),
        dcc.Store(id='store-expense-category-id-to-delete'),
        dcc.Store(id='store-expense-category-id-to-edit'),

        dbc.Modal([ # Edit Expense Modal
            dbc.ModalHeader("Editar Gasto"),
            dbc.ModalBody(dbc.Form([
                dbc.Row([
                    dbc.Col([dbc.Label("Tipo de Gasto"), dcc.Dropdown(id='edit-expense-category', options=[])]),
                    dbc.Col([dbc.Label("Monto"), dbc.Input(id='edit-expense-amount', type='number')]),
                ]),
                dbc.Label("Fecha del Gasto", className="mt-2"),
                dcc.DatePickerSingle(id='edit-expense-date')
            ])),
            dbc.ModalFooter([
                dbc.Button("Cancelar", id="cancel-edit-expense-button", color="secondary", className="ms-auto"),
                dbc.Button("Guardar Cambios", id="save-edited-expense-button", color="primary"),
            ]),
        ], id="expense-edit-modal", is_open=False),

        dbc.Modal([ # Edit Expense Category Modal
            dbc.ModalHeader("Editar Tipo de Gasto"),
            dbc.ModalBody(dbc.Form([
                dbc.Label("Nombre del Tipo de Gasto"),
                dbc.Input(id='edit-expense-category-name', type='text')
            ])),
            dbc.ModalFooter([
                dbc.Button("Cancelar", id="cancel-edit-expense_category-button", color="secondary", className="ms-auto"),
                dbc.Button("Guardar Cambios", id="save-edited-expense_category-button", color="primary"),
            ]),
        ], id="expense_category-edit-modal", is_open=False),

        dbc.Modal([ # Delete Expense Modal
            dbc.ModalHeader("Confirmar Eliminación"),
            dbc.ModalBody("¿Estás seguro de que quieres eliminar este gasto?"),
            dbc.ModalFooter([
                dbc.Button("Cancelar", id="cancel-delete-expense-button", color="secondary", className="ms-auto"),
                dbc.Button("Eliminar", id="confirm-delete-expense-button", color="danger"),
            ]),
        ], id="expense-delete-confirm-modal", is_open=False),

        dbc.Modal([ # Delete Expense Category Modal
            dbc.ModalHeader("Confirmar Eliminación de Categoría"),
            dbc.ModalBody("¿Estás seguro de que quieres eliminar este tipo de gasto? Se ocultará de las listas y se desasignará de todos los gastos asociados."),
            dbc.ModalFooter([
                dbc.Button("Cancelar", id="cancel-delete-expense_category-button", color="secondary", className="ms-auto"),
                dbc.Button("Eliminar", id="confirm-delete-expense_category-button", color="danger"),
            ]),
        ], id="expense_category-delete-confirm-modal", is_open=False),

        dbc.Tabs(id="expense-sub-tabs", active_tab="sub-tab-add-expense", children=[
            dbc.Tab(label="Añadir Gasto", tab_id="sub-tab-add-expense", children=[
                dbc.Card(className="m-4", children=[
                    dbc.CardBody([
                        html.H3("Registrar un Gasto Operativo"),
                        html.Div(id="add-expense-alert"),
                        dbc.Row([
                            dbc.Col([html.Label("Tipo de Gasto"), dcc.Dropdown(id='expense-category-dropdown', placeholder="Selecciona un tipo de gasto...")], width=6),
                            dbc.Col([html.Label("Monto"), dbc.Input(id='expense-amount-input', type='number', min=0, placeholder="0.00")], width=6),
                        ], className="mb-3"),
                        dbc.Button("Guardar Gasto", id="save-expense-button", color="danger", className="mt-3")
                    ])
                ]),

                dbc.Accordion([
                    dbc.AccordionItem(
                        children=[
                            dcc.Upload(
                                id='upload-expenses-data',
                                children=html.Div(['Arrastra y suelta o ', html.A('Selecciona un Archivo')]),
                                style={
                                    'width': '100%', 'height': '60px', 'lineHeight': '60px',
                                    'borderWidth': '1px', 'borderStyle': 'dashed',
                                    'borderRadius': '5px', 'textAlign': 'center', 'margin': '10px 0'
                                },
                                multiple=False
                            ),
                            
                            dbc.Alert([
                                html.H5("Formato Requerido:", className="alert-heading"),
                                html.P("El archivo Excel debe tener las siguientes columnas (exactamente como se escriben):"),
                                html.Ul([
                                    html.Li([html.B("nombre"), " (El 'Tipo de Gasto' ya debe existir en tu lista de categorías)"]),
                                    html.Li([html.B("monto"), " (El valor numérico del gasto)"]),
                                    html.Li([html.B("fecha"), " (Formato AAAA-MM-DD o similar)"]),
                                ]),
                            ], color="info", className="mt-2"),
                            
                            html.Div(id='upload-expenses-output')
                        ],
                        title="Importar Historial de Gastos desde Excel"
                    )
                ], start_collapsed=True, className="m-4"),

                dbc.Accordion([
                    dbc.AccordionItem(
                        children=[ # <-- Contenido envuelto en lista
                            dbc.Button("Descargar Excel", id="btn-download-expenses-excel", color="success", className="mb-3 me-2"),
                            
                            # --- INICIO DE MODIFICACIÓN: BORRADO MASIVO ---
                            dbc.Button("Borrar Seleccionados", id="delete-selected-expenses-btn", color="danger", n_clicks=0, className="mb-3"),
                            html.Div(id='bulk-delete-expenses-output'), # Para mostrar alertas

                            # La DataTable ahora se define aquí
                            dash_table.DataTable(
                                id='expenses-table', # <-- ID movido aquí
                                columns=[
                                    {"name": "ID Gasto", "id": "expense_id"},
                                    {"name": "Fecha", "id": "expense_date_display"},
                                    {"name": "Gasto", "id": "gasto"},
                                    {"name": "Monto", "id": "amount", 'type': 'numeric', 'format': Format(precision=2, scheme=Scheme.fixed)},
                                    {"name": "Editar", "id": "editar"},
                                    {"name": "Eliminar", "id": "eliminar"}
                                ],
                                data=[], # Se inicializa vacía
                                page_size=10,
                                sort_action='native',
                                sort_by=[{'column_id': 'expense_date_display', 'direction': 'desc'}],
                                # Propiedades de selección
                                row_selectable='multi',
                                selected_rows=[],
                                selected_row_ids=[],
                                # Estilos
                                style_cell_conditional=[
                                    {'if': {'column_id': 'editar'}, 'cursor': 'pointer'},
                                    {'if': {'column_id': 'eliminar'}, 'cursor': 'pointer'}
                                ]
                            )
                            # --- FIN DE MODIFICACIÓN ---
                        ],
                        title="Ver Historial de Gastos"
                    )
                ], start_collapsed=True, className="m-4")
            ]),
            dbc.Tab(label="Gestionar Gastos", tab_id="sub-tab-manage-expenses", children=[
                dbc.Row([
                    dbc.Col([
                        dbc.Card(className="m-4", children=[
                            dbc.CardBody([
                                html.H3("Crear Nuevo Tipo de Gasto"),
                                html.Div(id="add-expense-category-alert"),
                                dbc.Input(id="expense-category-name-input", placeholder="Nombre del nuevo gasto", className="mb-2"),
                                dbc.Button("Guardar Gasto", id="save-expense-category-button", color="primary")
                            ])
                        ])
                    ], width=4),
                    dbc.Col([
                        html.Div(className="p-4", children=[
                            html.H3("Tipos de Gastos Existentes"),
                            html.Div(id='expense-categories-table-container')
                        ])
                    ], width=8)
                ])
            ])
        ])
    ])

def register_callbacks(app):
    @app.callback(
        Output('add-expense-alert', 'children'),
        Output('store-data-signal', 'data', allow_duplicate=True),
        Input('save-expense-button', 'n_clicks'),
        [State('expense-category-dropdown', 'value'),
         State('expense-amount-input', 'value'),
         State('store-data-signal', 'data')],
        prevent_initial_call=True
    )
    def add_expense(n, cat_id, amount, signal_data):
        if n is None or n < 1:
            raise PreventUpdate
        if not current_user.is_authenticated: raise PreventUpdate

        user_id = int(current_user.id)
        
        if not cat_id or amount is None:
            return dbc.Alert("Los campos Tipo de Gasto y Monto son obligatorios.", color="danger"), dash.no_update
        try:
            amount_f = float(amount) if amount is not None else 0.0
            if amount_f <= 0:
                 return dbc.Alert("El monto debe ser positivo.", color="danger"), dash.no_update
        except (ValueError, TypeError):
             return dbc.Alert("Monto no válido.", color="danger"), dash.no_update

        from database import engine
        current_time = datetime.now() 

        pd.DataFrame([{
            'expense_date': current_time, 
            'expense_category_id': cat_id,
            'amount': amount_f, 
            'user_id': user_id
        }]).to_sql('expenses', engine, if_exists='append', index=False)

        expense_cat_name = "Gasto"
        if cat_id:
            cats_df = pd.DataFrame(get_expense_category_options(user_id))
            if not cats_df.empty:
                match = cats_df[cats_df['value'] == cat_id]
                if not match.empty:
                    expense_cat_name = match['label'].iloc[0]

        new_signal = (signal_data or 0) + 1
        return dbc.Alert(f"Gasto de '{expense_cat_name}' por ${amount_f:,.2f} guardado.", color="success", dismissable=True, duration=4000), new_signal

    # Callback añadir categoría (con reactivación)
    @app.callback(
        Output('add-expense-category-alert', 'children'),
        Output('store-data-signal', 'data', allow_duplicate=True),
        Input('save-expense-category-button', 'n_clicks'),
        [State('expense-category-name-input', 'value'),
         State('store-data-signal', 'data')],
        prevent_initial_call=True
    )
    def add_expense_category(n_clicks, name, signal_data):
        if n_clicks is None: raise PreventUpdate
        if not current_user.is_authenticated: raise PreventUpdate

        user_id = int(current_user.id)
        if not name:
            return dbc.Alert("El nombre no puede estar vacío.", color="warning"), dash.no_update

        from database import engine

        existing_cats = load_expense_categories(user_id) 

        if not existing_cats.empty and 'is_active' in existing_cats.columns:
            match = existing_cats[existing_cats['name'].str.lower() == name.lower()]
            if not match.empty:
                category_data = match.iloc[0]
                if category_data['is_active']:
                    return dbc.Alert(f"El tipo de gasto '{name}' ya existe.", color="danger"), dash.no_update
                else:
                    reactivate_expense_category(category_data['expense_category_id'], user_id)
                    new_signal = (signal_data or 0) + 1
                    return dbc.Alert(f"Tipo de gasto '{category_data['name']}' reactivado.", color="success"), new_signal

        pd.DataFrame([{'name': name.title(), 'user_id': user_id, 'is_active': True}]).to_sql('expense_categories', engine, if_exists='append', index=False)
        new_signal = (signal_data or 0) + 1
        return dbc.Alert(f"Tipo de gasto '{name.title()}' guardado.", color="success"), new_signal

    # Callback refrescar tablas
    @app.callback(
        Output('expenses-table', 'data'), # <-- MODIFICADO
        Output('expense-categories-table-container', 'children'),
        Output('expense-category-dropdown', 'options'),
        [Input('main-tabs', 'active_tab'),
         Input('expense-sub-tabs', 'active_tab'),
         Input('store-data-signal', 'data')]
    )
    def refresh_expenses_components(main_tab, sub_tab, signal_data):
        if not current_user.is_authenticated:
            raise PreventUpdate
        if main_tab != 'tab-expenses':
            raise PreventUpdate
        triggered_id = dash.callback_context.triggered_id
        if triggered_id != 'store-data-signal' and main_tab != 'tab-expenses':
             raise PreventUpdate

        user_id = int(current_user.id)
        expenses_df = load_expenses(user_id)
        exp_cat_df = load_expense_categories(user_id)

        # Generar datos para la tabla de gastos
        display_df = pd.DataFrame()
        if not expenses_df.empty:
            if not exp_cat_df.empty:
                display_df = pd.merge(expenses_df, exp_cat_df, on='expense_category_id', how='left').rename(columns={'name': 'gasto'})
            else:
                display_df = expenses_df

            display_df['gasto'] = display_df['gasto'].fillna('Categoría Eliminada')
            display_df['expense_date_display'] = display_df['expense_date'].dt.strftime('%Y-%m-%d %H:%M')
            display_df['editar'] = "✏️"
            display_df['eliminar'] = "🗑️"
            display_df['id'] = display_df['expense_id'] # <-- AÑADIDO PARA BORRADO MASIVO

        # Generar tabla de categorías (solo activas)
        exp_cat_active_df = pd.DataFrame()
        if not exp_cat_df.empty and 'is_active' in exp_cat_df.columns:
            exp_cat_active_df = exp_cat_df[exp_cat_df['is_active'] == True].copy()
        elif not exp_cat_df.empty: 
             exp_cat_active_df = exp_cat_df.copy()

        exp_cat_active_df['editar'] = "✏️"
        exp_cat_active_df['eliminar'] = "🗑️"

        expense_categories_table = dash_table.DataTable(
            id='expense-categories-table',
            columns=[
                {"name": "ID", "id": "expense_category_id"},
                {"name": "Nombre", "id": "name"},
                {"name": "Editar", "id": "editar"},
                {"name": "Eliminar", "id": "eliminar"}
            ],
            data=exp_cat_active_df.to_dict('records'),
            style_cell_conditional=[
                {'if': {'column_id': 'editar'}, 'cursor': 'pointer'},
                {'if': {'column_id': 'eliminar'}, 'cursor': 'pointer'}
            ]
        )
        
        # --- MODIFICADO: Devuelve solo 'data' para la tabla de gastos ---
        return display_df.to_dict('records'), expense_categories_table, get_expense_category_options(user_id)

    # Callback descargar excel
    @app.callback(
        Output("download-expenses-excel", "data"),
        Input("btn-download-expenses-excel", "n_clicks"),
        prevent_initial_call=True
    )
    def download_expenses(n_clicks):
        if n_clicks is None: raise PreventUpdate
        if not current_user.is_authenticated: raise PreventUpdate
        user_id = int(current_user.id)
        expenses_df = load_expenses(user_id) 
        exp_cat_df = load_expense_categories(user_id)
        if not expenses_df.empty and not exp_cat_df.empty:
            df = pd.merge(expenses_df, exp_cat_df, on='expense_category_id', how='left').rename(columns={'name': 'gasto'})
        else:
            df = expenses_df
        return dcc.send_data_frame(df.to_excel, "historial_gastos.xlsx", sheet_name="Gastos", index=False)

    # Callback importar excel
    @app.callback(
        Output('upload-expenses-output', 'children'),
        Output('store-data-signal', 'data', allow_duplicate=True),
        Input('upload-expenses-data', 'contents'),
        [State('upload-expenses-data', 'filename'),
         State('store-data-signal', 'data')],
        prevent_initial_call=True
    )
    def upload_expenses_data(contents, filename, signal_data):
        if not current_user.is_authenticated or contents is None: raise PreventUpdate

        user_id = int(current_user.id)
        content_type, content_string = contents.split(',')
        decoded = base64.b64decode(content_string)

        try:
            if 'xls' in filename:
                df = pd.read_excel(io.BytesIO(decoded))
            else:
                return dbc.Alert("El archivo debe ser un .xlsx o .xls", color="danger"), dash.no_update
        except Exception as e:
            return dbc.Alert(f"Error al procesar el archivo: {e}", color="danger"), dash.no_update

        required_columns = ['nombre', 'monto', 'fecha']
        errors = []
        if not all(col in df.columns for col in required_columns):
            return dbc.Alert(f"El archivo debe contener las columnas: {', '.join(required_columns)}", color="danger"), dash.no_update

        expense_cats_db = pd.DataFrame(get_expense_category_options(user_id))
        expense_cats_lookup = {}
        if not expense_cats_db.empty:
             expense_cats_lookup = expense_cats_db.set_index('label')['value'].to_dict()

        expenses_to_insert = []
        for index, row in df.iterrows():
            category_name = row['nombre']
            amount = row['monto']
            expense_date = row['fecha']

            if category_name not in expense_cats_lookup:
                errors.append(f"Fila {index + 2}: El tipo de gasto '{category_name}' no existe o está inactivo.")
                continue
            try:
                amount = float(amount)
                if amount <= 0:
                     errors.append(f"Fila {index + 2}: El monto debe ser positivo.")
                     continue
            except (ValueError, TypeError):
                errors.append(f"Fila {index + 2}: El monto '{amount}' no es un número válido.")
                continue
            try:
                expense_date_dt = pd.to_datetime(expense_date)
                expense_date_to_save = expense_date_dt.to_pydatetime()
            except (ValueError, TypeError):
                errors.append(f"Fila {index + 2}: La fecha '{expense_date}' no tiene un formato válido.")
                continue

            expenses_to_insert.append({
                'expense_category_id': expense_cats_lookup[category_name],
                'amount': amount,
                'expense_date': expense_date_to_save, 
                'user_id': user_id
            })

        if errors:
            return dbc.Alert([html.H5("Se encontraron errores...")] + [html.P(e) for e in errors], color="danger"), dash.no_update

        if expenses_to_insert:
            from database import engine
            expenses_df_to_insert = pd.DataFrame(expenses_to_insert)
            expenses_df_to_insert.to_sql('expenses', engine, if_exists='append', index=False)
            new_signal = (signal_data or 0) + 1
            return dbc.Alert(f"¡Éxito! Se importaron {len(expenses_to_insert)} registros de gastos.", color="success"), new_signal

        return dbc.Alert("No se encontraron registros válidos.", color="warning"), dash.no_update

    # Callback abrir modales Editar/Eliminar Gasto
    @app.callback(
        Output('expense-edit-modal', 'is_open'),
        Output('expense-delete-confirm-modal', 'is_open'),
        Output('store-expense-id-to-edit', 'data'),
        Output('store-expense-id-to-delete', 'data'),
        Output('edit-expense-category', 'value'),
        Output('edit-expense-amount', 'value'),
        Output('edit-expense-date', 'date'),
        Output('edit-expense-category', 'options'),
        Input('expenses-table', 'active_cell'),
        State('expenses-table', 'derived_virtual_data'),
        prevent_initial_call=True
    )
    def open_expense_modals(active_cell, data):
        if not current_user.is_authenticated or not active_cell or 'row' not in active_cell:
            raise PreventUpdate

        user_id = int(current_user.id)
        row_idx = active_cell['row']
        column_id = active_cell['column_id']

        if not data or row_idx >= len(data): raise PreventUpdate
        expense_id = data[row_idx]['expense_id']

        expenses_df = load_expenses(user_id)
        try:
             expense_info = expenses_df[expenses_df['expense_id'] == expense_id].iloc[0]
        except IndexError:
             return False, False, None, None, dash.no_update, dash.no_update, dash.no_update, dash.no_update

        category_options = get_expense_category_options(user_id)
        no_update_list = [dash.no_update] * 4 

        if column_id == "editar":
            cat_val = int(expense_info['expense_category_id']) if pd.notna(expense_info['expense_category_id']) else None
            amount_val = expense_info['amount']
            date_val = expense_info['expense_date'].date() if pd.notna(expense_info['expense_date']) else None
            return True, False, expense_id, None, cat_val, amount_val, date_val, category_options

        elif column_id == "eliminar":
            return False, True, None, expense_id, *no_update_list

        return False, False, None, None, *no_update_list

    # Callback guardar edición Gasto
    @app.callback(
        Output('expense-edit-modal', 'is_open', allow_duplicate=True),
        Output('store-data-signal', 'data', allow_duplicate=True),
        Input('save-edited-expense-button', 'n_clicks'),
        [State('store-expense-id-to-edit', 'data'),
         State('edit-expense-category', 'value'),
         State('edit-expense-amount', 'value'),
         State('edit-expense-date', 'date'),
         State('store-data-signal', 'data')],
        prevent_initial_call=True
    )
    def save_edited_expense(n, expense_id, cat_id, amount, expense_date_str, signal):
        if not n or not expense_id: raise PreventUpdate

        if not all([cat_id, amount, expense_date_str]):
             print("Error: Todos los campos son obligatorios al editar gasto.")
             raise PreventUpdate
        try:
             amount = float(amount)
             if amount <=0: raise ValueError("Amount must be positive")
             expense_date_dt = datetime.strptime(expense_date_str, '%Y-%m-%d')
        except (ValueError, TypeError):
             print("Error: Monto o fecha inválidos al editar gasto.")
             raise PreventUpdate

        new_data = {
            "expense_category_id": cat_id,
            "amount": amount,
            "expense_date": expense_date_dt
        }
        update_expense(expense_id, new_data, current_user.id)
        return False, (signal or 0) + 1

    # Callback confirmar eliminar Gasto
    @app.callback(
        Output('expense-delete-confirm-modal', 'is_open', allow_duplicate=True),
        Output('store-data-signal', 'data', allow_duplicate=True),
        Input('confirm-delete-expense-button', 'n_clicks'),
        [State('store-expense-id-to-delete', 'data'), State('store-data-signal', 'data')],
        prevent_initial_call=True
    )
    def confirm_delete_expense(n, expense_id, signal):
        if not n or not expense_id: raise PreventUpdate
        delete_expense(expense_id, current_user.id)
        return False, (signal or 0) + 1

    # Callback cerrar modales Gasto
    @app.callback(
        Output('expense-edit-modal', 'is_open', allow_duplicate=True),
        Output('expense-delete-confirm-modal', 'is_open', allow_duplicate=True),
        [Input('cancel-edit-expense-button', 'n_clicks'),
         Input('cancel-delete-expense-button', 'n_clicks')],
        prevent_initial_call=True
    )
    def close_expense_modals(n_edit, n_delete):
        triggered_id = dash.callback_context.triggered_id
        if triggered_id in ['cancel-edit-expense-button', 'cancel-delete-expense-button']:
            return False, False
        raise PreventUpdate

    # Callback abrir modales Editar/Eliminar Categoría
    @app.callback(
        Output('expense_category-edit-modal', 'is_open'),
        Output('store-expense-category-id-to-edit', 'data'),
        Output('edit-expense-category-name', 'value'),
        Output('expense_category-delete-confirm-modal', 'is_open'),
        Output('store-expense-category-id-to-delete', 'data'),
        Input('expense-categories-table', 'active_cell'),
        State('expense-categories-table', 'derived_virtual_data'),
        prevent_initial_call=True
    )
    def open_expense_category_modals(active_cell, data):
        if not active_cell or 'row' not in active_cell: raise PreventUpdate

        row_idx = active_cell['row']
        col_id = active_cell['column_id']

        if not data or row_idx >= len(data): raise PreventUpdate

        category_id = data[row_idx]['expense_category_id']
        category_info = data[row_idx]

        if col_id == 'editar':
            return True, category_id, category_info['name'], False, dash.no_update
        elif col_id == 'eliminar':
            return False, dash.no_update, dash.no_update, True, category_id
        return False, dash.no_update, dash.no_update, False, dash.no_update

    # Callback confirmar eliminar Categoría (Borrado Suave)
    @app.callback(
        Output('expense_category-delete-confirm-modal', 'is_open', allow_duplicate=True),
        Output('store-data-signal', 'data', allow_duplicate=True),
        Input('confirm-delete-expense_category-button', 'n_clicks'),
        [State('store-expense-category-id-to-delete', 'data'), State('store-data-signal', 'data')],
        prevent_initial_call=True
    )
    def confirm_delete_expense_category(n, category_id, signal):
        if not n or not category_id: raise PreventUpdate
        delete_expense_category(category_id, current_user.id)
        return False, (signal or 0) + 1

    # Callback cerrar modal eliminar Categoría
    @app.callback(
        Output('expense_category-delete-confirm-modal', 'is_open', allow_duplicate=True),
        Input('cancel-delete-expense_category-button', 'n_clicks'),
        prevent_initial_call=True
    )
    def close_expense_category_delete_modal(n):
        if n: return False
        raise PreventUpdate

    # Callback guardar edición Categoría
    @app.callback(
        Output('expense_category-edit-modal', 'is_open', allow_duplicate=True),
        Output('store-data-signal', 'data', allow_duplicate=True),
        Input('save-edited-expense_category-button', 'n_clicks'),
        [State('store-expense-category-id-to-edit', 'data'),
         State('edit-expense-category-name', 'value'),
         State('store-data-signal', 'data')],
        prevent_initial_call=True
    )
    def save_edited_expense_category(n, category_id, name, signal):
        if n is None or not category_id: raise PreventUpdate
        if not name:
             print("Error: Nombre de categoría no puede estar vacío.")
             raise PreventUpdate

        update_expense_category(category_id, {"name": name}, current_user.id)
        return False, (signal or 0) + 1

    # Callback cerrar modal editar Categoría
    @app.callback(
        Output('expense_category-edit-modal', 'is_open', allow_duplicate=True),
        Input('cancel-edit-expense_category-button', 'n_clicks'),
        prevent_initial_call=True
    )
    def close_expense_category_edit_modal(n):
        if n: return False
        raise PreventUpdate
    
    # --- NUEVO CALLBACK: BORRADO MASIVO DE GASTOS ---
    @app.callback(
        Output('bulk-delete-expenses-output', 'children'),
        Output('store-data-signal', 'data', allow_duplicate=True),
        Input('delete-selected-expenses-btn', 'n_clicks'),
        [State('expenses-table', 'selected_row_ids'),
         State('store-data-signal', 'data')],
        prevent_initial_call=True
    )
    def delete_selected_expenses(n_clicks, selected_ids, signal_data):
        if n_clicks is None or n_clicks < 1 or not selected_ids:
            raise PreventUpdate
        
        if not current_user.is_authenticated:
            raise PreventUpdate
        
        user_id = int(current_user.id)
        
        try:
            success, message = delete_expenses_bulk(selected_ids, user_id)
            if success:
                new_signal = (signal_data or 0) + 1
                return dbc.Alert(message, color="success", dismissable=True, duration=4000), new_signal
            else:
                return dbc.Alert(message, color="danger", dismissable=True), dash.no_update
        except Exception as e:
            print(f"Error en borrado masivo de gastos: {e}")
            return dbc.Alert("Ocurrió un error al intentar borrar los gastos.", color="danger", dismissable=True), dash.no_update
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
from database import (
    load_expenses, load_expense_categories, get_expense_category_options, 
    update_expense, delete_expense, delete_expense_category, 
    reactivate_expense_category, update_expense_category
)

def get_layout():
    return html.Div([
        dcc.Store(id='store-expense-id-to-edit'),
        dcc.Store(id='store-expense-id-to-delete'),
        dcc.Store(id='store-expense-category-id-to-delete'),
        dcc.Store(id='store-expense-category-id-to-edit'), # <-- Añadido

        dbc.Modal([
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

        # --- AÑADIDO: Modal para Editar Tipo de Gasto ---
        dbc.Modal([
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

        dbc.Modal([
            dbc.ModalHeader("Confirmar Eliminación"),
            dbc.ModalBody("¿Estás seguro de que quieres eliminar este gasto?"),
            dbc.ModalFooter([
                dbc.Button("Cancelar", id="cancel-delete-expense-button", color="secondary", className="ms-auto"),
                dbc.Button("Eliminar", id="confirm-delete-expense-button", color="danger"),
            ]),
        ], id="expense-delete-confirm-modal", is_open=False),

        dbc.Modal([
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
                            dbc.Col([html.Label("Monto"), dbc.Input(id='expense-amount-input', type='number', min=0)], width=6),
                        ], className="mb-3"),
                        dbc.Button("Guardar Gasto", id="save-expense-button", color="danger", className="mt-3")
                    ])
                ]),
                
                dbc.Accordion([
                    dbc.AccordionItem(
                        [
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
                            html.Div(id='upload-expenses-output')
                        ],
                        title="Importar Historial de Gastos desde Excel"
                    )
                ], start_collapsed=True, className="m-4"),

                dbc.Accordion([
                    dbc.AccordionItem([
                        dbc.Button("Descargar Excel", id="btn-download-expenses-excel", color="success", className="mb-3"),
                        html.Div(id='expenses-table-container')
                    ], title="Ver Historial de Gastos")
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
        
        user_id = current_user.id
        if not all([cat_id, amount]):
            return dbc.Alert("Los campos Gasto y Monto son obligatorios.", color="danger"), dash.no_update
        
        from database import engine
        current_time = pd.to_datetime('now').strftime('%Y-%m-%d %H:%M:%S')
        
        pd.DataFrame([{
            'expense_date': current_time, 
            'expense_category_id': cat_id, 
            'amount': amount,
            'user_id': user_id
        }]).to_sql('expenses', engine, if_exists='append', index=False)
        
        expense_cat_name = "Gasto"
        if cat_id:
            # Usamos la función que solo trae activos, pero está bien para esto
            cats_df = pd.DataFrame(get_expense_category_options(user_id))
            if not cats_df.empty:
                match = cats_df[cats_df['value'] == cat_id]
                if not match.empty:
                    expense_cat_name = match['label'].iloc[0]
        
        new_signal = (signal_data or 0) + 1
        return dbc.Alert(f"Gasto de '{expense_cat_name}' por ${amount} guardado.", color="success", dismissable=True, duration=4000), new_signal

    # --- CALLBACK CORREGIDO: AÑADIR CATEGORÍA (CON REACTIVACIÓN) ---
    @app.callback(
        Output('add-expense-category-alert', 'children'),
        Output('store-data-signal', 'data', allow_duplicate=True),
        Input('save-expense-category-button', 'n_clicks'),
        [State('expense-category-name-input', 'value'),
         State('store-data-signal', 'data')],
        prevent_initial_call=True
    )
    def add_expense_category(n_clicks, name, signal_data):
        if n_clicks is None:
            raise PreventUpdate
        if not current_user.is_authenticated: raise PreventUpdate
        
        user_id = current_user.id
        if not name:
            return dbc.Alert("El nombre no puede estar vacío.", color="warning"), dash.no_update
        
        from database import engine
        
        # Cargamos TODAS las categorías (activas e inactivas)
        existing_cats = load_expense_categories(user_id)
        
        if not existing_cats.empty and 'is_active' in existing_cats.columns:
            match = existing_cats[existing_cats['name'].str.lower() == name.lower()]
            if not match.empty:
                category_data = match.iloc[0]
                
                # Si existe Y está activa, mostrar error
                if category_data['is_active']:
                    return dbc.Alert(f"El tipo de gasto '{name}' ya existe.", color="danger"), dash.no_update
                
                # Si existe PERO está inactiva, reactivarla
                else:
                    reactivate_expense_category(category_data['expense_category_id'], user_id)
                    new_signal = (signal_data or 0) + 1
                    return dbc.Alert(f"Tipo de gasto '{category_data['name']}' reactivado.", color="success"), new_signal

        # Si no existe (o si la columna 'is_active' aún no existe), crearla nueva
        # 'is_active' se establecerá en TRUE por defecto en la BD
        pd.DataFrame([{'name': name.title(), 'user_id': user_id}]).to_sql('expense_categories', engine, if_exists='append', index=False)
        
        new_signal = (signal_data or 0) + 1
        return dbc.Alert(f"Tipo de gasto '{name.title()}' guardado.", color="success"), new_signal

    # --- CALLBACK CORREGIDO: REFRESCAR TABLAS (CON FILTRO Y COLUMNA EDITAR) ---
    @app.callback(
        Output('expenses-table-container', 'children'),
        Output('expense-categories-table-container', 'children'),
        Output('expense-category-dropdown', 'options'),
        [Input('main-tabs', 'active_tab'), 
         Input('expense-sub-tabs', 'active_tab'),
         Input('store-data-signal', 'data')]
    )
    def refresh_expenses_components(main_tab, sub_tab, signal_data):
        if not current_user.is_authenticated or main_tab != 'tab-expenses':
            raise PreventUpdate
        
        user_id = current_user.id
        expenses_df = load_expenses(user_id)
        exp_cat_df = load_expense_categories(user_id) # Carga todas

        display_df = pd.DataFrame()
        if not expenses_df.empty:
            if not exp_cat_df.empty:
                # Merge con todas las categorías (incl. inactivas) para mostrar nombres históricos
                display_df = pd.merge(expenses_df, exp_cat_df, on='expense_category_id', how='left').rename(columns={'name': 'gasto'})
            else:
                display_df = expenses_df
            
            display_df['gasto'] = display_df['gasto'].fillna('Categoría Eliminada')
            display_df['expense_date'] = pd.to_datetime(display_df['expense_date'], format='mixed').dt.strftime('%Y-%m-%d %H:%M')
            display_df['editar'] = "✏️"
            display_df['eliminar'] = "🗑️"
        
        expenses_table = dash_table.DataTable(
            id='expenses-table',
            columns=[
                {"name": "ID Gasto", "id": "expense_id"}, {"name": "Fecha", "id": "expense_date"},
                {"name": "Gasto", "id": "gasto"}, 
                {"name": "Monto", "id": "amount", 'type': 'numeric', 'format': Format(precision=2, scheme=Scheme.fixed)},
                {"name": "Editar", "id": "editar"},
                {"name": "Eliminar", "id": "eliminar"}
            ],
            data=display_df.to_dict('records'),
            page_size=10,
            sort_action='native',
            sort_by=[{'column_id': 'expense_date', 'direction': 'desc'}],
            style_cell_conditional=[{'if': {'column_id': 'editar'}, 'cursor': 'pointer'}, {'if': {'column_id': 'eliminar'}, 'cursor': 'pointer'}]
        )

        # Filtrar categorías inactivas de la tabla de "Gestionar"
        if not exp_cat_df.empty and 'is_active' in exp_cat_df.columns:
            exp_cat_df = exp_cat_df[exp_cat_df['is_active'] == True].copy()
        
        exp_cat_df['editar'] = "✏️" 
        exp_cat_df['eliminar'] = "🗑️"
        
        expense_categories_table = dash_table.DataTable(
            id='expense-categories-table', 
            columns=[
                {"name": "ID", "id": "expense_category_id"}, 
                {"name": "Nombre", "id": "name"},
                {"name": "Editar", "id": "editar"}, 
                {"name": "Eliminar", "id": "eliminar"}
            ],
            data=exp_cat_df.to_dict('records'),
            style_cell_conditional=[
                {'if': {'column_id': 'eliminar'}, 'cursor': 'pointer'},
                {'if': {'column_id': 'editar'}, 'cursor': 'pointer'} 
            ]
        )
        
        return expenses_table, expense_categories_table, get_expense_category_options(user_id)

    @app.callback(
        Output("download-expenses-excel", "data"),
        Input("btn-download-expenses-excel", "n_clicks"),
        prevent_initial_call=True
    )
    def download_expenses(n_clicks):
        if n_clicks is None:
            raise PreventUpdate
            
        if not current_user.is_authenticated: raise PreventUpdate
        user_id = current_user.id
        expenses_df = load_expenses(user_id)
        exp_cat_df = load_expense_categories(user_id)
        if not expenses_df.empty and not exp_cat_df.empty:
            df = pd.merge(expenses_df, exp_cat_df, on='expense_category_id', how='left').rename(columns={'name': 'gasto'})
        else:
            df = expenses_df
        return dcc.send_data_frame(df.to_excel, "historial_gastos.xlsx", sheet_name="Gastos", index=False)

    @app.callback(
        Output('upload-expenses-output', 'children'),
        Output('store-data-signal', 'data', allow_duplicate=True),
        Input('upload-expenses-data', 'contents'),
        [State('upload-expenses-data', 'filename'),
         State('store-data-signal', 'data')],
        prevent_initial_call=True
    )
    def upload_expenses_data(contents, filename, signal_data):
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

        required_columns = ['Tipo de Gasto', 'Monto', 'Fecha de Gasto']
        errors = []
        if not all(col in df.columns for col in required_columns):
            return dbc.Alert(f"El archivo debe contener las columnas: {', '.join(required_columns)}", color="danger"), dash.no_update

        # Usamos la función que solo trae categorías activas
        expense_cats_db = pd.DataFrame(get_expense_category_options(user_id))
        expense_cats_lookup = {}
        if not expense_cats_db.empty:
             expense_cats_lookup = expense_cats_db.set_index('label')['value'].to_dict()

        expenses_to_insert = []
        for index, row in df.iterrows():
            category_name = row['Tipo de Gasto']
            amount = row['Monto']
            expense_date = row['Fecha de Gasto']
            
            if category_name not in expense_cats_lookup:
                errors.append(f"Fila {index + 2}: El tipo de gasto '{category_name}' no existe o está inactivo en la base de datos.")
                continue
            
            try: amount = float(amount)
            except (ValueError, TypeError):
                errors.append(f"Fila {index + 2}: El monto '{amount}' no es un número válido.")
                continue

            try: expense_date = pd.to_datetime(expense_date)
            except (ValueError, TypeError):
                errors.append(f"Fila {index + 2}: La fecha '{expense_date}' no tiene un formato válido.")
                continue

            expenses_to_insert.append({
                'expense_category_id': expense_cats_lookup[category_name],
                'amount': amount,
                'expense_date': expense_date.strftime('%Y-%m-%d %H:%M:%S'),
                'user_id': user_id
            })

        if errors:
            error_messages = [html.P(e) for e in errors]
            return dbc.Alert([html.H5("Se encontraron errores...")] + error_messages, color="danger"), dash.no_update

        if expenses_to_insert:
            from database import engine
            expenses_df = pd.DataFrame(expenses_to_insert)
            expenses_df.to_sql('expenses', engine, if_exists='append', index=False)
            new_signal = (signal_data or 0) + 1
            return dbc.Alert(f"¡Éxito! Se importaron {len(expenses_to_insert)} registros de gastos.", color="success"), new_signal
        
        return dbc.Alert("No se encontraron registros válidos.", color="warning"), dash.no_update

    @app.callback(
        Output('expense-edit-modal', 'is_open'),
        Output('expense-delete-confirm-modal', 'is_open'),
        Output('store-expense-id-to-edit', 'data'),
        Output('store-expense-id-to-delete', 'data'),
        Output('edit-expense-category', 'value'),
        Output('edit-expense-amount', 'value'),
        Output('edit-expense-date', 'date'),
        Output('edit-expense-category', 'options'), # <-- Añadido
        Input('expenses-table', 'active_cell'),
        State('expenses-table', 'derived_virtual_data'),
        prevent_initial_call=True
    )
    def open_expense_modals(active_cell, data):
        if not current_user.is_authenticated or not active_cell or 'row' not in active_cell: 
            raise PreventUpdate
        
        user_id = current_user.id
        row_idx = active_cell['row']
        column_id = active_cell['column_id']
        
        if not data or row_idx >= len(data):
            raise PreventUpdate
        expense_id = data[row_idx]['expense_id']
        
        expenses_df = load_expenses(user_id)
        expense_info = expenses_df[expenses_df['expense_id'] == expense_id].iloc[0]

        # Preparamos las opciones del dropdown para el modal
        category_options = get_expense_category_options(user_id)
        no_update_list = [dash.no_update] * 4

        if column_id == "editar":
            cat_val = int(expense_info['expense_category_id']) if pd.notna(expense_info['expense_category_id']) else None
            amount_val = expense_info['amount']
            date_val = pd.to_datetime(expense_info['expense_date']).date()
            return True, False, expense_id, None, cat_val, amount_val, date_val, category_options
        
        elif column_id == "eliminar":
            return False, True, None, expense_id, *no_update_list

        return False, False, None, None, *no_update_list

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
    def save_edited_expense(n, expense_id, cat_id, amount, expense_date, signal):
        if not n or not expense_id: raise PreventUpdate
        
        formatted_date = pd.to_datetime(expense_date).strftime('%Y-%m-%d %H:%M:%S')
        new_data = {
            "expense_category_id": cat_id, 
            "amount": float(amount), 
            "expense_date": formatted_date
        }
        update_expense(expense_id, new_data, current_user.id)
        return False, (signal or 0) + 1

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

    @app.callback(
        Output('expense-edit-modal', 'is_open', allow_duplicate=True),
        Output('expense-delete-confirm-modal', 'is_open', allow_duplicate=True),
        [Input('cancel-edit-expense-button', 'n_clicks'),
         Input('cancel-delete-expense-button', 'n_clicks')],
        prevent_initial_call=True
    )
    def close_expense_modals(n_edit, n_delete):
        return False, False

    # --- CALLBACK CORREGIDO: Abrir Modales de Edición/Eliminación de Categoría ---
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
        if not active_cell or 'row' not in active_cell:
            raise PreventUpdate

        row_idx = active_cell['row']
        col_id = active_cell['column_id']

        if not data or row_idx >= len(data):
            raise PreventUpdate
            
        category_id = data[row_idx]['expense_category_id']
        category_info = data[row_idx]
        
        if col_id == 'editar':
            # Abrir modal de edición y poblar datos
            return True, category_id, category_info['name'], False, dash.no_update

        elif col_id == 'eliminar':
            # Abrir modal de eliminación
            return False, dash.no_update, dash.no_update, True, category_id

        # Si se hace clic en cualquier otra celda
        return False, dash.no_update, dash.no_update, False, dash.no_update

    @app.callback(
        Output('expense_category-delete-confirm-modal', 'is_open', allow_duplicate=True),
        Output('store-data-signal', 'data', allow_duplicate=True),
        Input('confirm-delete-expense_category-button', 'n_clicks'),
        [State('store-expense-category-id-to-delete', 'data'), State('store-data-signal', 'data')],
        prevent_initial_call=True
    )
    def confirm_delete_expense_category(n, category_id, signal):
        if not n or not category_id: raise PreventUpdate
        # Llama a la función de borrado suave
        delete_expense_category(category_id, current_user.id)
        return False, (signal or 0) + 1
        
    @app.callback(
        Output('expense_category-delete-confirm-modal', 'is_open', allow_duplicate=True),
        Input('cancel-delete-expense_category-button', 'n_clicks'),
        prevent_initial_call=True
    )
    def close_expense_category_delete_modal(n):
        return False
        
    # --- AÑADIDO: Callbacks para el nuevo modal de Edición de Categoría ---
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
        if n is None: raise PreventUpdate
        if not category_id: raise PreventUpdate
        
        update_expense_category(category_id, {"name": name}, current_user.id)
        
        return False, (signal or 0) + 1

    @app.callback(
        Output('expense_category-edit-modal', 'is_open', allow_duplicate=True),
        Input('cancel-edit-expense_category-button', 'n_clicks'),
        prevent_initial_call=True
    )
    def close_expense_category_edit_modal(n):
        return False
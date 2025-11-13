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
from sqlalchemy import text

from app import app
from database import (
    load_expenses_detailed, load_expense_categories, get_expense_category_options,
    add_expense_category_strict, add_expense_concept, get_expense_concept_options,
    load_expense_concepts, delete_expense_concept, delete_expense, delete_expense_category,
    delete_expenses_bulk, engine,
    update_expense_concept, update_expense_category_strict
)

def get_layout():
    return html.Div([
        # --- STORES ---
        dcc.Store(id='store-expense-id-to-delete'),
        dcc.Store(id='store-expense-id-to-edit'),
        dcc.Store(id='store-concept-id-to-delete'),
        dcc.Store(id='store-concept-id-to-edit'),
        dcc.Store(id='store-exp-cat-id-to-delete'),
        dcc.Store(id='store-exp-cat-id-to-edit'),

        # --- 1. MODAL EDITAR GASTO (SIMPLIFICADO) ---
        dbc.Modal([
            dbc.ModalHeader("Editar Gasto Registrado"),
            dbc.ModalBody(dbc.Form([
                html.Div(id="alert-edit-expense"),
                
                # CAMBIO: Eliminado el filtro de categoría. Solo Concepto "Categoría - Nombre"
                dbc.Row([
                    dbc.Col([
                        dbc.Label("Concepto", className="fw-bold small"),
                        dcc.Dropdown(id='dropdown-edit-concept', placeholder="Selecciona concepto...", options=[])
                    ], xs=12, className="mb-3"),
                ]),

                dbc.Row([
                    dbc.Col([
                        dbc.Label("Monto", className="fw-bold small"),
                        dbc.Input(id='input-edit-amount', type='number', min=0, step="any")
                    ], xs=12, className="mb-3"),
                ]),
                
                dbc.Label("Fecha del Gasto", className="fw-bold small"),
                html.Div(dcc.DatePickerSingle(id='date-edit-expense', className="w-100"))
            ])),
            dbc.ModalFooter([
                dbc.Button("Cancelar", id="cancel-edit-exp", className="ms-auto"),
                dbc.Button("Guardar Cambios", id="save-edit-exp", color="primary")
            ]),
        ], id="modal-edit-exp", is_open=False),

        # --- 2. MODAL EDITAR CONCEPTO ---
        dbc.Modal([
            dbc.ModalHeader("Editar Concepto"),
            dbc.ModalBody(dbc.Form([
                html.Div(id="alert-edit-concept"),
                dbc.Label("Categoría Padre", className="fw-bold small"),
                dcc.Dropdown(id='dropdown-edit-con-cat', placeholder="Cambiar categoría...", options=[]),
                html.Div(className="mb-3"),
                dbc.Label("Nombre del Concepto", className="fw-bold small"),
                dbc.Input(id='input-edit-con-name', type='text')
            ])),
            dbc.ModalFooter([
                dbc.Button("Cancelar", id="cancel-edit-con", className="ms-auto"),
                dbc.Button("Guardar Cambios", id="save-edit-con", color="primary")
            ]),
        ], id="modal-edit-con", is_open=False),

        # --- 3. MODAL EDITAR CATEGORÍA ---
        dbc.Modal([
            dbc.ModalHeader("Editar Categoría"),
            dbc.ModalBody(dbc.Form([
                html.Div(id="alert-edit-cat"),
                dbc.Label("Nombre de la Categoría", className="fw-bold small"),
                dbc.Input(id='input-edit-cat-name', type='text')
            ])),
            dbc.ModalFooter([
                dbc.Button("Cancelar", id="cancel-edit-cat", className="ms-auto"),
                dbc.Button("Guardar Cambios", id="save-edit-cat", color="primary")
            ]),
        ], id="modal-edit-cat", is_open=False),

        # --- MODALES CONFIRMACIÓN ---
        dbc.Modal([
            dbc.ModalHeader("Confirmar Eliminación"),
            dbc.ModalBody("¿Eliminar este gasto registrado?"),
            dbc.ModalFooter([dbc.Button("Cancelar", id="cancel-del-exp", className="ms-auto"), dbc.Button("Eliminar", id="confirm-del-exp", color="danger")])
        ], id="modal-del-exp", is_open=False),

        dbc.Modal([
            dbc.ModalHeader("Confirmar Eliminación Concepto"),
            dbc.ModalBody("¿Eliminar este concepto? (No borrará gastos históricos)."),
            dbc.ModalFooter([dbc.Button("Cancelar", id="cancel-del-con", className="ms-auto"), dbc.Button("Eliminar", id="confirm-del-con", color="danger")])
        ], id="modal-del-con", is_open=False),

        dbc.Modal([
            dbc.ModalHeader("Confirmar Eliminación Categoría"),
            dbc.ModalBody("¿Eliminar esta categoría? Se borrarán sus conceptos asociados."),
            dbc.ModalFooter([dbc.Button("Cancelar", id="cancel-del-cat", className="ms-auto"), dbc.Button("Eliminar", id="confirm-del-cat", color="danger")])
        ], id="modal-del-exp-cat", is_open=False), 

        # --- PESTAÑAS ---
        dbc.Tabs(id="expense-tabs", active_tab="tab-add-expense", children=[
            
            # TAB 1: AÑADIR GASTO
            dbc.Tab(label="Registrar Gasto", tab_id="tab-add-expense", children=[
                dbc.Card(className="m-2 m-md-4 shadow-sm", children=[
                    dbc.CardBody([
                        html.H3("Registrar Gasto", className="card-title mb-4"),
                        html.Div(id="alert-add-expense"),
                        dbc.Row([
                            dbc.Col([
                                html.Label("Concepto del Gasto", className="fw-bold small"),
                                dcc.Dropdown(id='dropdown-expense-concepts', placeholder="Busca el concepto...", options=[])
                            ], xs=12, md=6, className="mb-3 mb-md-0"),
                            dbc.Col([
                                html.Label("Monto", className="fw-bold small"),
                                dbc.Input(id='input-expense-amount', type='number', min=0, placeholder="0.00")
                            ], xs=12, md=6),
                        ], className="mb-3"),
                        dbc.Button("Guardar Gasto", id="btn-save-expense", color="success", className="w-100 w-md-auto")
                    ])
                ]),

                # ACORDEÓN IMPORTAR EXCEL
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
                                html.P("El archivo Excel debe tener las siguientes columnas:"),
                                html.Ul([
                                    html.Li([html.B("categoria"), " (Ej: 'Transporte')"]),
                                    html.Li([html.B("concepto"), " (Ej: 'Uber')"]),
                                    html.Li([html.B("monto"), " (Valor numérico)"]),
                                    html.Li([html.B("fecha"), " (Formato AAAA-MM-DD)"]),
                                ]),
                            ], color="info", className="mt-2 small"),
                            html.Div(id='upload-expenses-output')
                        ],
                        title="Importar Historial de Gastos desde Excel"
                    )
                ], start_collapsed=True, className="m-2 m-md-4")
            ]),

            # TAB 2: HISTORIAL
            dbc.Tab(label="Historial", tab_id="tab-history", children=[
                html.Div(className="p-2 p-md-4", children=[
                    dbc.Row([
                        dbc.Col(html.H4("Historial de Gastos"), width="auto"),
                        dbc.Col(dbc.Button("Borrar Seleccionados", id="btn-bulk-del-exp", color="danger", size="sm"), width="auto", className="ms-auto")
                    ], className="mb-3 align-items-center"),
                    
                    html.Div(id="output-bulk-del-exp"),
                    
                    dash_table.DataTable(
                        id='table-expenses-history',
                        columns=[
                            {"name": "Fecha", "id": "fecha_fmt"},
                            {"name": "Categoría", "id": "categoria"},
                            {"name": "Concepto", "id": "concepto"},
                            {"name": "Monto", "id": "amount", 'type': 'numeric', 'format': Format(precision=2, scheme=Scheme.fixed)},
                            {"name": "Editar", "id": "editar"},
                            {"name": "Eliminar", "id": "eliminar"}
                        ],
                        data=[], page_size=15, row_selectable='multi', selected_rows=[],
                        sort_action='native', filter_action='native',
                        style_table={'overflowX': 'auto'},
                        style_cell={'textAlign': 'left', 'minWidth': '100px'},
                        style_cell_conditional=[
                            {'if': {'column_id': 'eliminar'}, 'cursor': 'pointer', 'textAlign': 'center', 'width': '80px'},
                            {'if': {'column_id': 'editar'}, 'cursor': 'pointer', 'textAlign': 'center', 'width': '80px'}
                        ]
                    )
                ])
            ]),

            # TAB 3: CREAR CONCEPTO
            dbc.Tab(label="Crear Concepto", tab_id="tab-create-concept", children=[
                dbc.Row([
                    dbc.Col([
                        dbc.Card(className="m-2 m-md-4 shadow-sm", children=[
                            dbc.CardBody([
                                html.H4("Nuevo Concepto", className="mb-3"),
                                html.Div(id="alert-add-concept"),
                                html.Label("Categoría Padre", className="small fw-bold"),
                                dcc.Dropdown(id='dropdown-parent-category', placeholder="Selecciona categoría...", className="mb-3"),
                                html.Label("Nombre del Concepto", className="small fw-bold"),
                                dbc.Input(id='input-concept-name', placeholder="Ej: Pauta Instagram", className="mb-3"),
                                dbc.Button("Crear Concepto", id="btn-save-concept", color="primary", className="w-100")
                            ])
                        ])
                    ], xs=12, md=4, className="mb-4 mb-md-0"),
                    dbc.Col([
                        html.Div(className="p-2 p-md-4", children=[
                            html.H4("Conceptos Existentes"),
                            dash_table.DataTable(
                                id='table-concepts',
                                columns=[
                                    {"name": "Categoría", "id": "category_name"},
                                    {"name": "Concepto", "id": "concept_name"},
                                    {"name": "Editar", "id": "editar"},
                                    {"name": "Eliminar", "id": "eliminar"}
                                ],
                                data=[], page_size=10, style_table={'overflowX': 'auto'},
                                style_cell={'textAlign': 'left'},
                                style_cell_conditional=[
                                    {'if': {'column_id': 'eliminar'}, 'cursor': 'pointer', 'textAlign': 'center', 'width': '80px'},
                                    {'if': {'column_id': 'editar'}, 'cursor': 'pointer', 'textAlign': 'center', 'width': '80px'}
                                ]
                            )
                        ])
                    ], xs=12, md=8)
                ])
            ]),

            # TAB 4: CREAR CATEGORÍA
            dbc.Tab(label="Crear Categoría", tab_id="tab-create-category", children=[
                dbc.Row([
                    dbc.Col([
                        dbc.Card(className="m-2 m-md-4 shadow-sm", children=[
                            dbc.CardBody([
                                html.H4("Nueva Categoría", className="mb-3"),
                                html.Div(id="alert-add-category"),
                                html.Label("Nombre Categoría", className="small fw-bold"),
                                dbc.Input(id='input-category-name', placeholder="Ej: Marketing", className="mb-3"),
                                dbc.Button("Crear Categoría", id="btn-save-category", color="primary", className="w-100")
                            ])
                        ])
                    ], xs=12, md=4, className="mb-4 mb-md-0"),
                    dbc.Col([
                        html.Div(className="p-2 p-md-4", children=[
                            html.H4("Categorías Existentes"),
                            dash_table.DataTable(
                                id='table-categories',
                                columns=[{"name": "ID", "id": "expense_category_id"}, {"name": "Nombre", "id": "name"}, {"name": "Editar", "id": "editar"}, {"name": "Eliminar", "id": "eliminar"}],
                                data=[], page_size=10, style_table={'overflowX': 'auto'},
                                style_cell={'textAlign': 'left'},
                                style_cell_conditional=[
                                    {'if': {'column_id': 'eliminar'}, 'cursor': 'pointer', 'textAlign': 'center', 'width': '80px'},
                                    {'if': {'column_id': 'editar'}, 'cursor': 'pointer', 'textAlign': 'center', 'width': '80px'}
                                ]
                            )
                        ])
                    ], xs=12, md=8)
                ])
            ])
        ])
    ])

def register_callbacks(app):
    
    # --- 1. CARGA DE DATOS ---
    @app.callback(
        Output('table-expenses-history', 'data'),
        Output('table-concepts', 'data'),
        Output('table-categories', 'data'),
        Output('dropdown-expense-concepts', 'options'),
        Output('dropdown-parent-category', 'options'),
        # Ahora 'dropdown-edit-concept' se llena desde aquí con TODOS los conceptos
        Output('dropdown-edit-concept', 'options'), 
        Output('dropdown-edit-con-cat', 'options'), 
        [Input('expense-tabs', 'active_tab'), Input('store-data-signal', 'data')]
    )
    def refresh_data(tab, signal):
        if not current_user.is_authenticated: raise PreventUpdate
        uid = int(current_user.id)
        
        expenses = load_expenses_detailed(uid)
        expenses['fecha_fmt'] = expenses['expense_date'].dt.strftime('%Y-%m-%d')
        expenses['eliminar'] = "🗑️"
        expenses['editar'] = "✏️"
        expenses['id'] = expenses['expense_id']

        concepts = load_expense_concepts(uid)
        concepts['eliminar'] = "🗑️"
        concepts['editar'] = "✏️"
        concepts['id'] = concepts['concept_id']

        cats = load_expense_categories(uid)
        active_cats = cats[cats['is_active']==True].copy() if not cats.empty and 'is_active' in cats.columns else cats
        active_cats['eliminar'] = "🗑️"
        active_cats['editar'] = "✏️"
        active_cats['id'] = active_cats['expense_category_id']

        concept_opts = get_expense_concept_options(uid)
        cat_opts = get_expense_category_options(uid)

        # Enviamos concept_opts a 'dropdown-edit-concept' también
        return (expenses.to_dict('records'), concepts.to_dict('records'), active_cats.to_dict('records'),
                concept_opts, cat_opts, concept_opts, cat_opts)

    # --- 2. UPLOAD EXCEL (CON CATEGORÍA) ---
    @app.callback(
        Output('upload-expenses-output', 'children'),
        Output('store-data-signal', 'data', allow_duplicate=True),
        Input('upload-expenses-data', 'contents'),
        [State('upload-expenses-data', 'filename'), State('store-data-signal', 'data')],
        prevent_initial_call=True
    )
    def upload_expenses(contents, filename, signal):
        if not current_user.is_authenticated or not contents: raise PreventUpdate
        uid = int(current_user.id)
        content_type, content_string = contents.split(',')
        decoded = base64.b64decode(content_string)
        
        try:
            if 'xls' in filename: df = pd.read_excel(io.BytesIO(decoded))
            else: return dbc.Alert("Formato incorrecto. Usa .xlsx", color="danger"), dash.no_update
        except Exception as e: return dbc.Alert(f"Error leyendo archivo: {e}", color="danger"), dash.no_update

        df.columns = [c.lower().strip() for c in df.columns]
        required = ['categoria', 'concepto', 'monto', 'fecha']
        missing = [col for col in required if col not in df.columns]
        
        if missing:
            return dbc.Alert(f"Faltan columnas: {', '.join(missing)}.", color="danger"), dash.no_update

        existing_concepts = load_expense_concepts(uid)
        concept_map = {}
        if not existing_concepts.empty:
            for _, row in existing_concepts.iterrows():
                key = (str(row['category_name']).strip().lower(), str(row['concept_name']).strip().lower())
                concept_map[key] = row['concept_id']
        
        expenses_to_insert = []
        errors = []

        for i, row in df.iterrows():
            cat_name = str(row['categoria']).strip()
            con_name = str(row['concepto']).strip()
            key = (cat_name.lower(), con_name.lower())
            
            if key in concept_map:
                cid = concept_map[key]
            else:
                errors.append(f"Fila {i+2}: Concepto '{con_name}' en categoría '{cat_name}' no existe.")
                continue
            
            try:
                amt = float(row['monto'])
                if amt <= 0: raise ValueError
                dt = pd.to_datetime(row['fecha']).to_pydatetime()
            except:
                errors.append(f"Fila {i+2}: Monto o fecha inválidos.")
                continue
                
            expenses_to_insert.append({'expense_concept_id': cid, 'amount': amt, 'expense_date': dt, 'user_id': uid})

        if errors:
            return dbc.Alert([html.H5("Errores en la importación:")] + [html.P(e) for e in errors[:10]], color="danger"), dash.no_update

        if expenses_to_insert:
            pd.DataFrame(expenses_to_insert).to_sql('expenses', engine, if_exists='append', index=False)
            return dbc.Alert(f"¡Éxito! {len(expenses_to_insert)} gastos importados.", color="success"), (signal or 0) + 1
        
        return dbc.Alert("No se encontraron datos válidos.", color="warning"), dash.no_update

    # --- 3. CRUD (Create) ---
    @app.callback(
        Output('alert-add-category', 'children'), Output('input-category-name', 'value'), Output('store-data-signal', 'data', allow_duplicate=True),
        Input('btn-save-category', 'n_clicks'), State('input-category-name', 'value'), State('store-data-signal', 'data'), prevent_initial_call=True
    )
    def save_cat(n, name, signal):
        if n is None or n == 0: raise PreventUpdate 
        if not name or not name.strip(): return dbc.Alert("Nombre vacío.", color="warning"), dash.no_update, dash.no_update
        try:
            success, msg = add_expense_category_strict(name, current_user.id)
            return dbc.Alert(msg, color="success" if success else "danger", dismissable=True), "" if success else dash.no_update, (signal or 0)+1 if success else dash.no_update
        except Exception as e: return dbc.Alert(f"Error: {e}", color="danger"), dash.no_update, dash.no_update

    @app.callback(
        Output('alert-add-concept', 'children'), Output('input-concept-name', 'value'), Output('dropdown-parent-category', 'value'), Output('store-data-signal', 'data', allow_duplicate=True),
        Input('btn-save-concept', 'n_clicks'), [State('input-concept-name', 'value'), State('dropdown-parent-category', 'value'), State('store-data-signal', 'data')], prevent_initial_call=True
    )
    def save_con(n, name, cat_id, signal):
        if not n: raise PreventUpdate
        if not cat_id: return dbc.Alert("Falta Categoría.", color="warning"), dash.no_update, dash.no_update, dash.no_update
        if not name or not name.strip(): return dbc.Alert("Falta Nombre.", color="warning"), dash.no_update, dash.no_update, dash.no_update
        try:
            success, msg = add_expense_concept(name, cat_id, current_user.id)
            return dbc.Alert(msg, color="success" if success else "danger", dismissable=True), "" if success else dash.no_update, dash.no_update, (signal or 0)+1 if success else dash.no_update
        except Exception as e: return dbc.Alert(f"Error: {e}", color="danger"), dash.no_update, dash.no_update, dash.no_update

    @app.callback(
        Output('alert-add-expense', 'children'), Output('input-expense-amount', 'value'), Output('dropdown-expense-concepts', 'value'), Output('store-data-signal', 'data', allow_duplicate=True),
        Input('btn-save-expense', 'n_clicks'), [State('dropdown-expense-concepts', 'value'), State('input-expense-amount', 'value'), State('store-data-signal', 'data')], prevent_initial_call=True
    )
    def save_exp(n, con_id, amt, signal):
        if not n: raise PreventUpdate
        if not con_id: return dbc.Alert("Falta Concepto.", color="warning"), dash.no_update, dash.no_update, dash.no_update
        try:
            val = float(amt)
            if val <= 0: raise ValueError
        except: return dbc.Alert("Monto inválido.", color="danger"), dash.no_update, dash.no_update, dash.no_update
        try:
            pd.DataFrame([{'expense_concept_id': int(con_id), 'amount': val, 'expense_date': datetime.now(), 'user_id': int(current_user.id)}]).to_sql('expenses', engine, if_exists='append', index=False)
            return dbc.Alert("Gasto registrado.", color="success", duration=3000), "", None, (signal or 0)+1
        except Exception as e: return dbc.Alert(f"Error: {e}", color="danger"), dash.no_update, dash.no_update, dash.no_update

    # --- 4. MODALES ACCIÓN (Row ID) ---
    @app.callback(
        Output('modal-edit-exp', 'is_open'), Output('store-expense-id-to-edit', 'data'),
        Output('dropdown-edit-concept', 'value'),
        Output('input-edit-amount', 'value'), Output('date-edit-expense', 'date'),
        Output('modal-del-exp', 'is_open'), Output('store-expense-id-to-delete', 'data'),
        Input('table-expenses-history', 'active_cell'), State('table-expenses-history', 'derived_virtual_data'), prevent_initial_call=True
    )
    def action_expenses(cell, data):
        if not cell or not data or 'row_id' not in cell: raise PreventUpdate
        eid = cell['row_id']; col = cell['column_id']
        record = next((r for r in data if r['id'] == eid), None)
        if col == 'editar' and record:
            d_val = str(record['expense_date']).split('T')[0] if record.get('expense_date') else None
            # Eliminamos la lógica de categoría del dropdown de editar
            return True, eid, record.get('expense_concept_id'), record.get('amount'), d_val, False, dash.no_update
        elif col == 'eliminar':
            return False, dash.no_update, dash.no_update, dash.no_update, dash.no_update, True, eid
        raise PreventUpdate

    @app.callback(
        Output('modal-edit-con', 'is_open'), Output('store-concept-id-to-edit', 'data'),
        Output('dropdown-edit-con-cat', 'value'), Output('input-edit-con-name', 'value'),
        Output('modal-del-con', 'is_open'), Output('store-concept-id-to-delete', 'data'),
        Input('table-concepts', 'active_cell'), State('table-concepts', 'derived_virtual_data'), prevent_initial_call=True
    )
    def action_concepts(cell, data):
        if not cell or not data or 'row_id' not in cell: raise PreventUpdate
        cid = cell['row_id']; col = cell['column_id']
        if col == 'editar':
            record = next((r for r in data if r['id'] == cid), None)
            if record:
                try:
                    con_df = load_expense_concepts(current_user.id)
                    match = con_df[con_df['concept_id'] == cid]
                    cat_id = int(match.iloc[0]['expense_category_id']) if not match.empty else None
                except: cat_id = None
                return True, cid, cat_id, record.get('concept_name'), False, dash.no_update
        elif col == 'eliminar':
            return False, dash.no_update, dash.no_update, dash.no_update, True, cid
        raise PreventUpdate

    @app.callback(
        Output('modal-edit-cat', 'is_open'), Output('store-exp-cat-id-to-edit', 'data'),
        Output('input-edit-cat-name', 'value'),
        Output('modal-del-exp-cat', 'is_open'), Output('store-exp-cat-id-to-delete', 'data'),
        Input('table-categories', 'active_cell'), State('table-categories', 'derived_virtual_data'), prevent_initial_call=True
    )
    def action_categories(cell, data):
        if not cell or not data or 'row_id' not in cell: raise PreventUpdate
        cid = cell['row_id']; col = cell['column_id']
        if col == 'editar':
            record = next((r for r in data if r['id'] == cid), None)
            return True, cid, record.get('name') if record else "", False, dash.no_update
        elif col == 'eliminar':
            return False, dash.no_update, dash.no_update, True, cid
        raise PreventUpdate

    # --- 5. GUARDAR EDICIONES (Updates) ---
    @app.callback(
        Output('modal-edit-exp', 'is_open', allow_duplicate=True), Output('store-data-signal', 'data', allow_duplicate=True), Output('alert-edit-expense', 'children'),
        Input('save-edit-exp', 'n_clicks'),
        [State('store-expense-id-to-edit', 'data'), State('dropdown-edit-concept', 'value'), State('input-edit-amount', 'value'), State('date-edit-expense', 'date'), State('store-data-signal', 'data')],
        prevent_initial_call=True
    )
    def save_edit_exp(n, eid, cid, amt, dt, sig):
        if not n or not eid: raise PreventUpdate
        if not cid or not amt or not dt: return True, dash.no_update, dbc.Alert("Datos incompletos.", color="danger")
        try:
            with engine.connect() as connection:
                with connection.begin():
                    connection.execute(text("UPDATE expenses SET expense_concept_id=:cid, amount=:amt, expense_date=:dt WHERE expense_id=:eid"), {"cid":cid, "amt":amt, "dt":dt, "eid":eid})
            return False, (sig or 0)+1, None
        except Exception as e: return True, dash.no_update, dbc.Alert(f"Error: {e}", color="danger")

    @app.callback(
        Output('modal-edit-con', 'is_open', allow_duplicate=True), Output('store-data-signal', 'data', allow_duplicate=True), Output('alert-edit-concept', 'children'),
        Input('save-edit-con', 'n_clicks'),
        [State('store-concept-id-to-edit', 'data'), State('input-edit-con-name', 'value'), State('dropdown-edit-con-cat', 'value'), State('store-data-signal', 'data')], prevent_initial_call=True
    )
    def save_edit_con(n, cid, name, cat_id, sig):
        if not n or not cid: raise PreventUpdate
        try:
            update_expense_concept(cid, name, cat_id, current_user.id)
            return False, (sig or 0)+1, None
        except Exception as e: return True, dash.no_update, dbc.Alert(str(e), color="danger")

    @app.callback(
        Output('modal-edit-cat', 'is_open', allow_duplicate=True), Output('store-data-signal', 'data', allow_duplicate=True), Output('alert-edit-cat', 'children'),
        Input('save-edit-cat', 'n_clicks'),
        [State('store-exp-cat-id-to-edit', 'data'), State('input-edit-cat-name', 'value'), State('store-data-signal', 'data')], prevent_initial_call=True
    )
    def save_edit_cat(n, cid, name, sig):
        if not n or not cid: raise PreventUpdate
        try:
            update_expense_category_strict(cid, name, current_user.id)
            return False, (sig or 0)+1, None
        except Exception as e: return True, dash.no_update, dbc.Alert(str(e), color="danger")

    # --- 6. ELIMINACIONES ---
    @app.callback(Output('modal-del-exp', 'is_open', allow_duplicate=True), Output('store-data-signal', 'data', allow_duplicate=True), Input('confirm-del-exp', 'n_clicks'), State('store-expense-id-to-delete', 'data'), State('store-data-signal', 'data'), prevent_initial_call=True)
    def conf_del_exp(n, eid, sig):
        if n and eid: delete_expense(eid, current_user.id); return False, (sig or 0)+1
        raise PreventUpdate
    @app.callback(Output('modal-del-con', 'is_open', allow_duplicate=True), Output('store-data-signal', 'data', allow_duplicate=True), Input('confirm-del-con', 'n_clicks'), State('store-concept-id-to-delete', 'data'), State('store-data-signal', 'data'), prevent_initial_call=True)
    def conf_del_con(n, cid, sig):
        if n and cid: delete_expense_concept(cid, current_user.id); return False, (sig or 0)+1
        raise PreventUpdate
    @app.callback(Output('modal-del-exp-cat', 'is_open', allow_duplicate=True), Output('store-data-signal', 'data', allow_duplicate=True), Input('confirm-del-cat', 'n_clicks'), State('store-exp-cat-id-to-delete', 'data'), State('store-data-signal', 'data'), prevent_initial_call=True)
    def conf_del_cat(n, cid, sig):
        if n and cid: delete_expense_category(cid, current_user.id); return False, (sig or 0)+1
        raise PreventUpdate

    # Cierres
    @app.callback(Output('modal-edit-exp', 'is_open', allow_duplicate=True), Input('cancel-edit-exp', 'n_clicks'), prevent_initial_call=True)
    def c1(n): return False
    @app.callback(Output('modal-edit-con', 'is_open', allow_duplicate=True), Input('cancel-edit-con', 'n_clicks'), prevent_initial_call=True)
    def c2(n): return False
    @app.callback(Output('modal-edit-cat', 'is_open', allow_duplicate=True), Input('cancel-edit-cat', 'n_clicks'), prevent_initial_call=True)
    def c3(n): return False
    @app.callback(Output('modal-del-exp', 'is_open', allow_duplicate=True), Input('cancel-del-exp', 'n_clicks'), prevent_initial_call=True)
    def c4(n): return False
    @app.callback(Output('modal-del-con', 'is_open', allow_duplicate=True), Input('cancel-del-con', 'n_clicks'), prevent_initial_call=True)
    def c5(n): return False
    @app.callback(Output('modal-del-exp-cat', 'is_open', allow_duplicate=True), Input('cancel-del-cat', 'n_clicks'), prevent_initial_call=True)
    def c6(n): return False

    # Bulk Delete (CORREGIDO: Limpieza de Selección)
    @app.callback(
        Output('output-bulk-del-exp', 'children'),
        Output('store-data-signal', 'data', allow_duplicate=True),
        Output('table-expenses-history', 'selected_rows'), # Clear Selection
        Output('table-expenses-history', 'selected_row_ids'), # Clear Selection
        Input('btn-bulk-del-exp', 'n_clicks'),
        [State('table-expenses-history', 'selected_row_ids'), State('store-data-signal', 'data')],
        prevent_initial_call=True
    )
    def bulk_del(n, ids, sig):
        if not n or not ids: raise PreventUpdate
        success, msg = delete_expenses_bulk(ids, current_user.id)
        alert = dbc.Alert(msg, color="success" if success else "danger", dismissable=True)
        return alert, (sig or 0)+1, [], [] # Return empty lists
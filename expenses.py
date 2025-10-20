from dash import dcc, html, dash_table
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
import pandas as pd
import base64
import io
import dash

from app import app
from database import load_expenses, load_expense_categories, get_expense_category_options

def get_layout():
    return dbc.Tabs(id="expense-sub-tabs", active_tab="sub-tab-add-expense", children=[
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
                    dash_table.DataTable(
                        id='expenses-table',
                        columns=[
                            {"name": "ID Gasto", "id": "expense_id"},
                            {"name": "Fecha", "id": "expense_date"},
                            {"name": "Gasto", "id": "gasto"},
                            {"name": "Monto", "id": "amount"}
                        ],
                        page_size=10,
                        sort_action='native',
                        sort_by=[{'column_id': 'expense_date', 'direction': 'desc'}]
                    )
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
                        dash_table.DataTable(id='expense-categories-table', columns=[{"name": "ID", "id": "expense_category_id"}, {"name": "Nombre", "id": "name"}])
                    ])
                ], width=8)
            ])
        ])
    ])

def register_callbacks(app):
    @app.callback(
        Output('add-expense-alert', 'children'),
        # ### CAMBIO: Se añade allow_duplicate y prevent_initial_call ###
        Output('store-data-signal', 'data', allow_duplicate=True),
        Input('save-expense-button', 'n_clicks'),
        [State('expense-category-dropdown', 'value'),
         State('expense-amount-input', 'value'),
         State('store-data-signal', 'data')],
        prevent_initial_call=True
    )
    def add_expense(n, cat_id, amount, signal_data):
        if not all([cat_id, amount]):
            return dbc.Alert("Los campos Gasto y Monto son obligatorios.", color="danger"), dash.no_update
        
        from database import engine
        current_time = pd.to_datetime('now').strftime('%Y-%m-%d %H:%M:%S')
        
        pd.DataFrame([{'expense_date': current_time, 'expense_category_id': cat_id, 'amount': amount}]).to_sql('expenses', engine, if_exists='append', index=False)
        
        expense_cat_name = "Gasto"
        if cat_id:
            cats = load_expense_categories()
            if not cats[cats['expense_category_id'] == cat_id].empty:
                expense_cat_name = cats[cats['expense_category_id'] == cat_id]['name'].iloc[0]
        
        new_signal = (signal_data or 0) + 1
        
        return dbc.Alert(f"Gasto de '{expense_cat_name}' por ${amount} guardado.", color="success", dismissable=True, duration=4000), new_signal

    @app.callback(
        Output('add-expense-category-alert', 'children'),
        Input('save-expense-category-button', 'n_clicks'),
        State('expense-category-name-input', 'value'),
        prevent_initial_call=True
    )
    def add_expense_category(n_clicks, name):
        if not name:
            return dbc.Alert("El nombre no puede estar vacío.", color="warning")
        
        from database import engine
        existing_cats = load_expense_categories()
        if name.lower() in existing_cats['name'].str.lower().tolist():
            return dbc.Alert(f"El tipo de gasto '{name}' ya existe.", color="danger")
        pd.DataFrame([{'name': name.title()}]).to_sql('expense_categories', engine, if_exists='append', index=False)
        
        return dbc.Alert(f"Tipo de gasto '{name.title()}' guardado.", color="success")

    @app.callback(
        Output('expenses-table', 'data'),
        Output('expense-category-dropdown', 'options'),
        Output('expense-categories-table', 'data'),
        [Input('main-tabs', 'active_tab'), 
         Input('expense-sub-tabs', 'active_tab'),
         Input('store-data-signal', 'data')]
    )
    def refresh_expenses_components(main_tab, sub_tab, signal_data):
        if main_tab != 'tab-expenses':
            raise PreventUpdate
        
        expenses_df = load_expenses()
        exp_cat_df = load_expense_categories()

        display_df = pd.DataFrame()
        if not expenses_df.empty and not exp_cat_df.empty:
            display_df = pd.merge(expenses_df, exp_cat_df, on='expense_category_id', how='left').rename(columns={'name': 'gasto'})
            display_df['expense_date'] = pd.to_datetime(display_df['expense_date'], format='mixed').dt.strftime('%Y-%m-%d %H:%M')
        
        return display_df.to_dict('records'), get_expense_category_options(), exp_cat_df.to_dict('records')

    @app.callback(
        Output("download-expenses-excel", "data"),
        Input("btn-download-expenses-excel", "n_clicks"),
        prevent_initial_call=True
    )
    def download_expenses(n_clicks):
        expenses_df = load_expenses()
        exp_cat_df = load_expense_categories()
        if not expenses_df.empty and not exp_cat_df.empty:
            df = pd.merge(expenses_df, exp_cat_df, on='expense_category_id', how='left').rename(columns={'name': 'gasto'})
        else:
            df = expenses_df
        return dcc.send_data_frame(df.to_excel, "historial_gastos.xlsx", sheet_name="Gastos", index=False)

    @app.callback(
        Output('upload-expenses-output', 'children'),
        # ### CAMBIO: Se añade allow_duplicate y prevent_initial_call ###
        Output('store-data-signal', 'data', allow_duplicate=True),
        Input('upload-expenses-data', 'contents'),
        [State('upload-expenses-data', 'filename'),
         State('store-data-signal', 'data')],
        prevent_initial_call=True
    )
    def upload_expenses_data(contents, filename, signal_data):
        if contents is None:
            raise PreventUpdate

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

        expense_cats_db = load_expense_categories()
        expense_cats_lookup = expense_cats_db.set_index('name')['expense_category_id'].to_dict()

        expenses_to_insert = []
        for index, row in df.iterrows():
            category_name = row['Tipo de Gasto']
            amount = row['Monto']
            expense_date = row['Fecha de Gasto']

            if category_name not in expense_cats_lookup:
                errors.append(f"Fila {index + 2}: El tipo de gasto '{category_name}' no existe en la base de datos.")
                continue
            
            try:
                amount = float(amount)
            except (ValueError, TypeError):
                errors.append(f"Fila {index + 2}: El monto '{amount}' no es un número válido.")
                continue

            try:
                expense_date = pd.to_datetime(expense_date)
            except (ValueError, TypeError):
                errors.append(f"Fila {index + 2}: La fecha '{expense_date}' no tiene un formato válido.")
                continue

            expenses_to_insert.append({
                'expense_category_id': expense_cats_lookup[category_name],
                'amount': amount,
                'expense_date': expense_date.strftime('%Y-%m-%d %H:%M:%S'),
            })

        if errors:
            error_messages = [html.P(e) for e in errors]
            return dbc.Alert([html.H5("Se encontraron errores. Por favor, corrígelos y vuelve a subir el archivo:")] + error_messages, color="danger"), dash.no_update

        if expenses_to_insert:
            from database import engine
            expenses_df = pd.DataFrame(expenses_to_insert)
            expenses_df.to_sql('expenses', engine, if_exists='append', index=False)
            new_signal = (signal_data or 0) + 1
            return dbc.Alert(f"¡Éxito! Se importaron {len(expenses_to_insert)} registros de gastos.", color="success"), new_signal
        
        return dbc.Alert("No se encontraron registros válidos para importar.", color="warning"), dash.no_update
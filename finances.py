from dash import dcc, html, dash_table
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output
from dash.exceptions import PreventUpdate
from dash.dash_table.Format import Format, Scheme, Symbol
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from flask_login import current_user

from app import app
from database import load_sales, load_expenses, load_products, load_expense_categories, calculate_financials

today = date.today()
start_of_this_month = today.replace(day=1)
end_of_last_month = start_of_this_month - timedelta(days=1)
start_of_last_month = end_of_last_month.replace(day=1)

def get_layout():
    return dbc.Tabs(id="finances-sub-tabs", active_tab="sub-tab-summary", children=[
        dbc.Tab(label="Resumen", tab_id="sub-tab-summary", children=[
            html.Div(className="p-4", children=[
                dbc.Row([
                    dbc.Col(html.H4("Filtrar por Fecha:"), width='auto'),
                    dbc.Col(
                        dcc.DatePickerRange(
                            id='finances-date-picker',
                            start_date=start_of_this_month,
                            end_date=today,
                            display_format='YYYY-MM-DD',
                        ),
                    width=True),
                    dbc.Col(
                        dbc.Switch(
                            id="finances-see-all-switch",
                            label="Ver todo el historial",
                            value=True,
                        ),
                    width="auto")
                ], align="center", className="mb-4"),
                html.H3("Análisis Financiero Detallado", className="mb-4"),
                dbc.Row([
                    dbc.Col(dbc.Card(id='gross-margin-card', color="success", inverse=True)),
                    dbc.Col(dbc.Card(id='net-margin-card', color="info", inverse=True)),
                    dbc.Col(dbc.Card(id='avg-ticket-card', color="primary", inverse=True)),
                ], className="mb-4"),
                dbc.Row([
                    dbc.Col(width=6, children=[
                        dbc.Card([
                            dbc.CardHeader("Estado de Resultados (P&L)"),
                            dbc.CardBody(
                                dash_table.DataTable(
                                    id='pnl-table',
                                    columns=[{"name": "Concepto", "id": "Concepto"}, {"name": "Monto", "id": "Monto"}],
                                    style_cell={'textAlign': 'left'}, style_header={'fontWeight': 'bold'},
                                    style_data_conditional=[{'if': {'row_index': 2},'backgroundColor': '#F0F0F0'}, {'if': {'row_index': 4}, 'fontWeight': 'bold'}]
                                )
                            )
                        ])
                    ]),
                    dbc.Col(width=6, children=[
                        dbc.Card([
                            dbc.CardHeader("Desglose de Gastos Operativos"), # <-- Título general
                            dbc.CardBody([
                                dbc.Tabs(id="expense-breakdown-tabs", active_tab="tab-visual", children=[

                                    # Pestaña 1: El Gráfico de Pastel (Restaurado)
                                    dbc.Tab(label="Resumen Visual", tab_id="tab-visual", children=[
                                        dcc.Graph(id='expense-pie-chart', style={'height': '350px'}, className="mt-3")
                                    ]),

                                    # Pestaña 2: La Tabla de Detalle
# --- CÓDIGO CORREGIDO ---
                                    dbc.Tab(label="Detalle en Tabla", tab_id="tab-table", children=[
                                        # Envolvemos la tabla en un html.Div para aplicar el margen
                                        html.Div([ 
                                            dash_table.DataTable(
                                                id='expense-detail-table',
                                                columns=[
                                                    {"name": "Categoría de Gasto", "id": "Categoría"},
                                                    {"name": "Monto Total", "id": "Monto", 'type': 'numeric', 'format': Format(precision=2, scheme=Scheme.fixed, symbol=Symbol.yes)}
                                                ],
                                                style_cell={'textAlign': 'left'},
                                                style_header={'fontWeight': 'bold'},
                                                sort_action='native',
                                                sort_by=[{'column_id': 'Monto', 'direction': 'desc'}],
                                                page_size=7
                                                # className="mt-3" <-- ELIMINADO DE AQUÍ
                                            )
                                        ], className="mt-3") # <-- Y AÑADIDO AL html.Div
                                    ]),
                                ])
                            ])
                        ])
                    ]),
                ], className="mb-4"),
                dbc.Row([
                    dbc.Col(dbc.Card([
                        dbc.CardHeader("Análisis de Rentabilidad por Producto"),
                        dbc.CardBody(dash_table.DataTable(
                            id='product-performance-table',
                            columns=[
                                {"name": "Producto", "id": "Producto"},
                                {"name": "Unidades Vendidas", "id": "Unidades Vendidas"},
                                {"name": "Ingresos Totales", "id": "Ingresos Totales", 'type': 'numeric', 'format': Format(precision=2, scheme=Scheme.fixed)},
                                {"name": "Costo Total (COGS)", "id": "Costo Total (COGS)", 'type': 'numeric', 'format': Format(precision=2, scheme=Scheme.fixed)},
                                {"name": "Ganancia Bruta", "id": "Ganancia Bruta", 'type': 'numeric', 'format': Format(precision=2, scheme=Scheme.fixed)},
                                {"name": "Rentabilidad (%)", "id": "Rentabilidad (%)", 'type': 'numeric', 'format': Format(precision=2, scheme=Scheme.fixed, symbol=Symbol.yes, symbol_suffix=' %')}
                            ],
                            page_size=10,
                            sort_action='native',
                            style_table={'overflowX': 'auto'}
                        ))
                    ]))
                ])
            ])
        ]),
        dbc.Tab(label="Comparación", tab_id="sub-tab-comparison", children=[
            html.Div(className="p-4", children=[
                html.H3("Comparación entre Períodos", className="mb-4"),
                dbc.Row([
                    dbc.Col(width=6, children=[
                        html.H5("Período A"),
                        dcc.DatePickerRange(id='comparison-date-picker-a', start_date=start_of_last_month, end_date=end_of_last_month, display_format='YYYY-MM-DD')
                    ]),
                    dbc.Col(width=6, children=[
                        html.H5("Período B"),
                        dcc.DatePickerRange(id='comparison-date-picker-b', start_date=start_of_this_month, end_date=today, display_format='YYYY-MM-DD')
                    ])
                ], className="mb-4"),
                dbc.Row(id='comparison-card-ingresos', className="mb-4 g-3"),
                dbc.Row(id='comparison-cards-container', className="mb-4 g-3"),
                dbc.Row([
                    dbc.Col(dcc.Graph(id='top-products-a'), width=6),
                    dbc.Col(dcc.Graph(id='top-products-b'), width=6)
                ], className="mt-4")
            ])
        ])
    ])

def register_callbacks(app):
    @app.callback(
        Output('pnl-table', 'data'),
        Output('gross-margin-card', 'children'),
        Output('net-margin-card', 'children'),
        Output('avg-ticket-card', 'children'),
        Output('expense-pie-chart', 'figure'),    # <-- CORREGIDO: Output 5
        Output('expense-detail-table', 'data'),
        Output('product-performance-table', 'data'),
        Output('finances-date-picker', 'disabled'),
        [Input('finances-sub-tabs', 'active_tab'),
         Input('finances-date-picker', 'start_date'),
         Input('finances-date-picker', 'end_date'),
         Input('finances-see-all-switch', 'value'),
         Input('store-data-signal', 'data')]
    )
    def update_finances_summary_tab(active_tab, start_date, end_date, see_all, signal_data):
        if not current_user.is_authenticated or active_tab != 'sub-tab-summary' or not all([start_date, end_date]):
            raise PreventUpdate

        user_id = current_user.id
        
        results = calculate_financials(start_date, end_date, user_id, see_all=see_all)
        
        expenses_df = results['expenses_df']
        merged_df = results['merged_df']
        date_picker_disabled = see_all
        
        pnl_data = [
            {"Concepto": "Ingresos Totales (Ventas)", "Monto": f"${results['total_revenue']:,.2f}"},
            {"Concepto": "(-) Costo de Productos (COGS)", "Monto": f"${results['total_cogs']:,.2f}"},
            {"Concepto": "=> Ganancia Bruta", "Monto": f"${results['gross_profit']:,.2f}"},
            {"Concepto": "(-) Gastos Operativos", "Monto": f"${results['total_expenses']:.2f}"},
            {"Concepto": "=> Ganancia Neta", "Monto": f"${results['net_profit']:,.2f}"}
        ]

        gross_margin_card = dbc.CardBody([html.H4("Margen Ganancia Bruta", className="card-title"), html.H2(f"{results['gross_margin']:.2f}%")])
        net_margin_card = dbc.CardBody([html.H4("Margen Ganancia Neta", className="card-title"), html.H2(f"{results['net_margin']:.2f}%")])
        avg_ticket_card = dbc.CardBody([html.H4("Ticket de Venta Promedio", className="card-title"), html.H2(f"${results['avg_ticket']:,.2f}")])

        expense_table_data = []
        # --- INICIO DEL BLOQUE A AÑADIR (LÓGICA DEL GRÁFICO) ---
        fig_expenses = px.pie(title="Gastos por Categoría", names=['Sin Gastos'], values=[1]).update_traces(textinfo='none', hoverinfo='none')
        # --- FIN DEL BLOQUE A AÑADIR ---

        if not expenses_df.empty:
            exp_cat_df = load_expense_categories(user_id)
            if not exp_cat_df.empty:
                expenses_with_names = pd.merge(expenses_df, exp_cat_df, on='expense_category_id', how='left')
                expense_summary = expenses_with_names.groupby('name')['amount'].sum().reset_index()

                # Lógica para la TABLA (ya la tienes)
                expense_table_data = expense_summary.rename(
                    columns={'name': 'Categoría', 'amount': 'Monto'}
                ).to_dict('records')

                # --- INICIO DEL BLOQUE A AÑADIR (LÓGICA DEL GRÁFICO) ---
                # Lógica para el GRÁFICO
                fig_expenses = px.pie(expense_summary, names='name', values='amount', title="Gastos por Categoría", hole=.3)
                fig_expenses.update_layout(margin=dict(t=30, b=0, l=0, r=0))
                # --- FIN DEL BLOQUE A AÑADIR ---
        
        if not expenses_df.empty:
            exp_cat_df = load_expense_categories(user_id)
            if not exp_cat_df.empty:
                expenses_with_names = pd.merge(expenses_df, exp_cat_df, on='expense_category_id', how='left')
                # Agrupar, sumar, y renombrar para la tabla
                expense_summary = expenses_with_names.groupby('name')['amount'].sum().reset_index()
                expense_summary = expense_summary.rename(columns={'name': 'Categoría', 'amount': 'Monto'})
                # Opcional: añadir fila de Total
                # total_gastos = pd.DataFrame([{'Categoría': 'Total Gastos Operativos', 'Monto': expense_summary['Monto'].sum()}])
                # expense_summary = pd.concat([expense_summary, total_gastos], ignore_index=True)
                expense_table_data = expense_summary.to_dict('records')

        product_performance_data = []
        if not merged_df.empty:
            prod_perf = merged_df.groupby('name').agg(
                unidades_vendidas=('quantity', 'sum'),
                ingresos_totales=('total_amount', 'sum'),
                costo_total=('cogs_total', 'sum')
            ).reset_index()
            prod_perf['ganancia_bruta'] = prod_perf['ingresos_totales'] - prod_perf['costo_total']
            
            prod_perf['rentabilidad_%'] = 0.0
            mask = prod_perf['ingresos_totales'] > 0
            prod_perf.loc[mask, 'rentabilidad_%'] = (prod_perf.loc[mask, 'ganancia_bruta'] / prod_perf.loc[mask, 'ingresos_totales']) * 100
            
            prod_perf = prod_perf.sort_values(by='ganancia_bruta', ascending=False)
            
            product_performance_data = prod_perf.rename(columns={
                'name': 'Producto', 'unidades_vendidas': 'Unidades Vendidas',
                'ingresos_totales': 'Ingresos Totales', 'costo_total': 'Costo Total (COGS)',
                'ganancia_bruta': 'Ganancia Bruta', 'rentabilidad_%': 'Rentabilidad (%)'
            }).to_dict('records')

        # --- ORDEN CORREGIDO ---
        return pnl_data, gross_margin_card, net_margin_card, avg_ticket_card, fig_expenses, expense_table_data, product_performance_data, date_picker_disabled

    @app.callback(
        Output('comparison-card-ingresos', 'children'),
        Output('comparison-cards-container', 'children'),
        Output('top-products-a', 'figure'),
        Output('top-products-b', 'figure'),
        [Input('finances-sub-tabs', 'active_tab'),
         Input('comparison-date-picker-a', 'start_date'),
         Input('comparison-date-picker-a', 'end_date'),
         Input('comparison-date-picker-b', 'start_date'),
         Input('comparison-date-picker-b', 'end_date')]
    )
    def update_comparison_tab(active_sub_tab, start_a, end_a, start_b, end_b):
        if not current_user.is_authenticated or active_sub_tab != 'sub-tab-comparison' or not all([start_a, end_a, start_b, end_b]):
            raise PreventUpdate

        user_id = current_user.id
        data_a = calculate_financials(start_a, end_a, user_id)
        data_b = calculate_financials(start_b, end_b, user_id)

        def create_comparison_card(title, val_a, val_b, format_str, is_percent=False, invert_colors=False):
            diff = val_b - val_a
            
            color_good = "success"
            color_bad = "danger"
            
            if invert_colors:
                color_good, color_bad = color_bad, color_good
            
            if val_a == 0 and val_b != 0:
                pct_change_str, color = " (Nuevo)", "success"
            elif val_a != 0 and val_b == 0:
                pct_change_str, color = f" (▼ 100.00%)", color_bad
            elif val_a != 0:
                pct_change = (diff / abs(val_a)) * 100
                if diff > 0:
                    pct_change_str, color = f" (▲ {pct_change:.2f}%)", color_good
                else:
                    pct_change_str, color = f" (▼ {abs(pct_change):.2f}%)", color_bad
            else:
                pct_change_str, color = " (=)", "secondary"

            suffix = " %" if is_percent else ""
            label_a = f"{format_str.format(val_a)}{suffix}"
            label_b = f"{format_str.format(val_b)}{suffix}"
            
            max_val = max(abs(val_a), abs(val_b))
            val_a_pct, val_b_pct = (0, 0) if max_val == 0 else ((abs(val_a) / max_val * 100), (abs(val_b) / max_val * 100))

            return dbc.Card([
                    dbc.CardHeader(title),
                    dbc.CardBody([
                        html.P("Período A", className="card-text fw-bold"),
                        dbc.Progress(label=label_a, value=val_a_pct, color="danger" if val_a < 0 else "secondary", className="mb-2"),
                        html.P("Período B", className="card-text fw-bold mt-3"),
                        dbc.Progress(label=label_b, value=val_b_pct, color="danger" if val_b < 0 else "primary", className="mb-2"),
                        html.H5(html.Span(pct_change_str, className=f"text-{color} mt-3 d-block"))
                    ])
                ])

        top_row = [
            dbc.Col(create_comparison_card("Ingresos Totales", data_a['total_revenue'], data_b['total_revenue'], "${:,.2f}"), width=9),
            dbc.Col(create_comparison_card("Ticket Promedio", data_a['avg_ticket'], data_b['avg_ticket'], "${:,.2f}"), width=3)
        ]

        col_volumen = dbc.Col([
            html.H4("Volumen y Clientes", className="mb-3"),
            create_comparison_card("Número de Ventas", data_a['num_sales'], data_b['num_sales'], "{:,.0f}"),
            html.Div(className="mt-3"),
            create_comparison_card("Unidades Vendidas", data_a['unidades_vendidas'], data_b['unidades_vendidas'], "{:,.0f}")
        ], width=3)

        col_costos = dbc.Col([
            html.H4("Costos", className="mb-3"),
            create_comparison_card("Costo de Productos", data_a['total_cogs'], data_b['total_cogs'], "${:,.2f}", invert_colors=True),
            html.Div(className="mt-3"),
            create_comparison_card("Gastos Operativos", data_a['total_expenses'], data_b['total_expenses'], "${:,.2f}", invert_colors=True)
        ], width=3)
        
        col_ganancias = dbc.Col([
            html.H4("Ganancias ($)", className="mb-3"),
            create_comparison_card("Ganancia Bruta", data_a['gross_profit'], data_b['gross_profit'], "${:,.2f}"),
            html.Div(className="mt-3"),
            create_comparison_card("Ganancia Neta", data_a['net_profit'], data_b['net_profit'], "${:,.2f}")
        ], width=3)

        col_margenes = dbc.Col([
            html.H4("Márgenes (%)", className="mb-3"),
            create_comparison_card("Margen Bruto", data_a['gross_margin'], data_b['gross_margin'], "{:.2f}", is_percent=True),
            html.Div(className="mt-3"),
            create_comparison_card("Margen Neto", data_a['net_margin'], data_b['net_margin'], "{:.2f}", is_percent=True)
        ], width=3)
        
        bottom_rows_layout = [col_volumen, col_costos, col_ganancias, col_margenes]
        
        products_df = load_products(user_id)
        
        sales_df_a = data_a['sales_df']
        if not sales_df_a.empty:
            merged_a = pd.merge(sales_df_a, products_df, on='product_id')
            top_5_a = merged_a.groupby('name')['quantity'].sum().nlargest(5).sort_values(ascending=False)
            fig_a = px.bar(top_5_a, x=top_5_a.values, y=top_5_a.index, orientation='h', 
                           title=f"Top 5 Productos (Período A)",
                           labels={'y': '', 'x': 'Unidades Vendidas'}, text_auto=True,
                           color_discrete_sequence=['#6c757d'])
            fig_a.update_layout(
                xaxis=dict(autorange='reversed'),
                yaxis=dict(side='right', autorange='reversed'),
                margin=dict(l=20, r=150, t=40, b=20),
                yaxis_title=None
            )
        else:
            fig_a = px.bar(title="Top 5 Productos Vendidos (Período A)").update_layout(
                annotations=[dict(text="Sin datos de ventas", showarrow=False)],
                margin=dict(l=20, r=20, t=40, b=20)
            )

        sales_df_b = data_b['sales_df']
        if not sales_df_b.empty:
            merged_b = pd.merge(sales_df_b, products_df, on='product_id')
            top_5_b = merged_b.groupby('name')['quantity'].sum().nlargest(5).sort_values(ascending=False)
            fig_b = px.bar(top_5_b, x=top_5_b.values, y=top_5_b.index, orientation='h',
                           title=f"Top 5 Productos (Período B)",
                           labels={'y': '', 'x': 'Unidades Vendidas'}, text_auto=True,
                           color_discrete_sequence=['#0d6efd'])
            fig_b.update_layout(
                yaxis=dict(autorange='reversed'),
                xaxis_title="Unidades Vendidas",
                margin=dict(l=150, r=20, t=40, b=20),
                yaxis_title=None,
                title_x=0,
                title_xanchor='left'
            )
        else:
            fig_b = px.bar(title="Top 5 Productos Vendidos (Período B)").update_layout(
                annotations=[dict(text="Sin datos de ventas", showarrow=False)],
                margin=dict(l=20, r=20, t=40, b=20)
            )

        return top_row, bottom_rows_layout, fig_a, fig_b
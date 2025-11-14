# finances.py
from dash import dcc, html, dash_table
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output
from dash.exceptions import PreventUpdate
from dash.dash_table.Format import Format, Scheme, Symbol
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from datetime import date, timedelta
from flask_login import current_user

from app import app
from database import calculate_financials, load_products

today = date.today()
start_of_this_month = today.replace(day=1)
end_of_last_month = start_of_this_month - timedelta(days=1)
start_of_last_month = end_of_last_month.replace(day=1)

def get_layout():
    # Estilo de tarjetas
    card_style = {"border": "none", "borderRadius": "10px"}

    return dbc.Tabs(id="finances-sub-tabs", active_tab="sub-tab-summary", children=[
        
        # --- TAB 1: RESUMEN ---
        dbc.Tab(label="Resumen", tab_id="sub-tab-summary", children=[
            html.Div(className="p-2 p-md-4", children=[
                
                dbc.Row([
                    dbc.Col(html.H4("Filtrar por Fecha:"), xs=12, md='auto', className="mb-2 mb-md-0"),
                    dbc.Col(dcc.DatePickerRange(id='finances-date-picker', start_date=start_of_this_month, end_date=today, display_format='YYYY-MM-DD', className="w-100"), xs=12, md=True, className="ps-md-4 mb-2 mb-md-0"),
                    dbc.Col(dbc.Switch(id="finances-see-all-switch", label="Ver todo el historial", value=True), xs=12, md="auto")
                ], align="center", className="mb-4"),

                html.H3("Análisis Financiero Detallado", className="mb-4"),
                
                dbc.Row([
                    dbc.Col(dbc.Card(id='gross-margin-card', color="success", inverse=True, className="h-100 shadow-sm", style=card_style), xs=12, md=4, className="mb-3 mb-md-0"),
                    dbc.Col(dbc.Card(id='net-margin-card', color="info", inverse=True, className="h-100 shadow-sm", style=card_style), xs=12, md=4, className="mb-3 mb-md-0"),
                    dbc.Col(dbc.Card(id='avg-ticket-card', color="primary", inverse=True, className="h-100 shadow-sm", style=card_style), xs=12, md=4),
                ], className="mb-4 g-3", align="stretch"),

                dbc.Row([
                    dbc.Col(dbc.Card([
                        dbc.CardHeader("Resumen P&L"),
                        dbc.CardBody(dash_table.DataTable(id='pnl-table', columns=[{"name": "Concepto", "id": "Concepto"}, {"name": "Monto", "id": "Monto"}], style_cell={'textAlign': 'left'}, style_header={'fontWeight': 'bold'}, style_data_conditional=[{'if': {'row_index': 2},'backgroundColor': '#F0F0F0'}, {'if': {'row_index': 4}, 'fontWeight': 'bold'}], style_table={'overflowX': 'auto'}))
                    ], className="h-100 shadow-sm border-0"), xs=12, lg=6, className="mb-3 mb-lg-0"),
                    
                    dbc.Col(dbc.Card([
                        dbc.CardHeader("Desglose de Gastos Operativos"),
                        dbc.CardBody([
                            dbc.Tabs(id="expense-breakdown-tabs", active_tab="tab-visual", children=[
                                dbc.Tab(label="Resumen Visual", tab_id="tab-visual", children=[dcc.Graph(id='expense-pie-chart', style={'height': '350px'}, className="mt-3")]),
                                dbc.Tab(label="Detalle en Tabla", tab_id="tab-table", children=[html.Div([
                                    
                                    # CAMBIO: Agregada columna "Concepto" a la tabla
                                    dash_table.DataTable(
                                        id='expense-detail-table',
                                        columns=[
                                            {"name": "Categoría", "id": "Categoría"},
                                            {"name": "Concepto", "id": "Concepto"}, # <--- NUEVA COLUMNA
                                            {"name": "Monto Total", "id": "Monto", 'type': 'numeric', 'format': Format(precision=2, scheme=Scheme.fixed, symbol=Symbol.yes)}
                                        ],
                                        style_cell={'textAlign': 'left'},
                                        style_header={'fontWeight': 'bold'},
                                        sort_action='native',
                                        sort_by=[{'column_id': 'Monto', 'direction': 'desc'}],
                                        page_size=7,
                                        style_table={'overflowX': 'auto'}
                                    )
                                ], className="mt-3")]),
                            ])
                        ])
                    ], className="h-100 shadow-sm border-0"), xs=12, lg=6),
                ], className="mb-4 g-3", align="stretch"),

                dbc.Row([
                    dbc.Col(dbc.Card([
                        dbc.CardHeader("Detalle de Ingresos y Costos (por Producto)"),
                        dbc.CardBody(dash_table.DataTable(id='product-performance-table', columns=[{"name": "Producto", "id": "Producto"}, {"name": "Unidades", "id": "Unidades Vendidas"}, {"name": "Ingresos", "id": "Ingresos Totales", 'type': 'numeric', 'format': Format(precision=2, scheme=Scheme.fixed)}, {"name": "Costo (COGS)", "id": "Costo Total (COGS)", 'type': 'numeric', 'format': Format(precision=2, scheme=Scheme.fixed)}, {"name": "Ganancia", "id": "Ganancia Bruta", 'type': 'numeric', 'format': Format(precision=2, scheme=Scheme.fixed)}, {"name": "Rentabilidad", "id": "Rentabilidad (%)", 'type': 'numeric', 'format': Format(precision=2, scheme=Scheme.fixed, symbol=Symbol.yes, symbol_suffix=' %')}], page_size=10, sort_action='native', style_table={'overflowX': 'auto'}))
                    ], className="shadow-sm border-0"), xs=12)
                ])
            ])
        ]),

        # --- TAB 2: COMPARACIÓN ---
        dbc.Tab(label="Comparación", tab_id="sub-tab-comparison", children=[
            dbc.Container([
                html.H3("Comparación entre Períodos", className="mb-4 mt-4"),
                dbc.Row([
                    dbc.Col([html.H5("Período A (Anterior)"), dcc.DatePickerRange(id='comparison-date-picker-a', start_date=start_of_last_month, end_date=end_of_last_month, display_format='YYYY-MM-DD', className="w-100")], xs=12, md=6, className="mb-3 mb-md-0"),
                    dbc.Col([html.H5("Período B (Actual)"), dcc.DatePickerRange(id='comparison-date-picker-b', start_date=start_of_this_month, end_date=today, display_format='YYYY-MM-DD', className="w-100")], xs=12, md=6)
                ], className="mb-5"),
                html.Div(id='comparison-card-ingresos', className="mb-5"),
                dbc.Row(id='comparison-cards-container', className="g-4 mb-5"), 
                html.H5("PRODUCTOS", className="mb-4 text-center text-muted fw-bold text-uppercase"),
                dbc.Row([
                    dbc.Col(dcc.Graph(id='top-products-a', style={'height': '400px'}), xs=12, lg=6, className="mb-4 mb-lg-0"),
                    dbc.Col(dcc.Graph(id='top-products-b', style={'height': '400px'}), xs=12, lg=6)
                ], className="mt-5")
            ], fluid=True, className="px-2 px-md-4 pb-5")
        ])
    ])

def register_callbacks(app):
    @app.callback(
        Output('pnl-table', 'data'),
        Output('gross-margin-card', 'children'),
        Output('net-margin-card', 'children'),
        Output('avg-ticket-card', 'children'),
        Output('expense-pie-chart', 'figure'),
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

        card_body_class = "d-flex flex-column justify-content-center h-100 text-center"
        
        gross_margin_card = dbc.CardBody([html.H4("Margen Ganancia Bruta", className="card-title small text-uppercase"), html.H2(f"{results['gross_margin']:.2f}%")], className=card_body_class)
        net_margin_card = dbc.CardBody([html.H4("Margen Ganancia Neta", className="card-title small text-uppercase"), html.H2(f"{results['net_margin']:.2f}%")], className=card_body_class)
        avg_ticket_card = dbc.CardBody([html.H4("Ticket de Venta Promedio", className="card-title small text-uppercase"), html.H2(f"${results['avg_ticket']:,.2f}")], className=card_body_class)

        # --- GASTOS (VISUAL + TABLA) ---
        fig_expenses = px.pie(title="Gastos por Categoría", names=['Sin Gastos'], values=[1]).update_traces(textinfo='none', hoverinfo='none')
        expense_table_data = []
        
        if not expenses_df.empty:
            # 1. GRÁFICO (Agrupado por Categoría)
            pie_data = expenses_df.groupby('categoria')['amount'].sum().reset_index()
            fig_expenses = px.pie(pie_data, names='categoria', values='amount', title="Gastos por Categoría", hole=.3)
            
            # 2. TABLA DETALLADA (Agrupada por Categoría y Concepto)
            table_data = expenses_df.groupby(['categoria', 'concepto'])['amount'].sum().reset_index()
            
            # Ordenar de mayor a menor
            table_data = table_data.sort_values(by='amount', ascending=False)
            
            expense_table_data = table_data.rename(columns={
                'categoria': 'Categoría', 
                'concepto': 'Concepto', 
                'amount': 'Monto'
            }).to_dict('records')
                
        fig_expenses.update_layout(margin=dict(t=30, b=0, l=0, r=0))

        product_performance_data = []
        if not merged_df.empty:
            prod_perf = merged_df.groupby('name').agg(unidades_vendidas=('quantity', 'sum'), ingresos_totales=('total_amount', 'sum'), costo_total=('cogs_total', 'sum')).reset_index()
            prod_perf['ganancia_bruta'] = prod_perf['ingresos_totales'] - prod_perf['costo_total']
            prod_perf['rentabilidad_%'] = 0.0
            mask = prod_perf['ingresos_totales'] > 0
            prod_perf.loc[mask, 'rentabilidad_%'] = (prod_perf.loc[mask, 'ganancia_bruta'] / prod_perf.loc[mask, 'ingresos_totales']) * 100
            prod_perf = prod_perf.sort_values(by='ganancia_bruta', ascending=False)
            product_performance_data = prod_perf.rename(columns={'name': 'Producto', 'unidades_vendidas': 'Unidades Vendidas', 'ingresos_totales': 'Ingresos Totales', 'costo_total': 'Costo Total (COGS)', 'ganancia_bruta': 'Ganancia Bruta', 'rentabilidad_%': 'Rentabilidad (%)'}).to_dict('records')

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
            color_good, color_bad = "success", "danger"
            if invert_colors: color_good, color_bad = color_bad, color_good
            
            if val_a == 0 and val_b != 0: pct_change_str, color = " (Nuevo)", color_good
            elif val_a != 0 and val_b == 0: pct_change_str, color = f" (▼ 100.00%)", color_bad
            elif val_a != 0:
                pct_change = (diff / abs(val_a)) * 100
                if diff > 0: pct_change_str, color = f" (▲ {pct_change:.2f}%)", color_good
                else: pct_change_str, color = f" (▼ {abs(pct_change):.2f}%)", color_bad
            else: pct_change_str, color = " (=)", "secondary"

            suffix = " %" if is_percent else ""
            label_a = f"{format_str.format(val_a)}{suffix}"
            label_b = f"{format_str.format(val_b)}{suffix}"
            max_val = max(abs(val_a), abs(val_b))
            val_a_pct = (abs(val_a) / max_val * 100) if max_val > 0 else 0
            val_b_pct = (abs(val_b) / max_val * 100) if max_val > 0 else 0

            return dbc.Card([
                    dbc.CardHeader(title, className="fw-bold small text-uppercase bg-light py-2"),
                    dbc.CardBody([
                        html.Div([html.Span("Período A", className="text-muted small"), html.Span(label_a, className="float-end fw-bold text-secondary small")], className="mb-1"),
                        dbc.Progress(value=val_a_pct, color="secondary", className="mb-2", style={"height": "4px"}),
                        html.Div([html.Span("Período B", className="text-muted small"), html.Span(label_b, className="float-end fw-bold text-dark small")], className="mb-1"),
                        dbc.Progress(value=val_b_pct, color="#32a852", className="mb-2", style={"height": "4px"}),
                        html.H6(html.Span(pct_change_str, className=f"text-{color} mt-2 d-block text-end fw-bold"))
                    ], className="p-3")
                ], className="shadow-sm border mb-3")

        top_row = dbc.Row([
            dbc.Col(create_comparison_card("Ingresos Totales", data_a['total_revenue'], data_b['total_revenue'], "${:,.2f}"), xs=12, lg=8),
            dbc.Col(create_comparison_card("Ticket Promedio", data_a['avg_ticket'], data_b['avg_ticket'], "${:,.2f}"), xs=12, lg=4)
        ])

        col_width = {"xs": 12, "md": 6, "xl": 3}

        bottom_rows_layout = [
            dbc.Col([
                html.H6("Volumen", className="mb-3 text-center text-muted fw-bold text-uppercase"),
                create_comparison_card("Número de Ventas", data_a['num_sales'], data_b['num_sales'], "{:,.0f}"),
                create_comparison_card("Unidades Vendidas", data_a['unidades_vendidas'], data_b['unidades_vendidas'], "{:,.0f}")
            ], **col_width),

            dbc.Col([
                html.H6("Costos", className="mb-3 text-center text-muted fw-bold text-uppercase"),
                create_comparison_card("Costo de Productos", data_a['total_cogs'], data_b['total_cogs'], "${:,.2f}", invert_colors=True),
                create_comparison_card("Gastos Operativos", data_a['total_expenses'], data_b['total_expenses'], "${:,.2f}", invert_colors=True)
            ], **col_width),
            
            dbc.Col([
                html.H6("Ganancias", className="mb-3 text-center text-muted fw-bold text-uppercase"),
                create_comparison_card("Ganancia Bruta", data_a['gross_profit'], data_b['gross_profit'], "${:,.2f}"),
                create_comparison_card("Ganancia Neta", data_a['net_profit'], data_b['net_profit'], "${:,.2f}")
            ], **col_width),

            dbc.Col([
                html.H6("Márgenes", className="mb-3 text-center text-muted fw-bold text-uppercase"),
                create_comparison_card("Margen Bruto", data_a['gross_margin'], data_b['gross_margin'], "{:.2f}", is_percent=True),
                create_comparison_card("Margen Neto", data_a['net_margin'], data_b['net_margin'], "{:.2f}", is_percent=True)
            ], **col_width)
        ]
        
        products_df = load_products(user_id)
        
        def create_top_products_chart(sales_df, title, color_hex):
            if sales_df.empty:
                return px.bar(title=title).update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
            merged = pd.merge(sales_df, products_df, on='product_id')
            top_5 = merged.groupby('name')['quantity'].sum().nlargest(5).sort_values(ascending=True)
            fig = px.bar(top_5, x=top_5.values, y=top_5.index, orientation='h', title=title, text_auto=True)
            fig.update_traces(marker_color=color_hex, textposition='outside')
            fig.update_layout(
                plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                font=dict(family="Poppins, sans-serif"), margin=dict(l=20, r=50, t=50, b=20),
                xaxis=dict(showgrid=False, showticklabels=False, title=None), yaxis=dict(showgrid=False, title=None), height=350
            )
            return fig

        fig_a = create_top_products_chart(data_a['sales_df'], "Top 5 Productos (Período A)", "#95a5a6")
        fig_b = create_top_products_chart(data_b['sales_df'], "Top 5 Productos (Período B)", "#32a852")

        return top_row, bottom_rows_layout, fig_a, fig_b
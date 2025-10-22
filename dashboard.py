from dash import dcc, html
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output
from dash.exceptions import PreventUpdate
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from datetime import date, timedelta
from flask_login import current_user

from app import app
from database import load_products, load_categories, load_expense_categories, calculate_financials

today = date.today()
start_of_month = today.replace(day=1)

def get_layout():
    return html.Div(className="p-4", children=[
        dbc.Row([
            dbc.Col(html.H4("Filtrar por Fecha:"), width='auto'),
            dbc.Col(
                dcc.DatePickerRange(
                    id='dashboard-date-picker',
                    start_date=start_of_month,
                    end_date=today,
                    display_format='YYYY-MM-DD',
                ),
            width=True),
            dbc.Col(
                dbc.Switch(
                    id="dashboard-see-all-switch",
                    label="Ver todo el historial",
                    value=True,
                ),
            width="auto")
        ], align="center", className="mb-4"),
        dbc.Row([
            dbc.Col([
                dbc.Row([
                    dbc.Col(dbc.Card(dbc.CardBody([html.H4("Ingresos Totales", className="card-title"), html.H2(id="kpi-total-revenue", style={'fontSize': '1.5rem'})])), width=3),
                    dbc.Col(dbc.Card(dbc.CardBody([html.H4("Ganancia Bruta", className="card-title"), html.H2(id="kpi-gross-profit", style={'fontSize': '1.5rem'})])), width=3),
                    dbc.Col(dbc.Card(dbc.CardBody([html.H4("Ganancia Neta", className="card-title"), html.H2(id="kpi-net-profit", style={'fontSize': '1.5rem'})])), width=3),
                    dbc.Col(dbc.Card(dbc.CardBody([html.H4("Inversión (Stock)", className="card-title"), html.H2(id="kpi-total-investment", style={'fontSize': '1.5rem'})])), width=3),
                ])
            ], width=8),
            dbc.Col(dbc.Card([dbc.CardHeader("Alertas de Stock Bajo"), dbc.CardBody(id="low-stock-alerts", style={"maxHeight": "95px", "overflowY": "auto"})]), width=4),
        ], align="center"),
        dbc.Row([
            dbc.Col(dcc.Graph(id="monthly-summary-chart"), width=8),
            dbc.Col(dcc.Graph(id="profit-vs-cogs-chart"), width=4),
        ], className="mt-4"),
        dbc.Row([
            dbc.Col(
                # --- INICIO CORRECCIÓN: Div para Scroll ---
                html.Div(
                    dcc.Graph(id="chart-sales-by-product"),
                    style={'overflowX': 'auto', 'width': '100%'}
                ),
                # --- FIN CORRECCIÓN ---
                width=6
            ),
            dbc.Col(
                # --- INICIO CORRECCIÓN: Div para Scroll ---
                html.Div(
                    dcc.Graph(id="revenue-by-category-chart"),
                    style={'overflowX': 'auto', 'width': '100%'}
                ),
                # --- FIN CORRECCIÓN ---
                width=6
            ),
        ], className="mt-4"),

        dbc.Row([dbc.Col(dcc.Graph(id="sales-over-time-chart"), width=12)], className="mt-4")
    ])

def register_callbacks(app):
    @app.callback(
        Output('kpi-total-revenue', 'children'), Output('kpi-gross-profit', 'children'),
        Output('kpi-net-profit', 'children'), Output('kpi-total-investment', 'children'),
        Output('low-stock-alerts', 'children'), Output('monthly-summary-chart', 'figure'),
        Output('profit-vs-cogs-chart', 'figure'), Output('chart-sales-by-product', 'figure'),
        Output('revenue-by-category-chart', 'figure'), Output('sales-over-time-chart', 'figure'),
        Output('dashboard-date-picker', 'disabled'),
        [Input('dashboard-date-picker', 'start_date'),
         Input('dashboard-date-picker', 'end_date'),
         Input('dashboard-see-all-switch', 'value'),
         Input('store-data-signal', 'data')]
    )
    def update_dashboard_data(start_date, end_date, see_all, signal_data):
        if not current_user.is_authenticated or not all([start_date, end_date]):
            raise PreventUpdate

        user_id = current_user.id
        
        results = calculate_financials(start_date, end_date, user_id, see_all=see_all)
        
        sales_df = results['sales_df']
        expenses_df = results['expenses_df']
        merged_df = results['merged_df']
        total_revenue = results['total_revenue']
        gross_profit = results['gross_profit']
        total_cogs = results['total_cogs']
        net_profit = results['net_profit']
        date_picker_disabled = see_all
        
        products_df = load_products(user_id)
        categories_df = load_categories(user_id)
        
        products_with_cat_names = pd.merge(products_df, categories_df, on='category_id', how='left')
        total_investment = (products_with_cat_names['cost'] * products_with_cat_names['stock']).sum() if not products_with_cat_names.empty else 0

        # Inicializar figuras
        fig_profit_pie = go.Figure(go.Pie(labels=[], values=[])).update_layout(title_text="Composición de Ingresos", height=400)
        fig_sales_by_prod = px.bar(title="Ingresos por Producto", height=400)
        fig_revenue_by_cat = px.bar(title="Ingresos por Categoría", height=400)
        fig_sales_over_time = px.line(title="Ingresos por Día", height=400)
        fig_monthly = px.bar(title="Resumen Financiero Mensual", height=400)

        if not sales_df.empty:
            pie_data = pd.DataFrame([{'tipo': 'Ganancia Bruta', 'monto': gross_profit}, {'tipo': 'Costo de Venta', 'monto': total_cogs}])
            fig_profit_pie = px.pie(pie_data, names='tipo', values='monto', title="Ingresos vs Costo de Productos", height=400)
            fig_profit_pie.update_traces(marker=dict(colors=["#64ec64", "#ec5858"]))
            fig_profit_pie.update_layout(
                legend=dict(orientation="h", yanchor="top", y=-0.3, xanchor="center", x=0.5, traceorder="reversed"),
                margin=dict(l=20, r=20, t=50, b=20)
            )
        
        if not merged_df.empty:
            revenue_by_product = merged_df.groupby('name')['total_amount'].sum().reset_index()
            merged_df_with_cat = pd.merge(merged_df, categories_df, on='category_id', how='left').rename(columns={'name_y': 'category_name'})
            revenue_by_category = merged_df_with_cat.groupby('category_name')['total_amount'].sum().reset_index()

            # --- INICIO CORRECCIÓN ---
            # 1. QUITAR cálculo de Y máximo. Cada gráfico tendrá su escala.

            # 2. Calcular ancho mínimo para scroll (Aumentar un poco por etiqueta)
            num_products = len(revenue_by_product)
            num_categories = len(revenue_by_category)
            # Aumentamos a 70px por barra para dar más espacio a etiquetas horizontales
            min_width_prod = max(400, num_products * 70) 
            min_width_cat = max(400, num_categories * 70) 

            # 3. Crear y actualizar figura PRODUCTOS
            fig_sales_by_prod = px.bar(revenue_by_product, x='name', y='total_amount', title="Ingresos por Producto",
                                         labels={'name': 'Producto', 'total_amount': 'Ingresos'}, height=400)
            fig_sales_by_prod.update_layout(
                # QUITAR yaxis_range para escala automática
                xaxis_tickangle=0, # Etiquetas horizontales
                # Aumentar margen inferior para que quepan las etiquetas
                margin=dict(l=20, r=20, t=40, b=80), 
                xaxis={'categoryorder':'total descending'}, # Ordenar barras
                width=min_width_prod # Establecer ancho para scroll
            )
            
            # 4. Crear y actualizar figura CATEGORÍAS
            fig_revenue_by_cat = px.bar(revenue_by_category, x='category_name', y='total_amount', title="Ingresos por Categoría",
                                         labels={'category_name': 'Categoría', 'total_amount': 'Ingresos'}, height=400)
            fig_revenue_by_cat.update_layout(
                # QUITAR yaxis_range para escala automática
                xaxis_tickangle=0, # Etiquetas horizontales
                # Aumentar margen inferior
                margin=dict(l=20, r=20, t=40, b=80), 
                width=min_width_cat # Establecer ancho para scroll
            )
            # --- FIN CORRECCIÓN ---

            # ... (código del gráfico de línea) ...
            
            sales_by_day = merged_df.groupby(merged_df['sale_date'].dt.date)['total_amount'].sum().reset_index()
            fig_sales_over_time = px.line(sales_by_day, x='sale_date', y='total_amount', title='Ingresos por Día',
                                              labels={'sale_date': 'Fecha', 'total_amount': 'Ingresos'}, markers=True, height=400)
            fig_sales_over_time.update_xaxes(
                            rangeselector=dict(
                                buttons=list([
                                    dict(count=1, label="1m", step="month", stepmode="backward"),
                                    dict(count=6, label="6m", step="month", stepmode="backward"),
                                    dict(count=1, label="YTD", step="year", stepmode="todate"),
                                    dict(step="all", label="Todo")
                                ])
                            )
                        )

        # --- INICIO DE LA CORRECCIÓN ---
        if not sales_df.empty:
            sales_monthly = sales_df.resample('ME', on='sale_date').agg(Ingresos=('total_amount', 'sum'), COGS=('cogs_total', 'sum')).reset_index()
            sales_monthly['month'] = sales_monthly['sale_date'].dt.to_period('M')
        else:
            # Si no hay ventas, crea un DataFrame vacío con las columnas esperadas
            sales_monthly = pd.DataFrame(columns=['sale_date', 'Ingresos', 'COGS', 'month'])
        # --- FIN DE LA CORRECCIÓN ---
            
        expenses_monthly = pd.DataFrame()
        if not expenses_df.empty:
            # Remuestrear gastos directamente. No necesitamos categorías para sumar el total.
            expenses_monthly = expenses_df.resample('ME', on='expense_date').agg(Gastos=('amount', 'sum')).reset_index()
            expenses_monthly['month'] = expenses_monthly['expense_date'].dt.to_period('M')
        else:
            # Si no hay gastos, crea un DataFrame vacío con las columnas esperadas
            expenses_monthly = pd.DataFrame(columns=['expense_date', 'Gastos', 'month'])

        summary_df = pd.merge(sales_monthly, expenses_monthly, on='month', how='outer').fillna(0)

        if not summary_df.empty:
            for col in ['Ingresos', 'COGS', 'Gastos']:
                if col not in summary_df.columns:
                    summary_df[col] = 0

            summary_df['Ganancia Neta'] = summary_df['Ingresos'] - summary_df['COGS'] - summary_df['Gastos']
            summary_df['month'] = summary_df['month'].astype(str)

            plot_df = pd.melt(summary_df, id_vars=['month'], value_vars=['COGS', 'Gastos', 'Ganancia Neta'], var_name='Tipo', value_name='Monto')
            plot_df['Tipo'] = plot_df['Tipo'].replace({'COGS': 'Costo de Venta'})
            fig_monthly = px.bar(plot_df, x='month', y='Monto', color='Tipo', title="Resumen Financiero Mensual", labels={'month': 'Mes'},
                                     color_discrete_map={'Costo de Venta': "#ec9f58", 'Gastos': "#ec5858", 'Ganancia Neta': "#64ec64"}, height=400)
            fig_monthly.update_layout(
                barmode='relative',
                legend=dict(orientation="h", yanchor="top", y=-0.2, xanchor="center", x=0.5),
                margin=dict(l=25, r=25, t=50, b=0)
            )
            fig_monthly.update_xaxes(type='category')

        low_stock_products = products_df[products_df['stock'] <= products_df['alert_threshold']]
        alerts = dbc.ListGroupItem("¡Todo en orden!", color="success") if low_stock_products.empty else \
                 dbc.ListGroup([dbc.ListGroupItem(f"{row['name']} (Stock: {row['stock']})", color="danger") for _, row in low_stock_products.iterrows()])

        return (f"${total_revenue:,.2f}", f"${gross_profit:,.2f}", f"${net_profit:,.2f}",
                f"${total_investment:,.2f}", alerts, fig_monthly, fig_profit_pie,
                fig_sales_by_prod, fig_revenue_by_cat, fig_sales_over_time, date_picker_disabled)
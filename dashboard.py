from dash import dcc, html
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output
from dash.exceptions import PreventUpdate
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from datetime import date, timedelta

# Importar la app y las funciones de la base de datos
from app import app
from database import load_sales, load_expenses, load_products, load_categories, load_expense_categories

# --- Valores por defecto para fechas ---
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
            dbc.Col(dcc.Graph(id="chart-sales-by-product"), width=6),
            dbc.Col(dcc.Graph(id="revenue-by-category-chart"), width=6),
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
         Input('store-data-signal', 'data')]  # ### CAMBIO: Se añade el "avisador" como Input ###
    )
    def update_dashboard_data(start_date, end_date, see_all, signal_data): # ### CAMBIO: Se añade el argumento ###
        # El resto de la función es idéntica, no necesita cambios.
        all_sales_df = load_sales()
        all_expenses_df = load_expenses()
        products_df = load_products()
        categories_df = load_categories()

        all_sales_df['sale_date'] = pd.to_datetime(all_sales_df['sale_date'])
        all_expenses_df['expense_date'] = pd.to_datetime(all_expenses_df['expense_date'])

        if see_all:
            sales_df = all_sales_df
            expenses_df = all_expenses_df
            date_picker_disabled = True
        else:
            end_date_inclusive = pd.to_datetime(end_date) + timedelta(days=1)
            sales_df = all_sales_df[(all_sales_df['sale_date'] >= start_date) & (all_sales_df['sale_date'] < end_date_inclusive)]
            expenses_df = all_expenses_df[(all_expenses_df['expense_date'] >= start_date) & (all_expenses_df['expense_date'] < end_date_inclusive)]
            date_picker_disabled = False
        
        products_with_cat_names = pd.merge(products_df, categories_df, on='category_id', how='left').rename(
            columns={'name_y': 'category_name', 'name_x': 'product_name'}
        )

        total_revenue, gross_profit, total_cogs, sales_monthly = 0, 0, 0, pd.DataFrame()
        total_investment = (products_with_cat_names['cost'] * products_with_cat_names['stock']).sum()
        total_expenses = expenses_df['amount'].sum() if not expenses_df.empty else 0

        fig_profit_pie = go.Figure(go.Pie(labels=[], values=[])).update_layout(title_text="Composición de Ingresos", height=400)
        fig_sales_by_prod = px.bar(title="Ingresos por Producto", height=400)
        fig_revenue_by_cat = px.bar(title="Ingresos por Categoría", height=400)
        fig_sales_over_time = px.line(title="Ingresos por Día", height=400)

        if not sales_df.empty:
            merged_df = pd.merge(sales_df, products_with_cat_names, on='product_id', how='left')
            merged_df.dropna(subset=['cost'], inplace=True)
            merged_df['cogs'] = merged_df['cost'] * merged_df['quantity']
            total_cogs = merged_df['cogs'].sum()
            total_revenue = merged_df['total_amount'].sum()
            gross_profit = total_revenue - total_cogs
            pie_data = pd.DataFrame([{'tipo': 'Ganancia Bruta', 'monto': gross_profit}, {'tipo': 'Costo de Productos', 'monto': total_cogs}])
            fig_profit_pie = px.pie(pie_data, names='tipo', values='monto', title="Ingresos vs Costo de Productos", height=400)
            fig_profit_pie.update_traces(marker=dict(colors=["#64ec64", "#ec5858"]))
            fig_profit_pie.update_layout(
                barmode='relative',
                legend=dict(orientation="h", yanchor="top", y=-0.3, xanchor="center", x=0.5),
                margin=dict(l=20, r=20, t=50, b=0)
            )

            revenue_by_product = merged_df.groupby('product_name')['total_amount'].sum().reset_index()
            fig_sales_by_prod = px.bar(revenue_by_product, x='product_name', y='total_amount', title="Ingresos por Producto",
                                         labels={'product_name': 'Producto', 'total_amount': 'Ingresos'}, height=400)
            fig_sales_by_prod.update_xaxes(categoryorder='total descending')
            fig_sales_by_prod.update_layout(
                margin=dict(l=20, r=5, t=40, b=120),
                xaxis_tickangle=-45
            )
            
            revenue_by_category = merged_df.groupby('category_name')['total_amount'].sum().reset_index()
            fig_revenue_by_cat = px.bar(revenue_by_category, x='category_name', y='total_amount', title="Ingresos por Categoría",
                                         labels={'category_name': 'Categoría', 'total_amount': 'Ingresos'}, height=400)
            fig_revenue_by_cat.update_xaxes(categoryorder='total descending')
            fig_revenue_by_cat.update_layout(
                margin=dict(l=20, r=5, t=40, b=120),
                xaxis_tickangle=-45
            )
            sales_by_day = merged_df.groupby(merged_df['sale_date'].dt.date)['total_amount'].sum().reset_index()
            fig_sales_over_time = px.line(sales_by_day, x='sale_date', y='total_amount', title='Ingresos por Día',
                                              labels={'sale_date': 'Fecha', 'total_amount': 'Ingresos'}, markers=True, height=400)
            fig_sales_over_time.update_xaxes(
                tickformat="%Y-%m-%d",
                rangeselector=dict(
                    buttons=list([
                        dict(count=1, label="1m", step="month", stepmode="backward"),
                        dict(count=6, label="6m", step="month", stepmode="backward"),
                        dict(count=1, label="YTD", step="year", stepmode="todate"),
                        dict(step="all", label="Todo")
                    ])
                )
            )
            sales_monthly = merged_df.set_index('sale_date').resample('ME').agg(Ingresos=('total_amount', 'sum'), COGS=('cogs', 'sum')).reset_index()
            sales_monthly['month'] = sales_monthly['sale_date'].dt.to_period('M')

        net_profit = gross_profit - total_expenses
        expenses_monthly = pd.DataFrame()
        if not expenses_df.empty:
            expense_cat_df = load_expense_categories()
            expenses_with_names = pd.merge(expenses_df, expense_cat_df, on='expense_category_id', how='left')
            expenses_with_names['expense_date'] = pd.to_datetime(expenses_with_names['expense_date'])
            expenses_monthly = expenses_with_names.set_index('expense_date').resample('ME')['amount'].sum().reset_index().rename(columns={'amount': 'Gastos'})
            expenses_monthly['month'] = expenses_monthly['expense_date'].dt.to_period('M')

        if sales_monthly.empty and expenses_monthly.empty:
            summary_df = pd.DataFrame()
        elif sales_monthly.empty:
            summary_df = expenses_monthly
        elif expenses_monthly.empty:
            summary_df = sales_monthly
        else:
            summary_df = pd.merge(sales_monthly, expenses_monthly, on='month', how='outer')

        if not summary_df.empty:
            summary_df = summary_df.fillna(0)
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
        else:
            fig_monthly = px.bar(title="Resumen Financiero Mensual", height=400)

        low_stock_products = products_df[products_df['stock'] <= products_df['alert_threshold']]
        alerts = dbc.ListGroupItem("¡Todo en orden!", color="success") if low_stock_products.empty else \
                 dbc.ListGroup([dbc.ListGroupItem(f"{row['name']} (Stock: {row['stock']})", color="danger") for _, row in low_stock_products.iterrows()])

        return (f"${total_revenue:,.2f}", f"${gross_profit:,.2f}", f"${net_profit:,.2f}",
                f"${total_investment:,.2f}", alerts, fig_monthly, fig_profit_pie,
                fig_sales_by_prod, fig_revenue_by_cat, fig_sales_over_time, date_picker_disabled)
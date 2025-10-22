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
                    # --- Force line breaks in H4 titles ---
                    dbc.Col(dbc.Card(dbc.CardBody([
                        # Replace string with list + html.Br()
                        html.H4(["Ingresos", html.Br(), "Totales"], className="card-title"),
                        html.H2(id="kpi-total-revenue", style={'fontSize': '1.5rem'}) # Removed mt-auto/flex-grow-1
                    ]), # Removed flex classes from CardBody
                    style={'height': '120px'}), width=3),

                    dbc.Col(dbc.Card(dbc.CardBody([
                        # Replace string with list + html.Br()
                        html.H4(["Ganancia", html.Br(), "Bruta"], className="card-title"),
                        html.H2(id="kpi-gross-profit", style={'fontSize': '1.5rem'}) # Removed mt-auto/flex-grow-1
                    ]), # Removed flex classes from CardBody
                    style={'height': '120px'}), width=3),

                    dbc.Col(dbc.Card(dbc.CardBody([
                         # Replace string with list + html.Br()
                        html.H4(["Ganancia", html.Br(), "Neta"], className="card-title"),
                        html.H2(id="kpi-net-profit", style={'fontSize': '1.5rem'}) # Removed mt-auto/flex-grow-1
                    ]), # Removed flex classes from CardBody
                    style={'height': '120px'}), width=3),

                    dbc.Col(dbc.Card(dbc.CardBody([
                         # Replace string with list + html.Br()
                        html.H4(["Inversión", html.Br(), "(Stock)"], className="card-title"),
                        html.H2(id="kpi-total-investment", style={'fontSize': '1.5rem'}) # Removed mt-auto/flex-grow-1
                    ]), # Removed flex classes from CardBody
                    style={'height': '120px'}), width=3),
                    # --- End forced line breaks ---
                ])
            ], width=8),
            dbc.Col(dbc.Card([dbc.CardHeader("Alertas de Stock Bajo"), dbc.CardBody(id="low-stock-alerts", style={"maxHeight": "95px", "overflowY": "auto"})]), width=4),
        ], align="center"),
        dbc.Row([
            dbc.Col(dcc.Graph(id="monthly-summary-chart"), width=8),
            dbc.Col(dcc.Graph(id="waterfall-profit-summary"), width=4),
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

# dashboard.py
# ... (Importaciones existentes) ...
import plotly.graph_objects as go # Asegúrate de que go esté importado

# ... (Definición de get_layout, con el ID ya cambiado) ...

def register_callbacks(app):
    @app.callback(
        # --- CORREGIDO: Cambiado Output del pie chart al waterfall chart ---
        Output('kpi-total-revenue', 'children'), Output('kpi-gross-profit', 'children'),
        Output('kpi-net-profit', 'children'), Output('kpi-total-investment', 'children'),
        Output('low-stock-alerts', 'children'), Output('monthly-summary-chart', 'figure'),
        Output('waterfall-profit-summary', 'figure'), # <-- Cambiado ID
        Output('chart-sales-by-product', 'figure'),
        Output('revenue-by-category-chart', 'figure'),
        Output('sales-over-time-chart', 'figure'),
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
        total_expenses = results['total_expenses'] # Necesitamos gastos para el waterfall
        net_profit = results['net_profit']
        date_picker_disabled = see_all

        products_df = load_products(user_id)
        categories_df = load_categories(user_id)
        products_with_cat_names = pd.merge(products_df, categories_df, on='category_id', how='left')
        total_investment = (products_with_cat_names['cost'] * products_with_cat_names['stock']).sum() if not products_with_cat_names.empty else 0

# --- Waterfall Chart ---
# --- Waterfall Chart ---

        # --- START WORKAROUND for first bar color ---
        # Add a dummy start point at 0
        waterfall_x = ["Inicio", "Ingresos", "Costo Ventas (COGS)", "Gastos Op.", "Ganancia Neta"]
        # Start absolute, Ingresos now relative, rest same, end total
        waterfall_measures = ["absolute", "relative", "relative", "relative", "total"]
        # Values: Start at 0, add revenue, subtract costs/expenses
        waterfall_y = [0, total_revenue, -total_cogs, -total_expenses, net_profit]
        # Text: Empty for start, then values
        waterfall_text = ["", f"${total_revenue:,.2f}", f"${total_cogs:,.2f}", f"${total_expenses:,.2f}", f"${net_profit:,.2f}"]
        # --- END WORKAROUND ---

        net_profit_color = "limegreen" if net_profit >= 0 else "firebrick"

        fig_waterfall = go.Figure(go.Waterfall(
            name = "P&L", orientation = "v",
            measure = waterfall_measures,
            x = waterfall_x,
            textposition = "outside",
            text = waterfall_text,
            y = waterfall_y,
            # Make the text of the "Inicio" bar invisible
            textfont_color = ['rgba(0,0,0,0)', 'black', 'black', 'black', 'black'],
            connector = {"line":{"color":"rgb(63, 63, 63)"}},

            # Colors should now work: Ingresos is positive 'relative'
            increasing = {"marker": {"color": "royalblue"}},
            decreasing = {"marker": {"color": "firebrick"}},
            totals     = {"marker": {"color": net_profit_color}}
        ))
        fig_waterfall.update_layout(
                title="Resumen P&L",
                waterfallgap = 0.3,
                height=400,
                # --- CORRECCIÓN: Reducir margen izquierdo ---
                margin=dict(l=0, r=0, t=50, b=20),
                # --- FIN CORRECCIÓN ---
                xaxis=dict(
                    tickmode='array',
                    tickvals=waterfall_x[0:], 
                    ticktext=waterfall_x[0:]
                ),
                shapes=[ # Línea Cero
                    dict(
                        type='line', xref='paper', x0=0, x1=1,
                        yref='y', y0=0, y1=0,
                        line=dict(color='Gray', width=1, dash='dash')
                    )
                ]
        )
        min_y = min(0, net_profit)
        # Max Y needs to consider the base revenue now explicitly
        max_y = max(total_revenue, gross_profit, net_profit, 0) # Include 0
        padding_y = (max_y - min_y) * 0.1 if max_y > min_y else 50
        fig_waterfall.update_yaxes(range=[min_y - padding_y, max_y + padding_y])

        # ... rest of the callback logic ...
        # ... rest of the callback logic ...
        # --- Inicializar figuras de barras ---
        fig_sales_by_prod = px.bar(title="Ingresos por Producto", height=400)
        fig_revenue_by_cat = px.bar(title="Ingresos por Categoría", height=400)
        fig_sales_over_time = px.line(title="Ingresos por Día", height=400)
        fig_monthly = px.bar(title="Resumen Financiero Mensual", height=400)

# ... (code before the bar charts) ...

        if not merged_df.empty:
            revenue_by_product = merged_df.groupby('name')['total_amount'].sum().reset_index()
            merged_df_with_cat = pd.merge(merged_df, categories_df, on='category_id', how='left').rename(columns={'name_y': 'category_name'})
            revenue_by_category = merged_df_with_cat.groupby('category_name')['total_amount'].sum().reset_index()

            # --- CORRECCIÓN: Remover height y width fijos ---

            # Actualizar figura PRODUCTOS
            fig_sales_by_prod = px.bar(revenue_by_product, x='name', y='total_amount', title="Ingresos por Producto",
                                         labels={'name': 'Producto', 'total_amount': 'Ingresos'}) # <-- height=400 REMOVIDO
            fig_sales_by_prod.update_layout(
                xaxis_tickangle=-45,
                margin=dict(l=20, r=20, t=40, b=100),
                xaxis={'categoryorder':'total descending'}
                # width=min_width_prod # <-- REMOVIDO
            )

            # Ordenar Categorías y actualizar figura CATEGORÍAS
            revenue_by_category = revenue_by_category.sort_values(by='total_amount', ascending=False)
            fig_revenue_by_cat = px.bar(revenue_by_category, x='category_name', y='total_amount', title="Ingresos por Categoría",
                                         labels={'category_name': 'Categoría', 'total_amount': 'Ingresos'}) # <-- height=400 REMOVIDO
            fig_revenue_by_cat.update_layout(
                xaxis_tickangle=-45,
                margin=dict(l=20, r=20, t=40, b=100)
                # width=min_width_cat # <-- REMOVIDO
            )
            # --- FIN CORRECCIÓN ---

            # Gráfico de Línea (sin cambios)
            # ... (código existente para fig_sales_over_time) ...

        # ... (código restante del callback: Resumen Mensual, Alertas, return) ...
            # --- FIN CORRECCIÓN ---

            # Gráfico de Línea (sin cambios)
# Gráfico de Línea (sin cambios)
            sales_by_day = merged_df.groupby(merged_df['sale_date'].dt.date)['total_amount'].sum().reset_index()
            fig_sales_over_time = px.line(sales_by_day, x='sale_date', y='total_amount', title='Ingresos por Día',
                                              labels={'sale_date': 'Fecha', 'total_amount': 'Ingresos'}, markers=True, height=400)
            fig_sales_over_time.update_xaxes(
                tickformat="%Y-%m-%d",
                # --- START CORRECTION: Restore rangeselector dictionary ---
                rangeselector=dict(
                    buttons=list([
                        dict(count=1, label="1m", step="month", stepmode="backward"),
                        dict(count=6, label="6m", step="month", stepmode="backward"),
                        dict(count=1, label="YTD", step="year", stepmode="todate"),
                        dict(step="all", label="Todo")
                    ])
                )
                # --- END CORRECTION ---
            )

        # Resumen Mensual (sin cambios)
        if not sales_df.empty:
             sales_monthly = sales_df.resample('ME', on='sale_date').agg(Ingresos=('total_amount', 'sum'), COGS=('cogs_total', 'sum')).reset_index()
             sales_monthly['month'] = sales_monthly['sale_date'].dt.to_period('M')
        else:
             sales_monthly = pd.DataFrame(columns=['sale_date', 'Ingresos', 'COGS', 'month'])

        if not expenses_df.empty:
            expenses_monthly = expenses_df.resample('ME', on='expense_date').agg(Gastos=('amount', 'sum')).reset_index()
            expenses_monthly['month'] = expenses_monthly['expense_date'].dt.to_period('M')
        else:
            expenses_monthly = pd.DataFrame(columns=['expense_date', 'Gastos', 'month'])

        summary_df = pd.merge(sales_monthly.drop(columns=['sale_date']),
                              expenses_monthly.drop(columns=['expense_date']),
                              on='month', how='outer').fillna(0)

        if not summary_df.empty:
            for col in ['Ingresos', 'COGS', 'Gastos']:
                if col not in summary_df.columns: summary_df[col] = 0

            # 1. Renombrar 'Ganancia Neta' a 'P&L' en el resumen
            summary_df['P&L'] = summary_df['Ingresos'] - summary_df['COGS'] - summary_df['Gastos'] # Usar P&L como nombre de columna
            summary_df['month'] = summary_df['month'].astype(str)

            # 2. Preparar datos para graficar (melt)
            plot_df = pd.melt(summary_df,
                              id_vars=['month'],
                              # Incluir P&L en lugar de Ganancia Neta
                              value_vars=['COGS', 'Gastos', 'P&L'],
                              var_name='Tipo', value_name='Monto')
            plot_df['Tipo'] = plot_df['Tipo'].replace({'COGS': 'Costo de Venta'})

            # --- INICIO CORRECCIÓN ---
            # 3. Crear columna para colores condicionales de P&L
            def assign_pnl_category(row):
                if row['Tipo'] == 'P&L':
                    return 'P&L Positivo' if row['Monto'] >= 0 else 'P&L Negativo'
                return row['Tipo'] # Devolver el tipo original para COGS y Gastos

            plot_df['Tipo_Color'] = plot_df.apply(assign_pnl_category, axis=1)

            # 4. Definir el mapa de colores para las nuevas categorías
            color_map = {
                'Costo de Venta': "#ec9f58",
                'Gastos': "#ec5858",
                'P&L Positivo': "#64ec64",  # Verde original
                'P&L Negativo': "#A84848"   # Rojo Oscuro (DarkRed)
            }

            # 5. Crear el gráfico usando la nueva columna 'Tipo_Color'
            fig_monthly = px.bar(plot_df, x='month', y='Monto',
                                 # Usar la columna auxiliar para el color
                                 color='Tipo_Color',
                                 title="Resumen Financiero Mensual",
                                 labels={'month': 'Mes', 'Tipo_Color': 'Tipo'}, # Etiqueta de leyenda general
                                 # Pasar el nuevo mapa de colores
                                 color_discrete_map=color_map,
                                 height=400)

            # 6. Ajustar nombres en la leyenda (opcional pero recomendado)
            # Renombrar 'P&L Positivo' y 'P&L Negativo' a solo 'P&L' para una leyenda más limpia
            # Esto requiere manipular los datos de la figura directamente
            fig_monthly.for_each_trace(lambda t: t.update(name=t.name.replace(' Positivo', '').replace(' Negativo', '')))

            # Mantener otros ajustes de layout
            fig_monthly.update_layout(
                barmode='relative',
                legend=dict(orientation="h", yanchor="top", y=-0.2, xanchor="center", x=0.5),
                margin=dict(l=25, r=25, t=50, b=0)
            )
            fig_monthly.update_xaxes(type='category')

        # Alertas de Stock Bajo (sin cambios)
        low_stock_products = products_df[products_df['stock'] <= products_df['alert_threshold']]
        alerts = dbc.ListGroupItem("¡Todo en orden!", color="success") if low_stock_products.empty else \
                 dbc.ListGroup([dbc.ListGroupItem(f"{row['name']} (Stock: {row['stock']})", color="danger") for _, row in low_stock_products.iterrows()])

        # --- CORREGIDO: Devolver fig_waterfall en lugar de fig_profit_pie ---
        return (f"${total_revenue:,.2f}", f"${gross_profit:,.2f}", f"${net_profit:,.2f}",
                f"${total_investment:,.2f}", alerts, fig_monthly, fig_waterfall, # <-- Cambiado aquí
                    fig_sales_by_prod, fig_revenue_by_cat, fig_sales_over_time, date_picker_disabled)
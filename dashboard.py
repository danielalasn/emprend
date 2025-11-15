# dashboard.py
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
from database import load_products, load_categories, load_expense_categories, calculate_financials, load_raw_materials

today = date.today()
start_of_month = today.replace(day=1)

def get_layout():
    # Estilo común para las tarjetas de KPIs
    card_style = {"border": "none", "borderRadius": "10px"}
    
    return html.Div(className="p-2 p-md-4", children=[ 
        
        # --- FILA 1: FILTRO DE FECHA ---
        dbc.Row([
            dbc.Col(html.H4("Dashboard General", className="fw-bold text-secondary"), xs=12, md='auto', className="mb-2 mb-md-0"),
            
            dbc.Col(
                dcc.DatePickerRange(
                    id='dashboard-date-picker',
                    start_date=start_of_month,
                    end_date=today,
                    display_format='YYYY-MM-DD',
                    style={'fontSize': '14px'},
                    className="w-100" 
                ),
            xs=12, md=True, className="ps-md-4 mb-2 mb-md-0"),
            
            dbc.Col(
                dbc.Switch(
                    id="dashboard-see-all-switch",
                    label="Ver histórico completo",
                    value=True,
                    className="text-muted small"
                ),
            xs=12, md="auto")
        ], align="center", className="mb-4"),

        # --- FILA 2: KPIs FINANCIEROS ---
        # align="stretch" iguala la altura de las COLUMNAS.
        # g-3 maneja el espaciado horizontal Y vertical automáticamente.
        dbc.Row([
            # 1. Ingresos
            dbc.Col(dbc.Card([
                dbc.CardBody([
                    html.H6("Ingresos Totales", className="card-subtitle text-muted mb-2 small text-uppercase fw-bold"),
                    html.H2(id="kpi-total-revenue", className="card-title fw-bold text-dark")
                ], className="flex-grow-1 p-3") # flex-grow-1 llena el espacio vacío
            ], className="h-100 d-flex flex-column shadow-sm", style=card_style), xs=12, sm=6, lg=3),

            # 2. Ganancia Bruta
            dbc.Col(dbc.Card([
                dbc.CardBody([
                    html.H6("Ganancia Bruta", className="card-subtitle text-muted mb-2 small text-uppercase fw-bold"),
                    html.H2(id="kpi-gross-profit", className="card-title fw-bold text-success")
                ], className="flex-grow-1 p-3")
            ], className="h-100 d-flex flex-column shadow-sm", style=card_style), xs=12, sm=6, lg=3),

            # 3. Gastos
            dbc.Col(dbc.Card([
                dbc.CardBody([
                    html.H6("Gastos Operativos", className="card-subtitle text-muted mb-2 small text-uppercase fw-bold"),
                    html.H2(id="kpi-total-expenses", className="card-title fw-bold text-danger")
                ], className="flex-grow-1 p-3")
            ], className="h-100 d-flex flex-column shadow-sm", style=card_style), xs=12, sm=6, lg=3),

            # 4. Ganancia Neta
            dbc.Col(dbc.Card([
                dbc.CardBody([
                    html.H6("Ganancia Neta", className="card-subtitle text-muted mb-2 small text-uppercase fw-bold"),
                    html.H2(id="kpi-net-profit", className="card-title fw-bold") 
                ], className="flex-grow-1 p-3")
            ], className="h-100 d-flex flex-column shadow-sm", style=card_style), xs=12, sm=6, lg=3),
        ], className="mb-4 g-3", align="stretch"),

        # --- FILA 3: KPIs DE INVENTARIO Y ALERTAS ---
        dbc.Row([
            # KPI Inversión Productos
            dbc.Col(dbc.Card([
                dbc.CardBody([
                    html.H6("Inv. Productos", className="card-subtitle text-muted mb-2 small text-uppercase fw-bold"),
                    html.H3(id="kpi-product-investment", className="card-title fw-bold")
                ], className="flex-grow-1 p-3")
            ], className="h-100 d-flex flex-column shadow-sm", style=card_style), xs=12, sm=6, lg=3),

            # KPI Inversión Insumos
            dbc.Col(dbc.Card([
                dbc.CardBody([
                    html.H6("Inv. Insumos", className="card-subtitle text-muted mb-2 small text-uppercase fw-bold"),
                    html.H3(id="kpi-material-investment", className="card-title fw-bold")
                ], className="flex-grow-1 p-3")
            ], className="h-100 d-flex flex-column shadow-sm", style=card_style), xs=12, sm=6, lg=3),

            # Alertas Productos
            dbc.Col(dbc.Card([
                dbc.CardBody([
                    html.H6("Alertas Productos", className="card-subtitle text-muted mb-2 small text-uppercase fw-bold"),
                    html.Div(id="low-stock-alerts-products", style={"maxHeight": "60px", "overflowY": "auto", "fontSize": "0.85rem"})
                ], className="flex-grow-1 p-3")
            ], className="h-100 d-flex flex-column shadow-sm", style=card_style), xs=12, sm=6, lg=3),

            # Alertas Insumos
            dbc.Col(dbc.Card([
                dbc.CardBody([
                    html.H6("Alertas Insumos", className="card-subtitle text-muted mb-2 small text-uppercase fw-bold"),
                    html.Div(id="low-stock-alerts-materials", style={"maxHeight": "60px", "overflowY": "auto", "fontSize": "0.85rem"})
                ], className="flex-grow-1 p-3")
            ], className="h-100 d-flex flex-column shadow-sm", style=card_style), xs=12, sm=6, lg=3),
        ], className="mb-4 g-3", align="stretch"),

        # --- FILAS DE GRÁFICOS ---
        dbc.Row([
            dbc.Col(dbc.Card(dcc.Graph(id="monthly-summary-chart"), className="shadow-sm border-0 p-2"), xs=12, lg=8),
            dbc.Col(dbc.Card(dcc.Graph(id="waterfall-profit-summary"), className="shadow-sm border-0 p-2"), xs=12, lg=4),
        ], className="mb-4 g-3"),
        
        dbc.Row([
            dbc.Col(
                dbc.Card(
                    html.Div(dcc.Graph(id="chart-sales-by-product"), style={'overflowX': 'auto'}),
                    className="shadow-sm border-0 p-2"
                ), xs=12, md=6
            ),
            dbc.Col(
                dbc.Card(
                    html.Div(dcc.Graph(id="revenue-by-category-chart"), style={'overflowX': 'auto'}),
                    className="shadow-sm border-0 p-2"
                ), xs=12, md=6
            ),
        ], className="mb-4 g-3"),

        dbc.Row([
            dbc.Col(dbc.Card(dcc.Graph(id="sales-over-time-chart"), className="shadow-sm border-0 p-2"), width=12)
        ], className="mb-4")
    ])


def register_callbacks(app):
    @app.callback(
        Output('kpi-total-revenue', 'children'), 
        Output('kpi-gross-profit', 'children'),
        Output('kpi-total-expenses', 'children'), # <-- NUEVO OUTPUT
        Output('kpi-net-profit', 'children'),
        Output('kpi-net-profit', 'className'),    # <-- NUEVO OUTPUT (para el color)
        Output('kpi-product-investment', 'children'),   
        Output('kpi-material-investment', 'children'),  
        Output('low-stock-alerts-products', 'children'), 
        Output('low-stock-alerts-materials', 'children'),
        Output('monthly-summary-chart', 'figure'),
        Output('waterfall-profit-summary', 'figure'), 
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

        total_revenue = results['total_revenue']
        gross_profit = results['gross_profit']
        total_cogs = results['total_cogs']
        total_expenses = results['total_expenses']
        net_profit = results['net_profit']
        date_picker_disabled = see_all
        merged_df = results['merged_df']
        sales_df = results['sales_df']
        expenses_df = results['expenses_df']

        # Lógica de color para Ganancia Neta
        net_profit_class = "card-title fw-bold text-success" if net_profit >= 0 else "card-title fw-bold text-danger"

        # --- PRODUCTOS ---
        products_df = load_products(user_id)
        categories_df = load_categories(user_id)
        products_with_cat_names = pd.merge(products_df, categories_df, on='category_id', how='left')
        
        total_product_investment = (products_with_cat_names['cost'] * products_with_cat_names['stock']).sum() if not products_with_cat_names.empty else 0
        
        if 'is_active' in products_df.columns:
             # Convertir a booleanos reales por si vienen como 1/0 o True/False
             products_df['is_active'] = products_df['is_active'].astype(bool)
             
             low_stock_products = products_df[
                (products_df['stock'] <= products_df['alert_threshold']) & 
                (products_df['alert_threshold'] > 0) &
                (products_df['is_active'] == True) # <--- FILTRO AÑADIDO
            ]
        else:
             # Fallback por si la columna no existe (aunque update_tables ya la creó)
             low_stock_products = products_df[
                (products_df['stock'] <= products_df['alert_threshold']) & 
                (products_df['alert_threshold'] > 0)
            ]


        if low_stock_products.empty:
            product_alerts = html.Div([html.I(className="fas fa-check-circle text-success me-2"), "Todo en orden"], className="text-success small")
        else:
            product_alerts = dbc.ListGroup(
                [dbc.ListGroupItem(
                    f"{row['name']} ({row['stock']})", 
                    color="danger", 
                    className="py-1 px-2 border-0 small"
                ) for _, row in low_stock_products.iterrows()],
                flush=True
            )

        # --- INSUMOS ---
        raw_materials_df = load_raw_materials(user_id)
        total_material_investment = 0
        
        if not raw_materials_df.empty:
            raw_materials_df['valor_stock'] = raw_materials_df['current_stock'] * raw_materials_df['average_cost']
            total_material_investment = raw_materials_df['valor_stock'].sum()
            
            low_stock_materials = raw_materials_df[
                (raw_materials_df['current_stock'] <= raw_materials_df['alert_threshold']) &
                (raw_materials_df['alert_threshold'] > 0)
            ]
            if low_stock_materials.empty:
                material_alerts = html.Div([html.I(className="fas fa-check-circle text-success me-2"), "Todo en orden"], className="text-success small")
            else:
                material_alerts = dbc.ListGroup(
                    [dbc.ListGroupItem(
                        f"{row['name']} ({float(row['current_stock']):.3g} {row['unit_measure']})", 
                        color="warning", 
                        className="py-1 px-2 border-0 small"
                    ) for _, row in low_stock_materials.iterrows()],
                    flush=True
                )
        else:
             material_alerts = html.Div("Sin datos", className="text-muted small")
        
        # --- ESTILOS GRÁFICOS ---
        layout_style = dict(
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            margin=dict(l=40, r=20, t=40, b=80), # Margen base
            font=dict(family="Poppins, sans-serif")
        )

# --- WATERFALL (SOLO MONTOS) ---
        waterfall_x = ["Inicio", "Ingresos", "Costo Ventas", "Gastos Op.", "Ganancia Neta"]
        waterfall_measures = ["absolute", "relative", "relative", "relative", "total"]
        
        waterfall_y = [0, total_revenue, -total_cogs, -total_expenses, net_profit]
        
        saldo_tras_costos = total_revenue - total_cogs 
        saldo_tras_gastos = saldo_tras_costos - total_expenses 

        # TEXTO: Ahora solo mostramos el dinero, sin títulos adicionales
        waterfall_text = [
            "", 
            f"${total_revenue:,.2f}",       # Antes decía "Ingresos<br>..."
            f"${saldo_tras_costos:,.2f}",    
            f"${saldo_tras_gastos:,.2f}",    
            f"${net_profit:,.2f}"           # Antes decía "Ganancia Neta<br>..."
        ]
        
        water_color = "#32a852" if net_profit >= 0 else "#dc3545"

        # DATOS PARA HOVER [Inicio, Fin, Total_de_la_barra]
        custom_tooltip_data = [
            [0, 0, 0],                                         
            [0, total_revenue, total_revenue],                 
            [total_revenue, saldo_tras_costos, total_cogs],    
            [saldo_tras_costos, saldo_tras_gastos, total_expenses], 
            [0, net_profit, net_profit]                        
        ]

        # PLANTILLAS DE HOVER (Mantenemos tu configuración deseada)
        hover_simple = "<b>%{x}</b><br>%{customdata[2]:$,.2f}<extra></extra>"
        
        hover_detailed = (
            "<b>%{x}</b><br>" +
            "Total: %{customdata[2]:$,.2f}<br>" +
            "Inicio: %{customdata[0]:$,.2f}<br>" +
            "Fin: %{customdata[1]:$,.2f}" +
            "<extra></extra>"
        )

        hover_templates_list = [
            hover_simple,    # Inicio
            hover_simple,    # Ingresos (Solo Total)
            hover_detailed,  # Costo Ventas (Detallado)
            hover_detailed,  # Gastos Op. (Detallado)
            hover_simple     # Ganancia Neta (Solo Total)
        ]

        fig_waterfall = go.Figure(go.Waterfall(
            name = "P&L", orientation = "v", measure = waterfall_measures, x = waterfall_x,
            textposition = "outside", 
            text = waterfall_text,      # Usamos la lista limpia solo con montos
            y = waterfall_y,            
            textfont_color = ['rgba(0,0,0,0)', 'black', 'black', 'black', 'black'],
            connector = {"line":{"color":"rgb(63, 63, 63)"}},
            increasing = {"marker": {"color": "#2c3e50"}},
            decreasing = {"marker": {"color": "#e74c3c"}},
            totals     = {"marker": {"color": water_color}},
            
            customdata = custom_tooltip_data,
            hovertemplate = hover_templates_list
        ))

        fig_waterfall.update_layout(
                title="Resumen P&L", waterfallgap = 0.3, height=400,
                margin=dict(l=0, r=0, t=50, b=20),
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                xaxis=dict(tickmode='array', tickvals=waterfall_x[0:], ticktext=waterfall_x[0:]),
                shapes=[dict(type='line', xref='paper', x0=0, x1=1, yref='y', y0=0, y1=0, line=dict(color='Gray', width=1, dash='dash'))]
        )
        min_y = min(0, net_profit); max_y = max(total_revenue, gross_profit, net_profit, 0)
        padding_y = (max_y - min_y) * 0.1 if max_y > min_y else 50
        fig_waterfall.update_yaxes(range=[min_y - padding_y, max_y + padding_y])

        # --- INICIALIZAR FIGURAS VACÍAS ---
        fig_sales_by_prod = px.bar(title="Ingresos por Producto", height=400)
        fig_revenue_by_cat = px.bar(title="Ingresos por Categoría", height=400)
        fig_sales_over_time = px.line(title="Ingresos por Día", height=400)
        fig_monthly = px.bar(title="Resumen Financiero Mensual", height=400)

        # --- GRÁFICOS BARRAS ---
        if not merged_df.empty:
            revenue_by_product = merged_df.groupby('name')['total_amount'].sum().reset_index()
            merged_df_with_cat = pd.merge(merged_df, categories_df, on='category_id', how='left').rename(columns={'name_y': 'category_name'})
            revenue_by_category = merged_df_with_cat.groupby('category_name')['total_amount'].sum().reset_index()

            fig_sales_by_prod = px.bar(revenue_by_product, x='name', y='total_amount', title="Ingresos por Producto",
                                         labels={'name': 'Producto', 'total_amount': 'Ingresos'},
                                         color_discrete_sequence=['#32a852'])
            fig_sales_by_prod.update_layout(**layout_style, xaxis_tickangle=-45, xaxis={'categoryorder':'total descending'})

            revenue_by_category = revenue_by_category.sort_values(by='total_amount', ascending=False)
            fig_revenue_by_cat = px.bar(revenue_by_category, x='category_name', y='total_amount', title="Ingresos por Categoría",
                                         labels={'category_name': 'Categoría', 'total_amount': 'Ingresos'},
                                         color_discrete_sequence=['#2c3e50'])
            fig_revenue_by_cat.update_layout(**layout_style, xaxis_tickangle=-45)
            
            # --- GRÁFICO LÍNEA (CORRECCIÓN OVERLAP) ---
            sales_by_day = merged_df.groupby(merged_df['sale_date'].dt.date)['total_amount'].sum().reset_index()
            fig_sales_over_time = px.line(sales_by_day, x='sale_date', y='total_amount', title='Ingresos por Día',
                                              labels={'sale_date': 'Fecha', 'total_amount': 'Ingresos'}, markers=True, height=400,
                                              color_discrete_sequence=['#32a852'])
            
            # Aumentamos el margen superior (t=80) para que el título no choque con los botones
            line_layout = layout_style.copy()
            line_layout['margin'] = dict(l=40, r=20, t=80, b=40) # <-- CORRECCIÓN AQUÍ
            fig_sales_over_time.update_layout(**line_layout)
            
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

# --- GRÁFICO MENSUAL (CORREGIDO) ---
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

            summary_df['P&L'] = summary_df['Ingresos'] - summary_df['COGS'] - summary_df['Gastos']
            summary_df['month'] = summary_df['month'].astype(str)
            plot_df = pd.melt(summary_df, id_vars=['month'], value_vars=['COGS', 'Gastos', 'P&L'], var_name='Tipo', value_name='Monto')
            
            # CAMBIO 1: Renombrar 'Costo de Venta' a 'Costos'
            plot_df['Tipo'] = plot_df['Tipo'].replace({'COGS': 'Costos'})
            
            def assign_pnl_category(row):
                if row['Tipo'] == 'P&L':
                    return 'P&L Positivo' if row['Monto'] >= 0 else 'P&L Negativo'
                return row['Tipo']
            plot_df['Tipo_Color'] = plot_df.apply(assign_pnl_category, axis=1)
            
            # CAMBIO 2: Actualizar mapa de colores con la nueva llave 'Costos'
            color_map = {
                'Costos': "#495057",       # Gris oscuro/Carbón (para costos base)
                'Gastos': "#493397",       # Ámbar/Amarillo (para gastos operativos)
                'P&L Positivo': "#32a852",  # Verde Marca (Ganancia)
                'P&L Negativo': "#dc3545"   # Rojo (Pérdida)
            }
            
            fig_monthly = px.bar(plot_df, x='month', y='Monto', color='Tipo_Color', title="Resumen Financiero Mensual",
                                 # Quitamos el label 'Tipo_Color' de aquí
                                 labels={'month': 'Mes', 'Monto': 'Monto'}, 
                                 color_discrete_map=color_map, height=400)
            
            # Limpieza de nombres en leyenda (quita ' Positivo'/' Negativo')
            fig_monthly.for_each_trace(lambda t: t.update(name=t.name.replace(' Positivo', '').replace(' Negativo', '')))
            
            monthly_layout = layout_style.copy()
            # Ajustamos márgenes: reducimos 'b' (bottom) un poco ya que ganaremos espacio quitando el título
            monthly_layout['margin'] = dict(l=20, r=20, t=60, b=80)
            
            monthly_layout['legend'] = dict(
                orientation="h", 
                yanchor="top", 
                y=-0.25, # Posición optimizada: Debajo de las fechas pero más cerca
                xanchor="center", 
                x=0.5,
                title=None, # Sin título de leyenda
                itemwidth=30 # Fuerza a que los items estén más compactos (ayuda en móvil)
            )
            
            fig_monthly.update_layout(**monthly_layout, barmode='relative')
            
            # CAMBIO CLAVE: title=None elimina la palabra "Mes" y evita el overlap
            fig_monthly.update_xaxes(type='category', tickangle=-45, title=None)

        return (
            f"${total_revenue:,.2f}", 
            f"${gross_profit:,.2f}", 
            f"${total_expenses:,.2f}", # <-- GASTOS AGREGADO
            f"${net_profit:,.2f}",
            net_profit_class,           # <-- COLOR NETO AGREGADO
            f"${total_product_investment:,.2f}",   
            f"${total_material_investment:,.2f}",  
            product_alerts,                        
            material_alerts,                       
            fig_monthly,                           
            fig_waterfall,                         
            fig_sales_by_prod,                     
            fig_revenue_by_cat,                    
            fig_sales_over_time,                   
            date_picker_disabled                   
        )
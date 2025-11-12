# resumen_excel.py
import pandas as pd
import io
from datetime import date, timedelta
import numpy as np
import dash_bootstrap_components as dbc
from dash import html, dcc

# Importar todas las funciones de base de datos necesarias
from database import (
    load_sales, load_expenses, load_products, load_categories,
    load_expense_categories, load_raw_materials, calculate_financials
)

# --- LAYOUT DE LA PESTAÑA DE RESUMEN ---
def get_summary_layout():
    """Diseño de la pestaña para descargar el reporte Excel."""
    return html.Div(className="p-4", children=[
        dbc.Row(justify="center", children=[
            dbc.Col(width=8, children=[
                dbc.Card(className="shadow-sm", children=[
                    dbc.CardHeader(html.H3("Generar Reporte Gerencial Completo", className="text-center")),
                    dbc.CardBody([
                        html.P(
                            "Este reporte generará un archivo Excel con múltiples hojas, incluyendo: "
                            "Dashboard de KPIs, Análisis ABC (Pareto), Estado de Resultados (P&L), "
                            "Historial de Ventas/Gastos y Valoración de Inventario.",
                            className="text-center text-muted mb-4"
                        ),
                        html.Hr(),
                        dbc.Row(justify="center", className="mb-4", children=[
                            dbc.Col(width=6, children=[
                                html.Label("Selecciona el Rango de Fechas:", className="fw-bold"),
                                dcc.DatePickerRange(
                                    id='summary-date-picker',
                                    start_date=date.today().replace(day=1), # Default: 1ro del mes
                                    end_date=date.today(),
                                    display_format='YYYY-MM-DD',
                                    className="w-100"
                                ),
                                # Switch para ver todo el historial
                                dbc.Switch(
                                    id="summary-see-all-switch",
                                    label="Descargar todo el historial (Ignorar fechas)",
                                    value=False,
                                    className="mt-3 fw-bold text-primary"
                                ),
                            ])
                        ]),
                        html.Div(className="d-grid gap-2 col-6 mx-auto", children=[
                            dbc.Button(
                                [html.I(className="fas fa-file-excel me-2"), "Descargar Resumen Excel"], 
                                id="btn-download-summary-excel", 
                                color="success", 
                                size="lg"
                            )
                        ])
                    ])
                ])
            ])
        ])
    ])

# --- LOGICA DE GENERACIÓN DE EXCEL ---

def create_dashboard_sheet(writer, user_id, start_date=None, end_date=None):
    """Crea la hoja de Dashboard con KPIs filtrados por fecha."""
    
    # 1. Calcular KPIs Financieros (Filtrados)
    # Si no hay fechas, see_all=True
    see_all_flag = False if (start_date and end_date) else True
    financials = calculate_financials(start_date, end_date, user_id, see_all=see_all_flag)
    
    rango_txt = "Histórico Completo"
    if start_date and end_date:
        rango_txt = f"Del {start_date} al {end_date}"

    kpi_data = {
        "Métrica Financiera Clave": [
            "Periodo Reportado", "Ingresos Totales", "Costo de Productos (COGS)", "(-) Gastos Operativos", 
            "Ganancia Neta Total", "Ticket de Venta Promedio", "Margen de Ganancia Neta (%)"
        ],
        "Valor": [
            rango_txt, financials['total_revenue'], financials['total_cogs'], financials['total_expenses'], 
            financials['net_profit'], financials['avg_ticket'], financials['net_margin']
        ]
    }
    df_kpi = pd.DataFrame(kpi_data)

    # 2. Calcular KPIs de Inventario (El stock SIEMPRE es el actual, no histórico)
    products_df = load_products(user_id)
    materials_df = load_raw_materials(user_id)
    
    valor_inv_productos = (products_df['cost'] * products_df['stock']).sum() if not products_df.empty else 0
    valor_inv_insumos = (materials_df['current_stock'] * materials_df['average_cost']).sum() if not materials_df.empty else 0
    
    inventory_data = {
        "Métrica de Inventario (Stock Actual)": ["Valor de Inventario (Productos)", "Valor de Inventario (Insumos)", "Total Invertido en Stock"],
        "Valor": [valor_inv_productos, valor_inv_insumos, valor_inv_productos + valor_inv_insumos]
    }
    df_inv = pd.DataFrame(inventory_data)

    # 3. Top Productos (Filtrado)
    merged_sales = financials['merged_df']
    top_prod_count = 0
    
    if not merged_sales.empty:
        prod_perf = merged_sales.groupby('name')[['total_amount', 'cogs_total']].sum().reset_index()
        prod_perf = prod_perf.fillna(0)
        prod_perf['Ganancia Bruta'] = prod_perf['total_amount'] - prod_perf['cogs_total']
        
        df_top_prod = prod_perf.nlargest(5, 'Ganancia Bruta')
        top_prod_count = len(df_top_prod)
        
        title_prod = f"Top {top_prod_count} Productos Rentables (En este periodo)"
        df_top_prod = df_top_prod[['name', 'Ganancia Bruta']].rename(columns={'name': title_prod})
    else:
        title_prod = "Top Productos Rentables"
        df_top_prod = pd.DataFrame(columns=[title_prod, 'Ganancia Bruta'])

    # 4. Top Gastos (Filtrado)
    expenses_df = financials['expenses_df']
    top_exp_count = 0
    
    if not expenses_df.empty:
        exp_cat_df = load_expense_categories(user_id)
        if not exp_cat_df.empty:
            expenses_with_names = pd.merge(expenses_df, exp_cat_df, on='expense_category_id', how='left')
            expense_summary = expenses_with_names.groupby('name')['amount'].sum().reset_index()
            
            df_top_exp = expense_summary.nlargest(5, 'amount')
            top_exp_count = len(df_top_exp)
            
            title_exp = f"Top {top_exp_count} Gastos (En este periodo)"
            df_top_exp = df_top_exp.rename(columns={'name': title_exp, 'amount': 'Monto'})
        else:
            df_top_exp = pd.DataFrame()
            title_exp = "Top Gastos"
    else:
        df_top_exp = pd.DataFrame()
        title_exp = "Top Gastos"

    # --- Escribir en Excel ---
    workbook = writer.book
    worksheet = workbook.add_worksheet('Dashboard')
    writer.sheets['Dashboard'] = worksheet

    header_format = workbook.add_format({'bold': True, 'bg_color': '#DDEBF7', 'border': 1})
    money_format = workbook.add_format({'num_format': '$#,##0.00', 'border': 1})
    percent_format = workbook.add_format({'num_format': '0.00%', 'border': 1})
    text_format = workbook.add_format({'border': 1})
    
    # KPIs Financieros
    worksheet.write('B2', 'Resumen Financiero', workbook.add_format({'bold': True, 'font_size': 14}))
    for i, col in enumerate(df_kpi.columns): worksheet.write(3, i + 1, col, header_format)
    for row_num, row_data in enumerate(df_kpi.values):
        worksheet.write(row_num + 4, 1, row_data[0], header_format)
        if "Margen" in str(row_data[0]):
            worksheet.write(row_num + 4, 2, row_data[1] / 100, percent_format)
        elif "Periodo" in str(row_data[0]):
             worksheet.write(row_num + 4, 2, row_data[1], text_format)
        else:
             worksheet.write(row_num + 4, 2, row_data[1], money_format)

    # KPIs Inventario
    worksheet.write('E2', 'Resumen de Inventario (Actual)', workbook.add_format({'bold': True, 'font_size': 14}))
    for i, col in enumerate(df_inv.columns): worksheet.write(3, i + 4, col, header_format)
    for row_num, row_data in enumerate(df_inv.values):
        worksheet.write(row_num + 4, 4, row_data[0], header_format)
        worksheet.write(row_num + 4, 5, row_data[1], money_format)

    # Top Productos
    worksheet.write('B13', title_prod, workbook.add_format({'bold': True, 'font_size': 14}))
    if not df_top_prod.empty:
        df_top_prod.to_excel(writer, sheet_name='Dashboard', startrow=14, startcol=1, index=False)
        for r in range(15, 15 + len(df_top_prod)):
            worksheet.write(r, 2, df_top_prod.iloc[r-15, 1], money_format)
    
    # Top Gastos
    worksheet.write('E13', title_exp, workbook.add_format({'bold': True, 'font_size': 14}))
    if not df_top_exp.empty:
        df_top_exp.to_excel(writer, sheet_name='Dashboard', startrow=14, startcol=4, index=False)
        for r in range(15, 15 + len(df_top_exp)):
            worksheet.write(r, 5, df_top_exp.iloc[r-15, 1], money_format)
    
    worksheet.set_column('B:B', 30); worksheet.set_column('C:C', 20); worksheet.set_column('E:E', 30); worksheet.set_column('F:F', 15)

# --- ANÁLISIS ABC (Filtrado) ---
def create_abc_analysis_df(products_df, sales_df):
    if sales_df.empty: return pd.DataFrame()
    
    sales_summary = sales_df.groupby('product_id')['total_amount'].sum().reset_index()
    sales_summary = pd.merge(sales_summary, products_df[['product_id', 'name']], on='product_id', how='left')
    sales_summary = sales_summary.sort_values(by='total_amount', ascending=False)
    
    sales_summary['cumulative_revenue'] = sales_summary['total_amount'].cumsum()
    total_revenue = sales_summary['total_amount'].sum()
    
    if total_revenue > 0:
        sales_summary['cumulative_percentage'] = (sales_summary['cumulative_revenue'] / total_revenue) * 100
        def classify_abc(pct):
            if pct <= 80: return 'A (Top 80% Ingresos)'
            if pct <= 95: return 'B (Siguiente 15%)'
            return 'C (Último 5%)'
        sales_summary['Clasificación ABC'] = sales_summary['cumulative_percentage'].apply(classify_abc)
    else:
        sales_summary['Clasificación ABC'] = '-'
    
    return sales_summary[['name', 'total_amount', 'cumulative_percentage', 'Clasificación ABC']].rename(columns={
        'name': 'Producto', 'total_amount': 'Ingresos Totales (En periodo)', 'cumulative_percentage': '% Acumulado'
    })

def generate_excel_summary(user_id, start_date=None, end_date=None):
    """
    Genera un archivo Excel en memoria, filtrando ventas y gastos por fecha.
    """
    # Stock SIEMPRE es el actual
    products_df = load_products(user_id)
    materials_df = load_raw_materials(user_id, include_inactive=False)
    
    # Ventas y Gastos FILTRADOS
    sales_df = load_sales(user_id, start_date, end_date)
    expenses_df = load_expenses(user_id, start_date, end_date)
    
    prod_cats_df = load_categories(user_id)
    exp_cats_df = load_expense_categories(user_id)
    
    output = io.BytesIO()
    
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        
        # 1. Dashboard (KPIs + Top Dinámicos)
        create_dashboard_sheet(writer, user_id, start_date, end_date)
        
        # 2. Análisis ABC (Sobre las ventas filtradas)
        df_abc = create_abc_analysis_df(products_df, sales_df)
        if not df_abc.empty:
            df_abc.to_excel(writer, sheet_name='Análisis ABC (Pareto)', index=False)
            worksheet_abc = writer.sheets['Análisis ABC (Pareto)']
            worksheet_abc.set_column('A:A', 25); worksheet_abc.set_column('B:B', 15); worksheet_abc.set_column('D:D', 20)

        # 3. P&L Mensual
        df_sales_pivot = sales_df.copy()
        if not df_sales_pivot.empty:
            df_sales_pivot['Month'] = df_sales_pivot['sale_date'].dt.to_period('M')
            pivot_sales = df_sales_pivot.groupby('Month')['total_amount'].sum()
            pivot_cogs = df_sales_pivot.groupby('Month')['cogs_total'].sum()
        else:
            pivot_sales = pd.Series(dtype=float); pivot_cogs = pd.Series(dtype=float)
        
        df_exp_pivot = expenses_df.copy()
        if not df_exp_pivot.empty:
            df_exp_pivot['Month'] = df_exp_pivot['expense_date'].dt.to_period('M')
            pivot_expenses = df_exp_pivot.groupby('Month')['amount'].sum()
        else:
            pivot_expenses = pd.Series(dtype=float)
        
        all_months = sorted(list(set(pivot_sales.index) | set(pivot_expenses.index)))
        if all_months:
            pnl_monthly = pd.DataFrame(index=all_months)
            pnl_monthly['(+) Ingresos'] = pivot_sales
            pnl_monthly['(-) Costo Ventas'] = pivot_cogs
            pnl_monthly['(=) Ganancia Bruta'] = pnl_monthly['(+) Ingresos'].fillna(0) - pnl_monthly['(-) Costo Ventas'].fillna(0)
            pnl_monthly['(-) Gastos Op.'] = pivot_expenses
            pnl_monthly['(=) Ganancia Neta'] = pnl_monthly['(=) Ganancia Bruta'] - pnl_monthly['(-) Gastos Op.'].fillna(0)
            pnl_monthly.fillna(0, inplace=True)
            
            pnl_monthly.index = [p.to_timestamp().date() for p in pnl_monthly.index]
            pnl_monthly.index.name = "Mes"
            pnl_monthly.to_excel(writer, sheet_name='Tendencia Mensual')

        # 4. Estado de Resultados Detallado
        df_ventas_pnl = pd.merge(sales_df, products_df, on='product_id', how='left')
        if not df_ventas_pnl.empty:
            df_ventas_pnl = df_ventas_pnl[['sale_date', 'name', 'quantity', 'total_amount', 'cogs_total']]
            df_ventas_pnl['ganancia_bruta'] = df_ventas_pnl['total_amount'] - df_ventas_pnl['cogs_total']
            df_ventas_pnl.rename(columns={'sale_date': 'Fecha', 'name': 'Detalle', 'quantity': 'Cantidad', 'total_amount': 'Ingresos', 'cogs_total': 'COGS', 'ganancia_bruta': 'Ganancia Bruta'}, inplace=True)
            df_ventas_pnl['Tipo'] = 'Venta'; df_ventas_pnl['Gasto Operativo'] = 0
        else:
            df_ventas_pnl = pd.DataFrame(columns=['Fecha', 'Detalle', 'Cantidad', 'Ingresos', 'COGS', 'Ganancia Bruta', 'Tipo', 'Gasto Operativo'])

        df_gastos_pnl = pd.merge(expenses_df, exp_cats_df, on='expense_category_id', how='left')
        if not df_gastos_pnl.empty:
            df_gastos_pnl = df_gastos_pnl[['expense_date', 'name', 'amount']]
            df_gastos_pnl.rename(columns={'expense_date': 'Fecha', 'name': 'Detalle', 'amount': 'Gasto Operativo'}, inplace=True)
            df_gastos_pnl['Tipo'] = 'Gasto'; df_gastos_pnl['Cantidad'] = 0; df_gastos_pnl['Ingresos'] = 0; df_gastos_pnl['COGS'] = 0; df_gastos_pnl['Ganancia Bruta'] = 0
        else:
            df_gastos_pnl = pd.DataFrame(columns=['Fecha', 'Detalle', 'Gasto Operativo', 'Tipo', 'Cantidad', 'Ingresos', 'COGS', 'Ganancia Bruta'])

        df_pnl = pd.concat([df_ventas_pnl, df_gastos_pnl], ignore_index=True)
        if not df_pnl.empty:
            df_pnl['Fecha'] = pd.to_datetime(df_pnl['Fecha'])
            df_pnl.sort_values(by='Fecha', inplace=True)
            cols_order = ['Fecha', 'Detalle', 'Tipo', 'Cantidad', 'Ingresos', 'COGS', 'Ganancia Bruta', 'Gasto Operativo']
            for col in cols_order:
                if col not in df_pnl.columns: df_pnl[col] = 0
            df_pnl = df_pnl[cols_order]
            df_pnl.to_excel(writer, sheet_name='Detalle Transacciones', index=False)

        # 5. Historial de Ventas
        if not df_ventas_pnl.empty:
            df_ventas_hist = df_ventas_pnl[['Fecha', 'Detalle', 'Cantidad', 'Ingresos']].rename(columns={'Fecha': 'Fecha Venta', 'Detalle': 'Producto', 'Ingresos': 'Monto'})
            df_ventas_hist.to_excel(writer, sheet_name='Historial Ventas', index=False)
        
        # 6. Historial de Gastos
        if not df_gastos_pnl.empty:
            df_gastos_hist = df_gastos_pnl[['Fecha', 'Detalle', 'Gasto Operativo']].rename(columns={'Fecha': 'Fecha Gasto', 'Detalle': 'Tipo', 'Gasto Operativo': 'Monto'})
            df_gastos_hist.to_excel(writer, sheet_name='Historial Gastos', index=False)

        # 7. Stock Productos
        if not products_df.empty:
            df_prod_stock = pd.merge(products_df[products_df['is_active'] == True], prod_cats_df, on='category_id', how='left')
            df_prod_stock['valor_inv'] = df_prod_stock['cost'] * df_prod_stock['stock']
            df_prod_stock = df_prod_stock[['name_x', 'name_y', 'stock', 'cost', 'price', 'valor_inv']].rename(columns={'name_x': 'Producto', 'name_y': 'Cat', 'stock': 'Stock', 'valor_inv': 'Valor Total'})
            df_prod_stock.to_excel(writer, sheet_name='Stock Productos', index=False)

        # 8. Stock Insumos
        if not materials_df.empty:
            df_mat_stock = materials_df[materials_df['is_active'] == True].copy()
            df_mat_stock['valor_inv'] = df_mat_stock['current_stock'] * df_mat_stock['average_cost']
            df_mat_stock = df_mat_stock[['name', 'unit_measure', 'current_stock', 'average_cost', 'valor_inv']].rename(columns={'name': 'Insumo', 'unit_measure': 'Unidad', 'current_stock': 'Stock', 'valor_inv': 'Valor Total'})
            df_mat_stock.to_excel(writer, sheet_name='Stock Insumos', index=False)

    output.seek(0)
    return output
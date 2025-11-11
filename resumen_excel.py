# resumen_excel.py
import pandas as pd
import io
from datetime import date
from flask_login import current_user

# Importar todas las funciones de base de datos necesarias
from database import (
    load_sales, load_expenses, load_products, load_categories,
    load_expense_categories, load_raw_materials, calculate_financials
)

def create_dashboard_sheet(writer, user_id):
    """Crea la hoja de Dashboard con KPIs."""
    
    # 1. Calcular KPIs Financieros (usando la función que ya existe)
    # Usamos 'see_all=True' para obtener todos los datos históricos
    financials = calculate_financials(None, None, user_id, see_all=True)
    
    kpi_data = {
        "Métrica Financiera Clave": [
            "Ingresos Totales",
            "Costo de Productos (COGS)",
            "(-) Gastos Operativos",
            "Ganancia Neta Total",
            "Ticket de Venta Promedio",
            "Margen de Ganancia Neta (%)"
        ],
        "Valor": [
            financials['total_revenue'],
            financials['total_cogs'],
            financials['total_expenses'],
            financials['net_profit'],
            financials['avg_ticket'],
            financials['net_margin']
        ]
    }
    df_kpi = pd.DataFrame(kpi_data)

    # 2. Calcular KPIs de Inventario
    products_df = load_products(user_id)
    materials_df = load_raw_materials(user_id)
    
    valor_inv_productos = (products_df['cost'] * products_df['stock']).sum()
    valor_inv_insumos = (materials_df['current_stock'] * materials_df['average_cost']).sum()
    
    inventory_data = {
        "Métrica de Inventario": [
            "Valor de Inventario (Productos)",
            "Valor de Inventario (Insumos)",
            "Total Invertido en Stock"
        ],
        "Valor": [
            valor_inv_productos,
            valor_inv_insumos,
            valor_inv_productos + valor_inv_insumos
        ]
    }
    df_inv = pd.DataFrame(inventory_data)

    # 3. Top 5 Productos por Ganancia Bruta
    merged_sales = financials['merged_df']
    if not merged_sales.empty:
        prod_perf = merged_sales.groupby('name').agg(
            ganancia_bruta=('total_amount', 'sum')
        ).reset_index()
        prod_perf['ganancia_bruta'] = merged_sales.groupby('name')['total_amount'].sum() - merged_sales.groupby('name')['cogs_total'].sum()
        df_top_prod = prod_perf.nlargest(5, 'ganancia_bruta').rename(columns={'name': 'Top 5 Productos Rentables', 'ganancia_bruta': 'Ganancia'})
    else:
        df_top_prod = pd.DataFrame(columns=['Top 5 Productos Rentables', 'Ganancia'])

    # 4. Top 5 Gastos por Categoría
    expenses_df = financials['expenses_df']
    if not expenses_df.empty:
        exp_cat_df = load_expense_categories(user_id)
        expenses_with_names = pd.merge(expenses_df, exp_cat_df, on='expense_category_id', how='left')
        expense_summary = expenses_with_names.groupby('name')['amount'].sum().reset_index()
        df_top_exp = expense_summary.nlargest(5, 'amount').rename(columns={'name': 'Top 5 Gastos', 'amount': 'Monto'})
    else:
        df_top_exp = pd.DataFrame(columns=['Top 5 Gastos', 'Monto'])

    # --- Escribir DataFrames en la hoja 'Dashboard' ---
    # Obtener el objeto workbook y worksheet
    workbook = writer.book
    worksheet = workbook.add_worksheet('Dashboard')
    writer.sheets['Dashboard'] = worksheet

    # Formatos
    header_format = workbook.add_format({'bold': True, 'bg_color': '#DDEBF7', 'border': 1})
    money_format = workbook.add_format({'num_format': '$#,##0.00', 'border': 1})
    percent_format = workbook.add_format({'num_format': '0.00%', 'border': 1})
    
    # Escribir KPIs Financieros
    worksheet.write('B2', 'Resumen Financiero Total', workbook.add_format({'bold': True, 'font_size': 14}))
    for i, col in enumerate(df_kpi.columns):
        worksheet.write(3, i + 1, col, header_format)
    for row_num, row_data in enumerate(df_kpi.values):
        worksheet.write(row_num + 4, 1, row_data[0], header_format)
        if "Margen" in row_data[0]:
             worksheet.write(row_num + 4, 2, row_data[1] / 100, percent_format)
        else:
             worksheet.write(row_num + 4, 2, row_data[1], money_format)

    # Escribir KPIs de Inventario
    worksheet.write('E2', 'Resumen de Inventario', workbook.add_format({'bold': True, 'font_size': 14}))
    for i, col in enumerate(df_inv.columns):
        worksheet.write(3, i + 4, col, header_format)
    for row_num, row_data in enumerate(df_inv.values):
        worksheet.write(row_num + 4, 4, row_data[0], header_format)
        worksheet.write(row_num + 4, 5, row_data[1], money_format)

    # Escribir Top 5 Productos
    worksheet.write('B12', 'Top 5 Productos Rentables', workbook.add_format({'bold': True, 'font_size': 14}))
    df_top_prod.to_excel(writer, sheet_name='Dashboard', startrow=13, startcol=1, index=False)
    
    # Escribir Top 5 Gastos
    worksheet.write('E12', 'Top 5 Gastos', workbook.add_format({'bold': True, 'font_size': 14}))
    df_top_exp.to_excel(writer, sheet_name='Dashboard', startrow=13, startcol=4, index=False)
    
    # Ajustar anchos de columna
    worksheet.set_column('B:B', 25)
    worksheet.set_column('C:C', 15)
    worksheet.set_column('E:E', 25)
    worksheet.set_column('F:F', 15)


def generate_excel_summary(user_id):
    """
    Genera un archivo Excel en memoria con 6 hojas:
    1. Dashboard, 2. P&L Detallado, 3. Ventas, 4. Gastos, 5. Stock Productos, 6. Stock Insumos
    """
    
    # 1. Cargar todos los datos
    products_df = load_products(user_id)
    materials_df = load_raw_materials(user_id, include_inactive=False)
    sales_df = load_sales(user_id, None, None) # Cargar todas las ventas
    expenses_df = load_expenses(user_id, None, None) # Cargar todos los gastos
    prod_cats_df = load_categories(user_id)
    exp_cats_df = load_expense_categories(user_id)
    
    # Crear un buffer de BytesIO para guardar el Excel
    output = io.BytesIO()
    
    # Usar xlsxwriter como engine para poder formatear la hoja Dashboard
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        
        # --- Hoja 1: Dashboard ---
        create_dashboard_sheet(writer, user_id)
        
        # --- Hoja 2: Estado de Resultados (Detallado) ---
        # Unir ventas con productos para obtener nombres
        df_ventas_pnl = pd.merge(sales_df, products_df, on='product_id', how='left')
        df_ventas_pnl = df_ventas_pnl[['sale_date', 'name', 'quantity', 'total_amount', 'cogs_total']]
        df_ventas_pnl['ganancia_bruta'] = df_ventas_pnl['total_amount'] - df_ventas_pnl['cogs_total']
        df_ventas_pnl.rename(columns={
            'sale_date': 'Fecha', 'name': 'Detalle', 'quantity': 'Cantidad',
            'total_amount': 'Ingresos', 'cogs_total': 'COGS', 'ganancia_bruta': 'Ganancia Bruta'
        }, inplace=True)
        df_ventas_pnl['Tipo'] = 'Venta'
        df_ventas_pnl['Gasto Operativo'] = 0

        # Unir gastos con categorías para obtener nombres
        df_gastos_pnl = pd.merge(expenses_df, exp_cats_df, on='expense_category_id', how='left')
        df_gastos_pnl = df_gastos_pnl[['expense_date', 'name', 'amount']]
        df_gastos_pnl.rename(columns={'expense_date': 'Fecha', 'name': 'Detalle', 'amount': 'Gasto Operativo'}, inplace=True)
        df_gastos_pnl['Tipo'] = 'Gasto'
        df_gastos_pnl['Cantidad'] = 0; df_gastos_pnl['Ingresos'] = 0; df_gastos_pnl['COGS'] = 0; df_gastos_pnl['Ganancia Bruta'] = 0

        # Combinar ambos
        df_pnl = pd.concat([df_ventas_pnl, df_gastos_pnl], ignore_index=True)
        df_pnl['Fecha'] = pd.to_datetime(df_pnl['Fecha'])
        df_pnl.sort_values(by='Fecha', inplace=True)
        df_pnl = df_pnl[['Fecha', 'Tipo', 'Detalle', 'Cantidad', 'Ingresos', 'COGS', 'Ganancia Bruta', 'Gasto Operativo']]
        
        # Añadir totales al final
        totales = df_pnl[['Ingresos', 'COGS', 'Ganancia Bruta', 'Gasto Operativo']].sum()
        totales['Fecha'] = 'Total'
        totales['Ganancia Neta'] = totales['Ganancia Bruta'] - totales['Gasto Operativo']
        df_pnl = pd.concat([df_pnl, totales.to_frame().T], ignore_index=True)
        
        df_pnl.to_excel(writer, sheet_name='Estado de Resultados', index=False)

        # --- Hoja 3: Historial de Ventas ---
        df_ventas_hist = df_ventas_pnl.rename(columns={
            'Fecha': 'Fecha de Venta', 'Detalle': 'Nombre del Producto',
            'Cantidad': 'Cantidad', 'Ingresos': 'Monto Total'
        })
        df_ventas_hist = df_ventas_hist[['Fecha de Venta', 'Nombre del Producto', 'Cantidad', 'Monto Total']]
        df_ventas_hist.sort_values(by='Fecha de Venta', inplace=True)
        df_ventas_hist.to_excel(writer, sheet_name='Historial de Ventas', index=False)
        
        # --- Hoja 4: Historial de Gastos ---
        df_gastos_hist = df_gastos_pnl.rename(columns={
            'Fecha': 'Fecha de Gasto', 'Detalle': 'Nombre Gasto',
            'Gasto Operativo': 'Monto'
        })
        df_gastos_hist = df_gastos_hist[['Fecha de Gasto', 'Nombre Gasto', 'Monto']]
        df_gastos_hist.sort_values(by='Fecha de Gasto', inplace=True)
        df_gastos_hist.to_excel(writer, sheet_name='Historial de Gastos', index=False)

        # --- Hoja 5: Productos en Stock ---
        df_prod_stock = pd.merge(products_df[products_df['is_active'] == True], prod_cats_df, on='category_id', how='left')
        df_prod_stock['valor_inventario'] = df_prod_stock['cost'] * df_prod_stock['stock']
        df_prod_stock = df_prod_stock[['name_x', 'name_y', 'stock', 'cost', 'price', 'valor_inventario']]
        df_prod_stock.rename(columns={
            'name_x': 'Producto', 'name_y': 'Categoría', 'stock': 'Stock Actual',
            'cost': 'Costo', 'price': 'Precio', 'valor_inventario': 'Valor Total'
        }, inplace=True)
        df_prod_stock.to_excel(writer, sheet_name='Productos en Stock', index=False)

        # --- Hoja 6: Insumos en Stock ---
        df_mat_stock = materials_df[materials_df['is_active'] == True].copy()
        df_mat_stock['valor_inventario'] = df_mat_stock['current_stock'] * df_mat_stock['average_cost']
        df_mat_stock = df_mat_stock[['name', 'unit_measure', 'current_stock', 'average_cost', 'valor_inventario']]
        df_mat_stock.rename(columns={
            'name': 'Insumo', 'unit_measure': 'Unidad', 'current_stock': 'Stock Actual',
            'average_cost': 'Costo Promedio', 'valor_inventario': 'Valor Total'
        }, inplace=True)
        df_mat_stock.to_excel(writer, sheet_name='Insumos en Stock', index=False)

    # Regresar al inicio del buffer
    output.seek(0)
    return output
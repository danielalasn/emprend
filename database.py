import pandas as pd
import sqlite3
from sqlalchemy import create_engine
from datetime import datetime, timedelta

# --- Configuración de la Base de Datos ---
db_file = 'tiendita.db'
engine = create_engine(f'sqlite:///{db_file}')

# --- Funciones de Carga ---
def load_products(): return pd.read_sql('SELECT * FROM products', engine)
def load_sales(): return pd.read_sql('SELECT * FROM sales', engine)
def load_expenses(): return pd.read_sql('SELECT * FROM expenses', engine)
def load_categories(): return pd.read_sql('SELECT * FROM categories', engine)
def load_expense_categories(): return pd.read_sql('SELECT * FROM expense_categories', engine)

# --- Funciones de Actualización ---
def update_stock(product_id, new_stock):
    with sqlite3.connect(db_file) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE products SET stock = ? WHERE product_id = ?", (int(new_stock), product_id))
        conn.commit()

# --- Funciones para Dropdowns ---
def get_product_options():
    try:
        products_df = load_products()
        if products_df.empty: return []
        return [{'label': f"{row['name']} (Stock: {row['stock']})", 'value': row['product_id']} for _, row in products_df.iterrows()]
    except Exception:
        return []

def get_category_options():
    try:
        categories_df = load_categories()
        if categories_df.empty: return []
        return [{'label': row['name'], 'value': row['category_id']} for _, row in categories_df.iterrows()]
    except Exception:
        return []

def get_expense_category_options():
    try:
        expense_cat_df = load_expense_categories()
        if expense_cat_df.empty: return []
        return [{'label': row['name'], 'value': row['expense_category_id']} for _, row in expense_cat_df.iterrows()]
    except Exception:
        return []

# --- Función de Cálculo Financiero ---
def calculate_financials(start_date, end_date):
    all_sales = load_sales()
    all_expenses = load_expenses()
    products = load_products()

    all_sales['sale_date'] = pd.to_datetime(all_sales['sale_date'])
    all_expenses['expense_date'] = pd.to_datetime(all_expenses['expense_date'])
    
    start_date_dt = pd.to_datetime(start_date)
    end_date_dt = pd.to_datetime(end_date) + timedelta(days=1)

    sales_df = all_sales[(all_sales['sale_date'] >= start_date_dt) & (all_sales['sale_date'] < end_date_dt)]
    expenses_df = all_expenses[(all_expenses['expense_date'] >= start_date_dt) & (all_expenses['expense_date'] < end_date_dt)]

    results = {
        "total_revenue": 0, "gross_profit": 0, "total_cogs": 0, 
        "net_profit": 0, "num_sales": 0, "avg_ticket": 0, 
        "net_margin": 0, "total_expenses": 0, "unidades_vendidas": 0, "gross_margin": 0,
        "sales_df": pd.DataFrame()
    }

    if not sales_df.empty:
        results["num_sales"] = len(sales_df)
        results["unidades_vendidas"] = int(sales_df['quantity'].sum())
        results["sales_df"] = sales_df
        if not products.empty:
            merged = pd.merge(sales_df, products, on='product_id', how='left')
            merged.dropna(subset=['cost'], inplace=True)
            merged['cogs'] = merged['cost'] * merged['quantity']
            results["total_cogs"] = merged['cogs'].sum()
            results["total_revenue"] = merged['total_amount'].sum()
            results["gross_profit"] = results["total_revenue"] - results["total_cogs"]
    
    results["total_expenses"] = expenses_df['amount'].sum() if not expenses_df.empty else 0
    results["net_profit"] = results["gross_profit"] - results["total_expenses"]
    results["avg_ticket"] = results["total_revenue"] / results["num_sales"] if results["num_sales"] > 0 else 0
    results["net_margin"] = (results["net_profit"] / results["total_revenue"] * 100) if results["total_revenue"] > 0 else 0
    results["gross_margin"] = (results["gross_profit"] / results["total_revenue"] * 100) if results["total_revenue"] > 0 else 0
    
    return results
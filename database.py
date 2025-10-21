# $env:DATABASE_URL="postgresql://emprend_db_user:dhlq3PHm09twtrGxblqcR8YB9lKVbPWt@dpg-d3rb6uhr0fns73cslfs0-a.oregon-postgres.render.com/emprend_db"
import pandas as pd
import sqlite3
from sqlalchemy import create_engine, text
from datetime import datetime, timedelta
import os

# --- CONFIGURACIÓN DE LA BASE DE DATOS ---
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)

# --- FUNCIONES DE CARGA ---
def load_products(user_id):
    query = text("SELECT * FROM products WHERE user_id = :user_id")
    return pd.read_sql(query, engine, params={"user_id": int(user_id)})

def load_sales(user_id):
    query = text("SELECT * FROM sales WHERE user_id = :user_id")
    return pd.read_sql(query, engine, params={"user_id": int(user_id)})

def load_expenses(user_id):
    query = text("SELECT * FROM expenses WHERE user_id = :user_id")
    return pd.read_sql(query, engine, params={"user_id": int(user_id)})

def load_categories(user_id):
    query = text("SELECT * FROM categories WHERE user_id = :user_id")
    return pd.read_sql(query, engine, params={"user_id": int(user_id)})

def load_expense_categories(user_id):
    query = text("SELECT * FROM expense_categories WHERE user_id = :user_id")
    return pd.read_sql(query, engine, params={"user_id": int(user_id)})

# --- FUNCIONES DE ACTUALIZACIÓN Y BORRADO ---
def update_stock(product_id, new_stock, user_id):
    with engine.connect() as connection:
        query = text("UPDATE products SET stock = :stock WHERE product_id = :product_id AND user_id = :user_id")
        connection.execute(query, {"stock": int(new_stock), "product_id": int(product_id), "user_id": int(user_id)})
        connection.commit()

def update_product(product_id, data, user_id):
    with engine.connect() as connection:
        query = text("""
            UPDATE products SET name = :name, description = :description, category_id = :category_id,
            price = :price, cost = :cost, stock = :stock, alert_threshold = :alert_threshold
            WHERE product_id = :product_id AND user_id = :user_id
        """)
        data['product_id'] = int(product_id)
        data['user_id'] = int(user_id)
        connection.execute(query, data)
        connection.commit()

def delete_product(product_id, user_id):
    with engine.connect() as connection:
        delete_sales_query = text("DELETE FROM sales WHERE product_id = :product_id AND user_id = :user_id")
        connection.execute(delete_sales_query, {"product_id": int(product_id), "user_id": int(user_id)})
        
        delete_product_query = text("DELETE FROM products WHERE product_id = :product_id AND user_id = :user_id")
        connection.execute(delete_product_query, {"product_id": int(product_id), "user_id": int(user_id)})
        connection.commit()

def update_category(category_id, data, user_id):
    with engine.connect() as connection:
        query = text("UPDATE categories SET name = :name WHERE category_id = :category_id AND user_id = :user_id")
        data['category_id'] = int(category_id)
        data['user_id'] = int(user_id)
        connection.execute(query, data)
        connection.commit()

def delete_category(category_id, user_id):
    with engine.connect() as connection:
        update_products_query = text("UPDATE products SET category_id = NULL WHERE category_id = :category_id AND user_id = :user_id")
        connection.execute(update_products_query, {"category_id": int(category_id), "user_id": int(user_id)})

        query = text("DELETE FROM categories WHERE category_id = :category_id AND user_id = :user_id")
        connection.execute(query, {"category_id": int(category_id), "user_id": int(user_id)})
        connection.commit()

def update_sale(sale_id, data, user_id):
    with engine.connect() as connection:
        query = text("""
            UPDATE sales SET product_id = :product_id, quantity = :quantity, 
            total_amount = :total_amount, sale_date = :sale_date, cogs_total = :cogs_total
            WHERE sale_id = :sale_id AND user_id = :user_id
        """)
        data['sale_id'] = int(sale_id)
        data['user_id'] = int(user_id)
        connection.execute(query, data)
        connection.commit()

def delete_sale(sale_id, user_id):
    with engine.connect() as connection:
        query = text("DELETE FROM sales WHERE sale_id = :sale_id AND user_id = :user_id")
        connection.execute(query, {"sale_id": int(sale_id), "user_id": int(user_id)})
        connection.commit()
        
def update_expense(expense_id, data, user_id):
    with engine.connect() as connection:
        query = text("""
            UPDATE expenses SET expense_category_id = :expense_category_id, amount = :amount, expense_date = :expense_date
            WHERE expense_id = :expense_id AND user_id = :user_id
        """)
        data['expense_id'] = int(expense_id)
        data['user_id'] = int(user_id)
        connection.execute(query, data)
        connection.commit()

def delete_expense(expense_id, user_id):
    with engine.connect() as connection:
        query = text("DELETE FROM expenses WHERE expense_id = :expense_id AND user_id = :user_id")
        connection.execute(query, {"expense_id": int(expense_id), "user_id": int(user_id)})
        connection.commit()

def delete_expense_category(category_id, user_id):
    with engine.connect() as connection:
        update_expenses_query = text("UPDATE expenses SET expense_category_id = NULL WHERE expense_category_id = :category_id AND user_id = :user_id")
        connection.execute(update_expenses_query, {"category_id": int(category_id), "user_id": int(user_id)})

        query = text("DELETE FROM expense_categories WHERE expense_category_id = :category_id AND user_id = :user_id")
        connection.execute(query, {"category_id": int(category_id), "user_id": int(user_id)})
        connection.commit()

# ### INICIO: NUEVA FUNCIÓN ###
def update_user_password(user_id, new_password_hash):
    with engine.connect() as connection:
        query = text("""
            UPDATE users SET password = :password, must_change_password = FALSE 
            WHERE id = :user_id
        """)
        connection.execute(query, {"password": new_password_hash, "user_id": int(user_id)})
        connection.commit()
# ### FIN: NUEVA FUNCIÓN ###

# --- FUNCIONES PARA DROPDOWNS ---
def get_product_options(user_id):
    try:
        products_df = load_products(int(user_id))
        if products_df.empty: return []
        return [{'label': f"{row['name']} (Stock: {row['stock']})", 'value': row['product_id']} for _, row in products_df.iterrows()]
    except Exception: return []

def get_category_options(user_id):
    try:
        categories_df = load_categories(int(user_id))
        if categories_df.empty: return []
        return [{'label': row['name'], 'value': row['category_id']} for _, row in categories_df.iterrows()]
    except Exception: return []

def get_expense_category_options(user_id):
    try:
        expense_cat_df = load_expense_categories(int(user_id))
        if expense_cat_df.empty: return []
        return [{'label': row['name'], 'value': row['expense_category_id']} for _, row in expense_cat_df.iterrows()]
    except Exception: return []

# --- FUNCIÓN DE CÁLCULO FINANCIERO ---
def calculate_financials(start_date, end_date, user_id, see_all=False):
    user_id = int(user_id)
    all_sales = load_sales(user_id)
    all_expenses = load_expenses(user_id)
    products = load_products(user_id)

    all_sales['sale_date'] = pd.to_datetime(all_sales['sale_date'], format='mixed')
    all_expenses['expense_date'] = pd.to_datetime(all_expenses['expense_date'], format='mixed')
    
    if see_all:
        sales_df = all_sales
        expenses_df = all_expenses
    else:
        start_date_dt = pd.to_datetime(start_date)
        end_date_dt = pd.to_datetime(end_date) + timedelta(days=1)
        sales_df = all_sales[(all_sales['sale_date'] >= start_date_dt) & (all_sales['sale_date'] < end_date_dt)]
        expenses_df = all_expenses[(all_expenses['expense_date'] >= start_date_dt) & (all_expenses['expense_date'] < end_date_dt)]

    results = {
        "total_revenue": 0, "gross_profit": 0, "total_cogs": 0, "net_profit": 0,
        "num_sales": 0, "avg_ticket": 0, "net_margin": 0, "total_expenses": 0,
        "unidades_vendidas": 0, "gross_margin": 0, "sales_df": sales_df,
        "expenses_df": expenses_df, "merged_df": pd.DataFrame()
    }

    if not sales_df.empty:
        results["num_sales"] = len(sales_df)
        results["unidades_vendidas"] = int(sales_df['quantity'].sum())
        
        if 'cogs_total' in sales_df.columns:
            results["total_cogs"] = sales_df['cogs_total'].sum()
        
        results["total_revenue"] = sales_df['total_amount'].sum()
        results["gross_profit"] = results["total_revenue"] - results["total_cogs"]
        
        if not products.empty:
            results["merged_df"] = pd.merge(sales_df, products, on='product_id', how='left')
    
    results["total_expenses"] = expenses_df['amount'].sum() if not expenses_df.empty else 0
    results["net_profit"] = results["gross_profit"] - results["total_expenses"]
    results["avg_ticket"] = results["total_revenue"] / results["num_sales"] if results["num_sales"] > 0 else 0
    results["net_margin"] = (results["net_profit"] / results["total_revenue"] * 100) if results["total_revenue"] > 0 else 0
    results["gross_margin"] = (results["gross_profit"] / results["total_revenue"] * 100) if results["total_revenue"] > 0 else 0
    
    return results
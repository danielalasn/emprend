
# $env:FLASK_SECRET_KEY="98781453ae8b980645b00b56c88ee536ef88c6fdbcfb7c76"
# $env:DATABASE_URL="postgresql://emprend_db_user:dhlq3PHm09twtrGxblqcR8YB9lKVbPWt@dpg-d3rb6uhr0fns73cslfs0-a.oregon-postgres.render.com/emprend_db"
import pandas as pd
from sqlalchemy import create_engine, text
from datetime import datetime, timedelta, date # <-- Añadido date
import os

# --- CONFIGURACIÓN DE LA BASE DE DATOS ---
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Asegurarse que DATABASE_URL esté definida antes de crear el engine
if not DATABASE_URL:
    raise ValueError("La variable de entorno DATABASE_URL no está configurada.")

engine = create_engine(DATABASE_URL)

# --- FUNCIONES DE CARGA ---
# (load_products, load_sales, load_expenses, load_categories, load_expense_categories sin cambios)
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
# (update_stock, update_product, delete_product, update_category, delete_category,
#  update_sale, delete_sale, update_expense, delete_expense,
#  update_expense_category, delete_expense_category, update_user_password sin cambios)
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
        query = text("UPDATE products SET is_active = FALSE WHERE product_id = :product_id AND user_id = :user_id")
        connection.execute(query, {"product_id": int(product_id), "user_id": int(user_id)})
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
        query = text("UPDATE categories SET is_active = FALSE WHERE category_id = :category_id AND user_id = :user_id")
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

def update_expense_category(category_id, data, user_id):
     with engine.connect() as connection:
        query = text("UPDATE expense_categories SET name = :name WHERE expense_category_id = :category_id AND user_id = :user_id")
        data['category_id'] = int(category_id)
        data['user_id'] = int(user_id)
        connection.execute(query, data)
        connection.commit()

def delete_expense_category(category_id, user_id):
    with engine.connect() as connection:
        update_expenses_query = text("UPDATE expenses SET expense_category_id = NULL WHERE expense_category_id = :category_id AND user_id = :user_id")
        connection.execute(update_expenses_query, {"category_id": int(category_id), "user_id": int(user_id)})
        query = text("UPDATE expense_categories SET is_active = FALSE WHERE expense_category_id = :category_id AND user_id = :user_id")
        connection.execute(query, {"category_id": int(category_id), "user_id": int(user_id)})
        connection.commit()

def update_user_password(user_id, new_password_hash):
    with engine.connect() as connection:
        query = text("""
            UPDATE users SET password = :password, must_change_password = FALSE
            WHERE id = :user_id
        """)
        connection.execute(query, {"password": new_password_hash, "user_id": int(user_id)})
        connection.commit()

# --- FUNCIONES PARA DROPDOWNS ---
# (get_product_options, get_category_options, get_expense_category_options sin cambios)
def get_product_options(user_id):
    try:
        query = text("SELECT product_id as value, name || ' (Stock: ' || stock || ')' as label FROM products WHERE user_id = :user_id AND is_active = TRUE")
        products_df = pd.read_sql(query, engine, params={"user_id": int(user_id)})
        return products_df.to_dict('records')
    except Exception: return []

def get_category_options(user_id):
    try:
        query = text("SELECT category_id as value, name as label FROM categories WHERE user_id = :user_id AND is_active = TRUE")
        categories_df = pd.read_sql(query, engine, params={"user_id": int(user_id)})
        return categories_df.to_dict('records')
    except Exception: return []

def get_expense_category_options(user_id):
    try:
        query = text("SELECT expense_category_id as value, name as label FROM expense_categories WHERE user_id = :user_id AND is_active = TRUE")
        expense_cat_df = pd.read_sql(query, engine, params={"user_id": int(user_id)})
        return expense_cat_df.to_dict('records')
    except Exception: return []

# --- FUNCIÓN DE CÁLCULO FINANCIERO ---
# (calculate_financials sin cambios)
def calculate_financials(start_date, end_date, user_id, see_all=False):
    user_id = int(user_id)
    all_sales = load_sales(user_id)
    all_expenses = load_expenses(user_id)
    products = load_products(user_id)

    all_sales['sale_date'] = pd.to_datetime(all_sales['sale_date'], format='mixed', errors='coerce')
    all_expenses['expense_date'] = pd.to_datetime(all_expenses['expense_date'], format='mixed', errors='coerce')

    all_sales = all_sales.dropna(subset=['sale_date'])
    all_expenses = all_expenses.dropna(subset=['expense_date'])

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

# ### FUNCIONES DE ADMINISTRACIÓN ###

# --- CORREGIDO: Obtener también 'subscription_end_date' ---
def get_all_users():
    query = text("""
        SELECT id, username, first_login, is_blocked, must_change_password, is_admin, last_block_change, subscription_end_date
        FROM users
    """)
    return pd.read_sql(query, engine)

def record_first_login(user_id):
    with engine.connect() as connection:
        query = text("UPDATE users SET first_login = NOW() WHERE id = :user_id AND first_login IS NULL")
        connection.execute(query, {"user_id": int(user_id)})
        connection.commit()

# --- CORREGIDO: Actualizar también 'last_block_change' ---
def set_user_block_status(user_id, is_blocked):
    with engine.connect() as connection:
        query = text("""
            UPDATE users
            SET is_blocked = :status, last_block_change = NOW()
            WHERE id = :user_id
        """)
        connection.execute(query, {"status": is_blocked, "user_id": int(user_id)})
        connection.commit()

def reset_user_password(user_id, new_hashed_password):
    with engine.connect() as connection:
        query = text("UPDATE users SET password = :password, must_change_password = TRUE WHERE id = :user_id")
        connection.execute(query, {"password": new_hashed_password, "user_id": int(user_id)})
        connection.commit()

def delete_user(user_id):
    with engine.connect() as connection:
        query = text("DELETE FROM users WHERE id = :user_id")
        connection.execute(query, {"user_id": int(user_id)})
        connection.commit()

# --- CORREGIDO: Añadir 'subscription_end_date' ---
def create_user(username, hashed_password, is_admin, subscription_end_date):
    """Crea un nuevo usuario en la base de datos."""
    user_df = pd.DataFrame([{
        'username': username,
        'password': hashed_password,
        'must_change_password': True,
        'is_blocked': False,
        'is_admin': is_admin,
        'subscription_end_date': subscription_end_date # <-- Añadido
    }])
    try:
        user_df.to_sql('users', engine, if_exists='append', index=False)
        return True, f"¡Usuario '{username}' creado con éxito!"
    except Exception as e:
        print(f"Error al crear usuario: {e}")
        return False, "Error: El nombre de usuario ya existe."

# --- NUEVA FUNCIÓN ---
def extend_subscription(user_id, new_end_date):
    """Actualiza la fecha de fin de suscripción para un usuario."""
    with engine.connect() as connection:
        query = text("""
            UPDATE users SET subscription_end_date = :end_date
            WHERE id = :user_id
        """)
        connection.execute(query, {"end_date": new_end_date, "user_id": int(user_id)})
        connection.commit()


# --- FUNCIONES DE REACTIVACIÓN ---
# (reactivate_product_category, reactivate_expense_category sin cambios)
def reactivate_product_category(category_id, user_id):
    with engine.connect() as connection:
        query = text("UPDATE categories SET is_active = TRUE WHERE category_id = :category_id AND user_id = :user_id")
        connection.execute(query, {"category_id": int(category_id), "user_id": int(user_id)})
        connection.commit()

def reactivate_expense_category(category_id, user_id):
    with engine.connect() as connection:
        query = text("UPDATE expense_categories SET is_active = TRUE WHERE expense_category_id = :category_id AND user_id = :user_id")
        connection.execute(query, {"category_id": int(category_id), "user_id": int(user_id)})
        connection.commit()

# --- NUEVA FUNCIÓN ATÓMICA PARA STOCK ---
def attempt_stock_deduction(product_id, quantity, user_id):
    """
    Intenta deducir stock de un producto de forma atómica.
    Devuelve True si la deducción fue exitosa, False en caso contrario.
    """
    with engine.connect() as connection:
        with connection.begin(): # Inicia transacción
            query = text("""
                UPDATE products
                SET stock = stock - :quantity
                WHERE product_id = :product_id
                  AND user_id = :user_id
                  AND stock >= :quantity
            """)
            result = connection.execute(query, {
                "quantity": int(quantity),
                "product_id": int(product_id),
                "user_id": int(user_id)
            })
            # commit se hace automáticamente al salir del with connection.begin()
            return result.rowcount == 1 # True si 1 fila fue afectada
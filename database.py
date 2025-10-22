# database.py
import pandas as pd
from sqlalchemy import create_engine, text
from datetime import datetime, timedelta, date # Asegúrate de tener date
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
def load_products(user_id):
    """Carga todos los productos (activos e inactivos) para un usuario."""
    query = text("SELECT * FROM products WHERE user_id = :user_id")
    # parse_dates informa a Pandas sobre columnas de fecha/hora si existen (aunque no hay en products)
    return pd.read_sql(query, engine, params={"user_id": int(user_id)})

def load_categories(user_id):
    """Carga todas las categorías de productos (activas e inactivas) para un usuario."""
    query = text("SELECT * FROM categories WHERE user_id = :user_id")
    return pd.read_sql(query, engine, params={"user_id": int(user_id)})

def load_expense_categories(user_id):
    """Carga todas las categorías de gastos (activas e inactivas) para un usuario."""
    query = text("SELECT * FROM expense_categories WHERE user_id = :user_id")
    return pd.read_sql(query, engine, params={"user_id": int(user_id)})

def load_sales(user_id, start_date=None, end_date=None):
    """Carga ventas para un usuario, opcionalmente filtradas por fecha."""
    params = {"user_id": int(user_id)}
    sql = "SELECT * FROM sales WHERE user_id = :user_id"
    if start_date and end_date:
        # Filtra entre start_date (inclusive) y el día SIGUIENTE a end_date (exclusivo)
        sql += " AND sale_date >= :start_date AND sale_date < :end_date_plus_one"
        params["start_date"] = start_date
        try:
            # Asegura que end_date sea un objeto fecha/hora antes de sumar
            end_date_dt = pd.to_datetime(end_date).normalize() # Normalizar a medianoche
            params["end_date_plus_one"] = end_date_dt + timedelta(days=1)
        except (TypeError, ValueError):
             print(f"Advertencia: Formato inválido de end_date '{end_date}' en load_sales. Cargando todas las ventas.")
             sql = "SELECT * FROM sales WHERE user_id = :user_id" # Fallback
             params = {"user_id": int(user_id)}

    query = text(sql)
    # Informar a Pandas que 'sale_date' es fecha/hora
    return pd.read_sql(query, engine, params=params, parse_dates=['sale_date'])

def load_expenses(user_id, start_date=None, end_date=None):
    """Carga gastos para un usuario, opcionalmente filtrados por fecha."""
    params = {"user_id": int(user_id)}
    sql = "SELECT * FROM expenses WHERE user_id = :user_id"
    if start_date and end_date:
        # Filtra entre start_date (inclusive) y el día SIGUIENTE a end_date (exclusivo)
        sql += " AND expense_date >= :start_date AND expense_date < :end_date_plus_one"
        params["start_date"] = start_date
        try:
            # Asegura que end_date sea un objeto fecha/hora antes de sumar
            end_date_dt = pd.to_datetime(end_date).normalize() # Normalizar a medianoche
            params["end_date_plus_one"] = end_date_dt + timedelta(days=1)
        except (TypeError, ValueError):
             print(f"Advertencia: Formato inválido de end_date '{end_date}' en load_expenses. Cargando todos los gastos.")
             sql = "SELECT * FROM expenses WHERE user_id = :user_id" # Fallback
             params = {"user_id": int(user_id)}

    query = text(sql)
    # Informar a Pandas que 'expense_date' es fecha/hora
    return pd.read_sql(query, engine, params=params, parse_dates=['expense_date'])


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
        # Asegurarse que los valores numéricos sean correctos
        data['price'] = float(data.get('price', 0))
        data['cost'] = float(data.get('cost', 0))
        data['stock'] = int(data.get('stock', 0))
        data['alert_threshold'] = int(data.get('alert_threshold', 0))
        data['product_id'] = int(product_id)
        data['user_id'] = int(user_id)
        connection.execute(query, data)
        connection.commit()

def delete_product(product_id, user_id):
    """Borrado suave de producto."""
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
    """Borrado suave de categoría de producto."""
    with engine.connect() as connection:
        # Desvincular productos de esta categoría
        update_products_query = text("UPDATE products SET category_id = NULL WHERE category_id = :category_id AND user_id = :user_id")
        connection.execute(update_products_query, {"category_id": int(category_id), "user_id": int(user_id)})
        # Marcar categoría como inactiva
        query = text("UPDATE categories SET is_active = FALSE WHERE category_id = :category_id AND user_id = :user_id")
        connection.execute(query, {"category_id": int(category_id), "user_id": int(user_id)})
        connection.commit()

def update_sale(sale_id, data, user_id):
    with engine.connect() as connection:
        # Asegurarse que la fecha esté en formato correcto para TIMESTAMP
        if 'sale_date' in data:
            if isinstance(data['sale_date'], str):
                 data['sale_date'] = pd.to_datetime(data['sale_date']).to_pydatetime()
            elif isinstance(data['sale_date'], date) and not isinstance(data['sale_date'], datetime):
                 data['sale_date'] = datetime.combine(data['sale_date'], datetime.min.time())

        query = text("""
            UPDATE sales SET product_id = :product_id, quantity = :quantity,
            total_amount = :total_amount, sale_date = :sale_date, cogs_total = :cogs_total
            WHERE sale_id = :sale_id AND user_id = :user_id
        """)
        # Asegurarse que los valores numéricos sean correctos
        data['total_amount'] = float(data.get('total_amount', 0))
        data['cogs_total'] = float(data.get('cogs_total', 0))
        data['quantity'] = int(data.get('quantity', 0))
        data['product_id'] = data.get('product_id') # Puede ser None si se eliminó
        data['sale_id'] = int(sale_id)
        data['user_id'] = int(user_id)
        connection.execute(query, data)
        connection.commit()

def delete_sale(sale_id, user_id):
    """Elimina permanentemente un registro de venta."""
    with engine.connect() as connection:
        query = text("DELETE FROM sales WHERE sale_id = :sale_id AND user_id = :user_id")
        connection.execute(query, {"sale_id": int(sale_id), "user_id": int(user_id)})
        connection.commit()

def update_expense(expense_id, data, user_id):
     with engine.connect() as connection:
        # Asegurarse que la fecha esté en formato correcto para TIMESTAMP
        if 'expense_date' in data:
             if isinstance(data['expense_date'], str):
                  data['expense_date'] = pd.to_datetime(data['expense_date']).to_pydatetime()
             elif isinstance(data['expense_date'], date) and not isinstance(data['expense_date'], datetime):
                  data['expense_date'] = datetime.combine(data['expense_date'], datetime.min.time())

        query = text("""
            UPDATE expenses SET expense_category_id = :expense_category_id, amount = :amount, expense_date = :expense_date
            WHERE expense_id = :expense_id AND user_id = :user_id
        """)
        # Asegurarse que los valores numéricos sean correctos
        data['amount'] = float(data.get('amount', 0))
        data['expense_category_id'] = data.get('expense_category_id') # Puede ser None
        data['expense_id'] = int(expense_id)
        data['user_id'] = int(user_id)
        connection.execute(query, data)
        connection.commit()

def delete_expense(expense_id, user_id):
    """Elimina permanentemente un registro de gasto."""
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
    """Borrado suave de categoría de gasto."""
    with engine.connect() as connection:
        # Desvincular gastos de esta categoría
        update_expenses_query = text("UPDATE expenses SET expense_category_id = NULL WHERE expense_category_id = :category_id AND user_id = :user_id")
        connection.execute(update_expenses_query, {"category_id": int(category_id), "user_id": int(user_id)})
        # Marcar categoría como inactiva
        query = text("UPDATE expense_categories SET is_active = FALSE WHERE expense_category_id = :category_id AND user_id = :user_id")
        connection.execute(query, {"category_id": int(category_id), "user_id": int(user_id)})
        connection.commit()

def update_user_password(user_id, new_password_hash):
    """Actualiza la contraseña y marca que ya no necesita cambio forzado."""
    with engine.connect() as connection:
        query = text("""
            UPDATE users SET password = :password, must_change_password = FALSE
            WHERE id = :user_id
        """)
        connection.execute(query, {"password": new_password_hash, "user_id": int(user_id)})
        connection.commit()

# --- FUNCIONES PARA DROPDOWNS ---
def get_product_options(user_id):
    """Obtiene productos activos para dropdowns."""
    try:
        query = text("SELECT product_id as value, name || ' (Stock: ' || stock || ')' as label FROM products WHERE user_id = :user_id AND is_active = TRUE ORDER BY name")
        products_df = pd.read_sql(query, engine, params={"user_id": int(user_id)})
        return products_df.to_dict('records')
    except Exception as e:
        print(f"Error en get_product_options: {e}")
        return []

def get_category_options(user_id):
    """Obtiene categorías de producto activas para dropdowns."""
    try:
        query = text("SELECT category_id as value, name as label FROM categories WHERE user_id = :user_id AND is_active = TRUE ORDER BY name")
        categories_df = pd.read_sql(query, engine, params={"user_id": int(user_id)})
        return categories_df.to_dict('records')
    except Exception as e:
        print(f"Error en get_category_options: {e}")
        return []

def get_expense_category_options(user_id):
    """Obtiene categorías de gasto activas para dropdowns."""
    try:
        query = text("SELECT expense_category_id as value, name as label FROM expense_categories WHERE user_id = :user_id AND is_active = TRUE ORDER BY name")
        expense_cat_df = pd.read_sql(query, engine, params={"user_id": int(user_id)})
        return expense_cat_df.to_dict('records')
    except Exception as e:
        print(f"Error en get_expense_category_options: {e}")
        return []

# --- FUNCIÓN DE CÁLCULO FINANCIERO ---
def calculate_financials(start_date, end_date, user_id, see_all=False):
    """Calcula métricas financieras clave usando datos filtrados por fecha desde la BD."""
    user_id = int(user_id)
    products = load_products(user_id) # Carga todos (incl. inactivos) para lookups de merge

    # Usar filtros de fecha al cargar, a menos que see_all sea True
    if see_all:
        sales_df = load_sales(user_id)
        expenses_df = load_expenses(user_id)
    else:
        sales_df = load_sales(user_id, start_date=start_date, end_date=end_date)
        expenses_df = load_expenses(user_id, start_date=start_date, end_date=end_date)

    # Las columnas de fecha ya vienen como datetime gracias a parse_dates=['...']

    results = { # Diccionario de resultados
        "total_revenue": 0, "gross_profit": 0, "total_cogs": 0, "net_profit": 0,
        "num_sales": 0, "avg_ticket": 0, "net_margin": 0, "total_expenses": 0,
        "unidades_vendidas": 0, "gross_margin": 0, "sales_df": sales_df,
        "expenses_df": expenses_df, "merged_df": pd.DataFrame()
    }

    # Cálculos
    if not sales_df.empty:
        # Convertir columnas NUMERIC a float para cálculos en Pandas si es necesario
        numeric_cols_sales = ['quantity', 'total_amount', 'cogs_total']
        for col in numeric_cols_sales:
             if col in sales_df.columns:
                 sales_df[col] = pd.to_numeric(sales_df[col], errors='coerce')

        sales_df = sales_df.dropna(subset=numeric_cols_sales) # Eliminar filas con valores no numéricos

        results["num_sales"] = len(sales_df)
        results["unidades_vendidas"] = int(sales_df['quantity'].sum())
        results["total_cogs"] = float(sales_df['cogs_total'].sum())
        results["total_revenue"] = float(sales_df['total_amount'].sum())
        results["gross_profit"] = results["total_revenue"] - results["total_cogs"]

        if not products.empty:
            # Convertir columnas NUMERIC/REAL de products a float para merge
            numeric_cols_prod = ['price', 'cost', 'stock', 'alert_threshold']
            for col in numeric_cols_prod:
                if col in products.columns:
                     products[col] = pd.to_numeric(products[col], errors='coerce')
            # Merge (how='left' mantiene todas las ventas, incluso si el producto fue eliminado)
            results["merged_df"] = pd.merge(sales_df, products, on='product_id', how='left')

    if not expenses_df.empty:
         expenses_df['amount'] = pd.to_numeric(expenses_df['amount'], errors='coerce')
         expenses_df = expenses_df.dropna(subset=['amount'])
         results["total_expenses"] = float(expenses_df['amount'].sum())
    else:
         results["total_expenses"] = 0

    results["net_profit"] = results["gross_profit"] - results["total_expenses"]
    results["avg_ticket"] = results["total_revenue"] / results["num_sales"] if results["num_sales"] > 0 else 0
    results["net_margin"] = (results["net_profit"] / results["total_revenue"] * 100) if results["total_revenue"] != 0 else 0
    results["gross_margin"] = (results["gross_profit"] / results["total_revenue"] * 100) if results["total_revenue"] != 0 else 0

    return results

# ### FUNCIONES DE ADMINISTRACIÓN ###
def get_all_users():
    """Obtiene todos los usuarios con sus detalles."""
    query = text("""
        SELECT id, username, first_login, is_blocked, must_change_password, is_admin, last_block_change, subscription_end_date
        FROM users ORDER BY id
    """)
    # Parsear fechas al cargar
    return pd.read_sql(query, engine, parse_dates=['first_login', 'last_block_change', 'subscription_end_date'])

def record_first_login(user_id):
    """Registra la fecha y hora del primer login de un usuario."""
    with engine.connect() as connection:
        query = text("UPDATE users SET first_login = NOW() WHERE id = :user_id AND first_login IS NULL")
        connection.execute(query, {"user_id": int(user_id)})
        connection.commit()

def set_user_block_status(user_id, is_blocked):
    """Bloquea o desbloquea un usuario y registra la fecha del cambio."""
    with engine.connect() as connection:
        query = text("""
            UPDATE users
            SET is_blocked = :status, last_block_change = NOW()
            WHERE id = :user_id
        """)
        connection.execute(query, {"status": is_blocked, "user_id": int(user_id)})
        connection.commit()

def reset_user_password(user_id, new_hashed_password):
    """Resetea la contraseña de un usuario y lo fuerza a cambiarla."""
    with engine.connect() as connection:
        query = text("UPDATE users SET password = :password, must_change_password = TRUE WHERE id = :user_id")
        connection.execute(query, {"password": new_hashed_password, "user_id": int(user_id)})
        connection.commit()

def delete_user(user_id):
    """Elimina permanentemente un usuario y sus datos asociados (CASCADE)."""
    with engine.connect() as connection:
        query = text("DELETE FROM users WHERE id = :user_id")
        connection.execute(query, {"user_id": int(user_id)})
        connection.commit()

def create_user(username, hashed_password, is_admin, subscription_end_date):
    """Crea un nuevo usuario en la base de datos."""
    user_df = pd.DataFrame([{
        'username': username,
        'password': hashed_password,
        'must_change_password': True,
        'is_blocked': False,
        'is_admin': is_admin,
        'subscription_end_date': subscription_end_date # Puede ser None
    }])
    try:
        user_df.to_sql('users', engine, if_exists='append', index=False)
        return True, f"¡Usuario '{username}' creado con éxito!"
    except Exception as e:
        print(f"Error al crear usuario: {e}")
        # Podría ser más específico si revisamos el error (e.g., UNIQUE constraint)
        return False, "Error: El nombre de usuario ya existe o hubo un problema en la base de datos."

def extend_subscription(user_id, new_end_date):
    """Actualiza la fecha de fin de suscripción para un usuario (puede ser None)."""
    with engine.connect() as connection:
        query = text("UPDATE users SET subscription_end_date = :end_date WHERE id = :user_id")
        # Pasar None directamente si new_end_date es None
        connection.execute(query, {"end_date": new_end_date, "user_id": int(user_id)})
        connection.commit()


# --- FUNCIONES DE REACTIVACIÓN ---
def reactivate_product_category(category_id, user_id):
    """Reactiva una categoría de producto."""
    with engine.connect() as connection:
        query = text("UPDATE categories SET is_active = TRUE WHERE category_id = :category_id AND user_id = :user_id")
        connection.execute(query, {"category_id": int(category_id), "user_id": int(user_id)})
        connection.commit()

def reactivate_expense_category(category_id, user_id):
    """Reactiva una categoría de gasto."""
    with engine.connect() as connection:
        query = text("UPDATE expense_categories SET is_active = TRUE WHERE expense_category_id = :category_id AND user_id = :user_id")
        connection.execute(query, {"category_id": int(category_id), "user_id": int(user_id)})
        connection.commit()

# --- FUNCIÓN ATÓMICA PARA STOCK ---
def attempt_stock_deduction(product_id, quantity, user_id):
    """Intenta deducir stock de forma atómica. Devuelve True si tuvo éxito."""
    with engine.connect() as connection:
        with connection.begin(): # Usar transacción explícita
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
            # El commit es automático al salir del 'with connection.begin()' si no hay error
            return result.rowcount == 1 # True si 1 fila fue afectada (éxito)
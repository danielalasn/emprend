# update_tables.py
import os
from sqlalchemy import create_engine, text
from sqlalchemy.exc import ProgrammingError, InternalError

DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

if not DATABASE_URL:
    raise Exception("ERROR: La variable de entorno DATABASE_URL no está configurada.")

engine = create_engine(DATABASE_URL)

# --- Definiciones Completas de SQL ---

add_column_commands = [
    "ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT FALSE NOT NULL;",
    "ALTER TABLE users ADD COLUMN last_block_change TIMESTAMP DEFAULT NULL;",
    "ALTER TABLE users ADD COLUMN subscription_end_date DATE DEFAULT NULL;",
    "ALTER TABLE categories ADD COLUMN is_active BOOLEAN DEFAULT TRUE NOT NULL;",
    "ALTER TABLE expense_categories ADD COLUMN is_active BOOLEAN DEFAULT TRUE NOT NULL;",
    "ALTER TABLE products ADD COLUMN is_active BOOLEAN DEFAULT TRUE NOT NULL;",
]
alter_type_commands = [
    "ALTER TABLE sales ALTER COLUMN sale_date TYPE TIMESTAMP USING sale_date::timestamp;",
    "ALTER TABLE expenses ALTER COLUMN expense_date TYPE TIMESTAMP USING expense_date::timestamp;",
    "ALTER TABLE products ALTER COLUMN price TYPE NUMERIC(10, 2) USING price::numeric(10, 2);",
    "ALTER TABLE products ALTER COLUMN cost TYPE NUMERIC(10, 2) USING cost::numeric(10, 2);",
    "ALTER TABLE sales ALTER COLUMN total_amount TYPE NUMERIC(10, 2) USING total_amount::numeric(10, 2);",
    "ALTER TABLE sales ALTER COLUMN cogs_total TYPE NUMERIC(10, 2) USING cogs_total::numeric(10, 2);",
    "ALTER TABLE expenses ALTER COLUMN amount TYPE NUMERIC(10, 2) USING amount::numeric(10, 2);"
]
create_new_tables_sql = """
CREATE TABLE IF NOT EXISTS raw_materials (
    material_id SERIAL PRIMARY KEY, name TEXT NOT NULL, unit_measure TEXT NOT NULL,
    current_stock NUMERIC(10, 3) DEFAULT 0 NOT NULL, average_cost NUMERIC(10, 3) DEFAULT 0 NOT NULL,
    alert_threshold NUMERIC(10, 3) DEFAULT 0 NOT NULL, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    is_active BOOLEAN DEFAULT TRUE NOT NULL, UNIQUE(user_id, name)
);
CREATE TABLE IF NOT EXISTS product_materials (
    product_material_id SERIAL PRIMARY KEY, product_id INTEGER NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
    material_id INTEGER NOT NULL REFERENCES raw_materials(material_id) ON DELETE CASCADE,
    quantity_used NUMERIC(10, 3) NOT NULL, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS material_purchases (
    purchase_id SERIAL PRIMARY KEY, material_id INTEGER NOT NULL REFERENCES raw_materials(material_id) ON DELETE RESTRICT,
    quantity_purchased NUMERIC(10, 3) NOT NULL, total_cost NUMERIC(10, 2) NOT NULL,
    purchase_date TIMESTAMP NOT NULL, supplier TEXT, notes TEXT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE
);
"""
adjust_constraints_sql = """
DO $$ BEGIN ALTER TABLE products DROP CONSTRAINT IF EXISTS products_category_id_fkey; ALTER TABLE products ADD CONSTRAINT products_category_id_fkey FOREIGN KEY (category_id) REFERENCES categories(category_id) ON DELETE SET NULL; EXCEPTION WHEN duplicate_object THEN RAISE NOTICE 'Constraint products_category_id_fkey already exists or cannot be dropped.'; END $$;
DO $$ BEGIN ALTER TABLE sales DROP CONSTRAINT IF EXISTS sales_product_id_fkey; ALTER TABLE sales ADD CONSTRAINT sales_product_id_fkey FOREIGN KEY (product_id) REFERENCES products(product_id) ON DELETE SET NULL; EXCEPTION WHEN duplicate_object THEN RAISE NOTICE 'Constraint sales_product_id_fkey already exists or cannot be dropped.'; END $$;
DO $$ BEGIN ALTER TABLE expenses DROP CONSTRAINT IF EXISTS expenses_expense_category_id_fkey; ALTER TABLE expenses ADD CONSTRAINT expenses_expense_category_id_fkey FOREIGN KEY (expense_category_id) REFERENCES expense_categories(expense_category_id) ON DELETE SET NULL; EXCEPTION WHEN duplicate_object THEN RAISE NOTICE 'Constraint expenses_expense_category_id_fkey already exists or cannot be dropped.'; END $$;
"""
# --- Fin Definiciones SQL ---

print("Conectando a la base de datos para actualizar la estructura...")

def execute_sql_safely(connection, command, description):
    """Ejecuta un comando SQL, hace commit en éxito, rollback en error."""
    print(f"\nIntentando: {description}")
    print(f"   SQL: {command[:120].strip()}...")
    trans = None # Inicializar transacción fuera del try
    try:
        trans = connection.begin()
        connection.execute(text(command))
        trans.commit()
        print(f"   => ¡Éxito!")
        return True
    except (ProgrammingError, InternalError) as e:
        if trans:
            try: trans.rollback(); print("   => Rollback ejecutado tras error.")
            except Exception as rb_exc: print(f"   => ERROR durante rollback: {rb_exc}")

        pgcode = getattr(e.orig, 'pgcode', None)
        pgerror_msg = str(e).lower()

        if pgcode == '42701' or ("column" in pgerror_msg and "already exists" in pgerror_msg):
            print(f"   => Aviso: La columna ya existe.")
            return True # Continuar
        elif pgcode == '42P07' or ("relation" in pgerror_msg and "already exists" in pgerror_msg):
             print(f"   => Aviso: La tabla/objeto ya existe.")
             return True # Continuar
        elif pgcode == '42804' or "already of type" in pgerror_msg:
             print(f"   => Aviso: La columna ya es del tipo correcto.")
             return True # Continuar
        elif pgcode == '42710' or ("constraint" in pgerror_msg and "already exists" in pgerror_msg):
             print(f"   => Aviso: La restricción ya existe.")
             return True # Continuar
        elif "cannot be cast automatically" in pgerror_msg:
             print(f"   => Aviso: No se pudo convertir automáticamente el tipo. Revisa los datos.")
             return True
        elif pgcode == '25P02': # InFailedSqlTransaction
             print(f"   => ERROR: La transacción falló. El script anterior puede haber dejado la conexión en mal estado. Reintenta el script.")
             return False # Detener
        else:
            print(f"   => ERROR SQL al ejecutar comando: {e} (Code: {pgcode})")
            return False # Detener
    except Exception as e:
         if trans:
             try: trans.rollback(); print("   => Rollback ejecutado tras error inesperado.")
             except Exception as rb_exc: print(f"   => ERROR durante rollback: {rb_exc}")
         print(f"   => ERROR inesperado: {e}")
         return False # Detener
    return True

try:
    with engine.connect() as connection:
        print("\n--- Añadiendo columnas faltantes (si aplica) ---")
        for command in add_column_commands:
            if not execute_sql_safely(connection, command, "Añadir columna"):
                 print("!!! Script detenido por error irrecuperable. !!!"); exit()

        print("\n--- Modificando tipos de columna (si aplica) ---")
        for command in alter_type_commands:
             if not execute_sql_safely(connection, command, "Cambiar tipo columna"):
                 print("!!! Script detenido por error irrecuperable. !!!"); exit()

        print("\n--- Creando nuevas tablas (si no existen) ---")
        for create_cmd in create_new_tables_sql.strip().split(';'):
            if create_cmd.strip():
                if not execute_sql_safely(connection, create_cmd.strip() + ';', "Crear tabla"):
                    print("!!! Script detenido por error irrecuperable. !!!"); exit()

        print("\n--- Ajustando restricciones FK (si aplica) ---")
        for cmd_block in adjust_constraints_sql.split('END $$;'):
             if cmd_block.strip():
                 full_cmd = cmd_block.strip() + ' END $$;'
                 if not execute_sql_safely(connection, full_cmd, "Ajustar restricciones ON DELETE"):
                      print("!!! Script detenido por error irrecuperable. !!!"); exit()

except Exception as e:
    print(f"\nERROR: No se pudo conectar a la base de datos: {e}")

print("\nActualización de estructura de tablas completada (Revisa mensajes por errores).")
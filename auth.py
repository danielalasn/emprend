from flask_login import UserMixin, LoginManager
from werkzeug.security import generate_password_hash, check_password_hash
from database import engine
import pandas as pd
from sqlalchemy import text
from datetime import date # <-- Añadido

login_manager = LoginManager()

class User(UserMixin):
    # --- CORREGIDO: Añadido subscription_end_date ---
    def __init__(self, id, username, password, must_change_password, is_blocked, first_login, is_admin, subscription_end_date):
        self.id = id
        self.username = username
        self.password = password
        self.must_change_password = must_change_password
        self.is_blocked = is_blocked
        self.first_login = first_login
        self.is_admin = is_admin
        self.subscription_end_date = subscription_end_date # <-- Añadido

    @staticmethod
    def get(user_id):
        # --- CORREGIDO: Obtener y pasar subscription_end_date ---
        query = text("SELECT * FROM users WHERE id = :user_id")
        try:
            user_df = pd.read_sql(query, engine, params={"user_id": int(user_id)})
            if not user_df.empty:
                user_data = user_df.iloc[0]
                # Convertir a objeto date si no es None
                sub_end = pd.to_datetime(user_data['subscription_end_date']).date() if pd.notna(user_data['subscription_end_date']) else None
                return User(
                    id=user_data['id'],
                    username=user_data['username'],
                    password=user_data['password'],
                    must_change_password=user_data['must_change_password'],
                    is_blocked=user_data['is_blocked'],
                    first_login=user_data['first_login'],
                    is_admin=user_data['is_admin'],
                    subscription_end_date=sub_end # <-- Añadido
                )
        except Exception as e:
            print(f"Error getting user: {e}")
        return None

    @staticmethod
    def find(username):
        # --- CORREGIDO: Obtener y pasar subscription_end_date ---
        query = text("SELECT * FROM users WHERE username = :username")
        try:
            user_df = pd.read_sql(query, engine, params={"username": username})
            if not user_df.empty:
                user_data = user_df.iloc[0]
                # Convertir a objeto date si no es None
                sub_end = pd.to_datetime(user_data['subscription_end_date']).date() if pd.notna(user_data['subscription_end_date']) else None
                return User(
                    id=user_data['id'],
                    username=user_data['username'],
                    password=user_data['password'],
                    must_change_password=user_data['must_change_password'],
                    is_blocked=user_data['is_blocked'],
                    first_login=user_data['first_login'],
                    is_admin=user_data['is_admin'],
                    subscription_end_date=sub_end # <-- Añadido
                )
        except Exception as e:
            print(f"Error finding user: {e}")
        return None

# (set_password y check_password sin cambios)
def set_password(password):
    return generate_password_hash(password)

def check_password(hashed_password, password):
    return check_password_hash(hashed_password, password)
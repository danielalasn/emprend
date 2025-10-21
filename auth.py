from flask_login import UserMixin, LoginManager
from werkzeug.security import generate_password_hash, check_password_hash
from database import engine
import pandas as pd

login_manager = LoginManager()

class User(UserMixin):
    def __init__(self, id, username, password, must_change_password):
        self.id = id
        self.username = username
        self.password = password
        self.must_change_password = must_change_password

    @staticmethod
    def get(user_id):
        query = f"SELECT * FROM users WHERE id = {user_id}"
        try:
            user_df = pd.read_sql(query, engine)
            if not user_df.empty:
                user_data = user_df.iloc[0]
                return User(
                    id=user_data['id'], 
                    username=user_data['username'], 
                    password=user_data['password'],
                    must_change_password=user_data['must_change_password']
                )
        except Exception as e:
            print(f"Error getting user: {e}")
        return None

    @staticmethod
    def find(username):
        query = f"SELECT * FROM users WHERE username = '{username}'"
        try:
            user_df = pd.read_sql(query, engine)
            if not user_df.empty:
                user_data = user_df.iloc[0]
                return User(
                    id=user_data['id'], 
                    username=user_data['username'], 
                    password=user_data['password'],
                    must_change_password=user_data['must_change_password']
                )
        except Exception as e:
            print(f"Error finding user: {e}")
        return None

def set_password(password):
    return generate_password_hash(password)

def check_password(hashed_password, password):
    return check_password_hash(hashed_password, password)
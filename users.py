import pandas as pd
from database import engine, get_all_users, set_user_block_status, reset_user_password, delete_user
from auth import set_password
import os
import sys

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def show_users():
    users = get_all_users()
    print("--- Lista de Usuarios ---")
    if users.empty:
        print("No hay usuarios en el sistema.")
    else:
        print(users.to_string(index=False))
    print("-" * 25)

def find_user_id(username):
    users = get_all_users()
    user = users[users['username'].str.lower() == username.lower()]
    if user.empty:
        print(f"Error: No se encontró al usuario '{username}'.")
        return None
    return user.iloc[0]['id']

def create_new_user():
    print("--- Crear Nuevo Usuario ---")
    username = input("Ingresa el nombre de usuario nuevo: ")
    password = input("Ingresa la contraseña: ")
    
    if not username or not password:
        print("El nombre de usuario y la contraseña no pueden estar vacíos.")
        return

    hashed_password = set_password(password)
    
    user_df = pd.DataFrame([{
        'username': username, 
        'password': hashed_password,
        'must_change_password': True,
        'is_admin': True
    }])
    
    try:
        user_df.to_sql('users', engine, if_exists='append', index=False)
        print(f"\n¡Usuario '{username}' creado con éxito!")
        print("El usuario deberá cambiar su contraseña en su primer inicio de sesión.")
    except Exception as e:
        print(f"\nError al crear el usuario. Es posible que el nombre de usuario ya exista.")
        print(f"Detalle: {e}")

def toggle_block():
    username = input("Ingresa el nombre de usuario a bloquear/desbloquear: ")
    user_id = find_user_id(username)
    if not user_id: return

    users = get_all_users()
    is_blocked = users[users['id'] == user_id].iloc[0]['is_blocked']
    
    if is_blocked:
        print(f"El usuario '{username}' está actualmente BLOQUEADO.")
        action = input("¿Deseas DESBLOQUEARLO? (s/n): ").lower()
        if action == 's':
            set_user_block_status(user_id, False)
            print(f"¡Usuario '{username}' desbloqueado!")
    else:
        print(f"El usuario '{username}' está actualmente ACTIVO.")
        action = input("¿Deseas BLOQUEARLO? (s/n): ").lower()
        if action == 's':
            set_user_block_status(user_id, True)
            print(f"¡Usuario '{username}' bloqueado!")

def reset_pwd():
    username = input("Ingresa el nombre de usuario para resetear su contraseña: ")
    user_id = find_user_id(username)
    if not user_id: return
    
    new_password = input("Ingresa la nueva contraseña temporal: ")
    if not new_password:
        print("La contraseña no puede estar vacía.")
        return
        
    hashed_password = set_password(new_password)
    reset_user_password(user_id, hashed_password)
    print(f"¡Contraseña de '{username}' reseteada! El usuario deberá cambiarla en su próximo inicio de sesión.")

def delete_user_account():
    username = input("Ingresa el nombre de usuario a ELIMINAR (ESTA ACCIÓN ES IRREVERSIBLE): ")
    user_id = find_user_id(username)
    if not user_id: return
    
    confirm = input(f"ADVERTENCIA: Esto borrará al usuario '{username}' y TODOS sus datos (ventas, gastos, productos).\nEscribe '{username}' de nuevo para confirmar: ")
    
    if confirm == username:
        delete_user(user_id)
        print(f"Usuario '{username}' y todos sus datos han sido eliminados.")
    else:
        print("La confirmación no coincide. Operación cancelada.")

def main_menu():
    while True:
        clear_screen()
        print("--- Herramienta de Administración de Usuarios ---")
        print("1. Ver todos los usuarios")
        print("2. Crear un nuevo usuario")
        print("3. Bloquear / Desbloquear un usuario")
        print("4. Resetear contraseña de un usuario")
        print("5. Eliminar un usuario (¡Peligroso!)")
        print("6. Salir")
        choice = input("Selecciona una opción (1-6): ")
        
        clear_screen()
        if choice == '1':
            show_users()
        elif choice == '2':
            create_new_user()
        elif choice == '3':
            show_users()
            toggle_block()
        elif choice == '4':
            show_users()
            reset_pwd()
        elif choice == '5':
            show_users()
            delete_user_account()
        elif choice == '6':
            print("Saliendo...")
            break
        else:
            print("Opción no válida. Inténtalo de nuevo.")
        
        input("\nPresiona Enter para continuar...")

if __name__ == "__main__":
    if not os.environ.get('DATABASE_URL'):
        print("ERROR: La variable de entorno DATABASE_URL no está configurada.")
        print("Por favor, configúrala antes de ejecutar este script.")
        sys.exit()
    main_menu()
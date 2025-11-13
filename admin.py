# admin.py
from dash import dcc, html, dash_table
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
import pandas as pd
from flask_login import current_user
import dash
import random
import string
from datetime import date, timedelta # <-- Añadido

from app import app
from database import (
    get_all_users, create_user, set_user_block_status,
    reset_user_password, delete_user, extend_subscription # <-- Añadido extend_subscription
)
from auth import set_password # Para hashear la nueva contraseña

def get_layout():
    """Devuelve el layout del panel de administración."""
    if not current_user.is_admin:
        return dbc.Alert("No tienes permisos para ver esta página.", color="danger")

    today = date.today()
    one_month_later = today + timedelta(days=30)

    return html.Div(className="p-2 p-md-4", children=[ # Padding responsivo
        dcc.Store(id='admin-user-id-store'), 
        dcc.Store(id='admin-username-store'), 

        # --- Modales (Sin cambios estructurales) ---
        dbc.Modal([
            dbc.ModalHeader("Confirmar Reseteo de Contraseña"),
            dbc.ModalBody([
                html.P(id='admin-reset-modal-text'),
                dbc.Label("Nueva Contraseña Temporal:", className="mt-2"),
                dbc.Input(id="admin-new-temp-password", type="text", placeholder="Ingresa la nueva contraseña temporal...")
            ]),
            dbc.ModalFooter([
                dbc.Button("Cancelar", id="admin-cancel-reset-button", color="secondary"),
                dbc.Button("Resetear", id="admin-confirm-reset-button", color="warning"),
            ]),
        ], id="admin-reset-modal", is_open=False),

        dbc.Modal([
            dbc.ModalHeader("Confirmar Eliminación Permanente de Usuario"),
            dbc.ModalBody([
                html.P(id='admin-delete-modal-text'), 
                html.Div(id='admin-delete-modal-alert', className="mt-2"), 
                dbc.Label("Para confirmar, escribe la frase exacta:", className="mt-3 fw-bold"),
                dbc.Input(id="admin-delete-confirm-input", type="text", placeholder="eliminar [nombre de usuario]", className="mb-2")
            ]),
            dbc.ModalFooter([
                dbc.Button("Cancelar", id="admin-cancel-delete-button", color="secondary"),
                dbc.Button("ELIMINAR PERMANENTEMENTE", id="admin-confirm-delete-button", color="danger"),
            ]),
        ], id="admin-delete-modal", is_open=False),

        dbc.Modal([
            dbc.ModalHeader("Extender Suscripción"),
            dbc.ModalBody([
                html.P(id='admin-extend-modal-text'),
                dbc.Label("Nueva Fecha de Vencimiento:", className="mt-2"),
                dcc.DatePickerSingle(
                    id='admin-extend-date-picker',
                    min_date_allowed=today,
                    initial_visible_month=today,
                    date=one_month_later,
                    display_format='YYYY-MM-DD',
                    className="w-100",
                    disabled=False 
                ),
                dbc.Switch(
                    id="admin-extend-no-expiry-switch",
                    label="Sin fecha de vencimiento (permanente)",
                    value=False, 
                    className="my-2"
                ),
            ]),
             dbc.ModalFooter([
                dbc.Button("Cancelar", id="admin-cancel-extend-button", color="secondary"),
                dbc.Button("Guardar Nueva Fecha", id="admin-confirm-extend-button", color="success"),
            ]),
        ], id="admin-extend-modal", is_open=False),


        # --- Layout Principal Responsivo ---
        dbc.Row([
            # Columna Izquierda: Crear Usuario
            # xs=12 (Celular: ancho completo) | md=4 (PC: 1/3 de ancho)
            dbc.Col([
                dbc.Card(className="shadow-sm border-0 h-100", children=[ # Estilo consistente
                    dbc.CardHeader(html.H4("Crear Nuevo Usuario", className="m-0")),
                    dbc.CardBody([
                        html.Div(id="admin-create-alert"),
                        dbc.Label("Nombre de Usuario:", className="fw-bold small"),
                        dbc.Input(id="admin-new-username", type="text", className="mb-2"),
                        dbc.Label("Contraseña Temporal:", className="fw-bold small"),
                        dbc.Input(id="admin-new-password", type="text", className="mb-2"),

                        dbc.Label("Vencimiento Suscripción:", className="fw-bold small"),
                        dcc.DatePickerSingle(
                            id='admin-subscription-date-picker',
                            min_date_allowed=today,
                            initial_visible_month=today,
                            date=one_month_later,
                            display_format='YYYY-MM-DD',
                            className="w-100", 
                            disabled=False 
                        ),
                        
                        dbc.Switch(
                            id="admin-no-expiry-switch",
                            label="Sin fecha de vencimiento",
                            value=False, 
                            className="my-2 small text-muted" 
                        ),
                        
                        dbc.Switch(
                            id="admin-is-admin-switch",
                            label="¿Es Administrador?",
                            value=False,
                            className="mb-3 small text-muted"
                        ),
                        dbc.Button("Crear Usuario", id="admin-create-user-button", color="primary", className="w-100")
                    ])
                ])
            ], xs=12, md=4, className="mb-4 mb-md-0"), # Margen inferior solo en móvil

            # Columna Derecha: Lista de Usuarios
            # xs=12 (Celular) | md=8 (PC: 2/3 de ancho)
            dbc.Col([
                dbc.Card(className="shadow-sm border-0 h-100", children=[
                    dbc.CardHeader(html.H4("Gestionar Usuarios", className="m-0")),
                    dbc.CardBody([
                        html.Div(id="admin-action-alert"),
                        
                        # Tabla con scroll horizontal
                        html.Div(
                            dash_table.DataTable(
                                id='admin-users-table',
                                columns=[
                                    {"name": "ID", "id": "id"},
                                    {"name": "Usuario", "id": "username"},
                                    {"name": "Admin", "id": "is_admin"},
                                    {"name": "Bloqueado", "id": "is_blocked"},
                                    {"name": "Vencimiento", "id": "subscription_end_date_display", "type": "datetime"}, 
                                    {"name": "Forzar Pass", "id": "must_change_password"},
                                    {"name": "Bloquear", "id": "action-block", "presentation": "markdown"},
                                    {"name": "Resetear", "id": "action-reset", "presentation": "markdown"},
                                    {"name": "Extender", "id": "action-extend", "presentation": "markdown"}, 
                                    {"name": "Eliminar", "id": "action-delete", "presentation": "markdown"},
                                ],
                                data=[],
                                page_size=10,
                                sort_action='native',
                                filter_action='native',
                                style_data_conditional=[
                                    { 'if': { 'filter_query': '{subscription_status} = "Expirado"', 'column_id': 'subscription_end_date_display'}, 'backgroundColor': '#FFCCCB', 'color': 'black'},
                                    { 'if': { 'filter_query': '{subscription_status} = "Expira Pronto"', 'column_id': 'subscription_end_date_display'}, 'backgroundColor': '#FFFFE0', 'color': 'black'}
                                ],
                                # Estilos de celda optimizados para móvil
                                style_cell={
                                    'textAlign': 'left', 
                                    'minWidth': '80px', 'width': '100px', 'maxWidth': '150px', 
                                    'overflow': 'hidden', 'textOverflow': 'ellipsis'
                                },
                                style_cell_conditional=[ 
                                    {'if': {'column_id': 'action-block'}, 'cursor': 'pointer', 'textAlign': 'center', 'width': '80px'},
                                    {'if': {'column_id': 'action-reset'}, 'cursor': 'pointer', 'textAlign': 'center', 'width': '80px'},
                                    {'if': {'column_id': 'action-extend'}, 'cursor': 'pointer', 'textAlign': 'center', 'width': '80px'},
                                    {'if': {'column_id': 'action-delete'}, 'cursor': 'pointer', 'textAlign': 'center', 'width': '80px'},
                                    {'if': {'column_id': 'username'}, 'minWidth': '120px'},
                                    {'if': {'column_id': 'subscription_end_date_display'}, 'minWidth': '100px'},
                                ],
                                markdown_options={"html": True}
                            ),
                            style={'overflowX': 'auto', 'width': '100%'} # Scroll horizontal crítico
                        )
                    ])
                ])
            ], xs=12, md=8)
        ])
    ])

def register_callbacks(app):

    # --- CORREGIDO: Lógica de formato de fecha y estado de suscripción ---
    @app.callback(
        Output('admin-users-table', 'data'),
        Output('admin-create-alert', 'children'),
        Output('admin-action-alert', 'children'),
        Input('store-data-signal', 'data'),
    )
    def refresh_admin_table(signal):
        """Recarga la tabla de usuarios."""
        if not current_user.is_authenticated or not current_user.is_admin:
            return [], None, None

        users_df = get_all_users()
        today = date.today()

        # Formato y estado de suscripción
        # 1. Convertir a datetime (sin .dt.date), manejar errores (NULLs -> NaT)
        users_df['subscription_end_date_dt'] = pd.to_datetime(users_df['subscription_end_date'], errors='coerce')
        # 2. Formatear usando .dt (ahora funciona), y rellenar NaT con '-'
        users_df['subscription_end_date_display'] = users_df['subscription_end_date_dt'].dt.strftime('%Y-%m-%d').fillna('-')

        # 3. Función get_status (usar la columna _dt y date() para comparar)
        def get_status(row):
            sub_date = row['subscription_end_date_dt'].date() if pd.notna(row['subscription_end_date_dt']) else None
            if sub_date is None: return "OK"
            if sub_date < today: return "Expirado"
            if sub_date <= today + timedelta(days=5): return "Expira Pronto"
            return "OK"

        users_df['subscription_status'] = users_df.apply(get_status, axis=1)

        # Añadir iconos de acción
        users_df['action-block'] = [f" { '✅' if r['is_blocked'] else '❌' } " for i, r in users_df.iterrows()]
        users_df['action-reset'] = "🔑"
        users_df['action-extend'] = "📅"
        users_df['action-delete'] = "🗑️"

        # Seleccionar y renombrar columnas para la tabla
        columns_to_show = ['id', 'username', 'is_admin', 'is_blocked',
                           'subscription_end_date_display', 'subscription_status',
                           'must_change_password', 'action-block',
                           'action-reset', 'action-extend', 'action-delete']
        return users_df[columns_to_show].to_dict('records'), None, None

    @app.callback(
        Output('admin-extend-date-picker', 'disabled'),
        Input('admin-extend-no-expiry-switch', 'value')
    )
    def toggle_extend_date_picker_disabled(no_expiry):
        """Habilita o deshabilita el date picker del modal de extensión."""
        return no_expiry # Si 'no_expiry' es True, el date picker se deshabilita
    

    @app.callback(
        Output('admin-subscription-date-picker', 'disabled'),
        Input('admin-no-expiry-switch', 'value')
    )
    def toggle_date_picker_disabled(no_expiry):
        """Habilita o deshabilita el date picker basado en el switch."""
        return no_expiry # Si 'no_expiry' es True, el date picker se deshabilita
    
    # --- CORREGIDO: Añadido state para fecha de suscripción ---
# --- CORREGIDO: Añadido state para switch 'no_expiry' ---
    @app.callback(
        Output('store-data-signal', 'data', allow_duplicate=True),
        Output('admin-create-alert', 'children', allow_duplicate=True),
        Output('admin-new-username', 'value'),
        Output('admin-new-password', 'value'),
        Input('admin-create-user-button', 'n_clicks'),
        [State('admin-new-username', 'value'),
         State('admin-new-password', 'value'), # <-- Password input
         State('admin-is-admin-switch', 'value'),
         State('admin-subscription-date-picker', 'date'),
         State('admin-no-expiry-switch', 'value'),
         State('store-data-signal', 'data')],
        prevent_initial_call=True
    )
    def handle_create_user(n, username, password, is_admin, sub_date, no_expiry, signal):
        if n is None: raise PreventUpdate

        # --- START CORRECTION ---
        # 1. Validate username
        if not username:
            return dash.no_update, dbc.Alert("Nombre de usuario es obligatorio.", color="warning"), dash.no_update, dash.no_update

        # 2. Validate password (Now mandatory)
        if not password:
            return dash.no_update, dbc.Alert("La contraseña temporal es obligatoria.", color="warning"), username, dash.no_update # Keep username

        # 3. Validate date (only if expiry switch is off)
        if not no_expiry and not sub_date:
             return dash.no_update, dbc.Alert("Fecha de vencimiento de suscripción es obligatoria (o marca 'Sin fecha de vencimiento').", color="warning"), username, password # Keep user/pass
        # --- END CORRECTION ---

        # Determine final subscription date (no changes here)
        final_sub_date = None if no_expiry else sub_date

        # Hash password and create user (no changes here)
        hashed_password = set_password(password)
        success, message = create_user(username, hashed_password, is_admin, final_sub_date)

        if success:
            # --- START CORRECTION ---
            # 4. Simplify success message (no need to check for generated password)
            alert_message = f"¡Usuario '{username}' creado!"
            # --- END CORRECTION ---
            if final_sub_date:
                alert_message += f" Vence: {final_sub_date}"
            else:
                 alert_message += " (Sin vencimiento)"
            # Clear fields on success
            return (signal or 0) + 1, dbc.Alert(alert_message, color="success"), "", ""
        else:
            # Keep fields on error
            return dash.no_update, dbc.Alert(message, color="danger"), username, password
    # --- CORREGIDO: Manejar acción de extender y limpiar campo de delete ---
    @app.callback(
        Output('admin-reset-modal', 'is_open'),
        Output('admin-delete-modal', 'is_open'),
        Output('admin-extend-modal', 'is_open'), # <-- NUEVO OUTPUT
        Output('store-data-signal', 'data', allow_duplicate=True),
        Output('admin-action-alert', 'children', allow_duplicate=True),
        Output('admin-user-id-store', 'data'),
        Output('admin-username-store', 'data'),
        Output('admin-reset-modal-text', 'children'),
        Output('admin-delete-modal-text', 'children'),
        Output('admin-extend-modal-text', 'children'), # <-- NUEVO OUTPUT
        Output('admin-delete-confirm-input', 'value', allow_duplicate=True),
        Output('admin-extend-date-picker', 'date'), # <-- NUEVO OUTPUT (reset date)
        Input('admin-users-table', 'active_cell'),
        State('admin-users-table', 'derived_virtual_data'),
        State('store-data-signal', 'data'),
        prevent_initial_call=True
    )
    def open_admin_modals(active_cell, data, signal):
        """Maneja los clics en los iconos de acción de la tabla."""
        if not active_cell or 'row' not in active_cell:
            raise PreventUpdate

        row_idx = active_cell['row']
        col_id = active_cell['column_id']

        # Añadido 'action-extend' a la lista
        if not data or row_idx >= len(data) or col_id not in ['action-block', 'action-reset', 'action-extend', 'action-delete']:
            raise PreventUpdate

        user_info = data[row_idx]
        user_id = user_info['id']
        username = user_info['username']

        # Definir salidas por defecto (ahora 12)
        no_update_tuple = (False, False, False, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update)

        # --- Lógica de Bloquear/Desbloquear ---
        if col_id == 'action-block':
            new_status = not user_info['is_blocked']
            set_user_block_status(user_id, new_status)
            status_text = "bloqueado" if new_status else "desbloqueado"
            alert = dbc.Alert(f"Usuario '{username}' ha sido {status_text}.", color="info")
            # Indices: (reset, delete, extend, signal, alert, user_id, username, reset_txt, delete_txt, extend_txt, confirm_input, extend_date)
            return False, False, False, (signal or 0) + 1, alert, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update

        # --- Lógica de Resetear Contraseña ---
        if col_id == 'action-reset':
            confirmation_text = f"Ingresa la nueva contraseña temporal para '{username}'. El usuario deberá cambiarla en su próximo inicio de sesión."
            return True, False, False, dash.no_update, dash.no_update, user_id, dash.no_update, confirmation_text, dash.no_update, dash.no_update, dash.no_update, dash.no_update

        # --- NUEVA LÓGICA: Extender Suscripción ---
        if col_id == 'action-extend':
            current_end_date_str = user_info['subscription_end_date_display']
            extend_text = f"Extendiendo suscripción para '{username}'. Vencimiento actual: {current_end_date_str}"
            default_new_date = date.today() + timedelta(days=30)
            if current_end_date_str != '-':
                try:
                    current_end_date = date.fromisoformat(current_end_date_str)
                    if current_end_date > date.today():
                         default_new_date = current_end_date + timedelta(days=30)
                except ValueError:
                    pass # Si la fecha tiene formato incorrecto, usa el default

            return False, False, True, dash.no_update, dash.no_update, user_id, username, dash.no_update, dash.no_update, extend_text, dash.no_update, default_new_date


        # --- Lógica de Eliminar Usuario ---
        if col_id == 'action-delete':
            warning_text = f"¡PELIGRO! Estás a punto de eliminar permanentemente al usuario '{username}' y TODOS sus datos asociados..."
            # Limpiar campo de confirmación al abrir
            return False, True, False, dash.no_update, dash.no_update, user_id, username, dash.no_update, warning_text, dash.no_update, "", dash.no_update

        return no_update_tuple


    # --- CALLBACK CORREGIDO: Resetear Contraseña (Admin ingresa pass) ---
    @app.callback(
        Output('admin-reset-modal', 'is_open', allow_duplicate=True),
        Output('store-data-signal', 'data', allow_duplicate=True),
        Output('admin-action-alert', 'children', allow_duplicate=True),
        Output('admin-new-temp-password', 'value'), # <-- Limpiar campo
        Input('admin-confirm-reset-button', 'n_clicks'),
        [State('admin-user-id-store', 'data'),
         State('admin-new-temp-password', 'value'), # <-- Leer input
         State('store-data-signal', 'data')],
        prevent_initial_call=True
    )
    def handle_reset_password(n, user_id, temp_password, signal):
        """Maneja la confirmación de resetear contraseña."""
        if n is None or not user_id: raise PreventUpdate

        # Validar contraseña ingresada
        if not temp_password:
            # Mantener modal abierto, sin señal, mostrar error (usamos action-alert), no limpiar campo
            return True, dash.no_update, dbc.Alert("La contraseña temporal no puede estar vacía.", color="warning"), dash.no_update

        hashed_password = set_password(temp_password)
        reset_user_password(user_id, hashed_password)

        alert = dbc.Alert(f"¡Contraseña reseteada exitosamente!", color="success")
        # Cerrar modal, enviar señal, mostrar éxito, limpiar campo
        return False, (signal or 0) + 1, alert, ""

    # --- CALLBACK CORREGIDO: Eliminar Usuario (con confirmación de texto) ---
    @app.callback(
        Output('admin-delete-modal', 'is_open', allow_duplicate=True),
        Output('store-data-signal', 'data', allow_duplicate=True),
        Output('admin-action-alert', 'children', allow_duplicate=True),
        Output('admin-delete-modal-alert', 'children'), # Alerta interna
        Output('admin-delete-confirm-input', 'value'), # Limpiar campo
        Input('admin-confirm-delete-button', 'n_clicks'),
        [State('admin-user-id-store', 'data'),
         State('admin-username-store', 'data'), # <-- Nuevo State
         State('admin-delete-confirm-input', 'value'), # <-- Nuevo State
         State('store-data-signal', 'data')],
        prevent_initial_call=True
    )
    def handle_delete_user(n, user_id, username, confirm_input, signal):
        """Maneja la confirmación de eliminar usuario con validación de texto."""
        if n is None or not user_id or not username:
            raise PreventUpdate

        expected_confirmation = f"eliminar {username}"

        # Verificar si la confirmación escrita es correcta
        if confirm_input != expected_confirmation:
            alert_modal = dbc.Alert(f"Texto incorrecto. Escribe exactamente '{expected_confirmation}'.", color="warning")
            # Mantener modal, sin señal, sin alerta afuera, alerta adentro, no limpiar campo
            return True, dash.no_update, dash.no_update, alert_modal, dash.no_update

        # Si la confirmación es correcta, proceder con la eliminación
        try:
            delete_user(user_id)
            alert_main = dbc.Alert(f"Usuario '{username}' (ID: {user_id}) eliminado permanentemente.", color="danger")
            # Cerrar modal, enviar señal, alerta afuera, limpiar alerta adentro, limpiar campo
            return False, (signal or 0) + 1, alert_main, None, ""
        except Exception as e:
            print(f"Error al eliminar usuario {user_id}: {e}")
            error_alert_modal = dbc.Alert(f"Error al eliminar: {e}", color="danger")
            # Mantener modal, sin señal, sin alerta afuera, alerta adentro, no limpiar campo
            return True, dash.no_update, dash.no_update, error_alert_modal, dash.no_update


    # --- NUEVO CALLBACK: Guardar extensión de suscripción ---
# --- NUEVO CALLBACK: Guardar extensión de suscripción ---
    @app.callback(
        Output('admin-extend-modal', 'is_open', allow_duplicate=True),
        Output('store-data-signal', 'data', allow_duplicate=True),
        Output('admin-action-alert', 'children', allow_duplicate=True),
        Input('admin-confirm-extend-button', 'n_clicks'),
        [State('admin-user-id-store', 'data'),
         State('admin-extend-date-picker', 'date'),
         State('admin-extend-no-expiry-switch', 'value'), # <-- NUEVO STATE
         State('store-data-signal', 'data')],
         prevent_initial_call=True
    )
    def handle_extend_subscription(n, user_id, new_date, no_expiry, signal): # <-- Nuevo param
        if n is None or not user_id: raise PreventUpdate

        # --- INICIO CORRECCIÓN ---
        # Determinar la fecha final a guardar
        final_new_date = None

        if not no_expiry: # Si NO se marcó "Sin vencimiento"
            if not new_date: # Y no se seleccionó fecha
                 # Idealmente, mostrar alerta dentro del modal
                return True, dash.no_update, dbc.Alert("Debes seleccionar una nueva fecha de vencimiento o marcar 'Sin fecha de vencimiento'.", color="warning")
            final_new_date = new_date # Usar la fecha seleccionada
        # Si SÍ se marcó "Sin vencimiento", final_new_date se queda como None
        # --- FIN CORRECCIÓN ---

        try:
            # --- CORREGIDO: Pasar final_new_date ---
            extend_subscription(user_id, final_new_date)

            # Ajustar mensaje de éxito
            if final_new_date:
                alert_main = dbc.Alert(f"Suscripción extendida hasta {final_new_date}.", color="success")
            else:
                alert_main = dbc.Alert("Suscripción actualizada a 'Sin vencimiento'.", color="success")

            return False, (signal or 0) + 1, alert_main
        except Exception as e:
             print(f"Error al extender suscripción para {user_id}: {e}")
             alert_main = dbc.Alert(f"Error al extender suscripción: {e}", color="danger")
             return True, dash.no_update, alert_main # Mantener modal abierto
    # --- Callbacks para cerrar modales ---
    @app.callback(
        Output('admin-reset-modal', 'is_open', allow_duplicate=True),
        Output('admin-delete-modal', 'is_open', allow_duplicate=True),
        Output('admin-extend-modal', 'is_open', allow_duplicate=True), # <-- Añadido
        [Input('admin-cancel-reset-button', 'n_clicks'),
         Input('admin-cancel-delete-button', 'n_clicks'),
         Input('admin-cancel-extend-button', 'n_clicks')], # <-- Añadido
        prevent_initial_call=True
    )
    def close_admin_modals(n_reset, n_delete, n_extend): # <-- Añadido n_extend
        triggered = dash.callback_context.triggered_id
        if triggered in ['admin-cancel-reset-button', 'admin-cancel-delete-button', 'admin-cancel-extend-button']:
            return False, False, False
        raise PreventUpdate
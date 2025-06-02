# dashboard_tactico_app.py (VERSIÓN FINAL CON PANTALLA DE GAME OVER)

from flask import Flask, request, render_template, redirect, url_for, jsonify
import json
import os
from datetime import datetime

app = Flask(__name__)

DATA_DIR = "data_dashboard"
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

current_alert_data = None
current_event_id = None
alert_received_time = None
new_alert_posted_flag = False

CONFIG = {}
try:
    with open("config.json", "r") as f_main_config:
        CONFIG = json.load(f_main_config)
except Exception:
    app.logger.warn("dashboard_tactico_app.py no pudo cargar config.json principal.")

@app.route('/', methods=['GET'])
def index():
    global current_alert_data, current_event_id, alert_received_time

    # --- MODIFICADO: Comprobar si el juego ha terminado y qué pantalla mostrar ---
    if current_alert_data and current_alert_data.get('game_status'):
        status = current_alert_data.get('game_status')
        if status == 'VICTORY':
            return render_template('victory.html', result=current_alert_data)
        elif status == 'DEFEAT':
            return render_template('game_over.html', result=current_alert_data)
        # Podrías añadir un else aquí para un estado desconocido, pero no debería ocurrir.
    # ----------------------------------------------------------------------

    alert_to_display = None
    time_left_for_decision = 0
    zone_css_class = "zone-default"
    available_heroes_flags = {"Sonic": False, "Tails": False, "Knuckles": False}

    timeout_seconds_from_config = CONFIG.get("dashboard_tactico", {}).get("decision_timeout_seconds", 40)

    if current_event_id: # Solo procesar si no es game_over (ya que current_event_id sería 'GAME_OVER')
        decision_file_path = os.path.join(DATA_DIR, f"decision_{current_event_id}.json")
        auto_decision_file_path = os.path.join(DATA_DIR, f"auto_decision_{current_event_id}.json")

        if os.path.exists(decision_file_path) or os.path.exists(auto_decision_file_path):
            app.logger.info(f"Decisión para {current_event_id} ya procesada. Limpiando dashboard.")
            current_alert_data = None # Limpiar para que no re-muestre game_over si se recarga sin /reset
            current_event_id = None
            alert_received_time = None
        elif current_alert_data: # Asegurarse de que current_alert_data no sea un estado de fin de juego aquí
            alert_to_display = current_alert_data
            if alert_received_time:
                elapsed_time = (datetime.now() - alert_received_time).total_seconds()
                time_left_for_decision = max(0, timeout_seconds_from_config - elapsed_time)
            
            if alert_to_display.get("location_details"): # Solo si es una alerta normal
                zone_css_class = alert_to_display["location_details"].get("css_class", "zone-unknown")
                known_heroes = alert_to_display["location_details"].get("known_nearby_heroes", [])
                for hero in known_heroes:
                    if hero in available_heroes_flags:
                        available_heroes_flags[hero] = True
    
    return render_template('dashboard_v2.html', 
                           alert=alert_to_display, 
                           event_id=current_event_id, 
                           time_left=int(time_left_for_decision),
                           zone_class=zone_css_class,
                           heroes_flags=available_heroes_flags,
                           poll_interval=CONFIG.get("dashboard_tactico", {}).get("dashboard_refresh_poll_seconds", 3) * 1000
                           )

# La función submit_alert_data no necesita cambios, ya que simplemente guarda lo que recibe.
@app.route('/submit_alert_data', methods=['POST'])
def submit_alert_data():
    global current_alert_data, current_event_id, alert_received_time, new_alert_posted_flag
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "No hay datos"}), 400

        # Si es un estado de fin de juego, el event_id será 'GAME_OVER'
        if data.get('game_status'):
             current_event_id = 'GAME_OVER'
        elif 'event_id' in data:
            if current_event_id and current_event_id != data["event_id"]:
                app.logger.warn(f"Recibida nueva alerta {data['event_id']} mientras {current_event_id} estaba activo. Sobrescribiendo.")
            current_event_id = data["event_id"]
        else:
             return jsonify({"status": "error", "message": "Datos inválidos"}), 400
        
        current_alert_data = data
        alert_received_time = datetime.now()
        new_alert_posted_flag = True
        
        app.logger.info(f"Nuevos datos recibidos en dashboard: {current_event_id}")
        return jsonify({"status": "success", "message": "Datos recibidos"}), 200
    except Exception as e:
        app.logger.error(f"Error en submit_alert_data: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/decision_made') # Esta es la ruta que define el endpoint
def decision_made():      # Este es el nombre del endpoint que url_for() busca
    event_id = request.args.get('event_id', 'N/A')
    message = request.args.get('message', 'Decisión procesada.')
    image_name = request.args.get('image_name', None)
    return render_template('decision_made_v2.html', event_id=event_id, message=message, image_name=image_name)

# La función make_decision y check_new_alert no necesitan cambios.
@app.route('/check_new_alert', methods=['GET'])
def check_new_alert():
    """Endpoint para que el cliente (JavaScript) pregunte si hay una nueva alerta."""
    global new_alert_posted_flag, current_event_id
    if new_alert_posted_flag and current_event_id:
        # Si es un estado de fin de juego, no lo indicamos como 'new_alert' para recarga, 
        # ya que la página de game_over se manejará directamente.
        if current_alert_data and current_alert_data.get('game_status'):
             return jsonify({"new_alert": False}) # No recargar si es game over

        new_alert_posted_flag = False # Resetear el flag una vez que el cliente lo sabe
        app.logger.debug(f"Cliente consultó /check_new_alert. Nueva alerta {current_event_id} indicada.")
        return jsonify({"new_alert": True, "event_id": current_event_id})
    return jsonify({"new_alert": False})

@app.route('/make_decision', methods=['POST'])
def make_decision():
    global current_alert_data, current_event_id, alert_received_time
    try:
        event_id_form = request.form.get('event_id')
        action = request.form.get('action')

        if not event_id_form or not action:
            return "Error: Faltan datos en la decisión.", 400

        target_destinations = ["LogDB"]
        # Lógica para determinar el nombre de la imagen basada en la acción
        image_name = "logdb.png" # Imagen por defecto

        if action == "sonic_only":
            target_destinations.append("Sonic")
            image_name = "sonic.png"
        elif action == "tails_only":
            target_destinations.append("Tails")
            image_name = "tails.png"
        elif action == "knuckles_only":
            target_destinations.append("Knuckles")
            image_name = "knuckles.png"
        elif action == "sonic_tails":
            target_destinations.extend(["Sonic", "Tails"])
            image_name = "sonic_tails.png" 
        elif action == "all_heroes":
            target_destinations.extend(["Sonic", "Tails", "Knuckles"])
            image_name = "all_heroes.png" 
        elif action == "register_only":
            pass # Ya tiene la imagen por defecto logdb.png

        decision_data = {
            "event_id": event_id_form,
            "user_decision": action,
            "target_destinations": list(set(target_destinations))
        }

        decision_file_path = os.path.join(DATA_DIR, f"decision_{event_id_form}.json")
        auto_decision_file_path = os.path.join(DATA_DIR, f"auto_decision_{event_id_form}.json")

        message_to_user = ""
        if os.path.exists(auto_decision_file_path):
            message_to_user = f"La decisión para el evento {event_id_form} fue tomada automáticamente (timeout). Tu selección de '{action}' no fue procesada."
            image_name = "timeout.png" 
        elif os.path.exists(decision_file_path):
            message_to_user = f"Una decisión previa ya fue registrada para el evento {event_id_form}."
            # Podrías intentar leer la decisión previa para obtener la imagen correcta si es necesario
            # o simplemente mantener la imagen de la acción actual.
        else:
            with open(decision_file_path, 'w') as f:
                json.dump(decision_data, f, indent=4)
            message_to_user = f"Decisión '{action}' registrada para el evento {event_id_form}."

        if event_id_form == current_event_id: # Solo limpiar si es la alerta actual
            current_alert_data = None
            current_event_id = None
            alert_received_time = None

        return redirect(url_for('decision_made', event_id=event_id_form, message=message_to_user, image_name=image_name))
    except Exception as e:
        app.logger.error(f"Error en make_decision: {e}")
        return "Error procesando la decisión.", 500

# --- NUEVO: Ruta para reiniciar el juego ---
@app.route('/reset')
def reset():
    """Resetea el estado del dashboard para empezar de nuevo."""
    global current_alert_data, current_event_id, alert_received_time, new_alert_posted_flag
    current_alert_data = None
    current_event_id = None
    alert_received_time = None
    new_alert_posted_flag = False
    app.logger.info("Dashboard reseteado. Listo para una nueva partida.")
    return redirect(url_for('index'))
# ---------------------------------------------

if __name__ == '__main__':
    import logging
    logging.basicConfig(level=logging.INFO)
    app.logger.info("Iniciando Dashboard Táctico...")
    app.run(host='0.0.0.0', port=5005, debug=True)
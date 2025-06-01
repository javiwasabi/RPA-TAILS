# dashboard_tactico_app.py
from flask import Flask, request, render_template, redirect, url_for, jsonify
import json
import os
from datetime import datetime

app = Flask(__name__)

DATA_DIR = "data_dashboard"
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

# Almacenamiento para la alerta actual y su estado
current_alert_data = None
current_event_id = None
alert_received_time = None
new_alert_posted_flag = False # Flag para indicar al cliente que hay una nueva alerta

# Cargar configuración del dashboard (si la tuvieras en un config.json separado)
# Por ahora, asumimos que bots.py le pasará el timeout, o usamos un default
DASHBOARD_CONFIG = { # Configuración por defecto o que podría venir de un archivo
    "decision_timeout_seconds": 40 # Default, se usará el de config.json de bots.py en la práctica
} 
# (Esta config es más para el HTML, bots.py maneja el timeout real)

@app.route('/', methods=['GET'])
def index():
    global current_alert_data, current_event_id, alert_received_time, new_alert_posted_flag

    alert_to_display = None
    time_left_for_decision = 0
    zone_css_class = "zone-default" # Clase CSS por defecto
    available_heroes_flags = {"Sonic": False, "Tails": False, "Knuckles": False}

    # Leer el config.json principal para el timeout (si existe)
    # Esto es para el contador visual, el timeout real lo maneja bots.py
    timeout_seconds_from_config = 40 
    try:
        with open("config.json", "r") as f:
            main_config = json.load(f)
            timeout_seconds_from_config = main_config.get("dashboard_tactico", {}).get("decision_timeout_seconds", 40)
    except Exception:
        app.logger.warn("No se pudo leer config.json para el timeout del dashboard, usando valor por defecto.")


    if current_event_id:
        decision_file_path = os.path.join(DATA_DIR, f"decision_{current_event_id}.json")
        auto_decision_file_path = os.path.join(DATA_DIR, f"auto_decision_{current_event_id}.json")

        if os.path.exists(decision_file_path) or os.path.exists(auto_decision_file_path):
            app.logger.info(f"Decisión para {current_event_id} ya procesada o automatizada. Limpiando dashboard para la próxima alerta.")
            current_alert_data = None
            current_event_id = None
            alert_received_time = None
            # No resetear new_alert_posted_flag aquí, se resetea cuando el cliente lo consulta
        elif current_alert_data: # Hay una alerta activa y no procesada
            alert_to_display = current_alert_data
            if alert_received_time:
                elapsed_time = (datetime.now() - alert_received_time).total_seconds()
                time_left_for_decision = max(0, timeout_seconds_from_config - elapsed_time)
            
            # Estilo dinámico y botones condicionales
            if alert_to_display and alert_to_display.get("location_details"):
                zone_css_class = alert_to_display["location_details"].get("css_class", "zone-unknown")
                known_heroes = alert_to_display["location_details"].get("known_nearby_heroes", [])
                for hero in known_heroes:
                    if hero in available_heroes_flags:
                        available_heroes_flags[hero] = True
            # Todos los héroes están "disponibles" en el sentido de que se pueden seleccionar,
            # pero podríamos filtrarlos si no están en "known_nearby_heroes"
            # Por ahora, para los botones individuales, los basaremos en known_nearby_heroes
            # El botón "Todos los héroes" siempre estará.

    # La plantilla HTML está al final de este script
    return render_template('dashboard_v2.html', 
                           alert=alert_to_display, 
                           event_id=current_event_id, 
                           time_left=int(time_left_for_decision),
                           zone_class=zone_css_class,
                           heroes_flags=available_heroes_flags,
                           poll_interval=CONFIG.get("dashboard_tactico", {}).get("dashboard_refresh_poll_seconds", 3) * 1000 # en ms
                           )


@app.route('/submit_alert_data', methods=['POST'])
def submit_alert_data():
    global current_alert_data, current_event_id, alert_received_time, new_alert_posted_flag
    try:
        data = request.get_json()
        if not data or "event_id" not in data:
            return jsonify({"status": "error", "message": "Datos inválidos"}), 400

        # Si hay una alerta activa no procesada, y llega una nueva, la nueva tiene prioridad.
        # Esto podría pasar si bots.py envía una nueva alerta antes de que el timeout de la anterior ocurra
        # o antes de que el usuario decida. Es un caso límite.
        if current_event_id and current_event_id != data["event_id"]:
             app.logger.warn(f"Recibida nueva alerta {data['event_id']} mientras {current_event_id} estaba activo. Sobrescribiendo.")
        
        current_alert_data = data
        current_event_id = data["event_id"]
        alert_received_time = datetime.now()
        new_alert_posted_flag = True # Indicar que hay una nueva alerta
        
        app.logger.info(f"Nueva alerta recibida y lista en dashboard: {current_event_id}")
        return jsonify({"status": "success", "message": "Alerta recibida y lista para mostrar"}), 200
    except Exception as e:
        app.logger.error(f"Error en submit_alert_data: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/check_new_alert', methods=['GET'])
def check_new_alert():
    """Endpoint para que el cliente (JavaScript) pregunte si hay una nueva alerta."""
    global new_alert_posted_flag, current_event_id
    if new_alert_posted_flag and current_event_id:
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

        # Usar el event_id del formulario, ya que current_event_id podría haber cambiado si llega otra alerta
        
        target_destinations = ["LogDB"] 
        if action == "sonic_only": target_destinations.append("Sonic")
        elif action == "tails_only": target_destinations.append("Tails")
        elif action == "knuckles_only": target_destinations.append("Knuckles")
        elif action == "sonic_tails": target_destinations.extend(["Sonic", "Tails"])
        elif action == "all_heroes": target_destinations.extend(["Sonic", "Tails", "Knuckles"])
        elif action == "register_only": pass 
        else: return "Error: Acción desconocida.", 400

        decision_data = {
            "event_id": event_id_form,
            "user_decision": action,
            "target_destinations": list(set(target_destinations))
        }
        
        decision_file_path = os.path.join(DATA_DIR, f"decision_{event_id_form}.json")
        auto_decision_file_path = os.path.join(DATA_DIR, f"auto_decision_{event_id_form}.json")

        if os.path.exists(auto_decision_file_path):
            app.logger.info(f"Decisión automática ya fue tomada para {event_id_form}. Decisión del usuario '{action}' ignorada (tardía).")
            message_to_user = f"La decisión para el evento {event_id_form} fue tomada automáticamente (timeout). Tu selección de '{action}' no fue procesada."
        elif os.path.exists(decision_file_path):
            app.logger.info(f"Decisión del usuario ya fue registrada para {event_id_form}. Acción '{action}' podría ser un reenvío o tardía.")
            # No sobrescribir si ya existe, bots.py debería haberla procesado y eliminado.
            message_to_user = f"Una decisión previa ya fue registrada para el evento {event_id_form}."
        else:
            with open(decision_file_path, 'w') as f:
                json.dump(decision_data, f, indent=4)
            app.logger.info(f"Decisión del usuario para evento {event_id_form} guardada: {action} -> {target_destinations}")
            message_to_user = f"Decisión '{action}' registrada para el evento {event_id_form}."
        
        # Limpiar la alerta actual del dashboard SI Y SOLO SI es la que se acaba de decidir
        if event_id_form == current_event_id:
            current_alert_data = None
            current_event_id = None
            alert_received_time = None
        
        return redirect(url_for('decision_made', event_id=event_id_form, message=message_to_user))
    except Exception as e:
        app.logger.error(f"Error en make_decision: {e}")
        return "Error procesando la decisión.", 500

@app.route('/decision_made')
def decision_made():
    event_id = request.args.get('event_id', 'N/A')
    message = request.args.get('message', 'Decisión procesada.')
    return render_template('decision_made_v2.html', event_id=event_id, message=message)

# --- Plantillas HTML ---
# Crear carpeta 'templates' si no existe
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
if not os.path.exists(TEMPLATES_DIR):
    os.makedirs(TEMPLATES_DIR)

# templates/dashboard_v2.html
DASHBOARD_TEMPLATE_V2 = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta http-equiv="X-UA-Compatible" content="IE=edge">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard Táctico - Alerta Eggman</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; color: #ecf0f1; display: flex; flex-direction: column; align-items: center; min-height: 100vh; padding: 20px; box-sizing: border-box; transition: background-color 0.5s ease; }
        /* Estilos base para el cuerpo */
        body.zone-default { background-color: #2c3e50; }
        body.zone-green-hill { background: linear-gradient(to bottom, #6ab04c, #82ccdd); color: #2c3e50; }
        body.zone-chemical-plant { background: linear-gradient(to bottom, #9b59b6, #34495e); }
        body.zone-station-square { background: linear-gradient(to bottom, #546e7a, #37474f); }
        body.zone-angel-island { background: linear-gradient(to bottom, #e67e22, #d35400); color: #fff; }
        body.zone-mystic-ruins { background: linear-gradient(to bottom, #795548, #4e342e); }
        body.zone-gun-hq { background: linear-gradient(to bottom, #424242, #212121); }
        body.zone-unknown { background-color: #7f8c8d; }

        .container { background-color: rgba(52, 73, 94, 0.85); padding: 30px; border-radius: 10px; box-shadow: 0 0 25px rgba(0,0,0,0.6); width: 90%; max-width: 950px; text-align: left; backdrop-filter: blur(5px); }
        h1 { text-align: center; font-size: 2.5em; border-bottom: 2px solid; padding-bottom: 10px; margin-bottom: 20px; }
        h1 .icon { font-size: 1em; vertical-align: middle; }
        /* Colores de títulos según la zona */
        .zone-default h1, .zone-chemical-plant h1, .zone-station-square h1, .zone-gun-hq h1 { color: #e74c3c; border-color: #e74c3c; }
        .zone-green-hill h1 { color: #27ae60; border-color: #27ae60; }
        .zone-angel-island h1 { color: #f39c12; border-color: #f39c12; }
        .zone-mystic-ruins h1 { color: #a1887f; border-color: #a1887f; }
        .zone-unknown h1 { color: #bdc3c7; border-color: #bdc3c7; }


        .alert-details { background-color: rgba(0,0,0,0.2); padding: 20px; border-radius: 8px; margin-bottom: 25px; border-left: 5px solid #1abc9c; }
        .alert-details h2 { color: #1abc9c; margin-top: 0; border-bottom: 1px solid #1abc9c; padding-bottom: 5px;}
        .alert-details p { margin: 10px 0; line-height: 1.6; }
        .alert-details strong { color: #e0e0e0; } /* Un color de strong que funcione en varios fondos */
        .zone-green-hill .alert-details strong { color: #1e824c; }


        .decision-form h2 { text-align: center; margin-bottom: 15px;}
        .zone-default .decision-form h2, .zone-chemical-plant .decision-form h2, .zone-station-square .decision-form h2, .zone-gun-hq .decision-form h2 { color: #f1c40f; }
        .zone-green-hill .decision-form h2 { color: #f39c12;}
        .zone-angel-island .decision-form h2 { color: #fefefe; }

        .buttons { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 15px; }
        .btn { color: white; padding: 12px 18px; border: none; border-radius: 5px; cursor: pointer; font-size: 1em; text-align: center; transition: background-color 0.3s ease, transform 0.1s ease; font-weight: bold; }
        .btn:hover { opacity: 0.9; transform: translateY(-2px); }
        .btn:active { transform: translateY(0px); }
        
        .btn-sonic { background-color: #007bff; }
        .btn-tails { background-color: #ffaa00; color: #2c3e50;}
        .btn-knuckles { background-color: #d90000; }
        .btn-sonic-tails { background-color: #16a085; }
        .btn-all { background-color: #2ecc71; }
        .btn-logdb { background-color: #95a5a6; }
        .btn[disabled] { background-color: #566573; cursor: not-allowed; opacity: 0.5; }

        .no-alert { font-size: 1.5em; text-align: center; margin-top: 50px;}
        .zone-default .no-alert, .zone-chemical-plant .no-alert, .zone-station-square .no-alert, .zone-gun-hq .no-alert { color: #95a5a6; }
        .zone-green-hill .no-alert { color: #387038; }

        .timer { text-align: center; font-size: 1.2em; margin-bottom: 20px; background-color: rgba(0,0,0,0.3); padding: 10px; border-radius: 5px;}
        .timer strong {font-size: 1.5em;}
        #countdown { animation: pulse_timer 1.5s infinite alternate; }
        @keyframes pulse_timer { 0% { opacity: 0.7; } 100% { opacity: 1; transform: scale(1.03); } }
        
        .hero-list .sonic_hero_class { color: #2980b9; font-weight: bold; background-color: rgba(255,255,255,0.1); padding: 2px 5px; border-radius:3px; }
        .hero-list .tails_hero_class { color: #f39c12; font-weight: bold; background-color: rgba(255,255,255,0.1); padding: 2px 5px; border-radius:3px; }
        .hero-list .knuckles_hero_class { color: #c0392b; font-weight: bold; background-color: rgba(255,255,255,0.1); padding: 2px 5px; border-radius:3px; }
        .hero-list .amy_hero_class { color: #e91e63; font-weight: bold; background-color: rgba(255,255,255,0.1); padding: 2px 5px; border-radius:3px; }

    </style>
</head>
<body class="{{ zone_class }}">
    <div class="container">
        <h1><span class="icon">🚨</span> Dashboard Táctico de Alertas <span class="icon">🚨</span></h1>

        {% if alert %}
            <div class="timer">
                Tiempo para decisión manual: <strong id="countdown">{{ time_left }}</strong> segundos
            </div>
            <div class="alert-details">
                <h2>Detalles del Evento: {{ alert.event_id }}</h2>
                <p><strong>Descripción:</strong> {{ alert.threat_assessment.description }}</p>
                <p><strong>Ubicación:</strong> {{ alert.location_reported }} (Zona: {{ alert.location_details.zone_name }})</p>
                <p><strong>Nivel de Amenaza:</strong> <span style="color: {% if alert.threat_assessment.initial_level == 'critico' %}#e74c3c{% elif alert.threat_assessment.initial_level == 'alto' %}#f39c12{% elif alert.threat_assessment.initial_level == 'medio' %}#f1c40f{% else %}#2ecc71{% endif %}; text-transform: uppercase; font-weight: bold;">{{ alert.threat_assessment.initial_level }}</span> (Prioridad: {{ alert.threat_assessment.priority_score }})</p>
                <p><strong>Nivel de Urgencia:</strong> <span style="font-weight: bold; color: #e74c3c;">{{ alert.urgency_level }}</span></p>
                <p><strong>Fuente:</strong> {{ alert.source_system_name }} (Tipo: {{ alert.source_type }})</p>
                <p><strong>Héroes Cercanos Detectados:</strong> 
                    <span class="hero-list">
                    {% if alert.location_details.known_nearby_heroes %}
                        {% for hero in alert.location_details.known_nearby_heroes %}
                            <span class="{{ hero.lower() }}_hero_class">{{ hero }}</span>{% if not loop.last %}, {% endif %}
                        {% endfor %}
                    {% else %}
                        Ninguno detectado en la zona.
                    {% endif %}
                    </span>
                </p>
            </div>

            <form action="{{ url_for('make_decision') }}" method="POST" class="decision-form">
                <h2>Tomar Decisión Táctica:</h2>
                <input type="hidden" name="event_id" value="{{ event_id }}">
                <div class="buttons">
                    <button type="submit" name="action" value="sonic_only" class="btn btn-sonic" {% if not heroes_flags.Sonic %}disabled title="Sonic no está en héroes cercanos para esta alerta"{% endif %}>Sonic</button>
                    <button type="submit" name="action" value="tails_only" class="btn btn-tails" {% if not heroes_flags.Tails %}disabled title="Tails no está en héroes cercanos para esta alerta"{% endif %}>Tails</button>
                    <button type="submit" name="action" value="knuckles_only" class="btn btn-knuckles" {% if not heroes_flags.Knuckles %}disabled title="Knuckles no está en héroes cercanos para esta alerta"{% endif %}>Knuckles</button>
                    <button type="submit" name="action" value="sonic_tails" class="btn btn-sonic-tails" {% if not (heroes_flags.Sonic and heroes_flags.Tails) %}disabled title="Sonic o Tails no están disponibles"{% endif %}>Sonic & Tails</button>
                    <button type="submit" name="action" value="all_heroes" class="btn btn-all">¡Todos los Héroes!</button>
                    <button type="submit" name="action" value="register_only" class="btn btn-logdb">Solo Registrar (LogDB)</button>
                </div>
            </form>
        {% else %}
            <p class="no-alert">Esperando nueva alerta del sistema Hedgehog...</p>
        {% endif %}
    </div>
    <script>
        const currentEventId = "{{ event_id if alert else '' }}";
        const pollInterval = {{ poll_interval if alert else 3000 }}; // Intervalo de sondeo para nuevas alertas

        function checkForNewAlert() {
            fetch("{{ url_for('check_new_alert') }}")
                .then(response => response.json())
                .then(data => {
                    if (data.new_alert) {
                        // Si la alerta actual en la página es diferente de la nueva, o si no hay alerta actual
                        if (currentEventId !== data.event_id || !document.querySelector('.alert-details')) {
                             console.log("Nueva alerta detectada por polling ("+ data.event_id +"), recargando dashboard...");
                             window.location.reload();
                        }
                    }
                })
                .catch(error => console.error("Error en polling de alertas:", error));
        }

        // Iniciar polling solo si no hay una alerta mostrándose actualmente
        // O si la alerta actual ya fue decidida y estamos esperando la próxima
        if (!document.querySelector('.alert-details h2') || document.querySelector('.alert-details h2').textContent.includes('N/A')) {
             setInterval(checkForNewAlert, pollInterval);
        }
        
        // Script simple para actualizar el contador visual del timeout
        let timeLeft = {{ time_left if alert else 0 }};
        const countdownElement = document.getElementById('countdown');
        let countdownInterval;

        function startCountdown() {
            if (countdownElement && timeLeft > 0) {
                countdownInterval = setInterval(() => {
                    timeLeft--;
                    countdownElement.textContent = timeLeft;
                    if (timeLeft <= 0) {
                        clearInterval(countdownInterval);
                        countdownElement.textContent = "Timeout!";
                        // Aquí podríamos deshabilitar botones, pero bots.py tomará la decisión automática.
                        // La página se recargará o mostrará "esperando" cuando bots.py envíe la siguiente alerta (o esta se limpie)
                        // O cuando el polling detecte que ya no hay alerta activa (porque fue manejada por timeout)
                        // Forzar un chequeo para ver si la alerta fue manejada por timeout
                        setTimeout(checkForNewAlert, 1500); // Chequear poco después del timeout visual
                    }
                }, 1000);
            }
        }
        
        if (timeLeft > 0) { // Solo iniciar si hay tiempo restante (es decir, una alerta activa)
            startCountdown();
        }

    </script>
</body>
</html>
"""

# templates/decision_made_v2.html
DECISION_MADE_TEMPLATE_V2 = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta http-equiv="X-UA-Compatible" content="IE=edge">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Decisión Procesada</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; background-color: #2c3e50; color: #ecf0f1; display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 100vh; padding: 20px; box-sizing: border-box; text-align: center; }
        .container { background-color: #34495e; padding: 40px; border-radius: 10px; box-shadow: 0 0 20px rgba(0,0,0,0.5); width: 80%; max-width: 600px; }
        h1 { color: #2ecc71; font-size: 2em; margin-bottom: 20px; }
        p { font-size: 1.2em; margin-bottom: 30px; }
        a.btn { display: inline-block; background-color: #3498db; color: white; padding: 12px 25px; border: none; border-radius: 5px; text-decoration: none; font-size: 1em; transition: background-color 0.3s ease; }
        a.btn:hover { background-color: #2980b9; }
    </style>
</head>
<body>
    <div class="container">
        <h1>{{ message.split(':')[0] if ':' in message else 'Decisión Registrada' }}</h1>
        <p>{{ message.split(':')[1] if ':' in message else message }}</p>
        <p>Evento ID: <strong>{{ event_id }}</strong></p>
        <a href="{{ url_for('index') }}" class="btn">Volver al Dashboard</a>
    </div>
    <script>
        // Redirigir al dashboard principal después de unos segundos
        setTimeout(function() {
            window.location.href = "{{ url_for('index') }}";
        }, 4000); // 4 segundos
    </script>
</body>
</html>
"""

# Crear/Actualizar archivos de plantilla
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
if not os.path.exists(TEMPLATES_DIR):
    os.makedirs(TEMPLATES_DIR)

with open(os.path.join(TEMPLATES_DIR, "dashboard_v2.html"), "w", encoding="utf-8") as f:
    f.write(DASHBOARD_TEMPLATE_V2)
with open(os.path.join(TEMPLATES_DIR, "decision_made_v2.html"), "w", encoding="utf-8") as f:
    f.write(DECISION_MADE_TEMPLATE_V2)

# Para cargar la config global de bots.py (solo para el timeout visual)
CONFIG = {}
try:
    with open("config.json", "r") as f_main_config:
        CONFIG = json.load(f_main_config)
except Exception:
    app.logger.warn("dashboard_tactico_app.py no pudo cargar config.json principal para leer dashboard_refresh_poll_seconds.")


if __name__ == '__main__':
    import logging
    logging.basicConfig(level=logging.INFO) 
    app.logger.info("Iniciando Dashboard Táctico Mejorado...")
    app.run(host='0.0.0.0', port=5005, debug=True) # debug=True es útil para desarrollo
# bots.py (VERSIÓN FINAL COMPLETA CON MECÁNICAS DE JUEGO)

import os
import json
import time
import random
from datetime import datetime, timedelta 
import requests

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.edge.options import Options as EdgeOptions
from webdriver_manager.microsoft import EdgeChromiumDriverManager
from selenium.common.exceptions import WebDriverException, NoSuchElementException, TimeoutException, InvalidArgumentException

# --- CONFIGURACIÓN GLOBAL ---
DATA_DIR = "data"
LOGS_DIR = "logs"
REPORTS_DIR = "reports"
DASHBOARD_DATA_DIR = "data_dashboard" 
EVENT_ID_COUNTER = 0
CONFIG = {}
KNOWLEDGE_BASE = {}
CURRENT_EVENT_HTML_REPORT = ""
WEBDRIVER_INSTANCE = None 

# --- Variables para el estado del juego ---
EGGMAN_HP = 100
GLOBAL_PANIC = 0
# ---

# --- FUNCIONES DE UTILIDAD ---
def ensure_dirs():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(LOGS_DIR, exist_ok=True)
    os.makedirs(REPORTS_DIR, exist_ok=True)
    os.makedirs(DASHBOARD_DATA_DIR, exist_ok=True) 

def logger(bot_name, message, level="INFO"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    log_message_console = f"[{timestamp}] [{bot_name:<28}] [{level:<5}] {message}" 
    print(log_message_console)
    log_file_path = os.path.join(LOGS_DIR, f"{bot_name}.log")
    os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
    with open(log_file_path, "a", encoding="utf-8") as f:
        f.write(log_message_console + "\n")

def write_json_data(filename, data, directory=DATA_DIR):
    if not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    logger("System", f"Archivo JSON '{filename}' escrito en '{directory}'.", "DEBUG")

def read_json_data(filename, directory=DATA_DIR): 
    path = os.path.join(directory, filename)
    if not os.path.exists(path):
        logger("System", f"Archivo JSON '{filename}' no encontrado en '{directory}'.", "WARN")
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except json.JSONDecodeError:
        logger("System", f"Error decodificando JSON '{filename}' de '{directory}'.", "ERROR")
        return None

def load_config():
    global CONFIG, KNOWLEDGE_BASE
    default_config = {
        "bot_maestro": {"process_interval_seconds_min": 5, "process_interval_seconds_max": 10, "max_cycles_to_run": 0},
        "bot_monitor": {
            "use_selenium_source": True, 
            "selenium_html_sources": ["fuente_de_datos_simulada.html"], 
            "edge_binary_path_override": "",
            "selenium_view_time_seconds": 3
            },
        "dashboard_tactico": { 
            "url": "http://127.0.0.1:5005",
            "submit_alert_endpoint": "/submit_alert_data",
            "check_alert_endpoint": "/check_new_alert",
            "decision_timeout_seconds": 40,
            "decision_poll_interval_seconds": 1,
            "dashboard_refresh_poll_seconds": 3
        },
        "bot_notificador": {"request_timeout_seconds": 5, "endpoints": {
            "Sonic": "http://127.0.0.1:5001/alert", "Knuckles": "http://127.0.0.1:5002/alert",
            "Tails": "http://127.0.0.1:5003/alert", "LogDB": "http://127.0.0.1:5004/alert"
        }},
        "bot_enriquecedor": {"knowledge_base_simulated": {
            "Green Hill Zone": {"zone_name": "Green Hill Zone", "description": "Colinas verdes.", "nearby_heroes": ["Sonic", "Tails"], "common_threats": ["Moto Bug"], "css_class": "zone-green-hill"}
            # ... (Añadir aquí el resto de tu KNOWLEDGE_BASE de config.json si es necesario)
        }},
        "game_state": { # Valores por defecto si no están en config.json
            "initial_eggman_hp": 100,
            "initial_global_panic": 0,
            "max_global_panic": 100
        }
    }
    try:
        with open("config.json", "r", encoding="utf-8") as f:
            loaded_config = json.load(f)
        CONFIG = default_config.copy() # Empezar con los defaults
        # Fusionar la configuración cargada con los defaults de forma inteligente
        for key, value in loaded_config.items():
            if isinstance(value, dict) and isinstance(CONFIG.get(key), dict):
                CONFIG[key].update(value)
            else:
                CONFIG[key] = value
        logger("BotMaestro", "Configuración cargada desde config.json")
    except FileNotFoundError:
        logger("BotMaestro", "config.json no encontrado. Usando config por defecto.", "WARN")
        CONFIG = default_config
    except json.JSONDecodeError:
        logger("BotMaestro", "Error decodificando config.json. Usando config por defecto.", "ERROR")
        CONFIG = default_config
    except Exception as e:
        logger("BotMaestro", f"Error inesperado cargando config.json: {e}. Usando config por defecto.", "ERROR")
        CONFIG = default_config

    KNOWLEDGE_BASE = CONFIG.get("bot_enriquecedor", {}).get("knowledge_base_simulated", {})
    if not KNOWLEDGE_BASE:
         KNOWLEDGE_BASE = default_config["bot_enriquecedor"]["knowledge_base_simulated"]
    logger("BotMaestro", "Base de conocimiento (re)inicializada.")

def find_edge_binary():
    paths_to_check = [
        "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
        "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
    ]
    for path in paths_to_check:
        if os.path.exists(path):
            return path
    return None

def init_webdriver():
    global WEBDRIVER_INSTANCE
    if WEBDRIVER_INSTANCE is not None:
        try:
            WEBDRIVER_INSTANCE.current_url 
            logger("WebDriver", "Reutilizando instancia de WebDriver existente.")
            return WEBDRIVER_INSTANCE
        except WebDriverException:
            logger("WebDriver", "La instancia anterior de WebDriver ya no es válida. Creando una nueva.")
            WEBDRIVER_INSTANCE = None 
            
    logger("WebDriver", "Inicializando nueva instancia de WebDriver (Edge)...")
    cfg_monitor = CONFIG.get("bot_monitor", {})
    edge_binary_override = cfg_monitor.get("edge_binary_path_override", "").strip()
    
    options = EdgeOptions()
    options.add_experimental_option('excludeSwitches', ['enable-logging'])
    options.add_argument('log-level=3') 
    
    edge_binary_path_to_use = edge_binary_override if edge_binary_override and os.path.exists(edge_binary_override) else find_edge_binary()

    if edge_binary_path_to_use:
        options.binary_location = edge_binary_path_to_use
        logger("WebDriver", f"Usando binario de Edge: {edge_binary_path_to_use}")
    else:
        logger("WebDriver", "Binario de Edge no encontrado/especificado. Dejando que WebDriverManager intente.", "WARN")

    try:
        service = EdgeService(executable_path=EdgeChromiumDriverManager().install())
        driver = webdriver.Edge(service=service, options=options)
        logger("WebDriver", "Nueva instancia de WebDriver creada exitosamente.")
        WEBDRIVER_INSTANCE = driver
        return driver
    except Exception as e:
        logger("WebDriver", f"FALLO AL INICIALIZAR WEBDRIVER: {e}", "CRITICAL")
        return None

def close_webdriver():
    global WEBDRIVER_INSTANCE
    if WEBDRIVER_INSTANCE is not None:
        logger("WebDriver", "Cerrando instancia de WebDriver...")
        try:
            WEBDRIVER_INSTANCE.quit()
        except Exception as e:
            logger("WebDriver", f"Error al cerrar WebDriver: {e}", "ERROR")
        finally:
            WEBDRIVER_INSTANCE = None

# --- Funciones para el Reporte HTML del Flujo ---
def start_html_report(event_id):
    global CURRENT_EVENT_HTML_REPORT
    CURRENT_EVENT_HTML_REPORT = os.path.join(REPORTS_DIR, f"evento_{event_id.replace(':', '-')}.html")
    html_content = f"""
    <!DOCTYPE html><html lang="es"><head><meta charset="UTF-8"><title>Reporte de Flujo - Evento {event_id}</title>
    <style>body{{font-family:Arial,sans-serif;margin:20px;background-color:#f4f4f4;color:#333}}.container{{background-color:#fff;padding:20px;border-radius:8px;box-shadow:0 0 10px rgba(0,0,0,.1)}}.bot-step{{margin-bottom:20px;padding:15px;border-left:5px solid;border-radius:5px}}.bot-monitor{{border-color:#3498db;background-color:#eaf5ff}}.bot-analizador{{border-color:#f1c40f;background-color:#fff9e6}}.bot-enriquecedor{{border-color:#2ecc71;background-color:#e9f7ef}}.bot-decision-tactica{{border-color:#e67e22;background-color:#fdf3e6}}.bot-notificador{{border-color:#9b59b6;background-color:#f5eff7}}h1{{color:#2c3e50;text-align:center}}h2{{color:#34495e;border-bottom:2px solid #eee;padding-bottom:5px}}pre{{background-color:#ecf0f1;padding:10px;border-radius:4px;white-space:pre-wrap;word-wrap:break-word;font-size:.9em}}.timestamp{{font-size:.8em;color:#7f8c8d;float:right}}.character{{font-weight:700;font-size:1.2em;margin-right:10px}}.sonic{{color:#007bff}}.tails{{color:#ffaa00}}.knuckles{{color:#d90000}}.eggman{{color:#c0c0c0}}</style></head>
    <body><div class="container"><h1><span class="eggman">🤖</span> Reporte de Flujo del Evento: {event_id} <span class="eggman">🚨</span></h1>"""
    with open(CURRENT_EVENT_HTML_REPORT, "w", encoding="utf-8") as f:
        f.write(html_content)

def add_to_html_report(bot_name, data_processed, details=""):
    if not CURRENT_EVENT_HTML_REPORT: return
    bot_class_map = {"BotMonitor": "bot-monitor", "BotAnalizador": "bot-analizador", "BotEnriquecedor": "bot-enriquecedor", "BotDecisionTactica": "bot-decision-tactica", "BotNotificador": "bot-notificador"}
    bot_icon_map = {"BotMonitor": "🛰️", "BotAnalizador": "🧠", "BotEnriquecedor": "🗺️", "BotDecisionTactica": "🎯", "BotNotificador": "📡"}
    bot_class = bot_class_map.get(bot_name, "")
    bot_icon = bot_icon_map.get(bot_name, "⚙️")
    timestamp_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    character_html = "" # Lógica para el character_html...
    html_content = f"""<div class="bot-step {bot_class}"><span class="timestamp">{timestamp_now}</span><h2>{bot_icon} {bot_name}</h2>{character_html}<p>{details}</p><pre>{json.dumps(data_processed, indent=2, ensure_ascii=False)}</pre></div>"""
    with open(CURRENT_EVENT_HTML_REPORT, "a", encoding="utf-8") as f:
        f.write(html_content)

def end_html_report():
    if not CURRENT_EVENT_HTML_REPORT: return
    html_content = "</div></body></html>"
    with open(CURRENT_EVENT_HTML_REPORT, "a", encoding="utf-8") as f:
        f.write(html_content)
    logger("System", f"Reporte HTML generado: {CURRENT_EVENT_HTML_REPORT}")

# --- 🛰️ BotMonitor ---
def bot_monitor():
    global EVENT_ID_COUNTER, WEBDRIVER_INSTANCE
    EVENT_ID_COUNTER += 1
    bot_name = "BotMonitor"
    logger(bot_name, "Iniciando monitoreo...")
    monitor_output = {}
    cfg_monitor = CONFIG.get("bot_monitor", {})
    use_selenium = cfg_monitor.get("use_selenium_source", False)
    selenium_data_extracted = False

    if use_selenium:
        driver = init_webdriver() 
        if driver is None:
            logger(bot_name, "Fallo al obtener instancia de WebDriver. Saltando Selenium.", "ERROR")
            use_selenium = False 
        else:
            selenium_html_sources = cfg_monitor.get("selenium_html_sources", ["fuente_de_datos_simulada.html"])
            if not selenium_html_sources: 
                selenium_html_sources = ["fuente_de_datos_simulada.html"]
            
            selected_html_file = random.choice(selenium_html_sources)
            logger(bot_name, f"Selenium: Fuente HTML para scraping: '{selected_html_file}'")
            
            try:
                local_html_path = os.path.abspath(selected_html_file)
                if not os.path.exists(local_html_path):
                    raise FileNotFoundError(f"Archivo HTML '{local_html_path}' no encontrado.")

                driver.get(f"file:///{local_html_path.replace(os.sep, '/')}")
                time.sleep(cfg_monitor.get("selenium_view_time_seconds", 3))

                data_ids = ["descripcion", "nivel", "ubicacion", "device_id", "reading_type", "value"]
                scraped_data = {id_name: driver.find_element(By.ID, id_name).text for id_name in data_ids}
                
                try: 
                    scraped_data["value"] = float(scraped_data["value"]) if '.' in scraped_data["value"] else int(scraped_data["value"])
                except ValueError: pass # Dejar como string si no se puede convertir

                logger(bot_name, f"Datos Selenium (Edge) de '{selected_html_file}': {scraped_data['descripcion']}")
                source_type_tag_sel = "WEB_SELENIUM_EDGE_GENERIC"
                if "angel_island" in selected_html_file.lower(): source_type_tag_sel = "WEB_SELENIUM_ANGEL_ISLAND"
                elif "tails" in selected_html_file.lower(): source_type_tag_sel = "WEB_SELENIUM_TAILS_REPORT"
                
                monitor_output = {
                    "event_id": f"EVT-SEL-{datetime.now().strftime('%Y%m%d%H%M%S')}-{EVENT_ID_COUNTER:04d}",
                    "timestamp_raw": datetime.now().isoformat(), 
                    "source_system": f"Fuente Web: {selected_html_file} (Scraped)", 
                    "source_type_tag": source_type_tag_sel, 
                    "detected_location_raw": scraped_data["ubicacion"],
                    "threat_level_raw": scraped_data["nivel"].lower(), 
                    "description_raw": scraped_data["descripcion"],
                    "raw_payload": {k: v for k, v in scraped_data.items() if k not in ["descripcion", "nivel", "ubicacion"]}
                }
                monitor_output["raw_payload"]["html_source_file"] = selected_html_file
                selenium_data_extracted = True
                
                cfg_dashboard = CONFIG.get("dashboard_tactico", {})
                dashboard_main_url = cfg_dashboard.get("url", "http://127.0.0.1:5005").rstrip('/') + "/"
                driver.get(dashboard_main_url)

            except Exception as e: 
                logger(bot_name, f"Error con Selenium (Edge) en '{selected_html_file}': {type(e).__name__} - {e}", "ERROR")
                if isinstance(e, WebDriverException) and ("target window already closed" in str(e).lower() or "no such window" in str(e).lower()):
                    close_webdriver()

    if not use_selenium or not selenium_data_extracted: 
        if use_selenium and not selenium_data_extracted: logger(bot_name, "Fallo en Selenium, usando generación aleatoria.")
        else: logger(bot_name, "Usando generación aleatoria (Selenium no activo).")
        
        sources_config = [
            {"name": "Sensor Tails", "type": "SENSOR_TAILS", "locations": ["Tails' Workshop", "Mystic Ruins"]},
            {"name": "Radar G.U.N.", "type": "RADAR_GUN", "locations": ["Station Square", "G.U.N. HQ"]},
        ]
        selected_source = random.choice(sources_config)
        location = random.choice(selected_source.get("locations", list(KNOWLEDGE_BASE.keys())))
        
        monitor_output = {
            "event_id": f"EVT-RND-{datetime.now().strftime('%Y%m%d%H%M%S')}-{EVENT_ID_COUNTER:04d}",
            "timestamp_raw": datetime.now().isoformat(), "source_system": selected_source["name"],
            "source_type_tag": selected_source["type"], "detected_location_raw": location,
            "threat_level_raw": random.choice(["bajo", "medio", "alto", "critico"]), 
            "description_raw": f"Actividad detectada en {location}", "raw_payload": {}
        }

    if not monitor_output: # Fallback
        monitor_output = {"event_id": f"EVT-FAIL-{datetime.now().strftime('%Y%m%d%H%M%S')}-{EVENT_ID_COUNTER:04d}"} # ... (otros campos por defecto)

    start_html_report(monitor_output['event_id'])
    add_to_html_report(bot_name, monitor_output, "Datos iniciales capturados/generados.")
    write_json_data("monitor_output.json", monitor_output)
    logger(bot_name, "Monitoreo completado.")
    return monitor_output

# --- BotAnalizador ---
def bot_analizador():
    bot_name = "BotAnalizador"
    logger(bot_name, "Iniciando análisis...")
    monitor_data = read_json_data("monitor_output.json")
    if not monitor_data:
        logger(bot_name, "No hay datos del monitor. Abortando.", "ERROR"); return None
    
    canonical_data = {
        "event_id": monitor_data["event_id"], "timestamp_event": monitor_data["timestamp_raw"],
        "source_system_name": monitor_data["source_system"], "source_type": monitor_data["source_type_tag"],
        "location_reported": monitor_data["detected_location_raw"],
        "threat_assessment": {"initial_level": monitor_data["threat_level_raw"].lower(), "description": monitor_data["description_raw"]},
        "original_raw_data": monitor_data.get("raw_payload", {})
    }
    level_scores = {"critico": 10, "alto": 7, "medio": 5, "bajo": 2}
    canonical_data["threat_assessment"]["priority_score"] = level_scores.get(canonical_data["threat_assessment"]["initial_level"], 0)
    
    add_to_html_report(bot_name, canonical_data, "Datos normalizados y priorizados.")
    write_json_data("analysis_output.json", canonical_data)
    logger(bot_name, "Análisis completado.")
    return canonical_data

# --- BotEnriquecedor ---
def bot_enriquecedor():
    bot_name = "BotEnriquecedor"
    logger(bot_name, "Iniciando enriquecimiento...")
    canonical_data = read_json_data("analysis_output.json")
    if not canonical_data:
        logger(bot_name, "No hay datos canónicos. Abortando.", "ERROR"); return None

    enriched_data = canonical_data.copy()
    location_key = enriched_data["location_reported"]
    default_loc_info = KNOWLEDGE_BASE.get("Unknown Location", {"zone_name": "Unknown Location", "css_class": "zone-unknown"})
    location_info = KNOWLEDGE_BASE.get(location_key, default_loc_info)
    
    enriched_data["location_details"] = {
        "zone_name": location_info.get("zone_name", location_key),
        "description": location_info.get("description", "N/A"),
        "known_nearby_heroes": location_info.get("nearby_heroes", []),
        "common_threats_in_zone": location_info.get("common_threats", []),
        "css_class": location_info.get("css_class", "zone-default")
    }
    
    priority_score = enriched_data.get("threat_assessment", {}).get("priority_score", 0)
    urgency_levels = {10: "MAXIMA_URGENCIA", 7: "ALTA_URGENCIA", 5: "URGENCIA_MEDIA"}
    enriched_data["urgency_level"] = urgency_levels.get(priority_score, "URGENCIA_BAJA")

    add_to_html_report(bot_name, enriched_data, "Datos contextualizados y enriquecidos.")
    write_json_data("enriched_output.json", enriched_data)
    logger(bot_name, "Enriquecimiento completado.")
    return enriched_data

# --- Función para actualizar el estado del juego ---
def actualizar_estado_juego(enriched_data, routing_data):
    global EGGMAN_HP, GLOBAL_PANIC
    bot_name = "GameStateManager"
    damage_to_eggman = 0
    panic_change = 0

    threat_level = enriched_data.get("threat_assessment", {}).get("initial_level", "bajo")
    decision_type = routing_data.get("decision_type", "")
    
    is_timeout = "Automática (Timeout)" in decision_type or "Error de conexión" in decision_type

    if is_timeout:
        damage_to_eggman = 0
        panic_change = {"critico": 15, "alto": 8, "medio": 4, "bajo": 2}.get(threat_level, 2)
    else: # Decisión del usuario
        heroes_sent = {h for h in routing_data.get("target_destinations", []) if h != "LogDB"}
        nearby_heroes = set(enriched_data.get("location_details", {}).get("known_nearby_heroes", []))
        is_optimal_response = heroes_sent and heroes_sent.issubset(nearby_heroes)

        if not heroes_sent: # Solo registrar
             damage_to_eggman = -2 
             panic_change = 2
        elif is_optimal_response:
            panic_change = -2 
            damage_to_eggman = {"critico": 20, "alto": 12, "medio": 8, "bajo": 5}.get(threat_level, 5)
        else: # Respuesta sub-óptima
            panic_change = 3
            damage_to_eggman = {"critico": 5, "alto": 3, "medio": 1, "bajo": 0}.get(threat_level, 0)
            
    EGGMAN_HP = max(0, EGGMAN_HP - damage_to_eggman)
    GLOBAL_PANIC = max(0, min(100, GLOBAL_PANIC + panic_change))

    logger(bot_name, f"Daño a Eggman: {damage_to_eggman}. HP restante: {EGGMAN_HP}", "INFO")
    logger(bot_name, f"Cambio de Pánico: {panic_change}. Pánico Global actual: {GLOBAL_PANIC}", "INFO")

# --- 🎯 BotDecisionTactica ---
def solicitar_decision_tactica_dashboard():
    global EGGMAN_HP, GLOBAL_PANIC # Asegurarse de que accedemos a las globales correctas
    bot_name = "BotDecisionTactica"
    logger(bot_name, "Iniciando proceso de decisión táctica con Dashboard...")
    enriched_data = read_json_data("enriched_output.json") 
    if not enriched_data:
        logger(bot_name, "No hay datos enriquecidos para decisión.", "ERROR"); return None
    
    enriched_data['game_state'] = {'eggman_hp': EGGMAN_HP, 'global_panic': GLOBAL_PANIC}
    
    event_id = enriched_data.get("event_id")
    if not event_id: return None # Ya logueado si falta event_id

    cfg_dashboard = CONFIG.get("dashboard_tactico", {})
    full_submit_url = f"{cfg_dashboard.get('url', '').rstrip('/')}{cfg_dashboard.get('submit_alert_endpoint', '')}"
    
    try:
        response = requests.post(full_submit_url, json=enriched_data, timeout=5) 
        response.raise_for_status()
        logger(bot_name, f"Alerta '{event_id}' enviada al dashboard. Esperando decisión...")
    except requests.exceptions.RequestException as e:
        logger(bot_name, f"Error enviando alerta al dashboard: {e}. Decisión automática.", "ERROR")
        return tomar_decision_automatica_por_timeout(event_id, enriched_data, "Error de conexión con Dashboard")

    start_time = datetime.now()
    decision_file_name = f"decision_{event_id}.json"
    timeout_seconds = cfg_dashboard.get("decision_timeout_seconds", 30)
    poll_interval = cfg_dashboard.get("decision_poll_interval_seconds", 1)
    
    user_decision_data = None
    while (datetime.now() - start_time).total_seconds() < timeout_seconds:
        user_decision_from_file = read_json_data(decision_file_name, directory=DASHBOARD_DATA_DIR)
        if user_decision_from_file and user_decision_from_file.get("event_id") == event_id:
            user_decision_data = user_decision_from_file
            try: os.remove(os.path.join(DASHBOARD_DATA_DIR, decision_file_name))
            except OSError as e_rem: logger(bot_name, f"Error eliminando archivo decisión: {e_rem}", "WARN")
            break 
        time.sleep(poll_interval)

    if user_decision_data:
        routing_data = {"event_id": event_id, **user_decision_data, "alert_payload_to_send": enriched_data, "decision_type": f"Usuario: {user_decision_data.get('user_decision', 'N/A')}"}
    else:
        logger(bot_name, f"Timeout para '{event_id}'. Decisión automática.")
        write_json_data(f"auto_decision_{event_id}.json", {"event_id": event_id, "decision_type": "timeout_auto"}, directory=DASHBOARD_DATA_DIR)
        routing_data = tomar_decision_automatica_por_timeout(event_id, enriched_data, "Timeout")
    
    add_to_html_report(bot_name, routing_data, f"Decisión táctica ({routing_data.get('decision_type', '')}).")
    write_json_data("routing_output.json", routing_data)
    return routing_data

def tomar_decision_automatica_por_timeout(event_id, enriched_data, reason="Timeout"):
    bot_name = "BotDecisionTactica"
    logger(bot_name, f"Tomando decisión AUTOMÁTICA para '{event_id}' por: {reason}")
    destinations = {"LogDB"} # Siempre al LogDB
    threat_level = enriched_data.get("threat_assessment", {}).get("initial_level", "bajo")
    nearby_heroes = enriched_data.get("location_details", {}).get("known_nearby_heroes", [])
    
    if threat_level == "critico": destinations.update(["Sonic", "Tails", "Knuckles"])
    elif threat_level == "alto":
        destinations.add("Sonic")
        if "Tails" in nearby_heroes: destinations.add("Tails")
    elif threat_level == "medio":
        if "Sonic" in nearby_heroes: destinations.add("Sonic")
        elif "Tails" in nearby_heroes: destinations.add("Tails")
        elif nearby_heroes: destinations.add(nearby_heroes[0])
        else: destinations.add(random.choice(["Sonic", "Tails"]))
        
    return {
        "event_id": event_id, "target_destinations": list(destinations),
        "alert_payload_to_send": enriched_data, "decision_type": f"Automática ({reason})"
    }

# --- BotNotificador ---
def bot_notificador():
    bot_name = "BotNotificador"
    routing_data = read_json_data("routing_output.json") 
    if not routing_data:
        logger(bot_name, "No hay datos de ruteo. Abortando.", "ERROR"); return

    payload_to_send = routing_data.get("alert_payload_to_send", {})
    if not payload_to_send: return # Ya logueado

    cfg_notifier = CONFIG.get("bot_notificador", {})
    endpoint_map = cfg_notifier.get("endpoints", {})
    sent_count = 0
    
    for dest_name in routing_data.get("target_destinations", []):
        url = endpoint_map.get(dest_name)
        if url:
            try:
                response = requests.post(str(url).strip(), json=payload_to_send, timeout=cfg_notifier.get("request_timeout_seconds", 5))
                response.raise_for_status() 
                sent_count += 1
            except requests.exceptions.RequestException as e:
                logger(bot_name, f"Error enviando a {dest_name} ({url}): {e}", "ERROR")
    
    add_to_html_report(bot_name, routing_data, "Notificaciones enviadas.") # Simplificado
    logger(bot_name, f"Notificaciones completadas. {sent_count}/{len(routing_data.get('target_destinations',[]))} enviadas.")

# --- CICLO PRINCIPAL DE ORQUESTACIÓN ---
def main_loop():
    global EGGMAN_HP, GLOBAL_PANIC 

    logger("BotMaestro", "Hedgehog Alert Processor INICIADO.")
    
    game_state_config = CONFIG.get("game_state", {})
    EGGMAN_HP = game_state_config.get("initial_eggman_hp", 100)
    GLOBAL_PANIC = game_state_config.get("initial_global_panic", 0)
    max_panic = game_state_config.get("max_global_panic", 100)
    logger("BotMaestro", f"Estado inicial: HP Eggman: {EGGMAN_HP}, Pánico: {GLOBAL_PANIC}")

    cfg_maestro = CONFIG.get("bot_maestro", {})
    max_cycles = cfg_maestro.get("max_cycles_to_run", 0)
    current_cycle = 0

    try:
        while True:
            current_cycle += 1
            global CURRENT_EVENT_HTML_REPORT 
            CURRENT_EVENT_HTML_REPORT = "" 
            logger("BotMaestro", f"--- Ciclo #{current_cycle} ---")
            
            monitor_result = bot_monitor() 
            if not monitor_result: time.sleep(cfg_maestro.get("process_interval_seconds_max", 7)); continue 
            
            analysis_result = bot_analizador()
            if not analysis_result: time.sleep(cfg_maestro.get("process_interval_seconds_max", 7)); continue
            
            enriched_result = bot_enriquecedor()
            if not enriched_result: time.sleep(cfg_maestro.get("process_interval_seconds_max", 7)); continue
            
            decision_data = solicitar_decision_tactica_dashboard() 
            if not decision_data: 
                end_html_report() # Asegurar que el reporte se cierre
                time.sleep(cfg_maestro.get("process_interval_seconds_max", 7)); continue
            
            if enriched_result and decision_data:
                actualizar_estado_juego(enriched_result, decision_data)
            
            bot_notificador() 
            end_html_report() 

            game_over = False
            final_data = {}

            if EGGMAN_HP <= 0:
                logger("BotMaestro", "¡VICTORIA! HP Eggman a 0.", "INFO")
                final_data = {"game_status": "VICTORY", "final_hp": EGGMAN_HP, "final_panic": GLOBAL_PANIC}
                game_over = True
            
            if GLOBAL_PANIC >= max_panic:
                logger("BotMaestro", "¡DERROTA! Pánico global al máximo.", "CRITICAL")
                final_data = {"game_status": "DEFEAT", "final_hp": EGGMAN_HP, "final_panic": GLOBAL_PANIC}
                game_over = True

            if game_over:
                try:
                    cfg_dashboard = CONFIG.get("dashboard_tactico", {})
                    full_submit_url = f"{cfg_dashboard.get('url', '').rstrip('/')}{cfg_dashboard.get('submit_alert_endpoint', '')}"
                    if full_submit_url: # Evitar enviar si la URL es inválida
                        logger("BotMaestro", f"Enviando estado final del juego a {full_submit_url}...")
                        requests.post(full_submit_url, json=final_data, timeout=5)
                except Exception as e:
                    logger("BotMaestro", f"No se pudo enviar estado final al dashboard: {e}", "ERROR")
                break 
            
            logger("BotMaestro", f"--- Ciclo #{current_cycle} COMPLETADO ---")
            if max_cycles > 0 and current_cycle >= max_cycles:
                logger("BotMaestro", f"Máximo de ciclos ({max_cycles}) alcanzado. Terminando.")
                break
            
            process_interval_seconds = random.randint(
                cfg_maestro.get("process_interval_seconds_min", 3), 
                cfg_maestro.get("process_interval_seconds_max", 7)
            )
            time.sleep(process_interval_seconds)
            
    except KeyboardInterrupt:
        logger("BotMaestro", "Interrupción por teclado. Deteniendo...")
    finally:
        close_webdriver() 
        if CURRENT_EVENT_HTML_REPORT and os.path.exists(CURRENT_EVENT_HTML_REPORT) and not game_over: # Solo cerrar si no es fin de juego
            try:
                with open(CURRENT_EVENT_HTML_REPORT, "r+", encoding="utf-8") as f: 
                    content = f.read()
                    if not content.strip().endswith("</html>"):
                        f.seek(0, os.SEEK_END) 
                        f.write("\n        </div>\n    </body>\n    </html>\n")
            except Exception as e_file:
                logger("BotMaestro", f"Error al intentar cerrar HTML en finally: {e_file}", "ERROR")
        logger("BotMaestro", "Hedgehog Alert Processor TERMINADO.")

if __name__ == "__main__":
    ensure_dirs()
    load_config() 
    main_loop()
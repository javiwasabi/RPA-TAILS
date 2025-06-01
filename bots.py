import os
import json
import time
import random
from datetime import datetime
import requests

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.edge.options import Options as EdgeOptions
from webdriver_manager.microsoft import EdgeChromiumDriverManager
from selenium.common.exceptions import WebDriverException, NoSuchElementException, TimeoutException

# --- CONFIGURACIÓN GLOBAL ---
DATA_DIR = "data"
LOGS_DIR = "logs"
REPORTS_DIR = "reports"
EVENT_ID_COUNTER = 0
CONFIG = {}
KNOWLEDGE_BASE = {}
CURRENT_EVENT_HTML_REPORT = ""

# --- FUNCIONES DE UTILIDAD ---
def ensure_dirs():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(LOGS_DIR, exist_ok=True)
    os.makedirs(REPORTS_DIR, exist_ok=True)

def logger(bot_name, message, level="INFO"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    log_message_console = f"[{timestamp}] [{bot_name:<15}] [{level:<5}] {message}"
    print(log_message_console)
    log_file_path = os.path.join(LOGS_DIR, f"{bot_name}.log")
    os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
    with open(log_file_path, "a", encoding="utf-8") as f:
        f.write(log_message_console + "\n")

def write_json_data(filename, data):
    path = os.path.join(DATA_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    logger("System", f"Archivo JSON '{filename}' escrito.", "DEBUG")

def read_json_data(filename):
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        logger("System", f"Archivo JSON '{filename}' no encontrado.", "ERROR")
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        logger("System", f"Archivo JSON '{filename}' leído.", "DEBUG")
        return data
    except json.JSONDecodeError:
        logger("System", f"Error decodificando JSON '{filename}'.", "ERROR")
        return None

def load_config():
    global CONFIG, KNOWLEDGE_BASE
    default_config = {
        "bot_maestro": {"process_interval_seconds_min": 5, "process_interval_seconds_max": 10, "max_cycles_to_run": 0},
        "bot_monitor": {
            "use_selenium_source": False, # Por defecto False si no se especifica
            "selenium_html_sources": ["fuente_de_datos_simulada.html"], # Lista con al menos un default
            "edge_binary_path_override": "",
            "selenium_view_time_seconds": 5
            },
        "bot_notificador": {"request_timeout_seconds": 5, "endpoints": {
            "Sonic": "[http://127.0.0.1:5001/alert](http://127.0.0.1:5001/alert)", "Knuckles": "[http://127.0.0.1:5002/alert](http://127.0.0.1:5002/alert)",
            "Tails": "[http://127.0.0.1:5003/alert](http://127.0.0.1:5003/alert)", "LogDB": "[http://127.0.0.1:5004/alert](http://127.0.0.1:5004/alert)"
        }},
        "bot_enriquecedor": {"knowledge_base_simulated": {
            "Unknown Location": {"zone_name": "Unknown Location", "description": "Ubicación desconocida.", "nearby_heroes": [], "common_threats": []}
        }}
    }
    try:
        with open("config.json", "r", encoding="utf-8") as f:
            loaded_config = json.load(f)
        # Fusionar de forma más robusta, especialmente para diccionarios anidados como bot_monitor
        CONFIG = default_config.copy()
        for key, value in loaded_config.items():
            if key in CONFIG and isinstance(CONFIG[key], dict) and isinstance(value, dict):
                CONFIG[key].update(value) # Actualiza el diccionario de primer nivel
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
        logger("BotMaestro", f"Error cargando config.json: {e}. Usando config por defecto.", "ERROR")
        CONFIG = default_config

    # Asegurar que KNOWLEDGE_BASE se inicializa desde la configuración cargada o la por defecto
    kb_config = CONFIG.get("bot_enriquecedor", {}).get("knowledge_base_simulated")
    if kb_config:
        KNOWLEDGE_BASE = kb_config
    else:
        KNOWLEDGE_BASE = default_config["bot_enriquecedor"]["knowledge_base_simulated"]
    logger("BotMaestro", "Base de conocimiento (re)inicializada.")


def find_edge_binary():
    paths_to_check = [
        "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
        "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
    ]
    for path in paths_to_check:
        if os.path.exists(path):
            logger("System", f"Binario de Edge encontrado en: {path}", "DEBUG")
            return path
    logger("System", "No se pudo encontrar automáticamente el binario de Edge.", "WARN")
    return None

# --- Funciones para el Reporte HTML del Flujo ---
def start_html_report(event_id):
    global CURRENT_EVENT_HTML_REPORT
    CURRENT_EVENT_HTML_REPORT = os.path.join(REPORTS_DIR, f"evento_{event_id.replace(':', '-')}.html")
    html_content = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>Reporte de Flujo - Evento {event_id}</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f4f4f4; color: #333; }}
            .container {{ background-color: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }}
            .bot-step {{ margin-bottom: 20px; padding: 15px; border-left: 5px solid; border-radius: 5px; }}
            .bot-monitor {{ border-color: #3498db; background-color: #eaf5ff; }}
            .bot-analizador {{ border-color: #f1c40f; background-color: #fff9e6; }}
            .bot-enriquecedor {{ border-color: #2ecc71; background-color: #e9f7ef; }}
            .bot-router {{ border-color: #e74c3c; background-color: #fdedec; }}
            .bot-notificador {{ border-color: #9b59b6; background-color: #f5eff7; }}
            h1 {{ color: #2c3e50; text-align: center; }}
            h2 {{ color: #34495e; border-bottom: 2px solid #eee; padding-bottom: 5px;}}
            pre {{ background-color: #ecf0f1; padding: 10px; border-radius: 4px; white-space: pre-wrap; word-wrap: break-word; font-size: 0.9em; }}
            .timestamp {{ font-size: 0.8em; color: #7f8c8d; float: right; }}
            .character {{ font-weight: bold; font-size: 1.2em; margin-right: 10px;}}
            .sonic {{ color: #007bff; }}
            .tails {{ color: #ffaa00; }}
            .knuckles {{ color: #d90000; }}
            .eggman {{ color: #c0c0c0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1><span class="eggman">🤖</span> Reporte de Flujo del Evento: {event_id} <span class="eggman">🚨</span></h1>
    """
    with open(CURRENT_EVENT_HTML_REPORT, "w", encoding="utf-8") as f:
        f.write(html_content)

def add_to_html_report(bot_name, data_processed, details=""):
    if not CURRENT_EVENT_HTML_REPORT: return
    bot_class_map = {
        "BotMonitor": "bot-monitor", "BotAnalizador": "bot-analizador",
        "BotEnriquecedor": "bot-enriquecedor", "BotRouter": "bot-router",
        "BotNotificador": "bot-notificador"
    }
    bot_icon_map = {
        "BotMonitor": "🛰️", "BotAnalizador": "🧠",
        "BotEnriquecedor": "🗺️", "BotRouter": "🚦",
        "BotNotificador": "📡"
    }
    bot_class = bot_class_map.get(bot_name, "")
    bot_icon = bot_icon_map.get(bot_name, "⚙️")
    timestamp_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    character_html = ""
    if bot_name == "BotMonitor":
        source = data_processed.get("source_system_name", data_processed.get("source_system", ""))
        if "Tails" in source or "TAILS_SENSOR" in data_processed.get("source_type_tag",""): character_html = '<span class="character tails">Tails:</span>' # Ajustado para fuente de Tails
        elif "G.U.N." in source: character_html = '<span class="character eggman">G.U.N.:</span>'
        elif "Campo" in source: character_html = '<span class="character sonic">Freedom Fighter:</span>'
        elif "ME" in source or "Angel Island" in source: character_html = '<span class="character knuckles">Alerta Esmeralda:</span>' # Ajustado para fuente de Angel Island
    elif bot_name == "BotRouter":
        targets = data_processed.get("target_destinations", [])
        if "Sonic" in targets: character_html += '<span class="character sonic">Sonic</span> '
        if "Tails" in targets: character_html += '<span class="character tails">Tails</span> '
        if "Knuckles" in targets: character_html += '<span class="character knuckles">Knuckles</span> '
        if character_html: character_html = f"Ruteado a: {character_html}"
    html_content = f"""
        <div class="bot-step {bot_class}">
            <span class="timestamp">{timestamp_now}</span>
            <h2>{bot_icon} {bot_name}</h2>
            {character_html}
            <p>{details}</p>
            <pre>{json.dumps(data_processed, indent=2, ensure_ascii=False)}</pre>
        </div>
    """
    with open(CURRENT_EVENT_HTML_REPORT, "a", encoding="utf-8") as f:
        f.write(html_content)

def end_html_report():
    if not CURRENT_EVENT_HTML_REPORT: return
    html_content = """
        </div>
    </body>
    </html>
    """
    with open(CURRENT_EVENT_HTML_REPORT, "a", encoding="utf-8") as f:
        f.write(html_content)
    logger("System", f"Reporte HTML generado: {CURRENT_EVENT_HTML_REPORT}")

# --- 🛰️ BotMonitor ---
def bot_monitor():
    global EVENT_ID_COUNTER
    EVENT_ID_COUNTER += 1
    bot_name = "BotMonitor"
    logger(bot_name, "Iniciando monitoreo...")

    monitor_output = {}
    cfg_monitor = CONFIG.get("bot_monitor", {})
    use_selenium = cfg_monitor.get("use_selenium_source", False)
    
    selenium_data_extracted = False

    if use_selenium:
        selenium_html_sources = cfg_monitor.get("selenium_html_sources", ["fuente_de_datos_simulada.html"])
        if not selenium_html_sources: # Asegurar que hay al menos un archivo por defecto
            selenium_html_sources = ["fuente_de_datos_simulada.html"]
            logger(bot_name, "No se especificaron selenium_html_sources en config, usando default.", "WARN")

        selected_html_file = random.choice(selenium_html_sources)
        logger(bot_name, f"Selenium: Fuente HTML seleccionada aleatoriamente: '{selected_html_file}'")
        
        edge_binary_override = cfg_monitor.get("edge_binary_path_override", "").strip()
        driver = None
        try:
            logger(bot_name, f"Intentando obtener datos de '{selected_html_file}' con Selenium (Microsoft Edge)...")
            
            options = EdgeOptions()
            # options.add_argument("--headless") # Comentado para ver la ventana
            options.add_experimental_option('excludeSwitches', ['enable-logging'])
            options.add_argument('log-level=3')

            edge_binary_path_to_use = None
            if edge_binary_override and os.path.exists(edge_binary_override):
                logger(bot_name, f"Usando ruta de binario de Edge desde config: {edge_binary_override}", "INFO")
                edge_binary_path_to_use = edge_binary_override
            else:
                if edge_binary_override:
                    logger(bot_name, f"Ruta de binario de Edge en config NO VÁLIDA: {edge_binary_override}", "WARN")
                logger(bot_name, "Intentando encontrar binario de Edge automáticamente...", "INFO")
                edge_binary_path_to_use = find_edge_binary()

            if edge_binary_path_to_use:
                options.binary_location = edge_binary_path_to_use
            else:
                logger(bot_name, "No se especificó/encontró ruta para msedge.exe. Dejando que WebDriverManager intente.", "WARN")

            service = EdgeService(executable_path=EdgeChromiumDriverManager().install())
            driver = webdriver.Edge(service=service, options=options)
            
            driver.set_page_load_timeout(10) # Timeout para la carga de la página
            
            local_html_path = os.path.abspath(selected_html_file)
            if not os.path.exists(local_html_path):
                raise FileNotFoundError(f"Archivo HTML '{local_html_path}' no encontrado.")

            driver.get(f"file:///{local_html_path.replace(os.sep, '/')}")

            logger(bot_name, "HTML abierto por Selenium. Observa la ventana del navegador. Se cerrará en unos segundos...")
            time.sleep(cfg_monitor.get("selenium_view_time_seconds", 5))

            # Extraer datos (asumiendo que los IDs son consistentes en todos los HTML)
            descripcion_web = driver.find_element(By.ID, "descripcion").text
            nivel_web = driver.find_element(By.ID, "nivel").text
            ubicacion_web = driver.find_element(By.ID, "ubicacion").text
            device_id_web = driver.find_element(By.ID, "device_id").text
            reading_type_web = driver.find_element(By.ID, "reading_type").text
            value_web_str = driver.find_element(By.ID, "value").text
            try:
                value_web = float(value_web_str) if '.' in value_web_str else int(value_web_str)
            except ValueError:
                value_web = value_web_str # Mantener como string si no es numérico

            logger(bot_name, f"Datos Selenium (Edge) de '{selected_html_file}': Desc:'{descripcion_web}', Nivel:'{nivel_web}', Ubic:'{ubicacion_web}'")
            
            # Determinar un source_type_tag más específico basado en el nombre del archivo o contenido
            source_type_tag_sel = "WEB_SELENIUM_EDGE_GENERIC"
            source_system_sel = f"Fuente Web: {selected_html_file}"
            if "angel_island" in selected_html_file.lower():
                source_type_tag_sel = "WEB_SELENIUM_ANGEL_ISLAND"
                source_system_sel = "Fuente Web: Alerta Angel Island"
            elif "tails" in selected_html_file.lower():
                source_type_tag_sel = "WEB_SELENIUM_TAILS_REPORT"
                source_system_sel = "Fuente Web: Reporte Taller de Tails"

            monitor_output = {
                "event_id": f"EVT-SEL-{datetime.now().strftime('%Y%m%d%H%M%S')}-{EVENT_ID_COUNTER:04d}",
                "timestamp_raw": datetime.now().isoformat(),
                "source_system": source_system_sel, 
                "source_type_tag": source_type_tag_sel,
                "detected_location_raw": ubicacion_web,
                "threat_level_raw": nivel_web.lower(), # Normalizar a minúsculas
                "description_raw": descripcion_web,
                "raw_payload": {
                    "device_id": device_id_web, "reading_type": reading_type_web,
                    "value": value_web, "html_source_file": selected_html_file
                }
            }
            selenium_data_extracted = True

        except FileNotFoundError as fnf_e: logger(bot_name, str(fnf_e), "ERROR")
        except TimeoutException: logger(bot_name, f"Timeout al cargar '{selected_html_file}' con Edge.", "ERROR")
        except WebDriverException as wde:
            if "cannot find msedge binary" in str(wde).lower() or "edge browser was not found" in str(wde).lower():
                logger(bot_name, "Error de Selenium: No se puede encontrar el binario de Microsoft Edge (msedge.exe).", "CRITICAL")
            else:
                logger(bot_name, f"WebDriverException con Selenium (Edge): {str(wde)[:200]}...", "ERROR")
        except NoSuchElementException as nsee: logger(bot_name, f"No se encontró elemento en '{selected_html_file}' con Edge: {nsee}", "ERROR")
        except Exception as e: logger(bot_name, f"Error inesperado con Selenium (Edge) en '{selected_html_file}': {type(e).__name__} - {e}", "ERROR")
        finally:
            if driver: driver.quit()
            if selenium_data_extracted: logger(bot_name, f"Datos obtenidos vía Selenium (Edge) de '{selected_html_file}'.")
            else: logger(bot_name, f"Fallo al obtener datos vía Selenium (Edge) de '{selected_html_file}'. Se usará generación aleatoria si está configurado o fallback.")
    
    if not selenium_data_extracted: # Si Selenium falló o no estaba activo
        logger(bot_name, "Procediendo con generación de datos aleatorios...")
        sources_config = [
            {"name": "Sensor Tails", "type": "SENSOR_TAILS", "locations": ["Tails' Workshop", "Mystic Ruins"]},
            {"name": "Radar G.U.N.", "type": "RADAR_GUN", "locations": ["Station Square", "G.U.N. HQ"]},
            {"name": "Reporte Campo", "type": "FIELD_REPORT", "locations": ["Green Hill Zone", "Chemical Plant Zone"]},
            {"name": "Alerta ME", "type": "MASTER_EMERALD_ALERT", "locations": ["Angel Island"]}
        ]
        selected_source = random.choice(sources_config)
        source_name = selected_source["name"]
        source_type = selected_source["type"]
        
        possible_locations = [loc for loc in KNOWLEDGE_BASE if loc != "Unknown Location"] 
        location = random.choice(selected_source.get("locations", possible_locations) or possible_locations or ["Unknown Location"])

        raw_data = {}
        threat_level, desc = "bajo", "Actividad menor detectada" # Default
        if source_type == "SENSOR_TAILS":
            raw_data = {"device_id":f"TS_{random.randint(100,999)}","reading":round(random.uniform(1.0,100.0),2)}
            threat_level, desc = random.choice([("bajo","Vibración menor"), ("medio","Pico de energía sospechoso")])
        elif source_type == "RADAR_GUN":
            raw_data = {"contacts":random.randint(1,5),"signature":random.choice(["EGGMAN_ROBOT","UNKNOWN_AERIAL"])}
            threat_level, desc = random.choice([("medio","Contacto sospechoso detectado"), ("alto","Múltiples robots de Eggman confirmados")])
        elif source_type == "FIELD_REPORT":
            raw_data = {"agent":f"Agent_{random.choice(['Sonic', 'Amy', 'Espio'])}","badniks_seen":random.randint(1,20)}
            threat_level, desc = random.choice([("medio","Badniks avistados en patrulla"), ("alto","Ataque a pequeña escala en progreso")])
        elif source_type == "MASTER_EMERALD_ALERT":
            raw_data = {"energy_flux":"HIGH","stability":"UNSTABLE", "guardian_status": "ENGAGED"}
            threat_level, desc = "critico", "Fluctuación crítica en la Master Emerald. ¡Alerta máxima!"
        
        description = f"{desc} en {location} (Fuente: {source_name})"

        monitor_output = {
            "event_id": f"EVT-RND-{datetime.now().strftime('%Y%m%d%H%M%S')}-{EVENT_ID_COUNTER:04d}",
            "timestamp_raw": datetime.now().isoformat(), "source_system": source_name,
            "source_type_tag": source_type, "detected_location_raw": location,
            "threat_level_raw": threat_level, "description_raw": description, "raw_payload": raw_data
        }
        logger(bot_name, f"Datos generados aleatoriamente de '{source_name}'.")

    if not monitor_output: 
        monitor_output = {
            "event_id": f"EVT-FAIL-{datetime.now().strftime('%Y%m%d%H%M%S')}-{EVENT_ID_COUNTER:04d}",
            "timestamp_raw": datetime.now().isoformat(), "source_system": "FallbackSystem", "source_type_tag": "ERROR_MONITOR",
            "detected_location_raw": "Unknown", "threat_level_raw": "bajo", "description_raw": "Error crítico en BotMonitor, no se pudo generar/capturar evento.",
            "raw_payload": {}
        }
        logger(bot_name, "Fallo crítico en BotMonitor, usando evento por defecto.", "CRITICAL")

    start_html_report(monitor_output['event_id'])
    add_to_html_report(bot_name, monitor_output, "Datos iniciales capturados/generados.")
    
    logger(bot_name, f"Datos finales: ID {monitor_output['event_id']}, Fuente: {monitor_output['source_system']}, Tipo: {monitor_output['source_type_tag']}")
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

    logger(bot_name, f"Analizando evento ID: {monitor_data['event_id']}")
    canonical_data = {
        "event_id": monitor_data["event_id"],
        "timestamp_event": monitor_data["timestamp_raw"],
        "source_system_name": monitor_data["source_system"],
        "source_type": monitor_data["source_type_tag"], # Usar el source_type_tag del monitor
        "location_reported": monitor_data["detected_location_raw"],
        "threat_assessment": {
             "initial_level": monitor_data["threat_level_raw"].lower(), # Asegurar minúsculas
             "description": monitor_data["description_raw"]
        },
        "original_raw_data": monitor_data.get("raw_payload", {})
    }
    level = canonical_data["threat_assessment"]["initial_level"]
    if "critico" in level: score = 10
    elif "alto" in level: score = 7
    elif "medio" in level: score = 5
    else: score = 2 
    canonical_data["threat_assessment"]["priority_score"] = score
    logger(bot_name, f"Prioridad asignada: {score}")
    
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

    logger(bot_name, f"Enriqueciendo evento ID: {canonical_data['event_id']}")
    enriched_data = canonical_data.copy()
    location_key = enriched_data["location_reported"]
    
    default_location_info = KNOWLEDGE_BASE.get("Unknown Location", 
        {"zone_name": "Unknown", "description":"Info no disponible", "nearby_heroes":[], "common_threats":[]})
    location_info = KNOWLEDGE_BASE.get(location_key, default_location_info)

    enriched_data["location_details"] = {
        "zone_name": location_info.get("zone_name", location_key),
        "description": location_info.get("description", "Descripción no disponible."),
        "known_nearby_heroes": location_info.get("nearby_heroes", []),
        "common_threats_in_zone": location_info.get("common_threats", [])
    }
    if location_key not in KNOWLEDGE_BASE:
        logger(bot_name, f"Usando info por defecto para '{location_key}'.", "WARN")
    
    priority_score = enriched_data.get("threat_assessment", {}).get("priority_score", 0)
    num_heroes = len(enriched_data.get("location_details", {}).get("known_nearby_heroes", []))
    
    # Lógica de urgencia revisada
    if priority_score >= 9: # critico
        urgency = "MAXIMA_URGENCIA"
    elif priority_score >= 7: # alto
        urgency = "ALTA_URGENCIA"
    elif priority_score >= 5: # medio
        urgency = "URGENCIA_MEDIA"
    else: # bajo
        urgency = "URGENCIA_BAJA"

    # Ajuste de urgencia si no hay héroes cercanos para amenazas altas/máximas
    if priority_score >= 7 and num_heroes == 0 and urgency != "MAXIMA_URGENCIA":
        logger(bot_name, f"Escalando urgencia a MAXIMA_URGENCIA para score {priority_score} sin héroes cercanos.")
        urgency = "MAXIMA_URGENCIA"
        
    enriched_data["urgency_level"] = urgency
    logger(bot_name, f"Nivel de urgencia asignado: {urgency}")

    add_to_html_report(bot_name, enriched_data, "Datos contextualizados y enriquecidos.")

    write_json_data("enriched_output.json", enriched_data)
    logger(bot_name, "Enriquecimiento completado.")
    return enriched_data

# --- BotRouter ---
def bot_router():
    bot_name = "BotRouter"
    logger(bot_name, "--- EJECUTANDO NUEVA VERSIÓN REVISADA DE BOT_ROUTER ---")
    logger(bot_name, "Iniciando ruteo...")
    enriched_data = read_json_data("enriched_output.json")
    if not enriched_data:
        logger(bot_name, "No hay datos enriquecidos. Abortando.", "ERROR"); return None

    logger(bot_name, f"Ruteando evento ID: {enriched_data['event_id']}")
    
    alert_payload = enriched_data.copy() 
    source_type = alert_payload.get("source_type", "").upper() 
    threat_level = alert_payload.get("threat_assessment", {}).get("initial_level", "bajo")
    location_details = alert_payload.get("location_details", {})
    nearby_heroes = location_details.get("known_nearby_heroes", [])
    zone_name = location_details.get("zone_name", "")
    urgency_level = alert_payload.get("urgency_level", "")

    destinations = set(["LogDB"]) 

    # Reglas específicas de fuente (prioridad alta)
    if source_type == "MASTER_EMERALD_ALERT" or source_type == "WEB_SELENIUM_ANGEL_ISLAND":
        destinations.add("Knuckles")
        if threat_level in ["alto", "critico"]:
            destinations.add("Sonic")
        logger(bot_name, f"Fuente {source_type} ({threat_level}): Añadido Knuckles (y Sonic si aplica).")
    elif source_type == "SENSOR_TAILS" or source_type == "WEB_SELENIUM_TAILS_REPORT":
        destinations.add("Tails")
        logger(bot_name, f"Fuente {source_type}: Añadido Tails.")

    # Reglas generales basadas en amenaza
    if threat_level == "critico":
        logger(bot_name, "Amenaza CRITICA detectada.")
        destinations.add("Sonic")
        destinations.add("Tails") 
        if "Angel Island" in zone_name:
            destinations.add("Knuckles")
    
    elif threat_level == "alto":
        logger(bot_name, "Amenaza ALTA detectada.")
        destinations.add("Sonic")
        if "Tails" in nearby_heroes:
            destinations.add("Tails")
        if "Knuckles" in nearby_heroes and "Angel Island" in zone_name:
            destinations.add("Knuckles")

    elif threat_level == "medio":
        logger(bot_name, "Amenaza MEDIA detectada.")
        if "Sonic" in nearby_heroes:
            destinations.add("Sonic")
        if "Tails" in nearby_heroes:
            destinations.add("Tails")
            
    # Regla de Urgencia Máxima
    if urgency_level == "MAXIMA_URGENCIA" and "Sonic" not in destinations:
        logger(bot_name, "MAXIMA URGENCIA: Asegurando notificación a Sonic.")
        destinations.add("Sonic")
    
    routing_decision = {
        "event_id": alert_payload["event_id"],
        "target_destinations": list(destinations),
        "alert_payload_to_send": alert_payload
    }
    
    logger(bot_name, f"Destinos finales determinados: {', '.join(list(destinations))}")
    add_to_html_report(bot_name, routing_decision, f"Decisión de ruteo: enviar a {', '.join(list(destinations))}.")
    write_json_data("routing_output.json", routing_decision)
    logger(bot_name, "Ruteo completado.")
    return routing_decision

# --- BotNotificador ---
def bot_notificador():
    bot_name = "BotNotificador"
    logger(bot_name, "Iniciando notificaciones...")
    routing_data = read_json_data("routing_output.json")
    if not routing_data:
        logger(bot_name, "No hay decisiones de ruteo. Abortando.", "ERROR"); return

    logger(bot_name, f"Notificando para evento ID: {routing_data['event_id']}")
    destinations_to_notify = routing_data["target_destinations"]
    payload_to_send = routing_data["alert_payload_to_send"]
    
    cfg_notifier = CONFIG.get("bot_notificador", {})
    endpoint_map = cfg_notifier.get("endpoints", {})
    request_timeout = cfg_notifier.get("request_timeout_seconds", 5)

    if not endpoint_map:
        logger(bot_name, "No hay endpoints configurados en config.json.", "ERROR"); return

    sent_count = 0
    notifications_summary = []
    for dest_name in destinations_to_notify:
        url = endpoint_map.get(dest_name)
        status_message = ""
        if url:
            try:
                logger(bot_name, f"Enviando a {dest_name} en {url}...")
                response = requests.post(url, json=payload_to_send, timeout=request_timeout)
                response.raise_for_status() 
                status_message = f"Enviado a {dest_name} OK (Status: {response.status_code})"
                logger(bot_name, status_message)
                sent_count += 1
            except requests.exceptions.ConnectionError:
                status_message = f"Error de conexión con {dest_name} ({url})"
                logger(bot_name, status_message, "ERROR")
            except requests.exceptions.Timeout:
                status_message = f"Timeout con {dest_name} ({url})"
                logger(bot_name, status_message, "ERROR")
            except requests.exceptions.HTTPError as e_http:
                status_message = f"Error HTTP {e_http.response.status_code} con {dest_name} ({url})"
                logger(bot_name, status_message, "ERROR")
            except Exception as e_generic:
                status_message = f"Error enviando a {dest_name} ({url}): {type(e_generic).__name__}"
                logger(bot_name, status_message, "ERROR")
        else:
            status_message = f"Destino '{dest_name}' sin URL configurada. Saltado."
            logger(bot_name, status_message, "WARN")
        notifications_summary.append(status_message)

    report_details = "Resumen de Notificaciones:<br>" + "<br>".join(notifications_summary)
    add_to_html_report(bot_name, {"payload_sent": payload_to_send, "destinations": destinations_to_notify, "summary": notifications_summary}, report_details)
    
    logger(bot_name, f"Notificaciones completadas. {sent_count}/{len(destinations_to_notify)} enviadas.")

# --- CICLO PRINCIPAL DE ORQUESTACIÓN ---
def main_loop():
    logger("BotMaestro", "Hedgehog Alert Processor INICIADO.")
    logger("BotMaestro", "Presiona Ctrl+C para detener.")

    cfg_maestro = CONFIG.get("bot_maestro", {})
    min_interval = cfg_maestro.get("process_interval_seconds_min", 3)
    max_interval = cfg_maestro.get("process_interval_seconds_max", 7)
    max_cycles = cfg_maestro.get("max_cycles_to_run", 0)
    
    current_cycle = 0
    try:
        while True:
            current_cycle += 1
            global CURRENT_EVENT_HTML_REPORT 
            CURRENT_EVENT_HTML_REPORT = "" 
            logger("BotMaestro", f"--- Ciclo #{current_cycle} ---")
            
            monitor_result = bot_monitor()
            if monitor_result is None: 
                logger("BotMaestro", "BotMonitor falló críticamente, saltando ciclo.", "ERROR")
                time.sleep(max_interval) 
                continue 
            
            time.sleep(0.2)
            analysis_result = bot_analizador()
            if analysis_result is None: 
                logger("BotMaestro", "BotAnalizador falló. El ciclo podría no completarse correctamente.");
                # Decidir si continuar o no. Por ahora, continuamos para que el reporte HTML se genere.
            
            time.sleep(0.2)
            enriched_result = bot_enriquecedor()
            if enriched_result is None: logger("BotMaestro", "BotEnriquecedor falló.");

            time.sleep(0.2)
            routing_result = bot_router()
            if routing_result is None: logger("BotMaestro", "BotRouter falló.");
            
            time.sleep(0.2)
            bot_notificador()

            end_html_report() 

            logger("BotMaestro", f"--- Ciclo #{current_cycle} COMPLETADO ---")

            if max_cycles > 0 and current_cycle >= max_cycles:
                logger("BotMaestro", f"Máximo de ciclos ({max_cycles}) alcanzado. Terminando.")
                break
            
            process_interval_seconds = random.randint(min_interval, max_interval)
            logger("BotMaestro", f"Esperando {process_interval_seconds}s...")
            time.sleep(process_interval_seconds)
            
    except KeyboardInterrupt:
        logger("BotMaestro", "Interrupción por teclado. Deteniendo...")
    finally:
        if CURRENT_EVENT_HTML_REPORT and os.path.exists(CURRENT_EVENT_HTML_REPORT):
            try:
                with open(CURRENT_EVENT_HTML_REPORT, "r+", encoding="utf-8") as f: # r+ para leer y escribir
                    content = f.read()
                    if not content.strip().endswith("</html>"):
                        f.seek(0, os.SEEK_END) # Ir al final del archivo
                        f.write("\n        </div>\n    </body>\n    </html>\n")
            except Exception as e_file:
                logger("BotMaestro", f"Error al intentar cerrar HTML en finally: {e_file}", "ERROR")
        logger("BotMaestro", "Hedgehog Alert Processor TERMINADO.")

if __name__ == "__main__":
    ensure_dirs()
    load_config()
    main_loop()

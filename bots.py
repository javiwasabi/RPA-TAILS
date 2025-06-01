import os
import json
import time
import random
from datetime import datetime
import requests # Para BotNotificador

# Selenium imports
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import WebDriverException, NoSuchElementException, TimeoutException

# --- CONFIGURACIÓN GLOBAL ---
DATA_DIR = "data"
LOGS_DIR = "logs"
EVENT_ID_COUNTER = 0
CONFIG = {} # Variable para almacenar la configuración cargada
KNOWLEDGE_BASE = {} # Se cargará desde config.json

# --- FUNCIONES DE UTILIDAD ---
def ensure_dirs():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(LOGS_DIR, exist_ok=True)

def logger(bot_name, message, level="INFO"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    log_message_console = f"[{timestamp}] [{bot_name:<15}] [{level:<5}] {message}"
    print(log_message_console)
    log_file_path = os.path.join(LOGS_DIR, f"{bot_name}.log")
    with open(log_file_path, "a", encoding="utf-8") as f:
        f.write(log_message_console + "\n")

def write_json_data(filename, data):
    path = os.path.join(DATA_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    logger("System", f"Archivo JSON '{filename}' escrito en '{DATA_DIR}/'.", "DEBUG")

def read_json_data(filename):
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        logger("System", f"Archivo JSON '{filename}' no encontrado en '{DATA_DIR}/'.", "ERROR")
        return None
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    logger("System", f"Archivo JSON '{filename}' leído de '{DATA_DIR}/'.", "DEBUG")
    return data

def load_config():
    global CONFIG, KNOWLEDGE_BASE
    default_config = {
        "bot_maestro": {"process_interval_seconds_min": 5, "process_interval_seconds_max": 10, "max_cycles_to_run": 0},
        "bot_monitor": {"use_selenium_source": False, "selenium_local_html_file": "fuente_de_datos_simulada.html"},
        "bot_notificador": {"request_timeout_seconds": 5, "endpoints": {
            "Sonic": "http://127.0.0.1:5001/alert", "Knuckles": "http://127.0.0.1:5002/alert",
            "Tails": "http://127.0.0.1:5003/alert", "LogDB": "http://127.0.0.1:5004/alert"
        }},
        "bot_enriquecedor": {"knowledge_base_simulated": {
            "Unknown Location": {"zone_name": "Unknown Location", "description": "Ubicación desconocida.", "nearby_heroes": [], "common_threats": []}
        }}
    }
    try:
        with open("config.json", "r", encoding="utf-8") as f:
            loaded_config = json.load(f)
        
        # Merge loaded_config into default_config to ensure all keys are present
        CONFIG = default_config.copy() # Start with defaults
        for key, value in loaded_config.items():
            if key in CONFIG and isinstance(CONFIG[key], dict) and isinstance(value, dict):
                CONFIG[key].update(value) # Merge dictionaries
            else:
                CONFIG[key] = value # Overwrite or add new keys

        logger("BotMaestro", "Configuración cargada exitosamente desde config.json")
    except FileNotFoundError:
        logger("BotMaestro", "config.json no encontrado. Usando configuración por defecto.", "WARN")
        CONFIG = default_config
    except json.JSONDecodeError:
        logger("BotMaestro", "Error al decodificar config.json. Usando configuración por defecto.", "ERROR")
        CONFIG = default_config
    except Exception as e:
        logger("BotMaestro", f"Error inesperado al cargar config.json: {e}. Usando configuración por defecto.", "ERROR")
        CONFIG = default_config

    if CONFIG.get("bot_enriquecedor", {}).get("knowledge_base_simulated"):
        KNOWLEDGE_BASE = CONFIG["bot_enriquecedor"]["knowledge_base_simulated"]
        logger("BotMaestro", "Base de conocimiento actualizada desde config.json")
    else: # Fallback if knowledge_base is somehow missing after merge
        KNOWLEDGE_BASE = default_config["bot_enriquecedor"]["knowledge_base_simulated"]
        logger("BotMaestro", "Usando base de conocimiento por defecto.", "WARN")


# --- 🛰️ BotMonitor ---
def bot_monitor():
    global EVENT_ID_COUNTER
    EVENT_ID_COUNTER += 1
    bot_name = "BotMonitor"
    logger(bot_name, "Iniciando monitoreo de actividad de Badniks...")

    monitor_output = {}
    cfg_monitor = CONFIG.get("bot_monitor", {})
    use_selenium = cfg_monitor.get("use_selenium_source", False)
    selenium_html_file = cfg_monitor.get("selenium_local_html_file", "fuente_de_datos_simulada.html")
    
    selenium_data_extracted = False

    if use_selenium:
        driver = None
        try:
            logger(bot_name, f"Intentando obtener datos de '{selenium_html_file}' con Selenium...")
            
            chrome_options = webdriver.ChromeOptions()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920x1080")
            chrome_options.add_argument("--log-level=3")
            chrome_options.add_experimental_option('excludeSwitches', ['enable-logging']) # Quieter console

            service = ChromeService(executable_path=ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            driver.set_page_load_timeout(10) # Timeout para carga de página
            
            local_html_path = os.path.abspath(selenium_html_file)
            if not os.path.exists(local_html_path):
                logger(bot_name, f"Archivo HTML '{local_html_path}' no encontrado para Selenium.", "ERROR")
                raise FileNotFoundError(f"Archivo HTML local '{local_html_path}' no encontrado.")

            driver.get(f"file:///{local_html_path.replace(os.sep, '/')}")
            # No es necesario time.sleep(1) si la página es local y simple. Selenium espera a que cargue.

            descripcion_web = driver.find_element(By.ID, "descripcion").text
            nivel_web = driver.find_element(By.ID, "nivel").text
            ubicacion_web = driver.find_element(By.ID, "ubicacion").text
            device_id_web = driver.find_element(By.ID, "device_id").text
            reading_type_web = driver.find_element(By.ID, "reading_type").text
            value_web_str = driver.find_element(By.ID, "value").text
            try:
                value_web = float(value_web_str) if '.' in value_web_str else int(value_web_str)
            except ValueError:
                value_web = value_web_str

            logger(bot_name, f"Datos Selenium: Desc:'{descripcion_web}', Nivel:'{nivel_web}', Ubic:'{ubicacion_web}'")

            monitor_output = {
                "event_id": f"EVT-SEL-{datetime.now().strftime('%Y%m%d%H%M%S')}-{EVENT_ID_COUNTER:04d}",
                "timestamp_raw": datetime.now().isoformat(),
                "source_system": "Fuente Web Simulada (Selenium)",
                "source_type_tag": "WEB_SELENIUM",
                "detected_location_raw": ubicacion_web,
                "threat_level_raw": nivel_web,
                "description_raw": descripcion_web,
                "raw_payload": {
                    "device_id": device_id_web, "reading_type": reading_type_web,
                    "value": value_web, "html_source_file": selenium_html_file
                }
            }
            selenium_data_extracted = True
        except FileNotFoundError as fnf_e:
            logger(bot_name, str(fnf_e), "ERROR")
        except TimeoutException:
            logger(bot_name, f"Timeout al cargar la página '{selenium_html_file}' con Selenium.", "ERROR")
        except WebDriverException as wde:
            logger(bot_name, f"WebDriverException con Selenium: {str(wde)[:200]}...", "ERROR") # Log resumido
        except NoSuchElementException as nsee:
            logger(bot_name, f"No se encontró elemento en '{selenium_html_file}': {nsee}", "ERROR")
        except Exception as e:
            logger(bot_name, f"Error inesperado con Selenium: {type(e).__name__} - {e}", "ERROR")
        finally:
            if driver:
                driver.quit()
            if selenium_data_extracted:
                logger(bot_name, "Datos obtenidos exitosamente vía Selenium.")
            else:
                logger(bot_name, "Fallo al obtener datos vía Selenium. Se usará generación aleatoria.")

    if not selenium_data_extracted:
        logger(bot_name, "Procediendo con generación de datos aleatorios...")
        sources_config = [
            {"name": "Sensor Tails", "type": "SENSOR_TAILS", "locations": ["Tails' Workshop"]},
            {"name": "Radar G.U.N.", "type": "RADAR_GUN", "locations": ["Station Square", "G.U.N. HQ"]},
            {"name": "Reporte Campo", "type": "FIELD_REPORT", "locations": ["Green Hill Zone", "Angel Island"]},
            {"name": "Alerta ME", "type": "MASTER_EMERALD_ALERT", "locations": ["Angel Island"]}
        ]
        selected_source = random.choice(sources_config)
        source_name = selected_source["name"]
        source_type = selected_source["type"]
        
        possible_locations = [loc for loc in KNOWLEDGE_BASE if loc != "Unknown Location"] # Excluir "Unknown" de opciones aleatorias
        location = random.choice(selected_source.get("locations", possible_locations) or possible_locations or ["Unknown Location"])


        raw_data = {}
        if source_type == "SENSOR_TAILS":
            raw_data = {"device_id":f"TS_{random.randint(100,999)}","reading":round(random.uniform(1.0,100.0),2)}
            threat_level, desc = random.choice([("bajo","Vibración menor"), ("medio","Pico de energía")])
        elif source_type == "RADAR_GUN":
            raw_data = {"contacts":random.randint(1,5),"signature":random.choice(["EGGMAN_ROBOT","UNKNOWN"])}
            threat_level, desc = random.choice([("medio","Contacto sospechoso"), ("alto","Múltiples robots de Eggman")])
        elif source_type == "FIELD_REPORT":
            raw_data = {"agent":f"Agent_{random.randint(1,10)}","badniks_seen":random.randint(1,20)}
            threat_level, desc = random.choice([("medio","Badniks avistados"), ("alto","Ataque a gran escala")])
        else: # MASTER_EMERALD_ALERT
            raw_data = {"energy_flux":"HIGH","stability":"UNSTABLE"}
            threat_level, desc = "critico", "Fluctuación crítica en la Master Emerald"
        
        description = f"{desc} en {location} ({source_name})"

        monitor_output = {
            "event_id": f"EVT-RND-{datetime.now().strftime('%Y%m%d%H%M%S')}-{EVENT_ID_COUNTER:04d}",
            "timestamp_raw": datetime.now().isoformat(), "source_system": source_name,
            "source_type_tag": source_type, "detected_location_raw": location,
            "threat_level_raw": threat_level, "description_raw": description, "raw_payload": raw_data
        }
        logger(bot_name, f"Datos generados aleatoriamente de '{source_name}'.")

    if not monitor_output: # Fallback final
        monitor_output = {
            "event_id": f"EVT-FAIL-{datetime.now().strftime('%Y%m%d%H%M%S')}-{EVENT_ID_COUNTER:04d}",
            "timestamp_raw": datetime.now().isoformat(), "source_system": "Fallback", "source_type_tag": "ERROR",
            "detected_location_raw": "Unknown", "threat_level_raw": "bajo", "description_raw": "Error crítico en generación de evento.",
            "raw_payload": {}
        }
        logger(bot_name, "Fallo crítico en BotMonitor, usando evento por defecto.", "CRITICAL")

    logger(bot_name, f"Datos finales: ID {monitor_output['event_id']}, Fuente: {monitor_output['source_system']}")
    write_json_data("monitor_output.json", monitor_output)
    logger(bot_name, "Monitoreo completado.")
    return monitor_output

# --- 🧠 BotAnalizador ---
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
        "source_type": monitor_data["source_type_tag"],
        "location_reported": monitor_data["detected_location_raw"],
        "threat_assessment": {
             "initial_level": monitor_data["threat_level_raw"].lower(),
             "description": monitor_data["description_raw"]
        },
        "original_raw_data": monitor_data.get("raw_payload", {})
    }
    level = canonical_data["threat_assessment"]["initial_level"]
    if "critico" in level: score = 10
    elif "alto" in level: score = 7
    elif "medio" in level: score = 5
    else: score = 2 # bajo o desconocido
    canonical_data["threat_assessment"]["priority_score"] = score
    logger(bot_name, f"Prioridad asignada: {score}")
    write_json_data("analysis_output.json", canonical_data)
    logger(bot_name, "Análisis completado.")
    return canonical_data

# --- 🗺️ BotEnriquecedor ---
def bot_enriquecedor():
    bot_name = "BotEnriquecedor"
    logger(bot_name, "Iniciando enriquecimiento...")
    canonical_data = read_json_data("analysis_output.json")
    if not canonical_data:
        logger(bot_name, "No hay datos canónicos. Abortando.", "ERROR"); return None

    logger(bot_name, f"Enriqueciendo evento ID: {canonical_data['event_id']}")
    enriched_data = canonical_data.copy()
    location_key = enriched_data["location_reported"]
    
    # Usar KNOWLEDGE_BASE global que se carga desde config.json
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
    if priority_score >= 7 and num_heroes == 0: urgency = "MAXIMA_URGENCIA"
    elif priority_score >= 7: urgency = "ALTA_URGENCIA"
    elif priority_score >= 5: urgency = "URGENCIA_MEDIA"
    else: urgency = "URGENCIA_BAJA"
    enriched_data["urgency_level"] = urgency
    logger(bot_name, f"Nivel de urgencia: {urgency}")
    write_json_data("enriched_output.json", enriched_data)
    logger(bot_name, "Enriquecimiento completado.")
    return enriched_data

# --- 🚦 BotRouter ---
def bot_router():
    bot_name = "BotRouter"
    logger(bot_name, "Iniciando ruteo...")
    enriched_data = read_json_data("enriched_output.json")
    if not enriched_data:
        logger(bot_name, "No hay datos enriquecidos. Abortando.", "ERROR"); return None

    logger(bot_name, f"Ruteando evento ID: {enriched_data['event_id']}")
    destinations = set(["LogDB"]) # Siempre a LogDB
    alert_payload = enriched_data.copy()
    threat_level = alert_payload.get("threat_assessment", {}).get("initial_level", "bajo")
    source_type = alert_payload.get("source_type", "")
    location_details = alert_payload.get("location_details", {})
    nearby_heroes = location_details.get("known_nearby_heroes", [])
    zone_name = location_details.get("zone_name", "")

    if source_type == "MASTER_EMERALD_ALERT": destinations.add("Knuckles")
    if source_type == "SENSOR_TAILS":
        destinations.add("Tails")
        if threat_level in ["alto", "critico"]: destinations.add("Sonic")
    if source_type == "RADAR_GUN" or source_type == "FIELD_REPORT":
        if threat_level in ["alto", "critico"]: destinations.add("Sonic")
        if "Tails" in nearby_heroes and threat_level in ["medio","alto","critico"]: destinations.add("Tails")
        if "Knuckles" in nearby_heroes and threat_level in ["alto","critico"] and "Angel Island" in zone_name:
            destinations.add("Knuckles")
    if alert_payload.get("urgency_level") == "MAXIMA_URGENCIA" and "Sonic" not in destinations:
        destinations.add("Sonic")

    routing_decision = {
        "event_id": alert_payload["event_id"],
        "target_destinations": list(destinations),
        "alert_payload_to_send": alert_payload
    }
    logger(bot_name, f"Destinos: {', '.join(list(destinations))}")
    write_json_data("routing_output.json", routing_decision)
    logger(bot_name, "Ruteo completado.")
    return routing_decision

# --- 📡 BotNotificador ---
def bot_notificador():
    bot_name = "BotNotificador"
    logger(bot_name, "Iniciando notificaciones...")
    routing_data = read_json_data("routing_output.json")
    if not routing_data:
        logger(bot_name, "No hay decisiones de ruteo. Abortando.", "ERROR"); return

    logger(bot_name, f"Notificando para evento ID: {routing_data['event_id']}")
    destinations = routing_data["target_destinations"]
    payload = routing_data["alert_payload_to_send"]
    
    cfg_notifier = CONFIG.get("bot_notificador", {})
    endpoint_map = cfg_notifier.get("endpoints", {})
    request_timeout = cfg_notifier.get("request_timeout_seconds", 5)

    if not endpoint_map:
        logger(bot_name, "No hay endpoints configurados en config.json.", "ERROR"); return

    sent_count = 0
    for dest_name in destinations:
        url = endpoint_map.get(dest_name)
        if url:
            try:
                logger(bot_name, f"Enviando a {dest_name} en {url}...")
                response = requests.post(url, json=payload, timeout=request_timeout)
                response.raise_for_status()
                logger(bot_name, f"Enviado a {dest_name} OK. Status: {response.status_code} {response.text[:50]}")
                sent_count += 1
            except requests.exceptions.ConnectionError:
                logger(bot_name, f"Error de conexión con {dest_name} ({url}). ¿Servidor Flask activo?", "ERROR")
            except requests.exceptions.Timeout:
                logger(bot_name, f"Timeout con {dest_name} ({url}).", "ERROR")
            except requests.exceptions.HTTPError as e:
                logger(bot_name, f"Error HTTP con {dest_name} ({url}): {e.response.status_code} {e.response.text[:100]}", "ERROR")
            except Exception as e:
                logger(bot_name, f"Error enviando a {dest_name} ({url}): {type(e).__name__} - {e}", "ERROR")
        else:
            logger(bot_name, f"Destino '{dest_name}' sin URL en config. Saltando.", "WARN")
    logger(bot_name, f"Notificaciones completadas. {sent_count}/{len(destinations)} enviadas.")

# --- CICLO PRINCIPAL DE ORQUESTACIÓN (Simula el BotMaestro) ---
def main_loop():
    load_config() # Cargar configuración PRIMERO
    ensure_dirs() # Asegurar que data/ y logs/ existan
    
    logger("BotMaestro", "Hedgehog Alert Processor - RPA Edition (Simulado) INICIADO.")
    logger("BotMaestro", "Presiona Ctrl+C para detener.")

    cfg_maestro = CONFIG.get("bot_maestro", {})
    min_interval = cfg_maestro.get("process_interval_seconds_min", 3)
    max_interval = cfg_maestro.get("process_interval_seconds_max", 7)
    # Corregir el nombre de la clave para max_cycles
    max_cycles = cfg_maestro.get("max_cycles_to_run", 0) 
    
    current_cycle = 0
    try:
        while True:
            current_cycle += 1
            logger("BotMaestro", f"--- Iniciando Ciclo de Procesamiento #{current_cycle} ---")
            
            if bot_monitor() is None: time.sleep(1); continue # Si monitor falla, esperar y reintentar ciclo
            time.sleep(0.2)
            if bot_analizador() is None: time.sleep(1); continue
            time.sleep(0.2)
            if bot_enriquecedor() is None: time.sleep(1); continue
            time.sleep(0.2)
            if bot_router() is None: time.sleep(1); continue
            time.sleep(0.2)
            bot_notificador() # Notificador no retorna valor crítico para el flujo

            logger("BotMaestro", f"--- Ciclo #{current_cycle} COMPLETADO ---")

            if max_cycles > 0 and current_cycle >= max_cycles:
                logger("BotMaestro", f"Máximo de ciclos ({max_cycles}) alcanzado. Terminando.")
                break
            
            process_interval_seconds = random.randint(min_interval, max_interval)
            logger("BotMaestro", f"Esperando {process_interval_seconds}s para el próximo ciclo...")
            time.sleep(process_interval_seconds)
            
    except KeyboardInterrupt:
        logger("BotMaestro", "Interrupción por teclado. Deteniendo sistema...")
    finally:
        logger("BotMaestro", "Hedgehog Alert Processor - RPA Edition (Simulado) TERMINADO.")

if __name__ == "__main__":
    main_loop()
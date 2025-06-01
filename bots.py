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

# --- FUNCIONES DE UTILIDAD ---
# (ensure_dirs, logger, write_json_data, read_json_data, load_config, find_edge_binary, init_webdriver, close_webdriver - SIN CAMBIOS IMPORTANTES, ASUMIR QUE ESTÁN AQUÍ)
# ... (COPIA AQUÍ LAS FUNCIONES DE UTILIDAD, load_config, webdriver y HTML report de la versión anterior)
# ... Asegúrate de que `load_config` y `init_webdriver` usen los valores de `CONFIG` correctamente.
# ... Y que `read_json_data` y `write_json_data` puedan usar el `DASHBOARD_DATA_DIR`.

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
        logger("System", f"Directorio '{directory}' creado.", "DEBUG")
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
        logger("System", f"Archivo JSON '{filename}' leído de '{directory}'.", "DEBUG")
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
            "selenium_view_time_seconds": 3 # Reducido, ya que la acción principal será en el dashboard
            },
        "dashboard_tactico": { 
            "url": "http://127.0.0.1:5005",
            "submit_alert_endpoint": "/submit_alert_data",
            "check_alert_endpoint": "/check_new_alert", # Añadido para polling del dashboard
            "decision_timeout_seconds": 40, # Aumentado
            "decision_poll_interval_seconds": 1,
            "dashboard_refresh_poll_seconds": 3 # Para el JS del dashboard
        },
        "bot_notificador": {"request_timeout_seconds": 5, "endpoints": {
            "Sonic": "http://127.0.0.1:5001/alert", "Knuckles": "http://127.0.0.1:5002/alert",
            "Tails": "http://127.0.0.1:5003/alert", "LogDB": "http://127.0.0.1:5004/alert"
        }},
        "bot_enriquecedor": {"knowledge_base_simulated": {
            "Green Hill Zone": {"zone_name": "Green Hill Zone", "description": "Colinas verdes.", "nearby_heroes": ["Sonic", "Tails"], "common_threats": ["Moto Bug"], "css_class": "zone-green-hill"},
            "Chemical Plant Zone": {"zone_name": "Chemical Plant Zone", "description": "Zona industrial.", "nearby_heroes": ["Sonic"], "common_threats": ["Grabber"], "css_class": "zone-chemical-plant"},
            "Station Square": {"zone_name": "Station Square", "description": "Metrópolis.", "nearby_heroes": ["Sonic", "Amy"], "common_threats": ["Egg Walker"], "css_class": "zone-station-square"},
            "Angel Island": {"zone_name": "Angel Island", "description": "Isla flotante.", "nearby_heroes": ["Knuckles", "Sonic"], "common_threats": ["EggRobo", "Master Emerald Threats"], "css_class": "zone-angel-island"},
            "Tails' Workshop": {"zone_name": "Tails' Workshop", "description": "Taller de Tails en Mystic Ruins.", "nearby_heroes": ["Tails", "Sonic"], "common_threats": ["Badniks exploradores", "Espionaje"], "css_class": "zone-mystic-ruins"},
             "Mystic Ruins": {"zone_name": "Mystic Ruins", "description": "Área antigua con ruinas y una jungla.", "nearby_heroes": ["Tails", "Knuckles", "Sonic"], "common_threats": ["Egg Hornet", "Chaos Gamma"], "css_class": "zone-mystic-ruins"},
            "G.U.N. HQ": {"zone_name": "Central City - G.U.N. HQ", "description": "Cuartel G.U.N.", "nearby_heroes": [], "common_threats": ["Robots G.U.N."], "css_class": "zone-gun-hq"},
            "Unknown Location": {"zone_name": "Unknown Location", "description": "Ubicación desconocida.", "nearby_heroes": [], "common_threats": [], "css_class": "zone-unknown"}
        }}
    }
    try:
        with open("config.json", "r", encoding="utf-8") as f:
            loaded_config = json.load(f)
        CONFIG = default_config.copy()
        for key, value in loaded_config.items():
            if key in CONFIG and isinstance(CONFIG[key], dict) and isinstance(value, dict):
                # Actualizar diccionarios anidados de forma más específica
                if key in ["bot_maestro", "bot_monitor", "dashboard_tactico", "bot_notificador", "bot_enriquecedor"]:
                    for sub_key, sub_value in value.items():
                        if isinstance(CONFIG[key].get(sub_key), dict) and isinstance(sub_value, dict):
                             CONFIG[key][sub_key].update(sub_value)
                        else:
                            CONFIG[key][sub_key] = sub_value
                else:
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
        logger("BotMaestro", f"Error cargando config.json: {e}. Usando config por defecto.", "ERROR")
        CONFIG = default_config

    kb_config = CONFIG.get("bot_enriquecedor", {}).get("knowledge_base_simulated")
    if kb_config:
        KNOWLEDGE_BASE = kb_config
        # Añadir css_class por defecto si falta en alguna entrada de la knowledge_base
        for loc, details in KNOWLEDGE_BASE.items():
            if "css_class" not in details:
                details["css_class"] = "zone-default" # O generar una a partir del nombre
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
    edge_binary_path_to_use = None
    if edge_binary_override and os.path.exists(edge_binary_override):
        logger("WebDriver", f"Usando ruta de binario de Edge desde config: {edge_binary_override}", "INFO")
        edge_binary_path_to_use = edge_binary_override
    else:
        if edge_binary_override: logger("WebDriver", f"Ruta de binario de Edge en config NO VÁLIDA: {edge_binary_override}", "WARN")
        logger("WebDriver", "Intentando encontrar binario de Edge automáticamente...", "INFO")
        edge_binary_path_to_use = find_edge_binary()
    if edge_binary_path_to_use: options.binary_location = edge_binary_path_to_use
    else: logger("WebDriver", "No se especificó/encontró ruta para msedge.exe. Dejando que WebDriverManager intente.", "WARN")
    try:
        service = EdgeService(executable_path=EdgeChromiumDriverManager().install())
        driver = webdriver.Edge(service=service, options=options)
        logger("WebDriver", "Nueva instancia de WebDriver creada exitosamente.")
        WEBDRIVER_INSTANCE = driver
        return driver
    except WebDriverException as e:
        logger("WebDriver", f"FALLO AL INICIALIZAR WEBDRIVER: {e}", "CRITICAL")
        if "cannot find msedge binary" in str(e).lower() or "edge browser was not found" in str(e).lower():
            logger("WebDriver", "Asegúrate de que Microsoft Edge esté instalado o la ruta en config.json sea correcta.", "CRITICAL")
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
# (start_html_report, add_to_html_report, end_html_report SIN CAMBIOS)
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
            .bot-decision-tactica {{ border-color: #e67e22; background-color: #fdf3e6; }}
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
        "BotEnriquecedor": "bot-enriquecedor", 
        "BotDecisionTactica": "bot-decision-tactica", 
        "BotNotificador": "bot-notificador"
    }
    bot_icon_map = {
        "BotMonitor": "🛰️", "BotAnalizador": "🧠",
        "BotEnriquecedor": "🗺️", 
        "BotDecisionTactica": "🎯", 
        "BotNotificador": "📡"
    }
    bot_class = bot_class_map.get(bot_name, "")
    bot_icon = bot_icon_map.get(bot_name, "⚙️")
    timestamp_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    character_html = ""
    if bot_name == "BotMonitor":
        source = data_processed.get("source_system_name", data_processed.get("source_system", ""))
        source_tag = data_processed.get("source_type_tag","").upper()
        if "TAILS" in source.upper() or "TAILS_SENSOR" in source_tag or "WEB_SELENIUM_TAILS_REPORT" in source_tag:
            character_html = '<span class="character tails">Tails:</span>'
        elif "G.U.N." in source.upper(): character_html = '<span class="character eggman">G.U.N.:</span>'
        elif "CAMPO" in source.upper(): character_html = '<span class="character sonic">Freedom Fighter:</span>'
        elif "ME" in source.upper() or "ANGEL ISLAND" in source.upper() or "WEB_SELENIUM_ANGEL_ISLAND" in source_tag:
            character_html = '<span class="character knuckles">Alerta Esmeralda:</span>'
    elif bot_name == "BotDecisionTactica": 
        targets = data_processed.get("target_destinations", [])
        decision_type = data_processed.get("decision_type", "Desconocida")
        if "Sonic" in targets: character_html += '<span class="character sonic">Sonic</span> '
        if "Tails" in targets: character_html += '<span class="character tails">Tails</span> '
        if "Knuckles" in targets: character_html += '<span class="character knuckles">Knuckles</span> '
        if character_html: character_html = f"Destinos Decididos ({decision_type}): {character_html}"
        else: character_html = f"Decisión ({decision_type}): Solo LogDB"
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
                logger(bot_name, "No se especificaron selenium_html_sources en config, usando default.", "WARN")
            
            selected_html_file = random.choice(selenium_html_sources)
            logger(bot_name, f"Selenium: Fuente HTML para scraping: '{selected_html_file}'")
            
            try:
                local_html_path = os.path.abspath(selected_html_file)
                if not os.path.exists(local_html_path):
                    raise FileNotFoundError(f"Archivo HTML '{local_html_path}' no encontrado para scraping.")

                # Abrir y scrapear el archivo HTML de la fuente de datos
                driver.get(f"file:///{local_html_path.replace(os.sep, '/')}")
                logger(bot_name, f"HTML '{selected_html_file}' cargado para scraping. Esperando...")
                time.sleep(cfg_monitor.get("selenium_view_time_seconds", 3)) # Tiempo para ver el HTML fuente

                descripcion_web = driver.find_element(By.ID, "descripcion").text
                nivel_web = driver.find_element(By.ID, "nivel").text
                ubicacion_web = driver.find_element(By.ID, "ubicacion").text
                device_id_web = driver.find_element(By.ID, "device_id").text
                reading_type_web = driver.find_element(By.ID, "reading_type").text
                value_web_str = driver.find_element(By.ID, "value").text
                try: value_web = float(value_web_str) if '.' in value_web_str else int(value_web_str)
                except ValueError: value_web = value_web_str

                logger(bot_name, f"Datos Selenium (Edge) de '{selected_html_file}': Desc:'{descripcion_web}', Nivel:'{nivel_web}', Ubic:'{ubicacion_web}'")
                source_type_tag_sel = "WEB_SELENIUM_EDGE_GENERIC"
                source_system_sel = f"Fuente Web Scraped: {selected_html_file}"
                if "angel_island" in selected_html_file.lower():
                    source_type_tag_sel = "WEB_SELENIUM_ANGEL_ISLAND"
                    source_system_sel = "Fuente Web: Alerta Angel Island (Scraped)"
                elif "tails" in selected_html_file.lower():
                    source_type_tag_sel = "WEB_SELENIUM_TAILS_REPORT"
                    source_system_sel = "Fuente Web: Reporte Taller de Tails (Scraped)"

                monitor_output = {
                    "event_id": f"EVT-SEL-{datetime.now().strftime('%Y%m%d%H%M%S')}-{EVENT_ID_COUNTER:04d}",
                    "timestamp_raw": datetime.now().isoformat(), "source_system": source_system_sel, 
                    "source_type_tag": source_type_tag_sel, "detected_location_raw": ubicacion_web,
                    "threat_level_raw": nivel_web.lower(), "description_raw": descripcion_web,
                    "raw_payload": {"device_id": device_id_web, "reading_type": reading_type_web, "value": value_web, "html_source_file": selected_html_file}
                }
                selenium_data_extracted = True
                
                # Después de scrapear, redirigir la misma ventana de Selenium al Dashboard Táctico
                cfg_dashboard = CONFIG.get("dashboard_tactico", {})
                dashboard_main_url = cfg_dashboard.get("url", "http://127.0.0.1:5005").rstrip('/') + "/"
                logger(bot_name, f"Scraping completo. Redirigiendo ventana de Selenium al Dashboard Táctico: {dashboard_main_url}")
                driver.get(dashboard_main_url)
                # La ventana de Selenium ahora muestra el dashboard y permanecerá allí hasta el próximo ciclo o el final.

            except FileNotFoundError as fnf_e: logger(bot_name, str(fnf_e), "ERROR")
            except TimeoutException: logger(bot_name, f"Timeout al cargar '{selected_html_file}' con Edge.", "ERROR")
            except InvalidArgumentException as iae: logger(bot_name, f"Error de Argumento Inválido con Selenium (Edge) para '{selected_html_file}': {iae}", "ERROR")
            except WebDriverException as wde: 
                logger(bot_name, f"WebDriverException con Selenium (Edge) en '{selected_html_file}': {type(wde).__name__} - {wde}", "ERROR")
                if "target window already closed" in str(wde).lower() or "no such window" in str(wde).lower():
                    logger(bot_name, "La ventana del navegador parece haberse cerrado. Se intentará reiniciar en el próximo ciclo.", "WARN")
                    close_webdriver() 
            except NoSuchElementException as nsee: logger(bot_name, f"No se encontró elemento en '{selected_html_file}' con Edge: {nsee}", "ERROR")
            except Exception as e: logger(bot_name, f"Error inesperado con Selenium (Edge) en '{selected_html_file}': {type(e).__name__} - {e}", "ERROR")
            
            if selenium_data_extracted: logger(bot_name, f"Datos obtenidos vía Selenium (Edge) de '{selected_html_file}'.")
            else: logger(bot_name, f"Fallo al obtener datos vía Selenium (Edge) de '{selected_html_file}'.")

    if not use_selenium or not selenium_data_extracted: 
        # ... (Lógica de generación aleatoria de BotMonitor SIN CAMBIOS) ...
        if use_selenium and not selenium_data_extracted: logger(bot_name, "Fallo en Selenium, recurriendo a generación de datos aleatorios...")
        else: logger(bot_name, "Procediendo con generación de datos aleatorios (Selenium no activo)...")
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
        threat_level, desc = "bajo", "Actividad menor detectada"
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
# (SIN CAMBIOS)
def bot_analizador():
    bot_name = "BotAnalizador"
    logger(bot_name, "Iniciando análisis...")
    monitor_data = read_json_data("monitor_output.json")
    if not monitor_data:
        logger(bot_name, "No hay datos del monitor. Abortando.", "ERROR"); return None
    logger(bot_name, f"Analizando evento ID: {monitor_data['event_id']}")
    canonical_data = {
        "event_id": monitor_data["event_id"], "timestamp_event": monitor_data["timestamp_raw"],
        "source_system_name": monitor_data["source_system"], "source_type": monitor_data["source_type_tag"],
        "location_reported": monitor_data["detected_location_raw"],
        "threat_assessment": {"initial_level": monitor_data["threat_level_raw"].lower(), "description": monitor_data["description_raw"]},
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
# (SIN CAMBIOS)
def bot_enriquecedor():
    bot_name = "BotEnriquecedor"
    logger(bot_name, "Iniciando enriquecimiento...")
    canonical_data = read_json_data("analysis_output.json")
    if not canonical_data:
        logger(bot_name, "No hay datos canónicos. Abortando.", "ERROR"); return None
    logger(bot_name, f"Enriqueciendo evento ID: {canonical_data['event_id']}")
    enriched_data = canonical_data.copy()
    location_key = enriched_data["location_reported"]
    # Añadir css_class al enriched_data si no está ya en KNOWLEDGE_BASE
    default_location_info = KNOWLEDGE_BASE.get("Unknown Location", {"zone_name": "Unknown Location", "description":"Info no disponible", "nearby_heroes":[], "common_threats":[], "css_class": "zone-unknown"})
    location_info = KNOWLEDGE_BASE.get(location_key, default_location_info)
    
    enriched_data["location_details"] = {
        "zone_name": location_info.get("zone_name", location_key),
        "description": location_info.get("description", "Descripción no disponible."),
        "known_nearby_heroes": location_info.get("nearby_heroes", []),
        "common_threats_in_zone": location_info.get("common_threats", []),
        "css_class": location_info.get("css_class", "zone-default") # Pasar la clase CSS
    }
    if location_key not in KNOWLEDGE_BASE: logger(bot_name, f"Usando info por defecto para '{location_key}'.", "WARN")
    priority_score = enriched_data.get("threat_assessment", {}).get("priority_score", 0)
    num_heroes = len(enriched_data.get("location_details", {}).get("known_nearby_heroes", []))
    if priority_score >= 9: urgency = "MAXIMA_URGENCIA"
    elif priority_score >= 7: urgency = "ALTA_URGENCIA"
    elif priority_score >= 5: urgency = "URGENCIA_MEDIA"
    else: urgency = "URGENCIA_BAJA"
    if priority_score >= 7 and num_heroes == 0 and urgency != "MAXIMA_URGENCIA":
        logger(bot_name, f"Escalando urgencia a MAXIMA_URGENCIA para score {priority_score} sin héroes cercanos.")
        urgency = "MAXIMA_URGENCIA"
    enriched_data["urgency_level"] = urgency
    logger(bot_name, f"Nivel de urgencia asignado: {urgency}")
    add_to_html_report(bot_name, enriched_data, "Datos contextualizados y enriquecidos.")
    write_json_data("enriched_output.json", enriched_data)
    logger(bot_name, "Enriquecimiento completado.")
    return enriched_data

# --- 🎯 BotDecisionTactica ---
# (SIN CAMBIOS respecto a la versión anterior que integra con el dashboard y maneja timeout)
def solicitar_decision_tactica_dashboard():
    bot_name = "BotDecisionTactica"
    logger(bot_name, "Iniciando proceso de decisión táctica con Dashboard...")
    enriched_data = read_json_data("enriched_output.json") 
    if not enriched_data:
        logger(bot_name, "No hay datos enriquecidos. No se puede solicitar decisión.", "ERROR")
        return None
    event_id = enriched_data.get("event_id")
    if not event_id:
        logger(bot_name, "Datos enriquecidos no tienen event_id. Abortando.", "ERROR")
        return None
    cfg_dashboard = CONFIG.get("dashboard_tactico", {})
    dashboard_url = cfg_dashboard.get("url", "http://127.0.0.1:5005")
    submit_endpoint = cfg_dashboard.get("submit_alert_endpoint", "/submit_alert_data")
    timeout_seconds = cfg_dashboard.get("decision_timeout_seconds", 15)
    poll_interval = cfg_dashboard.get("decision_poll_interval_seconds", 1)
    full_submit_url = f"{dashboard_url.rstrip('/')}{submit_endpoint}"
    try:
        logger(bot_name, f"Enviando datos de alerta '{event_id}' al dashboard en {full_submit_url}...")
        response = requests.post(full_submit_url, json=enriched_data, timeout=5) 
        response.raise_for_status()
        logger(bot_name, f"Alerta '{event_id}' enviada al dashboard exitosamente. Esperando decisión del usuario (timeout: {timeout_seconds}s)...")
    except requests.exceptions.RequestException as e:
        logger(bot_name, f"Error enviando alerta al dashboard: {e}. Se procederá con decisión automática.", "ERROR")
        return tomar_decision_automatica_por_timeout(event_id, enriched_data, "Error de conexión con Dashboard")
    start_time = datetime.now()
    decision_file_name = f"decision_{event_id}.json"
    auto_decision_file_name = f"auto_decision_{event_id}.json" 
    user_decision_data = None
    while (datetime.now() - start_time).total_seconds() < timeout_seconds:
        user_decision_from_file = read_json_data(decision_file_name, directory=DASHBOARD_DATA_DIR)
        if user_decision_from_file and user_decision_from_file.get("event_id") == event_id:
            user_decision_data = user_decision_from_file
            logger(bot_name, f"Decisión del usuario recibida para '{event_id}': {user_decision_data.get('user_decision')}")
            try: 
                os.remove(os.path.join(DASHBOARD_DATA_DIR, decision_file_name))
                logger(bot_name, f"Archivo de decisión '{decision_file_name}' eliminado.", "DEBUG")
            except OSError as e_rem: 
                logger(bot_name, f"Error eliminando archivo de decisión {decision_file_name}: {e_rem}", "WARN")
            break 
        time.sleep(poll_interval)
    routing_data_to_write = None
    decision_type_for_report = "Desconocida"
    if user_decision_data:
        target_destinations = user_decision_data.get("target_destinations", ["LogDB"])
        routing_data_to_write = {
            "event_id": event_id, "target_destinations": target_destinations,
            "alert_payload_to_send": enriched_data, 
            "decision_type": f"Usuario: {user_decision_data.get('user_decision', 'N/A')}"
        }
        decision_type_for_report = f"Usuario ({user_decision_data.get('user_decision', 'N/A')})"
        logger(bot_name, f"Decisión del USUARIO para '{event_id}': Enviar a {', '.join(target_destinations)}")
    else:
        logger(bot_name, f"Timeout esperando decisión del usuario para '{event_id}'. Tomando decisión automática.")
        write_json_data(auto_decision_file_name, {"event_id": event_id, "decision_type": "timeout_auto"}, directory=DASHBOARD_DATA_DIR)
        logger(bot_name, f"Archivo de auto-decisión '{auto_decision_file_name}' creado en '{DASHBOARD_DATA_DIR}'.")
        routing_data_to_write = tomar_decision_automatica_por_timeout(event_id, enriched_data, "Timeout")
        decision_type_for_report = routing_data_to_write.get("decision_type", "Automática (Timeout)")
    if routing_data_to_write:
        add_to_html_report(bot_name, routing_data_to_write, f"Decisión táctica ({decision_type_for_report}).")
        write_json_data("routing_output.json", routing_data_to_write, directory=DATA_DIR) 
        logger(bot_name, "Proceso de decisión táctica completado.")
        return routing_data_to_write
    else:
        logger(bot_name, "Fallo al generar datos de ruteo después de la decisión táctica.", "ERROR")
        fallback_routing = {
            "event_id": event_id, "target_destinations": ["LogDB"],
            "alert_payload_to_send": enriched_data, "decision_type": "Fallo en Decisión"
        }
        write_json_data("routing_output.json", fallback_routing, directory=DATA_DIR)
        add_to_html_report(bot_name, fallback_routing, "Fallo en decisión, enviando solo a LogDB.")
        return fallback_routing

def tomar_decision_automatica_por_timeout(event_id, enriched_data, reason="Timeout"):
    bot_name = "BotDecisionTactica" 
    logger(bot_name, f"Tomando decisión AUTOMÁTICA para '{event_id}' debido a: {reason}")
    possible_heroes = ["Sonic", "Tails", "Knuckles"]
    destinations = set(["LogDB"])
    threat_level = enriched_data.get("threat_assessment", {}).get("initial_level", "bajo")
    urgency_level = enriched_data.get("urgency_level", "")
    nearby_heroes_from_enrichment = enriched_data.get("location_details", {}).get("known_nearby_heroes", [])
    if threat_level == "critico":
        destinations.update(["Sonic", "Tails", "Knuckles"]) 
        logger(bot_name, "AUTO: Amenaza crítica, notificando a todos los héroes principales.")
    elif threat_level == "alto":
        destinations.add("Sonic")
        if "Tails" in nearby_heroes_from_enrichment: destinations.add("Tails")
        logger(bot_name, f"AUTO: Amenaza alta, notificando a Sonic y Tails si está cerca ({'Sí' if 'Tails' in nearby_heroes_from_enrichment else 'No'}).")
    elif threat_level == "medio":
        if "Sonic" in nearby_heroes_from_enrichment: destinations.add("Sonic")
        elif "Tails" in nearby_heroes_from_enrichment: destinations.add("Tails")
        elif nearby_heroes_from_enrichment: destinations.add(nearby_heroes_from_enrichment[0]) 
        else: destinations.add(random.choice(possible_heroes[:2])) 
        logger(bot_name, f"AUTO: Amenaza media, notificando a héroes cercanos o uno al azar.")
    else: 
        logger(bot_name, "AUTO: Amenaza baja, solo registrando en LogDB.")
    routing_data = {
        "event_id": event_id, "target_destinations": list(destinations),
        "alert_payload_to_send": enriched_data, "decision_type": f"Automática ({reason})"
    }
    logger(bot_name, f"Decisión AUTOMÁTICA para '{event_id}': Enviar a {', '.join(list(destinations))}")
    return routing_data

# --- BotNotificador ---
# (SIN CAMBIOS)
def bot_notificador():
    bot_name = "BotNotificador"
    logger(bot_name, "Iniciando notificaciones...")
    routing_data = read_json_data("routing_output.json") 
    if not routing_data:
        logger(bot_name, "No hay datos de ruteo (routing_output.json). Abortando.", "ERROR"); return
    logger(bot_name, f"Notificando para evento ID: {routing_data['event_id']}")
    destinations_to_notify = routing_data.get("target_destinations", []) 
    payload_to_send = routing_data.get("alert_payload_to_send", {})  
    if not payload_to_send: 
        logger(bot_name, "Payload de alerta vacío. No se pueden enviar notificaciones.", "ERROR")
        return
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
            clean_url = str(url).strip() 
            if '[' in clean_url or ']' in clean_url: 
                logger(bot_name, f"ADVERTENCIA CRITICA: La URL para {dest_name} AÚN CONTIENE CORCHETES: '{clean_url}'. ¡CORREGIR config.json URGENTEMENTE!", "CRITICAL")
                status_message = f"URL inválida para {dest_name} (contiene corchetes)."
                notifications_summary.append(status_message)
                continue 
            try:
                logger(bot_name, f"Enviando a {dest_name} en {clean_url}...")
                response = requests.post(clean_url, json=payload_to_send, timeout=request_timeout)
                response.raise_for_status() 
                status_message = f"Enviado a {dest_name} OK (Status: {response.status_code})"
                logger(bot_name, status_message)
                sent_count += 1
            except requests.exceptions.InvalidSchema as e_schema: 
                status_message = f"Error de Esquema Inválido enviando a {dest_name} ({clean_url}): {e_schema}."
                logger(bot_name, status_message, "CRITICAL")
            except requests.exceptions.ConnectionError:
                status_message = f"Error de conexión con {dest_name} ({clean_url})"
                logger(bot_name, status_message, "ERROR")
            except requests.exceptions.Timeout:
                status_message = f"Timeout con {dest_name} ({clean_url})"
                logger(bot_name, status_message, "ERROR")
            except requests.exceptions.HTTPError as e_http:
                status_message = f"Error HTTP {e_http.response.status_code} con {dest_name} ({clean_url})"
                logger(bot_name, status_message, "ERROR")
            except Exception as e_generic:
                status_message = f"Error genérico enviando a {dest_name} ({clean_url}): {type(e_generic).__name__} - {e_generic}"
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
            if analysis_result is None: logger("BotMaestro", "BotAnalizador falló.");
            
            time.sleep(0.2)
            enriched_result = bot_enriquecedor()
            if enriched_result is None: logger("BotMaestro", "BotEnriquecedor falló.");
            
            time.sleep(0.2)
            decision_data = solicitar_decision_tactica_dashboard() 
            if decision_data is None: 
                logger("BotMaestro", "El proceso de decisión táctica falló o no produjo datos de ruteo. Saltando notificación.", "ERROR")
                end_html_report() 
                time.sleep(max_interval) 
                continue
            
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
        close_webdriver() 
        if CURRENT_EVENT_HTML_REPORT and os.path.exists(CURRENT_EVENT_HTML_REPORT):
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

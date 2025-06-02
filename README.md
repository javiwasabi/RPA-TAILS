# Hedgehog Alert System - Edición Juego Interactivo (Simulado en Python)

Este proyecto simula un sistema automatizado de monitorización y alerta de actividad enemiga (Badniks del Dr. Eggman), transformado en un **juego de estrategia interactivo**. Originalmente concebido con un enfoque de Automatización Robótica de Procesos (RPA), ha sido implementado completamente en Python con una interfaz web dinámica para la toma de decisiones.

El sistema presenta alertas generadas dinámicamente. El jugador, a través de un **Dashboard Táctico (aplicación Flask)**, debe analizar la situación y despachar a los héroes adecuados. El objetivo es desmantelar la operación de Eggman (reduciendo su HP a 0) antes de que el Pánico Global alcance su límite.

## Características Principales

* **Simulación de Flujo de Alertas:**
    * `BotMonitor`: Simula la recepción de datos de diversas fuentes. Puede usar **Selenium WebDriver con Microsoft Edge** para leer datos de archivos HTML locales o generar datos de eventos aleatoriamente.
    * `BotAnalizador`: Normaliza los datos brutos a un modelo canónico y calcula una puntuación de prioridad.
    * `BotEnriquecedor`: Añade información contextual crucial (zonas, héroes cercanos) utilizando una base de conocimiento.
    * `BotNotificador`: Envía las alertas finales a los destinos (endpoints simulados) según la decisión tomada.
* **Dashboard Táctico Interactivo (Flask):**
    * Interfaz de usuario web (`http://127.0.0.1:5005`) para visualizar alertas en tiempo real.
    * Permite al jugador tomar decisiones tácticas (qué héroes enviar).
    * Muestra un temporizador para la toma de decisiones, con un sistema de decisión automática por timeout.
    * Estilo dinámico que cambia según la zona de la alerta.
    * Botones de héroes condicionales según la disponibilidad (basado en `known_nearby_heroes`).
* **Mecánicas de Juego:**
    * **HP de la Base de Eggman:** El objetivo principal del jugador es reducir el HP de Eggman a 0. El daño infligido depende de la efectividad de la respuesta a las alertas.
    * **Nivel de Pánico Global:** Si este nivel llega a 100 debido a respuestas tardías o incorrectas, el jugador pierde.
    * **Pantallas de Victoria y Derrota:** Interfaz gráfica que indica el resultado final del juego.
* **Orquestación Centralizada (`bots.py`):**
    * Un script principal actúa como `BotMaestro`, gestionando el ciclo de vida de cada evento y el estado del juego.
* **Comunicación de Datos:**
    * Entre etapas del bot: Mediante archivos JSON temporales en `data/`.
    * Entre `bots.py` y el Dashboard: Mediante peticiones HTTP y archivos JSON en `data_dashboard/`.
* **Configuración Detallada (`config.json`):**
    * Permite ajustar el comportamiento de los bots, los parámetros del juego (HP inicial, pánico), las fuentes de Selenium, los timeouts del dashboard, etc.
* **Logging y Reportes:**
    * Registros detallados por cada módulo en la carpeta `logs/`.
    * Reportes HTML individuales por cada evento procesado en la carpeta `reports/`, visualizando el flujo de datos.
* **Endpoints de Destino Simulados (Flask):**
    * Pequeñas aplicaciones Flask (`endpoints/*.py`) que simulan los comunicadores de los héroes (Sonic, Tails, Knuckles) y una base de datos de logs (LogDB). Se ejecutan en puertos diferentes (5001-5004).
* **Interfaz Web Estilizada:**
    * Uso de CSS centralizado (`static/css/dashboard_style.css`) para una apariencia consistente.
    * Imágenes (`static/images/`) para mejorar la inmersión visual en el dashboard y las pantallas de resultado.
* **Arranque Automatizado de Endpoints:**
    * Script `run_endpoints.py` para lanzar automáticamente todos los servidores de endpoints en ventanas de PowerShell separadas (Windows).

## Tecnologías Utilizadas

* **Python 3.7+**
* **Flask**: Para el Dashboard Táctico y los endpoints simulados.
* **Selenium**: Para la simulación de extracción de datos web con Microsoft Edge.
* **Requests**: Para la comunicación HTTP entre `bots.py` y el dashboard/endpoints.
* **HTML, CSS, JavaScript**: Para el frontend del Dashboard Táctico.
* **WebDriver-Manager**: Para gestionar automáticamente el driver de Edge.

## Estructura del Proyecto (Simplificada)
RPA-TAILS/
|-- bots.py                     # Orquestador principal y lógica de los bots/juego
|-- dashboard_tactico_app.py    # Aplicación Flask para el dashboard interactivo
|-- run_endpoints.py            # Script para iniciar los endpoints (Windows)
|-- config.json                 # Configuración centralizada
|-- requirements.txt            # Dependencias de Python
|
|-- endpoints/                  # Scripts Flask para los héroes y LogDB
|   |-- sonic_app.py
|   |-- tails_app.py
|   |-- knuckles_app.py
|   |-- logdb_app.py
|
|-- templates/                  # Plantillas HTML para Flask
|   |-- dashboard_v2.html
|   |-- decision_made_v2.html
|   |-- victory.html
|   |-- game_over.html
|
|-- static/                     # Archivos estáticos (CSS, imágenes)
|   |-- css/
|   |   |-- dashboard_style.css
|   |-- images/
|       |-- eggman.png
|       |-- sonic.png
|       |-- tails.png
|       |-- knuckles.png
|       |-- victory.png
|       |-- game_over.png
|       |-- (otras imágenes necesarias)
|
|-- data/                       # Datos temporales del flujo de bots
|-- data_dashboard/             # Datos temporales de decisión del dashboard
|-- logs/                       # Archivos de log
|-- reports/                    # Reportes HTML de eventos
|
|-- fuente_*.html               # Archivos HTML para simulación con Selenium
|-- venv/                       # (Entorno virtual, opcional pero recomendado)
|-- README.md                   # Este archivo

## Requisitos Previos

* Python 3.7 o superior.
* `pip` (el gestor de paquetes de Python).
* Navegador **Microsoft Edge** instalado (para la funcionalidad de Selenium).
* (Opcional) Un editor de código como Visual Studio Code.

## Instalación y Configuración

1.  **Clonar o Descargar el Proyecto:**
    Obtén todos los archivos y carpetas del proyecto.

2.  **Navegar a la Carpeta del Proyecto:**
    Abre una terminal o PowerShell y navega al directorio raíz del proyecto (ej. `RPA-TAILS`).
    ```bash
    cd ruta/a/tu/RPA-TAILS
    ```

3.  **(Recomendado) Crear y Activar un Entorno Virtual:**
    ```bash
    python -m venv venv
    ```
    En Windows (PowerShell/CMD):
    ```powershell
    .\venv\Scripts\activate
    ```
    En macOS/Linux:
    ```bash
    source venv/bin/activate
    ```

4.  **Instalar Dependencias:**
    Asegúrate de que tu entorno virtual esté activado y luego ejecuta:
    ```bash
    pip install -r requirements.txt
    ```
    Esto instalará Flask, Requests, Selenium, WebDriver-Manager y cualquier otra dependencia necesaria.

5.  **Revisar `config.json`:**
    * Abre `config.json` y familiarízate con las opciones.
    * Si Selenium no encuentra Edge automáticamente, puedes especificar la ruta en `bot_monitor.edge_binary_path_override`.
    * Asegúrate de que los archivos HTML fuente para Selenium (listados en `selenium_html_sources`) existan en la raíz del proyecto.

6.  **Añadir Imágenes:**
    * Crea la carpeta `static/images/` si no existe.
    * Coloca las imágenes necesarias dentro: `eggman.png`, `sonic.png`, `tails.png`, `knuckles.png`, `victory.png`, `game_over.png`, `logdb.png`, `sonic_tails.png`, `all_heroes.png`, `timeout.png`. Asegúrate de que los nombres coincidan exactamente (minúsculas, extensión `.png`).

## Ejecución del Juego

Para jugar, necesitarás ejecutar tres scripts principales en terminales separadas. Asegúrate de haber activado tu entorno virtual en cada terminal donde ejecutes un script Python.

1.  **Terminal 1: Iniciar los Endpoints de Héroes/LogDB:**
    * Navega a la carpeta raíz del proyecto.
    * Ejecuta:
        ```bash
        python run_endpoints.py
        ```
    * Esto abrirá 4 nuevas ventanas de PowerShell, cada una corriendo un endpoint. Mantenlas abiertas.

2.  **Terminal 2: Iniciar el Dashboard Táctico:**
    * Abre una nueva terminal.
    * Navega a la carpeta raíz y activa el entorno virtual.
    * Ejecuta:
        ```bash
        python dashboard_tactico_app.py
        ```
    * Esto iniciará el servidor web para el dashboard. Mantenla abierta.

3.  **Terminal 3: Iniciar el Motor Principal del Juego:**
    * Abre otra nueva terminal.
    * Navega a la carpeta raíz y activa el entorno virtual.
    * Ejecuta:
        ```bash
        python bots.py
        ```
    * Esto iniciará la simulación y la lógica del juego.

4.  **Abrir el Dashboard en el Navegador:**
    * Abre tu navegador web (preferiblemente uno diferente al que podría usar Selenium, como Firefox o una instancia normal de Edge/Chrome) y ve a: `http://127.0.0.1:5005/`

## Cómo Jugar

* Observa las alertas que aparecen en el Dashboard Táctico.
* Analiza la descripción, ubicación, nivel de amenaza y héroes cercanos.
* Toma una decisión táctica haciendo clic en los botones de acción antes de que el temporizador llegue a cero.
* Tu objetivo es reducir el HP de la Base de Eggman a 0.
* Evita que el Nivel de Pánico Global llegue a 100.
* El juego termina cuando ganas o pierdes, mostrando la pantalla correspondiente. Para jugar de nuevo, haz clic en el botón y luego reinicia el script `bots.py`.

## Observar la Simulación

* **Consola de `bots.py`:** Muestra los logs del `BotMaestro`, el procesamiento de cada bot, los cambios en HP/Pánico y el resultado del juego.
* **Consola de `dashboard_tactico_app.py`:** Muestra los logs del servidor web Flask, incluyendo las solicitudes HTTP.
* **Consolas de los Endpoints (abiertas por `run_endpoints.py`):** Muestran las alertas JSON que reciben.
* **Navegador:** Es tu interfaz principal para interactuar con el juego.
* **Carpetas `data/`, `data_dashboard/`, `logs/`, `reports/`:** Contienen archivos generados durante la ejecución que pueden ser útiles para depuración o análisis.

## Detalles de Configuración (`config.json`)

El archivo `config.json` permite un alto grado de personalización:

* `bot_maestro`: Intervalos del ciclo principal, máximo de ciclos.
* `bot_monitor`: Activar/desactivar Selenium, lista de archivos HTML fuente, ruta al ejecutable de Edge, tiempo de visualización de Selenium.
* `dashboard_tactico`: URL del dashboard, endpoints específicos, timeout para decisiones del usuario, intervalos de sondeo.
* `bot_notificador`: Timeout para peticiones HTTP, URLs de los endpoints de los héroes/LogDB.
* `bot_enriquecedor`: La `knowledge_base_simulated` con detalles de zonas, héroes, amenazas comunes y clases CSS para el dashboard.
* `game_state`: Valores iniciales para el HP de Eggman, Pánico Global, y el límite de pánico para la derrota.

---

¡Espero que este README sea mucho más completo y útil!
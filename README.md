# Hedgehog Alert System - RPA Edition (Simulado en Python)

Este proyecto simula un sistema automatizado de monitorización y alerta de actividad enemiga (Badniks del Dr. Eggman) utilizando un enfoque de Automatización Robótica de Procesos (RPA) implementado completamente en Python.

El sistema consiste en una serie de "bots" simulados que procesan datos de fuentes simuladas, los analizan, enriquecen, rutean y finalmente notifican a destinos simulados (aplicaciones Flask).

## Características

*   **Bots Simulados:**
    *   `BotMonitor`: Simula la recepción de datos (puede usar Selenium para leer un HTML local o generar datos aleatorios).
    *   `BotAnalizador`: Normaliza los datos a un modelo canónico.
    *   `BotEnriquecedor`: Añade contexto a los datos.
    *   `BotRouter`: Decide a qué destino enviar la alerta.
    *   `BotNotificador`: Envía la alerta a los endpoints Flask.
*   **Orquestación:** Un `BotMaestro` (simulado en el bucle principal) coordina la ejecución de los bots.
*   **Comunicación de Datos:** Mediante archivos JSON temporales en la carpeta `data/`.
*   **Configuración:** Gestionada a través de un archivo `config.json`.
*   **Logging:** Registros detallados para cada bot en la carpeta `logs/`.
*   **Endpoints de Destino Simulados:** Aplicaciones Flask que representan los comunicadores de los héroes y una base de datos de logs.
*   **Demostración de Selenium:** El `BotMonitor` puede configurarse para leer datos de un archivo HTML local usando Selenium WebDriver.

## Requisitos Previos

*   Python 3.7+
*   Navegador Google Chrome instalado (para la funcionalidad de Selenium).
*   `pip` (el gestor de paquetes de Python).

## Configuración y Ejecución

1.  **Clonar/Descargar el Proyecto:**
    Obtén todos los archivos del proyecto (`bots.py`, `config.json`, `fuente_de_datos_simulada.html`, `requirements.txt`, y la carpeta `endpoints/` con sus scripts Flask).

2.  **Navegar a la Carpeta del Proyecto:**
    Abre una terminal o símbolo del sistema y navega al directorio raíz del proyecto `HedgehogAlertSystem/`.
    ```bash
    cd ruta/a/tu/HedgehogAlertSystem
    ```

3.  **(Recomendado) Crear y Activar un Entorno Virtual:**
    ```bash
    python -m venv venv
    # En Windows:
    .\venv\Scripts\activate
    # En macOS/Linux:
    source venv/bin/activate
    ```

4.  **Instalar Dependencias:**
    ```bash
    pip install -r requirements.txt
    ```
    Esto instalará Flask, Requests, Selenium y WebDriver-Manager.

5.  **Ejecutar los Endpoints de Destino Flask:**
    Abre **4 terminales separadas**. En cada una, navega a la carpeta del proyecto, activa el entorno virtual (si lo creaste) y ejecuta uno de los siguientes comandos:
    *   Terminal 1: `python endpoints/sonic_app.py`
    *   Terminal 2: `python endpoints/knuckles_app.py`
    *   Terminal 3: `python endpoints/tails_app.py`
    *   Terminal 4: `python endpoints/logdb_app.py`
    Deja estas 4 terminales corriendo.

6.  **Ejecutar el Sistema Principal de Bots:**
    Abre una **quinta terminal**. Navega a la carpeta del proyecto, activa el entorno virtual (si lo creaste) y ejecuta:
    ```bash
    python bots.py
    ```

7.  **Observar:**
    *   **Terminal de `bots.py`:** Verás los logs del `BotMaestro` y cada bot individual procesando los eventos. Si `use_selenium_source` está en `true` en `config.json`, verás a `BotMonitor` intentar usar Selenium.
    *   **Terminales de los Endpoints Flask:** Verás mensajes cuando reciban alertas del `BotNotificador`.
    *   **Carpeta `data/`:** Se crearán archivos JSON (`monitor_output.json`, etc.) con los datos intermedios.
    *   **Carpeta `logs/`:** Se crearán archivos de log (`BotMonitor.log`, `BotMaestro.log`, etc.) con el historial de ejecución.

## Configuración

*   El archivo `config.json` en la raíz del proyecto permite ajustar varios parámetros:
    *   Intervalos de procesamiento.
    *   Si el `BotMonitor` debe usar Selenium (`use_selenium_source`).
    *   URLs de los endpoints de notificación.
    *   La base de conocimiento simulada para el `BotEnriquecedor`.

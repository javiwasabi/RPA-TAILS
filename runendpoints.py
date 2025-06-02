# run_endpoints.py
import os
import time

# --- Lista de los scripts de endpoints que queremos ejecutar ---
# Cada uno se ejecutará en su propia ventana de PowerShell.
endpoint_scripts = [
    "endpoints/logdb_app.py",
    "endpoints/sonic_app.py",
    "endpoints/tails_app.py",
    "endpoints/knuckles_app.py"
]

# --- Comando para activar el entorno virtual ---
# Usamos la ruta relativa que nos proporcionaste.
activate_venv_command = ".\\venv\\Scripts\\activate"

print("--- Iniciando Servidores de Endpoints ---")
print(f"Se abrirán {len(endpoint_scripts)} ventanas de PowerShell.")

# Recorremos la lista de scripts para lanzar cada uno
for script in endpoint_scripts:
    
    # Mensaje que se mostrará en la nueva terminal
    title_message = f"Iniciando Endpoint: {script}"
    
    # Construimos el comando completo que se ejecutará en la nueva ventana de PowerShell
    # 1. 'start powershell': Abre una nueva ventana de PowerShell.
    # 2. '-NoExit': Evita que la ventana se cierre después de ejecutar el comando. ¡Crucial!
    # 3. '-Command "..."': La cadena de comandos a ejecutar.
    # 4. Usamos ';' para separar los comandos dentro de PowerShell.
    full_command = (
        f'start powershell -NoExit -Command "'
        f"Write-Host '{title_message}' -ForegroundColor Green; "
        f"{activate_venv_command}; "
        f"python {script}"
        f'"'
    )
    
    print(f"Lanzando: {script}...")
    
    # Ejecutamos el comando en el sistema operativo
    os.system(full_command)
    
    # Esperamos un segundo antes de lanzar el siguiente para no saturar el sistema
    time.sleep(1)

print("\n--- Todos los servidores de endpoints han sido lanzados en sus terminales. ---")
print("Puedes cerrar esta ventana si lo deseas.")
from flask import Flask, request
import json
import datetime

app = Flask(__name__)

def log_to_console(message):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [Tails Endpoint] {message}")

@app.route('/alert', methods=['POST'])
def recibir_alerta_tails():
    data = request.get_json()
    log_to_console(f"Alerta recibida: {json.dumps(data, ensure_ascii=False, indent=2)}")
    return "OK_TAILS", 200

if __name__ == "__main__":
    port = 5003
    log_to_console(f"Iniciando servidor Flask de Tails en http://127.0.0.1:{port}")
    app.run(port=port, debug=False)
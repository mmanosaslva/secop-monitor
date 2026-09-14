import http.server
import socketserver
import json
import os
import sys
import urllib.parse
from typing import Dict

# Add project root to sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Safe imports for dependencies that might be missing in local system python
try:
    from src.sources.secop import SecopDataSource
    from src.filters.engine import FilterEngine, load_config
    from src.config import SECOP_APP_TOKEN
    HAS_BACKEND_DEPS = True
except ModuleNotFoundError as e:
    HAS_BACKEND_DEPS = False
    print(f"[SECOP WebServer Warning] Dependencias locales no instaladas completamente ({e}). Usando modo interactivo directo.")


PORT = 8000
WEB_DIR = os.path.join(os.path.dirname(__file__), "web")
CONFIG_PATH = os.path.join(PROJECT_ROOT, "config", "client_config.json")


class SecopMonitorHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_DIR, **kwargs)

    def log_message(self, format, *args):
        # Clean logging format
        print(f"[SECOP WebServer] {self.address_string()} - {format % args}")

    def send_json_response(self, data: dict, status: int = 200):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.end_headers()

    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        path = parsed_path.path

        if path == "/api/secop/live":
            self.handle_live_secop()
        elif path == "/api/config":
            self.handle_get_config()
        elif path == "/api/stats":
            self.handle_get_stats()
        else:
            # Fallback to serving static SPA files
            super().do_GET()

    def do_POST(self):
        parsed_path = urllib.parse.urlparse(self.path)
        path = parsed_path.path

        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length) if content_length > 0 else b'{}'
        
        try:
            payload = json.loads(post_data.decode('utf-8'))
        except Exception:
            payload = {}

        if path == "/api/filter/test":
            self.handle_test_filter(payload)
        elif path == "/api/config":
            self.handle_save_config(payload)
        else:
            self.send_json_response({"error": "Endpoint not found"}, 404)

    def handle_live_secop(self):
        try:
            if HAS_BACKEND_DEPS:
                config = load_config(CONFIG_PATH)
                source = SecopDataSource(app_token=SECOP_APP_TOKEN)
                departments = config.get("departments", [])
                raw_processes = source.fetch_processes(departments=departments, modality="Mínima cuantía", max_results=50)

                engine = FilterEngine(config)
                results = []
                for p in raw_processes:
                    p["is_matched"] = engine.matches(p)
                    p["certifications"] = engine.detect_certifications(p)
                    results.append(p)
                self.send_json_response(results)
            else:
                # Standard library fetch directly from datos.gov.co API
                import urllib.request
                config = self._read_config_file()
                depts = ",".join(f"'{d}'" for d in config.get("departments", ["Atlantico", "Bolivar"]))
                url = f"https://www.datos.gov.co/resource/p6dx-8zbt.json?$where=departamento_entidad%20IN%20({urllib.parse.quote(depts)})%20AND%20estado_del_procedimiento='Publicado'&amp;$limit=30"
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=10) as response:
                    raw_data = json.loads(response.read().decode('utf-8'))
                
                results = []
                for r in raw_data:
                    results.append({
                        "id": r.get("id_del_proceso", "CO1.REQ.000"),
                        "entity_name": r.get("entidad", ""),
                        "department": r.get("departamento_entidad", ""),
                        "city": r.get("ciudad_entidad", ""),
                        "name": r.get("nombre_del_procedimiento", ""),
                        "description": r.get("descripci_n_del_procedimiento", ""),
                        "modality": r.get("modalidad_de_contratacion", "Mínima cuantía"),
                        "base_price": float(r.get("precio_base", 0) or 0),
                        "unspsc_code": r.get("codigo_principal_de_categoria", ""),
                        "url": r.get("urlproceso", {}).get("url", "") if isinstance(r.get("urlproceso"), dict) else str(r.get("urlproceso", "")),
                        "is_matched": True,
                        "certifications": {
                            "favorece_mujer_lider": "mujer" in (r.get("nombre_del_procedimiento", "") + r.get("descripci_n_del_procedimiento", "")).lower(),
                            "favorece_pyme": "pyme" in (r.get("nombre_del_procedimiento", "") + r.get("descripci_n_del_procedimiento", "")).lower(),
                            "requiere_equidad_genero": "genero" in (r.get("nombre_del_procedimiento", "") + r.get("descripci_n_del_procedimiento", "")).lower()
                        }
                    })
                self.send_json_response(results)
        except Exception as e:
            self.send_json_response({"error": str(e)}, 500)

    def _read_config_file(self):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    def handle_get_config(self):
        try:
            config = self._read_config_file()
            self.send_json_response(config)
        except Exception as e:
            self.send_json_response({"error": str(e)}, 500)

    def handle_save_config(self, payload: dict):
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            self.send_json_response({"status": "ok", "message": "Configuración guardada en client_config.json"})
        except Exception as e:
            self.send_json_response({"error": str(e)}, 500)

    def handle_test_filter(self, payload: dict):
        try:
            if HAS_BACKEND_DEPS:
                config = load_config(CONFIG_PATH)
                engine = FilterEngine(config)
                is_matched = engine.matches(payload)
                certs = engine.detect_certifications(payload)
            else:
                config = self._read_config_file()
                text = (payload.get("name", "") + " " + payload.get("description", "")).lower()
                is_matched = any(kw.lower() in text for kw in config.get("keywords", []))
                certs = {
                    "favorece_mujer_lider": "mujer" in text,
                    "favorece_pyme": "pyme" in text,
                    "requiere_equidad_genero": "genero" in text
                }
            self.send_json_response({
                "is_matched": is_matched,
                "certifications": certs,
                "process": payload
            })
        except Exception as e:
            self.send_json_response({"error": str(e)}, 500)

    def handle_get_stats(self):
        self.send_json_response({
            "status": "online",
            "db_connected": True,
            "secop_api": "https://www.datos.gov.co/resource/p6dx-8zbt.json",
            "cron_schedule": "00:45, 10:00, 13:30, 20:00 COT"
        })


def run_server(port=PORT):
    server_address = ('', port)
    httpd = socketserver.TCPServer(server_address, SecopMonitorHandler)
    print("===========================================================")
    print(f"[OK] SECOP Monitor Frontend SENA activo en http://localhost:{port}")
    print("===========================================================")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido.")
        httpd.server_close()


if __name__ == "__main__":
    run_server()

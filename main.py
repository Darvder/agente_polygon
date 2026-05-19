"""
main.py — Loop infinito para Railway
"""
import os
import asyncio
import subprocess
import logging
import base64
import urllib.request
import json as json_lib
from datetime import datetime


logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")
log = logging.getLogger("main")

# Evitar doble instancia
lock_file = "/tmp/agente.lock"
if os.path.exists(lock_file):
    log.info("⚠️ Ya hay una instancia corriendo. Saliendo.")
    exit(0)
open(lock_file, "w").close()

INTERVALO_CICLO = 25 * 60  # 4 minutos de espera DESPUÉS de cada ciclo


async def bootstrap_datos():
    """Descarga el estado actual de la rama 'datos' antes de iniciar para evitar sobreescrituras locales."""
    try:
        token = os.environ.get("GIT_TOKEN", "")
        repo  = os.environ.get("GITHUB_REPOSITORY", "")
        
        # Crear directorios si no existen
        os.makedirs("datos_polymarket/paper_trading", exist_ok=True)
        
        archivos = [
            ("datos_polymarket/paper_trading/libro_hibrido.csv",   "datos_polymarket/paper_trading/libro_hibrido.csv"),
            ("datos_polymarket/paper_trading/estado_hibrido.json", "datos_polymarket/paper_trading/estado_hibrido.json")
        ]
        
        for filepath, github_path in archivos:
            url = f"https://raw.githubusercontent.com/{repo}/datos/{github_path}"
            req = urllib.request.Request(url, headers={"Authorization": f"token {token}"} if token else {})
            try:
                with urllib.request.urlopen(req) as response:
                    with open(filepath, "wb") as f:
                        f.write(response.read())
                log.info(f"📥 [BOOTSTRAP] {github_path} descargado con éxito desde la rama 'datos'.")
            except Exception as e:
                log.info(f"ℹ️ [BOOTSTRAP] No se encontró {github_path} en la rama 'datos' (iniciando nuevo archivo).")
    except Exception as e:
        log.error(f"❌ Error crítico en el bootstrap de datos: {e}")

async def push_github():
    try:
        token = os.environ.get("GIT_TOKEN", "")
        repo  = os.environ.get("GITHUB_REPOSITORY", "")
        ts    = datetime.now().strftime("%Y-%m-%d %H:%M")

        archivos = [
            ("datos_polymarket/paper_trading/libro_hibrido.csv",   "datos_polymarket/paper_trading/libro_hibrido.csv"),
            ("datos_polymarket/paper_trading/estado_hibrido.json", "datos_polymarket/paper_trading/estado_hibrido.json"),
            ("datos_polymarket/dashboard_hibrido.html",            "datos_polymarket/dashboard_hibrido.html"),
            ("datos_polymarket/dashboard_hibrido.html",            "index.html"),
        ]

        for filepath, github_path in archivos:
            if not os.path.exists(filepath):
                continue

            with open(filepath, "rb") as f:
                contenido = base64.b64encode(f.read()).decode()

            # GET SHA desde rama datos
            url_get = f"https://api.github.com/repos/{repo}/contents/{github_path}?ref=datos"
            req_get = urllib.request.Request(url_get, headers={
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github.v3+json"
            })
            try:
                with urllib.request.urlopen(req_get) as r:
                    sha = json_lib.loads(r.read())["sha"]
            except:
                sha = None

            # PUT a rama datos
            url_put = f"https://api.github.com/repos/{repo}/contents/{github_path}"
            data = json_lib.dumps({
                "message": f"ciclo {ts}",
                "content": contenido,
                "branch":  "datos",
                **({"sha": sha} if sha else {})
            }).encode()

            req_put = urllib.request.Request(url_put, data=data, method="PUT", headers={
                "Authorization": f"token {token}",
                "Content-Type": "application/json"
            })
            try:
                urllib.request.urlopen(req_put)
                log.info(f"✅ {github_path} OK")
            except Exception as e:
                log.error(f"❌ {github_path}: {e}")

    except Exception as e:
        log.error(f"❌ GitHub API: {e}")


async def main():
    from agente_hibrido import ciclo

    log.info("🚀 Agente iniciado en Railway — loop continuo")

    await bootstrap_datos()

    while True:
        try:
            await ciclo()
            subprocess.run("python generar_dashboard_momentum.py", shell=True)
            await push_github()
        except Exception as e:
            log.error(f"❌ Error en ciclo: {e}")

        log.info(f"⏳ Esperando {INTERVALO_CICLO//60} min antes del próximo ciclo...")
        await asyncio.sleep(INTERVALO_CICLO)


if __name__ == "__main__":
    asyncio.run(main())

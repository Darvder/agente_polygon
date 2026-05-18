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

INTERVALO_CICLO     = 6 * 60   # 6 minutos
INTERVALO_DASHBOARD = 30 * 60  # 30 minutos

ultimo_dashboard = 0


async def push_github():
    try:
        token = os.environ.get("GIT_TOKEN", "")
        repo  = os.environ.get("GITHUB_REPOSITORY", "")

        archivos = [
            ("datos_polymarket/paper_trading/libro_hibrido.csv",    "datos_polymarket/paper_trading/libro_hibrido.csv"),
            ("datos_polymarket/paper_trading/estado_hibrido.json",  "datos_polymarket/paper_trading/estado_hibrido.json"),
            ("datos_polymarket/dashboard_hibrido.html",             "datos_polymarket/dashboard_hibrido.html"),
            ("datos_polymarket/dashboard_hibrido.html",             "index.html"),
        ]

        for filepath, github_path in archivos:
            if not os.path.exists(filepath):
                continue

            with open(filepath, "rb") as f:
                contenido = base64.b64encode(f.read()).decode()

            url = f"https://api.github.com/repos/{repo}/contents/{github_path}"

            # Obtener SHA actual
            req_get = urllib.request.Request(url, headers={
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github.v3+json"
            })
            try:
                with urllib.request.urlopen(req_get) as r:
                    sha = json_lib.loads(r.read())["sha"]
            except:
                sha = None

            # Subir archivo
            ts   = datetime.now().strftime("%Y-%m-%d %H:%M")
            data = json_lib.dumps({
                "message": f"ciclo {ts}",
                "content": contenido,
                **({"sha": sha} if sha else {})
            }).encode()

            req_put = urllib.request.Request(url, data=data, method="PUT", headers={
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
    global ultimo_dashboard

    from agente_hibrido import ciclo

    log.info("🚀 Agente iniciado en Railway — loop continuo")

    while True:
        inicio = asyncio.get_event_loop().time()

        try:
            await ciclo()
            await push_github()
        except Exception as e:
            log.error(f"❌ Error en ciclo: {e}")

        ahora = asyncio.get_event_loop().time()

        if ahora - ultimo_dashboard >= INTERVALO_DASHBOARD:
            try:
                subprocess.run("python generar_dashboard_momentum.py", shell=True)
                log.info("📊 Dashboard regenerado")
                ultimo_dashboard = ahora
            except:
                pass

        elapsed = asyncio.get_event_loop().time() - inicio
        espera  = max(0, INTERVALO_CICLO - elapsed)
        log.info(f"⏳ Próximo ciclo en {espera/60:.1f} min")
        await asyncio.sleep(espera)


if __name__ == "__main__":
    asyncio.run(main())

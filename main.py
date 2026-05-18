"""
main.py — Loop infinito para Railway
El agente corre cada 5 minutos sin overhead de GitHub Actions.
"""
import os
import asyncio
import subprocess
import logging
from datetime import datetime
import base64
import urllib.request
import json as json_lib

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")
log = logging.getLogger("main")

INTERVALO_CICLO   = 6 * 60   # 5 minutos
INTERVALO_DASHBOARD = 6 * 60  # regenerar dashboard cada 30 min # push a GitHub cada 1 hora

ultimo_dashboard = 0
ultimo_git       = 0

async def push_github():
    try:
        token = os.environ.get("GIT_TOKEN", "")
        repo  = os.environ.get("GITHUB_REPOSITORY", "")
        
        archivos = [
            "datos_polymarket/paper_trading/libro_hibrido.csv",
            "datos_polymarket/paper_trading/estado_hibrido.json",
            "datos_polymarket/dashboard_hibrido.html",
            ("datos_polymarket/dashboard_hibrido.html", "index.html"),
        ]

        for item in archivos:
            if isinstance(item, tuple):
                filepath, github_path = item
            else:
                filepath = github_path = item
            
            if not os.path.exists(filepath): continue
            
            with open(filepath, "rb") as f:
                contenido = base64.b64encode(f.read()).decode()
            
            url = f"https://api.github.com/repos/{repo}/contents/{github_path}"
    # ... resto igual
        
        for filepath in archivos:
            if not os.path.exists(filepath): continue
            
            with open(filepath, "rb") as f:
                contenido = base64.b64encode(f.read()).decode()
            
            # Obtener SHA actual del archivo en GitHub
            url = f"https://api.github.com/repos/{repo}/contents/{filepath}"
            req = urllib.request.Request(url, headers={
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github.v3+json"
            })
            try:
                with urllib.request.urlopen(req) as r:
                    sha = json_lib.loads(r.read())["sha"]
            except: sha = None
            
            # Push del archivo
            data = json_lib.dumps({
                "message": f"ciclo {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                "content": contenido,
                "sha": sha
            }).encode()
            
            req = urllib.request.Request(url, data=data, method="PUT", headers={
                "Authorization": f"token {token}",
                "Content-Type": "application/json"
            })
            urllib.request.urlopen(req)
            log.info(f"📦 {filepath} → GitHub OK")
            
    except Exception as e:
        log.error(f"❌ GitHub API: {e}")

async def main():
    log.info("📥 Estado cargado desde GitHub")
    global ultimo_dashboard, ultimo_git

    # Import aquí para que Railway cargue variables de entorno primero
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

        # Dashboard cada 30 min
        if ahora - ultimo_dashboard >= INTERVALO_DASHBOARD:
            try:
                subprocess.run("python generar_dashboard_momentum.py", shell=True)
                log.info("📊 Dashboard regenerado")
                ultimo_dashboard = ahora
            except: pass

        # Esperar hasta completar 5 min
        elapsed = asyncio.get_event_loop().time() - inicio
        espera = max(0, INTERVALO_CICLO - elapsed)
        log.info(f"⏳ Próximo ciclo en {espera/60:.1f} min")
        await asyncio.sleep(espera)

if __name__ == "__main__":
    asyncio.run(main())

"""
main.py — Loop infinito para Railway
El agente corre cada 5 minutos sin overhead de GitHub Actions.
"""
import asyncio
import subprocess
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")
log = logging.getLogger("main")

INTERVALO_CICLO   = 5 * 60   # 5 minutos
INTERVALO_DASHBOARD = 30 * 60  # regenerar dashboard cada 30 min
INTERVALO_GIT     = 60 * 60  # push a GitHub cada 1 hora

ultimo_dashboard = 0
ultimo_git       = 0

async def push_github():
    """Guarda resultados en GitHub para persistencia."""
    try:
        cmds = [
            "git config user.email bot@agente",
            "git config user.name 'Agente Bot'",
            "git add -A",
            f"git commit -m 'ciclo {datetime.now().strftime(\"%Y-%m-%d %H:%M\")}' || true",
            "git push"
        ]
        for cmd in cmds:
            subprocess.run(cmd, shell=True, capture_output=True)
        log.info("📦 GitHub: push completado")
    except Exception as e:
        log.error(f"❌ Git push falló: {e}")

async def main():
    global ultimo_dashboard, ultimo_git

    # Import aquí para que Railway cargue variables de entorno primero
    from agente_hibrido import ciclo

    log.info("🚀 Agente iniciado en Railway — loop continuo")

    while True:
        inicio = asyncio.get_event_loop().time()
        try:
            await ciclo()
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

        # Git push cada hora
        if ahora - ultimo_git >= INTERVALO_GIT:
            await push_github()
            ultimo_git = ahora

        # Esperar hasta completar 5 min
        elapsed = asyncio.get_event_loop().time() - inicio
        espera = max(0, INTERVALO_CICLO - elapsed)
        log.info(f"⏳ Próximo ciclo en {espera/60:.1f} min")
        await asyncio.sleep(espera)

if __name__ == "__main__":
    asyncio.run(main())

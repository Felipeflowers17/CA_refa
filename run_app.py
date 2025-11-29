# -*- coding: utf-8 -*-
import sys
import os
import subprocess
from pathlib import Path


if sys.platform == 'win32':
    local_app_data = os.getenv('LOCALAPPDATA')
    if local_app_data:
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(local_app_data, 'ms-playwright')
# -----------------------------------

# Configuración del Path para PyInstaller
if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys.executable).resolve().parent
    ROOT_DIR = Path(sys._MEIPASS)
else:
    BASE_DIR = Path(__file__).resolve().parent.parent
    ROOT_DIR = Path(__file__).resolve().parent

if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

from PySide6.QtWidgets import QApplication, QSplashScreen
from PySide6.QtCore import Qt, QCoreApplication
from PySide6.QtGui import QPixmap, QFont

from src.utils.logger import configurar_logger
from config.config import DATABASE_URL

from alembic.config import Config
from alembic.command import upgrade

logger = configurar_logger("run_app")

def check_playwright_browsers():
    """
    Verifica e instala los navegadores de Playwright si no existen.
    Crítico para el primer uso del .exe en un equipo limpio.
    """
    try:
        logger.info("Verificando entorno de navegadores Playwright...")
        # Solo forzamos la instalación si estamos en modo compilado (.exe)
        if getattr(sys, 'frozen', False):
            # Intentamos ejecutar la instalación pasando el entorno modificado
            subprocess.run(["playwright", "install", "chromium"], check=True, env=os.environ)
            logger.info("Navegadores verificados correctamente.")
    except Exception as e:
        logger.error(f"Error verificando navegadores: {e}")
        # No lanzamos error fatal para permitir que la app intente arrancar

def run_migrations():
    logger.info("Verificando estado de la base de datos...")
    try:
        if getattr(sys, 'frozen', False):
            alembic_cfg_path = ROOT_DIR / "alembic.ini"
            script_location = ROOT_DIR / "alembic"
        else:
            alembic_cfg_path = ROOT_DIR / "alembic.ini"
            script_location = ROOT_DIR / "alembic"

        if not alembic_cfg_path.exists():
            logger.error(f"No se encontró alembic.ini en: {alembic_cfg_path}")
            return

        alembic_cfg = Config(str(alembic_cfg_path))
        alembic_cfg.set_main_option("script_location", str(script_location))
        alembic_cfg.set_main_option("sqlalchemy.url", DATABASE_URL)

        upgrade(alembic_cfg, "head")
        logger.info("BD actualizada correctamente.")

    except Exception as e:
        logger.critical(f"Error al ejecutar migraciones: {e}", exc_info=True)

def main():
    app = QApplication(sys.argv)
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    app.setQuitOnLastWindowClosed(False)

    splash = QSplashScreen()
    splash.showMessage("Iniciando Monitor CA...", Qt.AlignBottom | Qt.AlignCenter, Qt.black)
    splash.show()
    
    QCoreApplication.processEvents()

    # 1. Verificar Navegadores (Playwright)
    splash.showMessage("Verificando componentes web...", Qt.AlignBottom | Qt.AlignCenter, Qt.black)
    QCoreApplication.processEvents()
    check_playwright_browsers()

    # 2. Ejecutar Migraciones (Base de Datos)
    splash.showMessage("Conectando a Base de Datos...", Qt.AlignBottom | Qt.AlignCenter, Qt.black)
    QCoreApplication.processEvents()
    run_migrations()
    
    splash.showMessage("Cargando Interfaz...", Qt.AlignBottom | Qt.AlignCenter, Qt.black)
    QCoreApplication.processEvents()

    # 3. Iniciar GUI Principal
    try:
        from src.gui.gui_main import MainWindow
        window = MainWindow()
        window.show()
        splash.finish(window)
        sys.exit(app.exec())
    except Exception as e:
        logger.critical(f"Error fatal no manejado en la GUI: {e}", exc_info=True)
        print(f"Error Fatal: {e}")

if __name__ == "__main__":
    main()
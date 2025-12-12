# -*- coding: utf-8 -*-
"""
Punto de Entrada de la Aplicación (Modo Producción).
"""
import sys
import os
import subprocess
from pathlib import Path

# run_app.py



# Configuración específica para Windows y Playwright en modo ejecutable
if sys.platform == 'win32':
    local_app_data = os.getenv('LOCALAPPDATA')
    if local_app_data:
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(local_app_data, 'ms-playwright')

# Rutas para PyInstaller (Detecta si corre como script o como .exe)
if getattr(sys, 'frozen', False):
    DIR_BASE = Path(sys.executable).resolve().parent
    DIR_RAIZ = Path(sys._MEIPASS)
else:
    DIR_BASE = Path(__file__).resolve().parent.parent
    DIR_RAIZ = Path(__file__).resolve().parent

if str(DIR_BASE) not in sys.path:
    sys.path.append(str(DIR_BASE))

from PySide6.QtWidgets import QApplication, QSplashScreen, QMessageBox
from PySide6.QtCore import Qt, QCoreApplication
from PySide6.QtGui import QFont

from src.utils.logger import configurar_logger
from config.config import DATABASE_URL

from alembic.config import Config
from alembic.command import upgrade

logger = configurar_logger("run_app")

# --- FUNCIONES AUXILIARES ---

def verificar_navegadores_playwright():
    """
    Verifica e instala los navegadores de Playwright si no existen.
    Silencioso en producción a menos que haya error crítico.
    """
    try:
        logger.info("Verificando entorno de navegadores Playwright...")
        # Solo forzamos la instalación si estamos en modo compilado (.exe)
        if getattr(sys, 'frozen', False):
            subprocess.run(["playwright", "install", "chromium"], check=True, env=os.environ)
            logger.info("Navegadores verificados correctamente.")
    except Exception as e:
        logger.error(f"Error verificando navegadores: {e}")
        # No lanzamos error fatal para permitir que la app intente arrancar

def ejecutar_migraciones_bd():
    """Ejecuta Alembic para asegurar que la BD tenga las tablas al día."""
    logger.info("Verificando esquema de base de datos...")
    try:
        archivo_alembic = DIR_RAIZ / "alembic.ini"
        ubicacion_scripts = DIR_RAIZ / "alembic"

        if not archivo_alembic.exists():
            logger.error(f"No se encontró configuración de Alembic en: {archivo_alembic}")
            return

        cfg_alembic = Config(str(archivo_alembic))
        cfg_alembic.set_main_option("script_location", str(ubicacion_scripts))
        cfg_alembic.set_main_option("sqlalchemy.url", DATABASE_URL)

        upgrade(cfg_alembic, "head")
        logger.info("Base de datos sincronizada correctamente.")

    except Exception as e:
        logger.critical(f"Error fatal al ejecutar migraciones: {e}", exc_info=True)


# --- MAIN PRINCIPAL ---

def main():
    app = QApplication(sys.argv)
    

    font = QFont("Segoe UI", 10)
    app.setFont(font)
    app.setQuitOnLastWindowClosed(False)

    # 1. Mostrar Pantalla de Carga 
    splash = QSplashScreen()
    splash.showMessage("Iniciando Monitor de Compras...", Qt.AlignBottom | Qt.AlignCenter, Qt.black)
    splash.show()
    
    # Procesa eventos para asegurar que la imagen se pinte
    QCoreApplication.processEvents()

    # 2. Tareas de Inicialización (Actualizando el mensaje del Splash)
    splash.showMessage("Verificando componentes web...", Qt.AlignBottom | Qt.AlignCenter, Qt.black)
    QCoreApplication.processEvents()
    verificar_navegadores_playwright()

    splash.showMessage("Conectando a Base de Datos...", Qt.AlignBottom | Qt.AlignCenter, Qt.black)
    QCoreApplication.processEvents()
    ejecutar_migraciones_bd()
    
    splash.showMessage("Cargando Interfaz...", Qt.AlignBottom | Qt.AlignCenter, Qt.black)
    QCoreApplication.processEvents()

    # 3. Iniciar GUI Principal
    try:
        from src.gui.gui_main import MainWindow
        ventana = MainWindow()
        ventana.show()
        
        # Cierra el splash cuando la ventana principal aparece
        splash.finish(ventana)
        
        sys.exit(app.exec())
        
    except Exception as e:
        logger.critical(f"Error fatal no manejado en la GUI: {e}", exc_info=True)
        # En caso de error catastrófico que impida abrir la ventana, mostramos un mensaje nativo
        QMessageBox.critical(None, "Error Fatal", f"La aplicación no pudo iniciarse.\nRevise los logs.\nError: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
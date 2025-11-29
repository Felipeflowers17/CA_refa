# -*- coding: utf-8 -*-
import os
import sys  
from dotenv import load_dotenv
from pathlib import Path

# Detección de ruta base (funciona tanto en desarrollo como compilado .exe)
if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent.parent

# Carga de variables de entorno
env_path = BASE_DIR / ".env"
# CORRECCIÓN: Usar utf-8 para evitar errores con caracteres especiales en contraseñas o rutas
load_dotenv(env_path, encoding="utf-8")

# --- Base de Datos ---
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print(f"ADVERTENCIA: DATABASE_URL no encontrada en {env_path}")

# --- Constantes de URLs ---
URL_BASE_WEB = "https://buscador.mercadopublico.cl"
URL_BASE_API = "https://api.buscador.mercadopublico.cl"

# --- Configuración de Red (Scraping) ---
TIMEOUT_REQUESTS = 30      
DELAY_ENTRE_PAGINAS = 1    
MAX_RETRIES = 3            
DELAY_RETRY = 5            

# CORRECCIÓN LOGICA HEADLESS:
# Si en el .env dice HEADLESS=True, queremos que MODO_HEADLESS sea True.
# Default: True (Oculto) para producción, cambiar a False para depurar.
_headless_env = os.getenv('HEADLESS', 'True').lower()
MODO_HEADLESS = _headless_env == 'true'

# Seguridad: API Key (Idealmente no vacía)
_API_KEY = os.getenv('MERCADOPUBLICO_API_KEY', '')
HEADERS_API = {
    'X-Api-Key': _API_KEY
}

# --- Constantes de Negocio ---

# Umbrales para filtrado rápido en DB
UMBRAL_FASE_1 = 5
UMBRAL_FINAL_RELEVANTE = 10

# Puntajes Globales (Hardcoded)
# El resto de puntajes (keywords, organismos) ahora vienen de la BD.
# Este se mantiene aquí porque es una regla de negocio fija del sistema.
PUNTOS_SEGUNDO_LLAMADO = 20
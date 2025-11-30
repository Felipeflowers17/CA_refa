# -*- coding: utf-8 -*-
"""
Variables de Entorno y Constantes Globales.
"""
import os
import sys  
from dotenv import load_dotenv
from pathlib import Path

# Detección inteligente de la ruta base 
if getattr(sys, 'frozen', False):
    DIR_BASE = Path(sys.executable).resolve().parent
else:
    DIR_BASE = Path(__file__).resolve().parent.parent

# Carga de variables de entorno (.env)
ruta_env = DIR_BASE / ".env"
load_dotenv(ruta_env, encoding="utf-8")

# --- Base de Datos ---
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print(f"ADVERTENCIA CRÍTICA: DATABASE_URL no encontrada en {ruta_env}")

# --- URLs Externas ---
URL_BASE_WEB = "https://buscador.mercadopublico.cl"
URL_BASE_API = "https://api.buscador.mercadopublico.cl"

# --- Configuración de Scraping ---
TIMEOUT_PETICIONES = 30      
RETARDO_PAGINAS = 1    
MAX_REINTENTOS = 3            

# Configuración Headless (Navegador oculto)
_headless_env = os.getenv('HEADLESS', 'True').lower()
MODO_HEADLESS = _headless_env == 'true'

# API Key (Opcional, para headers)
_API_KEY = os.getenv('MERCADOPUBLICO_API_KEY', '')
HEADERS_API = {
    'X-Api-Key': _API_KEY
}

# --- Constantes de Negocio ---
# Puntaje adicional fijo por regla de negocio
PUNTOS_SEGUNDO_LLAMADO = 5
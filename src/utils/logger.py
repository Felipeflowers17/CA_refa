# -*- coding: utf-8 -*-
"""
Configuración centralizada del Logger.

Proporciona una función 'configurar_logger' para obtener una instancia
estandarizada de logging, asegurando trazabilidad en archivos y consola.
"""

import logging
import sys
from pathlib import Path

# Directorio de logs (../.. para salir de src/utils)
DIR_LOGS = Path(__file__).resolve().parents[2] / "data" / "logs"
DIR_LOGS.mkdir(parents=True, exist_ok=True)

FORMATO_LOG = "%(asctime)s - %(levelname)-8s - %(name)-15s - %(message)s"

# Configuración base (Archivo)
logging.basicConfig(
    level=logging.DEBUG,
    format=FORMATO_LOG,
    filename=DIR_LOGS / "app.log",
    filemode="a",
    encoding="utf-8",
)

# Configuración consola (Solo INFO o superior para no saturar)
handler_consola = logging.StreamHandler(sys.stdout)
handler_consola.setLevel(logging.INFO)
handler_consola.setFormatter(logging.Formatter(FORMATO_LOG))

logger_raiz = logging.getLogger()
if not any(isinstance(h, logging.StreamHandler) for h in logger_raiz.handlers):
    logger_raiz.addHandler(handler_consola)

def configurar_logger(nombre_modulo: str) -> logging.Logger:
    """Retorna un logger configurado para el módulo solicitado."""
    return logging.getLogger(nombre_modulo)
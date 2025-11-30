# -*- coding: utf-8 -*-
"""
Manejador de Respuestas API.

Contiene funciones utilitarias puras para analizar y extraer datos
de las respuestas JSON crudas del portal de Mercado Público.
"""
from typing import List, Dict, Any
from src.utils.logger import configurar_logger

logger = configurar_logger(__name__)

def validar_respuesta_api(datos: Dict[str, Any]) -> bool: 
    """
    Verifica que el JSON recibido tenga la estructura mínima esperada.
    Retorna True si es válido, False si está incompleto o corrupto.
    """
    try:
        if not datos:
            return False
        # Verificación: La API suele devolver 'payload' y dentro 'resultados'
        if not datos.get('payload'):
            return False
        if 'resultados' not in datos['payload']:
            return False
        return True
    except Exception:
        return False

def extraer_resultados_lista(datos_json: Dict[str, Any]) -> List[Dict]: 
    """
    Extrae la lista de licitaciones (items) del payload.
    Retorna una lista vacía si falla la extracción.
    """
    try:
        return datos_json['payload'].get('resultados', [])
    except Exception:
        return []

def extraer_metadata_paginacion(datos_json: Dict[str, Any]) -> Dict[str, int]: 
    """
    Extrae los contadores de paginación para saber cuántas páginas recorrer.
    Retorna un diccionario con 'total_resultados' y 'total_paginas'.
    """
    default = {'total_resultados': 0, 'total_paginas': 0}
    try:
        payload = datos_json.get('payload', {})
        return {
            'total_resultados': payload.get('resultCount', 0),
            'total_paginas': payload.get('pageCount', 0)
        }
    except Exception:
        return default
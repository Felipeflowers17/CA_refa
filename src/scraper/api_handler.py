# -*- coding: utf-8 -*-
from typing import List, Dict, Any
from src.utils.logger import configurar_logger

logger = configurar_logger(__name__)

def validar_respuesta_api(datos: Dict[str, Any]) -> bool: 
    """Verifica que el JSON tenga la estructura mínima esperada."""
    try:
        # Verificación: solo nos importa que tenga payload y resultados
        if not datos.get('payload'):
            return False
        if 'resultados' not in datos['payload']:
            return False
        return True
    except Exception:
        return False

def extraer_resultados(datos_json: Dict[str, Any]) -> List[Dict]: 
    """Devuelve la lista de compras o lista vacía si falla."""
    try:
        return datos_json['payload'].get('resultados', [])
    except Exception:
        return []

def extraer_metadata_paginacion(datos_json: Dict[str, Any]) -> Dict[str, int]: 
    """Devuelve contadores de paginación."""
    default = {'resultCount': 0, 'pageCount': 0}
    try:
        payload = datos_json.get('payload', {})
        return {
            'resultCount': payload.get('resultCount', 0),
            'pageCount': payload.get('pageCount', 0)
        }
    except Exception:
        return default
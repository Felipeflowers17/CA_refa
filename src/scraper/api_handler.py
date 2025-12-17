# -*- coding: utf-8 -*-
"""
Manejador de Respuestas API.

Contiene funciones utilitarias puras para analizar y extraer datos
de las respuestas JSON crudas del portal de Mercado Público.
"""
from typing import List, Dict, Any
from src.logic.schemas import LicitacionDetalleSchema
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
    
def normalizar_datos_ficha(payload: Dict) -> LicitacionDetalleSchema:
    """
    Extrae datos del JSON crudo e instancia un esquema validado por Pydantic.
    """
    # 1. Lógica de extracción (se mantiene igual para preparar los datos)
    nombre_organismo = ""
    info_inst = payload.get('informacion_institucion')
    if isinstance(info_inst, dict):
        nombre_organismo = info_inst.get('organismo_comprador', "")
    
    if not nombre_organismo:
        comprador_raw = payload.get('Comprador')
        if isinstance(comprador_raw, dict):
            nombre_organismo = comprador_raw.get('NombreOrganismo', "")
        elif isinstance(comprador_raw, str):
            nombre_organismo = comprador_raw

    estado_texto = payload.get('estado')
    if not estado_texto:
        adj = payload.get('Adjudicacion')
        if adj:
             if isinstance(adj, list) and len(adj) > 0:
                 estado_texto = "Adjudicada"
             elif isinstance(adj, dict) and adj.get('url_acta'):
                 estado_texto = "Adjudicada"
        elif payload.get('motivo_desierta') or estado_texto == 'Desierta':
            estado_texto = "Desierta"

    # 2. Retorno Seguro: Pydantic validará tipos y limpiará el monto aquí
    return LicitacionDetalleSchema(
        descripcion=payload.get('descripcion'),
        direccion_entrega=payload.get('direccion_entrega'),
        fecha_cierre_p1=payload.get('fecha_cierre_primer_llamado'),
        fecha_cierre_p2=payload.get('fecha_cierre_segundo_llamado'),
        productos_solicitados=payload.get('productos_solicitados', []),
        estado=estado_texto,
        cantidad_provedores_cotizando=payload.get('cantidad_provedores_cotizando'),
        estado_convocatoria=payload.get('estado_convocatoria'),
        plazo_entrega=payload.get('plazo_entrega'),
        organismo_nombre=nombre_organismo,
        monto_estimado=payload.get('presupuesto_estimado'),
        fecha_publicacion=payload.get('fecha_publicacion')
    )
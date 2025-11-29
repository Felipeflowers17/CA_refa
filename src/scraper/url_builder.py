# -*- coding: utf-8 -*-
from typing import Dict, Optional
from config.config import URL_BASE_WEB, URL_BASE_API 

def construir_url_listado(numero_pagina: int = 1, filtros: Optional[Dict] = None):
    """Construye URL para navegador web"""
    parametros = {
        'status': 2,
        'order_by': 'recent',
        'page_number': numero_pagina,
        'region': 'all' 
    }
    if filtros: 
        # Filtros de fecha sobrescriben si es necesario
        parametros.update(filtros)
    
    string_parametros = '&'.join([f"{k}={v}" for k, v in parametros.items()])
    return f"{URL_BASE_WEB}/compra-agil?{string_parametros}"

def construir_url_api_listado(numero_pagina: int = 1, filtros: Optional[Dict] = None):
    """Construye URL para API JSON (SIN region=all forzado)."""
    parametros = {
        'status': 2,
        'order_by': 'recent',
        'page_number': numero_pagina
    }
    if filtros: 
        parametros.update(filtros)
    
    # IMPORTANTE: No agregamos 'region' aquí para evitar conflictos con fechas en la API
    
    string_parametros = '&'.join([f"{k}={v}" for k, v in parametros.items()])
    return f"{URL_BASE_API}/compra-agil?{string_parametros}"

def construir_url_ficha(codigo_compra: str):
    return f"{URL_BASE_WEB}/ficha?code={codigo_compra}"

def construir_url_api_ficha(codigo_compra: str):
    return f"{URL_BASE_API}/compra-agil?action=ficha&code={codigo_compra}"
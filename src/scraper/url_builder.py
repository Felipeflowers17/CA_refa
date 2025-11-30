# -*- coding: utf-8 -*-
"""
Constructor de URLs.

Centraliza la lógica para generar los enlaces tanto para el navegador web
como para las peticiones a la API interna.
"""
from typing import Dict, Optional
from config.config import URL_BASE_WEB, URL_BASE_API 

def construir_url_web_listado(numero_pagina: int = 1, filtros: Optional[Dict] = None) -> str:
    """Construye la URL visible para el navegador."""
    parametros = {
        'status': 2,        # 2 suele indicar licitaciones abiertas
        'order_by': 'recent',
        'page_number': numero_pagina,
        'region': 'all'     # Forzar todas las regiones
    }
    if filtros: 
        # Los filtros de fecha (date_from, date_to) se añaden aquí
        parametros.update(filtros)
    
    string_parametros = '&'.join([f"{k}={v}" for k, v in parametros.items()])
    return f"{URL_BASE_WEB}/compra-agil?{string_parametros}"

def construir_url_api_listado(numero_pagina: int = 1, filtros: Optional[Dict] = None) -> str:
    """
    Construye la URL para consumir la API JSON.
    NOTA: No se fuerza 'region=all' aquí para evitar conflictos conocidos con filtros de fecha en la API.
    """
    parametros = {
        'status': 2,
        'order_by': 'recent',
        'page_number': numero_pagina
    }
    if filtros: 
        parametros.update(filtros)
    
    string_parametros = '&'.join([f"{k}={v}" for k, v in parametros.items()])
    return f"{URL_BASE_API}/compra-agil?{string_parametros}"

def construir_url_web_ficha(codigo_compra: str) -> str:
    """Genera el enlace directo a la ficha web pública."""
    return f"{URL_BASE_WEB}/ficha?code={codigo_compra}"

def construir_url_api_ficha(codigo_compra: str) -> str:
    """Genera el enlace al endpoint de detalles (Fase 2) de una compra específica."""
    return f"{URL_BASE_API}/compra-agil?action=ficha&code={codigo_compra}"
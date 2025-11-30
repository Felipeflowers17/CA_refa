# -*- coding: utf-8 -*-
"""
Excepciones Personalizadas del Dominio.

Define errores específicos para facilitar la depuración y el manejo
de fallos en la interfaz gráfica.
"""

class ErrorEtl(Exception):
    """Clase base para todos los errores del proceso ETL."""
    pass

class ErrorScrapingFase1(ErrorEtl):
    """Fallo durante la obtención del listado masivo (Fase 1)."""
    pass

class ErrorCargaBD(ErrorEtl):
    """Fallo durante la inserción/actualización en base de datos."""
    pass

class ErrorTransformacionBD(ErrorEtl):
    """Fallo durante el cálculo de puntajes o transformación de datos."""
    pass

class ErrorScrapingFase2(ErrorEtl):
    """Fallo durante la extracción de detalle de una ficha (Fase 2)."""
    pass

class ErrorRecalculo(ErrorEtl):
    """Fallo durante el proceso manual de recálculo de puntajes."""
    pass

class ErrorSaludScraper(Exception):
    """Fallo en la verificación de conectividad o sesión del scraper."""
    pass
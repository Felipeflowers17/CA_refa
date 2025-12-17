# -*- coding: utf-8 -*-
"""
Servicio de Scraping (Extracción Web).

Implementa una arquitectura híbrida para máxima eficiencia:
1. Playwright: Se usa brevemente para simular un usuario real y capturar tokens de sesión (Auth).
2. Requests: Se usa para la descarga masiva de datos usando los tokens capturados.
"""
import time
import requests 
from playwright.sync_api import sync_playwright, Playwright
from typing import Optional, Dict, Callable, List, Any

from src.utils.logger import configurar_logger
from . import api_handler as manejador_api
from . import url_builder as constructor_url
from config.config import MODO_HEADLESS, HEADERS_API

logger = configurar_logger(__name__)

class ServicioScraper:
    def __init__(self):
        logger.info("ServicioScraper inicializado.")
        # Almacenamiento volátil de credenciales
        self.headers_sesion = {} 
        self.cookies_sesion = {}

    def _capturar_credenciales_playwright(self, p: Playwright, callback_progreso: Callable[[str], None]):
        """
        Lanza un navegador real (Chrome/Chromium) para navegar al sitio,
        interceptar el tráfico de red y obtener el token de autorización válido.
        """
        logger.info(f"Iniciando captura de credenciales (Headless={MODO_HEADLESS})...")
        if callback_progreso: 
            callback_progreso("Obteniendo token de acceso seguro...")
        
        # Argumentos para evitar detección de bot
        args_navegador = ["--disable-blink-features=AutomationControlled", "--no-sandbox"]
        
        try:
            # Intentar usar Chrome instalado si es posible
            browser = p.chromium.launch(channel="chrome", headless=MODO_HEADLESS, args=args_navegador)
        except:
            # Fallback a Chromium incluido en Playwright
            browser = p.chromium.launch(headless=MODO_HEADLESS, args=args_navegador)
        
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        )
        
        page = context.new_page()
        credenciales_temp = {}

        # Listener de tráfico de red
        def interceptar_peticion(request):
            if "api.buscador" in request.url:
                headers = request.headers
                if "authorization" in headers: 
                    credenciales_temp['authorization'] = headers['authorization']
                if "x-api-key" in headers: 
                    credenciales_temp['x-api-key'] = headers['x-api-key']

        page.on("request", interceptar_peticion)

        try:
            # Navegar al sitio
            page.goto("https://buscador.mercadopublico.cl/compra-agil", wait_until="commit", timeout=45000)
            
            # Espera activa inteligente hasta capturar headers
            for _ in range(15):
                if "authorization" in credenciales_temp: 
                    break
                time.sleep(1)
                
            # Si aún no carga, intentamos forzar una interacción
            if "authorization" not in credenciales_temp:
                try: 
                    page.get_by_role("button", name="Buscar").click(timeout=2000)
                except: 
                    pass
                time.sleep(3)

            if "authorization" not in credenciales_temp:
                raise Exception("No se pudo interceptar el token de autorización.")

            # Guardamos headers definitivos para uso con requests
            self.headers_sesion = {
                'authorization': credenciales_temp['authorization'],
                'x-api-key': credenciales_temp.get('x-api-key', ''),
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                'accept': 'application/json',
                'referer': 'https://buscador.mercadopublico.cl/'
            }
            return None 

        except Exception as e:
            logger.error(f"Error crítico obteniendo credenciales: {e}")
            raise e
        finally:
            browser.close()

    def verificar_sesion(self, callback_progreso=None):
        """Método público para refrescar la sesión si los headers están vacíos."""
        if not self.headers_sesion:
            self.refrescar_sesion_completa(callback_progreso)

    def refrescar_sesion_completa(self, callback_progreso: Callable[[str], None]):
        """Fuerza un ciclo de Playwright para renovar tokens."""
        with sync_playwright() as p:
            self._capturar_credenciales_playwright(p, callback_progreso)

    def ejecutar_scraper_listado(self, callback_progreso: Callable[[str], None], filtros: Optional[Dict] = None, max_paginas: Optional[int] = None) -> List[Dict]:
        """
        Fase 1: Descarga masiva de listados.
        Utiliza 'requests' con los tokens capturados para iterar páginas rápidamente.
        """
        logger.info(f"INICIANDO FASE 1. Filtros activos: {filtros}")
        
        # 1. Autenticación (si es necesaria)
        if not self.headers_sesion:
            with sync_playwright() as p:
                self._capturar_credenciales_playwright(p, callback_progreso)
        
        todas_las_compras = []
        pagina_actual = 1
        total_paginas_estimado = 1
        
        # Sesión HTTP persistente para reutilizar conexión TCP (Keep-Alive)
        sesion_http = requests.Session()
        sesion_http.headers.update(self.headers_sesion)

        try:
            while True:
                # Condiciones de salida
                if max_paginas and pagina_actual > max_paginas: 
                    break
                if total_paginas_estimado > 0 and pagina_actual > total_paginas_estimado: 
                    break
                if pagina_actual > 600: # Límite de seguridad
                    break 

                if callback_progreso: 
                    callback_progreso(f"Descargando página {pagina_actual}...")
                
                url = constructor_url.construir_url_api_listado(pagina_actual, filtros)
                
                # Petición HTTP rápida
                resp = sesion_http.get(url, timeout=15)
                
                if resp.status_code != 200:
                    logger.warning(f"Error HTTP {resp.status_code} leyendo página {pagina_actual}")
                    # Si falla por 401/403, podría ser token vencido, pero por simplicidad abortamos el loop
                    break
                
                datos_json = resp.json()
                meta = manejador_api.extraer_metadata_paginacion(datos_json)
                items = manejador_api.extraer_resultados_lista(datos_json)

                # Actualizar total de páginas solo en la primera vuelta
                if pagina_actual == 1:
                    total_paginas_estimado = meta.get('total_paginas', 0)
                    if total_paginas_estimado == 0: 
                        break
                
                if not items: 
                    break

                todas_las_compras.extend(items)
                pagina_actual += 1
                
                # Pausa de cortesía para no saturar el servidor
                time.sleep(0.5)

        except Exception as e:
            logger.error(f"Excepción durante scraping de listado: {e}")
            # Retornamos lo que hayamos capturado hasta el error
            
        # Deduplicación de seguridad (por código ID)
        unicas = {c.get('codigo', c.get('id')): c for c in todas_las_compras}
        return list(unicas.values())

    def extraer_detalle_api(self, _, codigo_ca: str, callback_progreso: Callable[[str], None] = None) -> Optional[Dict]:
        url_api = constructor_url.construir_url_api_ficha(codigo_ca)
        
        try:
            headers = self.headers_sesion or HEADERS_API
            resp = requests.get(url_api, headers=headers, timeout=10)

            if resp.status_code != 200:
                return None
            
            datos = resp.json()
        except Exception:
            return None

        if datos and datos.get('success') == 'OK' and datos.get('payload'):
            return manejador_api.normalizar_datos_ficha(datos['payload'])
            
        return None
# -*- coding: utf-8 -*-
import time
import random
import requests # Mucho más rápido que Playwright para peticiones simples
from playwright.sync_api import sync_playwright, Playwright, Page
from typing import Optional, Dict, Callable, List, Any

from src.utils.logger import configurar_logger
from . import api_handler
from .url_builder import construir_url_api_listado, construir_url_api_ficha
from config.config import MODO_HEADLESS, MAX_RETRIES, DELAY_RETRY, HEADERS_API

logger = configurar_logger(__name__)

class ScraperService:
    def __init__(self):
        logger.info("ScraperService inicializado.")
        self.headers_sesion = {} 
        self.cookies_sesion = {}

    def _obtener_credenciales(self, p: Playwright, progress_callback: Callable[[str], None]):
        """Inicia navegador real para capturar tokens de sesión válidos."""
        logger.info(f"Iniciando navegador (Headless={MODO_HEADLESS})...")
        if progress_callback: progress_callback("Obteniendo token de acceso...")
        
        args = ["--disable-blink-features=AutomationControlled", "--no-sandbox"]
        
        try:
            browser = p.chromium.launch(channel="chrome", headless=MODO_HEADLESS, args=args)
        except:
            browser = p.chromium.launch(headless=MODO_HEADLESS, args=args)
        
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        )
        
        page = context.new_page()
        headers_capturados = {}

        def interceptar_request(request):
            if "api.buscador" in request.url:
                h = request.headers
                if "authorization" in h: headers_capturados['authorization'] = h['authorization']
                if "x-api-key" in h: headers_capturados['x-api-key'] = h['x-api-key']

        page.on("request", interceptar_request)

        try:
            page.goto("https://buscador.mercadopublico.cl/compra-agil", wait_until="commit", timeout=45000)
            
            # Espera activa inteligente
            for i in range(15):
                if "authorization" in headers_capturados: break
                time.sleep(1)
                
            if "authorization" not in headers_capturados:
                # Intento de forzar carga
                try: page.get_by_role("button", name="Buscar").click(timeout=2000)
                except: pass
                time.sleep(3)

            if "authorization" not in headers_capturados:
                raise Exception("Token no encontrado tras espera.")

            self.headers_sesion = {
                'authorization': headers_capturados['authorization'],
                'x-api-key': headers_capturados.get('x-api-key', ''),
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                'accept': 'application/json',
                'referer': 'https://buscador.mercadopublico.cl/'
            }
            return None 

        except Exception as e:
            logger.error(f"Error credenciales: {e}")
            raise e
        finally:
            browser.close()

    def check_session(self, callback=None):
        """Método público para refrescar sesión si es necesario."""
        if not self.headers_sesion:
            self.refrescar_sesion(callback)

    def refrescar_sesion(self, progress_callback: Callable[[str], None]):
        with sync_playwright() as p:
            self._obtener_credenciales(p, progress_callback)

    def run_scraper_listado(self, progress_callback: Callable[[str], None], filtros: Optional[Dict] = None, max_paginas: Optional[int] = None) -> List[Dict]:
        """Fase 1: Obtiene listado masivo usando requests (más rápido una vez tenemos token)."""
        logger.info(f"INICIANDO FASE 1. Filtros: {filtros}")
        
        # 1. Asegurar Token
        if not self.headers_sesion:
            with sync_playwright() as p:
                self._obtener_credenciales(p, progress_callback)
        
        todas_las_compras = []
        current_page = 1
        total_paginas = 1
        
        # Usamos requests Session para reutilizar conexión TCP
        session = requests.Session()
        session.headers.update(self.headers_sesion)

        try:
            while True:
                if max_paginas and current_page > max_paginas: break
                if total_paginas > 0 and current_page > total_paginas: break
                if current_page > 300: break # Safety limit

                if progress_callback: progress_callback(f"Descargando página {current_page}...")
                
                url = construir_url_api_listado(current_page, filtros)
                
                # Request directo
                resp = session.get(url, timeout=15)
                if resp.status_code != 200:
                    logger.warning(f"Error HTTP {resp.status_code} en pág {current_page}")
                    break
                
                datos = resp.json()
                meta = api_handler.extraer_metadata_paginacion(datos)
                items = api_handler.extraer_resultados(datos)

                if current_page == 1:
                    total_paginas = meta.get('pageCount', 0)
                    if total_paginas == 0: break
                
                if not items: break

                todas_las_compras.extend(items)
                current_page += 1
                time.sleep(0.5) # Politeness delay

        except Exception as e:
            logger.error(f"Error scraping listado: {e}")
            # No lanzamos error fatal para devolver lo que se haya capturado
            
        # Deduplicación básica por si acaso
        unicas = {c.get('codigo', c.get('id')): c for c in todas_las_compras}
        return list(unicas.values())

    def scrape_ficha_detalle_api(self, _, codigo_ca: str, progress_callback: Callable[[str], None] = None) -> Optional[Dict]:
        """
        Fase 2: Extrae detalle individual. 
        Usa 'requests' en lugar de 'page' (Playwright) para máxima velocidad.
        """
        url_api = construir_url_api_ficha(codigo_ca)
        
        try:
            resp = requests.get(url_api, headers=self.headers_sesion or HEADERS_API, timeout=10)
            if resp.status_code != 200: return None
            datos = resp.json()
        except Exception:
            return None
        
        if datos and datos.get('success') == 'OK' and 'payload' in datos:
            payload = datos['payload']
            
            # Lógica de fallback para el texto del estado
            estado_texto = payload.get('estado')
            if not estado_texto and payload.get('motivo_desierta'):
                estado_texto = "Desierta"
            
            # Mapeo limpio de datos (Keys deben coincidir con lo que espera DB Service)
            return {
                'descripcion': payload.get('descripcion'),
                'direccion_entrega': payload.get('direccion_entrega'),
                'fecha_cierre_p1': payload.get('fecha_cierre_primer_llamado'),
                'fecha_cierre_p2': payload.get('fecha_cierre_segundo_llamado'),
                'productos_solicitados': payload.get('productos_solicitados', []),
                'estado': estado_texto, 
                'cantidad_provedores_cotizando': payload.get('cantidad_provedores_cotizando'),
                'estado_convocatoria': payload.get('estado_convocatoria'),
                'plazo_entrega': payload.get('plazo_entrega') 
            }
        return None
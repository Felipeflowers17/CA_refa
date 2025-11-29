# -*- coding: utf-8 -*-
import time
from typing import TYPE_CHECKING, List
from src.utils.logger import configurar_logger
from src.utils.exceptions import (
    ScrapingFase1Error, DatabaseLoadError, DatabaseTransformError,
    ScrapingFase2Error, RecalculoError
)

if TYPE_CHECKING:
    from src.db.db_service import DbService
    from src.scraper.scraper_service import ScraperService
    from src.logic.score_engine import ScoreEngine

logger = configurar_logger(__name__)

class EtlService:
    def __init__(self, db_service: "DbService", scraper_service: "ScraperService", score_engine: "ScoreEngine"):
        self.db_service = db_service
        self.scraper_service = scraper_service
        self.score_engine = score_engine
        logger.info("EtlService inicializado.")

    def _create_progress_emitters(self, progress_callback_text, progress_callback_percent):
        """Helper para emitir progreso de forma segura si los callbacks son None."""
        def emit_text(msg: str):
            if progress_callback_text: progress_callback_text(msg)
        def emit_percent(val: int):
            if progress_callback_percent: progress_callback_percent(val)
        return emit_text, emit_percent

    def run_etl_live_to_db(self, progress_callback_text=None, progress_callback_percent=None, config=None) -> int:
        """
        Flujo principal: Scraping Fase 1 -> Guardado BD -> Puntuación -> Fase 2 Top.
        Retorna: Número (int) de registros procesados/encontrados.
        """
        emit_text, emit_percent = self._create_progress_emitters(progress_callback_text, progress_callback_percent)
        date_from, date_to, max_paginas = config["date_from"], config["date_to"], config["max_paginas"]
        
        # 1. SCRAPING FASE 1
        emit_text("Iniciando Fase 1 (Buscando listado)...")
        emit_percent(5)
        
        try:
            filtros = {'date_from': date_from.strftime('%Y-%m-%d'), 'date_to': date_to.strftime('%Y-%m-%d')}
            datos = self.scraper_service.run_scraper_listado(emit_text, filtros, max_paginas)
        except Exception as e:
            raise ScrapingFase1Error(f"Fallo scraping listado: {e}") from e

        count_datos = len(datos) if datos else 0
        if count_datos == 0:
            emit_text("No se encontraron datos.")
            emit_percent(100)
            return 0 

        # 2. GUARDADO (Bulk Upsert)
        emit_percent(20)
        emit_text(f"Guardando {count_datos} registros en BD...")
        try:
            # NOTA: Este método ahora devuelve None, no lista de objetos
            self.db_service.insertar_o_actualizar_licitaciones_raw(datos)
        except Exception as e:
            raise DatabaseLoadError(f"Fallo guardado BD: {e}") from e
            
        # 3. TRANSFORMACIÓN (Scoring Fase 1)
        emit_percent(30)
        self._transform_puntajes_fase_1(emit_text, emit_percent)
        
        # 4. FASE 2 AUTOMÁTICA (Para las TOP mejores)
        try:
            candidatas = self.db_service.obtener_candidatas_para_fase_2(umbral_minimo=10)
            if candidatas:
                emit_text(f"Iniciando Fase 2 para {len(candidatas)} oportunidades relevantes...")
                self._procesar_lista_fase_2(candidatas, emit_text, emit_percent)
        except Exception as e:
            logger.error(f"Error en Fase 2 automática: {e}") 
            
        emit_text("Proceso Completo.")
        emit_percent(100)
        
        return count_datos

    def _transform_puntajes_fase_1(self, progress_callback_text, progress_callback_percent):
        """Recalcula puntajes base para todas las candidatas."""
        emit_text, emit_percent = self._create_progress_emitters(progress_callback_text, progress_callback_percent)
        try:
            licitaciones_dicts = self.db_service.obtener_todas_candidatas_fase_1_para_recalculo()
            if not licitaciones_dicts: return
            
            total = len(licitaciones_dicts)
            emit_text(f"Recalculando puntajes de {total} registros...")
            
            lista_actualizaciones = []
            
            # Recargar reglas antes de procesar
            self.score_engine.recargar_reglas()

            for i, lic_data in enumerate(licitaciones_dicts):
                # Fase 1 Score
                item_f1 = { 
                    'codigo': lic_data['codigo_ca'],
                    'nombre': lic_data['nombre'], 
                    'estado_ca_texto': lic_data['estado_ca_texto'], 
                    'organismo_comprador': lic_data['organismo_nombre']
                }
                pts1, det1 = self.score_engine.calcular_puntuacion_fase_1(item_f1)
                
                # Fase 2 Score (si existen datos)
                pts2 = 0
                det2 = []
                desc = lic_data.get('descripcion')
                prods = lic_data.get('productos_solicitados')
                
                if desc or (prods and len(prods) > 0):
                    item_f2 = {'descripcion': desc, 'productos_solicitados': prods}
                    pts2, det2 = self.score_engine.calcular_puntuacion_fase_2(item_f2)
                
                total_score = pts1 + pts2
                total_detail = det1 + det2
                
                # Tupla (id, score, detalle) compatible con db_service
                lista_actualizaciones.append((lic_data['ca_id'], total_score, total_detail))
                
                if i % 200 == 0: # Emitir progreso cada 200 items para no saturar GUI
                    emit_percent(int(((i+1)/total)*100))
            
            self.db_service.actualizar_puntajes_fase_1_en_lote(lista_actualizaciones)
            
        except Exception as e:
            raise DatabaseTransformError(f"Error cálculo puntajes: {e}") from e

    def run_recalculo_total_fase_1(self, progress_callback_text=None, progress_callback_percent=None):
        """Tarea manual de recálculo (botón GUI)."""
        emit_text, emit_percent = self._create_progress_emitters(progress_callback_text, progress_callback_percent)
        try:
            emit_text("Recargando reglas...")
            self.score_engine.recargar_reglas()
            self._transform_puntajes_fase_1(emit_text, emit_percent)
            emit_percent(100)
        except Exception as e:
            raise RecalculoError(f"Fallo recalculo: {e}") from e

    def run_fase2_update(self, progress_callback_text=None, progress_callback_percent=None, scopes: List[str] = None):
        """Actualiza detalles (descripción/productos/estado) desde la web."""
        emit_text, emit_percent = self._create_progress_emitters(progress_callback_text, progress_callback_percent)
        
        try:
            # Refresco de sesión (Best Effort)
            if hasattr(self.scraper_service, 'check_session'):
                 self.scraper_service.check_session(emit_text)

            emit_text("Seleccionando CAs para actualizar...")
            lists_to_process = []
            
            # Selección de alcance
            scopes = scopes or ['all']
            if 'all' in scopes:
                lists_to_process.append(self.db_service.obtener_datos_tab3_seguimiento())
                lists_to_process.append(self.db_service.obtener_datos_tab4_ofertadas())
                lists_to_process.append(self.db_service.obtener_candidatas_top_para_actualizar(umbral_minimo=10))
            else:
                if 'seguimiento' in scopes:
                    lists_to_process.append(self.db_service.obtener_datos_tab3_seguimiento())
                if 'ofertadas' in scopes:
                    lists_to_process.append(self.db_service.obtener_datos_tab4_ofertadas())
                if 'candidatas' in scopes:
                    lists_to_process.append(self.db_service.obtener_candidatas_top_para_actualizar(umbral_minimo=10))
            
            # Deduplicación por ID
            mapa = {}
            for lst in lists_to_process:
                for ca in lst: mapa[ca.ca_id] = ca
            
            procesar = list(mapa.values())
            
            if not procesar:
                emit_text("Nada para actualizar.")
                emit_percent(100)
                return

            emit_text(f"Actualizando {len(procesar)} CAs desde web...")
            self._procesar_lista_fase_2(procesar, emit_text, emit_percent)
            
        except Exception as e:
             raise ScrapingFase2Error(f"Fallo actualización Fase 2: {e}") from e
        
        emit_text("Actualización finalizada.")
        emit_percent(100)

    def _procesar_lista_fase_2(self, lista_cas, emit_text, emit_percent):
        total = len(lista_cas)
        self.score_engine.recargar_reglas() # Asegurar reglas frescas

        for i, lic in enumerate(lista_cas):
            # Barra de progreso entre 0% y 95%
            percent = int(((i+1)/total)*95)
            emit_percent(percent)
            emit_text(f"Actualizando: {lic.codigo_ca}")
            
            try:
                # LLAMADA AL SCRAPER (Debe devolver Dict o None)
                datos = self.scraper_service.scrape_ficha_detalle_api(None, lic.codigo_ca, emit_text)
                
                if datos:
                    # Recalcular Score Total
                    item_f1 = {
                        'nombre': lic.nombre, 
                        'estado_ca_texto': lic.estado_ca_texto, 
                        'organismo_comprador': lic.organismo.nombre if lic.organismo else ""
                    }
                    pts1, det1 = self.score_engine.calcular_puntuacion_fase_1(item_f1)
                    pts2, det2 = self.score_engine.calcular_puntuacion_fase_2(datos)
                    
                    self.db_service.actualizar_ca_con_fase_2(
                        codigo_ca=lic.codigo_ca, 
                        datos_fase_2=datos, 
                        puntuacion_total=pts1 + pts2, 
                        detalle_completo=det1 + det2
                    )
                else:
                    logger.warning(f"Ficha no disponible/vacía para {lic.codigo_ca}")
            
            except Exception as e:
                logger.error(f"Error procesando {lic.codigo_ca}: {e}")
            
            # Pequeña pausa para no saturar CPU/Red
            time.sleep(0.1)

    def run_limpieza_automatica(self):
        try: 
            eliminados = self.db_service.limpiar_registros_antiguos()
            if eliminados > 0:
                logger.info(f"Limpieza automática: {eliminados} registros purgados.")
        except Exception as e:
            logger.error(f"Error en limpieza: {e}")
# -*- coding: utf-8 -*-
"""
Servicio ETL (Extract, Transform, Load).

Orquestador principal que coordina:
1. Extracción de datos (ServicioScraper).
2. Carga en Base de Datos (DbService).
3. Transformación y Puntuación (MotorPuntajes).
"""
import time
import datetime
from typing import TYPE_CHECKING, List, Dict
from src.utils.logger import configurar_logger


from src.utils.exceptions import (
    ErrorScrapingFase1, ErrorCargaBD, ErrorTransformacionBD,
    ErrorScrapingFase2, ErrorRecalculo
)

if TYPE_CHECKING:
    from src.db.db_service import DbService
    from src.scraper.scraper_service import ServicioScraper
    from src.logic.score_engine import MotorPuntajes

logger = configurar_logger(__name__)

class ServicioEtl:
    def __init__(self, db_service: "DbService", scraper_service: "ServicioScraper", score_engine: "MotorPuntajes"):
        self.db_service = db_service
        self.scraper_service = scraper_service
        self.score_engine = score_engine
        logger.info("ServicioEtl inicializado correctamente.")

    def _crear_emisores_progreso(self, callback_texto, callback_porcentaje):
        """Ayudante para emitir progreso de forma segura si los callbacks son None."""
        def emitir_texto(msg: str):
            if callback_texto: callback_texto(msg)
        def emitir_porcentaje(val: int):
            if callback_porcentaje: callback_porcentaje(val)
        return emitir_texto, emitir_porcentaje

    def ejecutar_etl_completo(self, callback_texto=None, callback_porcentaje=None, configuracion=None) -> int:
        """
        Flujo principal: Scraping Fase 1 -> Guardado BD -> Puntuación -> Fase 2 Top.
        Retorna: Número (int) de registros procesados/encontrados.
        """
        emitir_texto, emitir_porcentaje = self._crear_emisores_progreso(callback_texto, callback_porcentaje)
        
        fecha_desde = configuracion["date_from"]
        fecha_hasta = configuracion["date_to"]
        max_paginas = configuracion["max_paginas"]
        
        # 1. EXTRACCIÓN (Scraping Fase 1)
        emitir_texto("Iniciando Fase 1 (Buscando listado)...")
        emitir_porcentaje(5)
        
        try:
            filtros = {
                'date_from': fecha_desde.strftime('%Y-%m-%d'), 
                'date_to': fecha_hasta.strftime('%Y-%m-%d')
            }

            datos = self.scraper_service.ejecutar_scraper_listado(emitir_texto, filtros, max_paginas)
        except Exception as e:
            raise ErrorScrapingFase1(f"Fallo scraping listado: {e}") from e

        cantidad_datos = len(datos) if datos else 0
        if cantidad_datos == 0:
            emitir_texto("No se encontraron datos nuevos.")
            emitir_porcentaje(100)
            return 0 

        # 2. CARGA (Bulk Upsert)
        emitir_porcentaje(20)
        emitir_texto(f"Guardando {cantidad_datos} registros en BD...")
        try:
            self.db_service.insertar_o_actualizar_masivo(datos)
        except Exception as e:
            raise ErrorCargaBD(f"Fallo guardado en BD: {e}") from e
            
        # 3. TRANSFORMACIÓN (Cálculo de Puntajes Fase 1)
        emitir_porcentaje(30)
        self._transformar_puntajes_fase_1(emitir_texto, emitir_porcentaje)
        
        # 4. ENRIQUECIMIENTO (Fase 2 Automática para las TOP mejores)
        try:
            candidatas = self.db_service.obtener_candidatas_para_fase_2(umbral_minimo=10)
            if candidatas:
                emitir_texto(f"Iniciando Fase 2 para {len(candidatas)} oportunidades relevantes...")
                self._procesar_detalle_lote(candidatas, emitir_texto, emitir_porcentaje)
        except Exception as e:
            logger.error(f"Error en Fase 2 automática: {e}") 
            
        emitir_texto("Proceso Completo.")
        emitir_porcentaje(100)
        
        return cantidad_datos

    def _transformar_puntajes_fase_1(self, callback_texto, callback_porcentaje):
        """Recalcula puntajes base para todas las candidatas en la BD."""
        emitir_texto, emitir_porcentaje = self._crear_emisores_progreso(callback_texto, callback_porcentaje)
        try:
            # Obtener datos ligeros para recalculo
            licitaciones_dicts = self.db_service.obtener_datos_para_recalculo_puntajes()
            if not licitaciones_dicts: return
            
            total = len(licitaciones_dicts)
            emitir_texto(f"Recalculando puntajes de {total} registros...")
            
            lista_actualizaciones = []
            
            # Recargar reglas en memoria antes de procesar
            self.score_engine.recargar_reglas_memoria()

            for i, lic_data in enumerate(licitaciones_dicts):
                # Cálculo Fase 1
                item_f1 = { 
                    'codigo': lic_data['codigo_ca'],
                    'nombre': lic_data['nombre'], 
                    'estado_ca_texto': lic_data['estado_ca_texto'], 
                    'organismo_comprador': lic_data['organismo_nombre']
                }
                pts1, det1 = self.score_engine.calcular_puntaje_fase_1(item_f1)
                
                # Cálculo Fase 2 (si existen datos previos)
                pts2 = 0
                det2 = []
                desc = lic_data.get('descripcion')
                prods = lic_data.get('productos_solicitados')
                
                if desc or (prods and len(prods) > 0):
                    item_f2 = {'descripcion': desc, 'productos_solicitados': prods}
                    pts2, det2 = self.score_engine.calcular_puntaje_fase_2(item_f2)
                
                total_score = pts1 + pts2
                total_detail = det1 + det2
                
                # Tupla (id, score, detalle) compatible con db_service
                lista_actualizaciones.append((lic_data['ca_id'], total_score, total_detail))
                
                if i % 200 == 0: # Emitir progreso cada 200 items para no saturar GUI
                    emitir_porcentaje(int(((i+1)/total)*100))
            
            # Guardado masivo de puntajes
            self.db_service.actualizar_puntajes_en_lote(lista_actualizaciones)
            
        except Exception as e:
            raise ErrorTransformacionBD(f"Error cálculo puntajes: {e}") from e

    def ejecutar_recalculo_total(self, callback_texto=None, callback_porcentaje=None):
        """Tarea manual de recálculo disparada desde la GUI."""
        emitir_texto, emitir_porcentaje = self._crear_emisores_progreso(callback_texto, callback_porcentaje)
        try:
            emitir_texto("Recargando reglas...")
            self.score_engine.recargar_reglas_memoria()
            self._transformar_puntajes_fase_1(emitir_texto, emitir_porcentaje)
            emitir_porcentaje(100)
        except Exception as e:
            raise ErrorRecalculo(f"Fallo recalculo: {e}") from e

    def ejecutar_actualizacion_selectiva(self, callback_texto=None, callback_porcentaje=None, alcances: List[str] = None):
        """
        Actualiza información de licitaciones específicas (Seguimiento, Ofertadas)
        o busca actualizaciones de estado.
        """
        emitir_texto, emitir_porcentaje = self._crear_emisores_progreso(callback_texto, callback_porcentaje)
        alcances = alcances or ['all']
        
        try:
            # 1. ACTUALIZACIÓN MASIVA DE ESTADOS (Barrido de lista)
            if 'candidatas' in alcances or 'all' in alcances:
                emitir_texto("Analizando fechas de candidatas activas...")
                fecha_min, fecha_max = self.db_service.obtener_rango_fechas_candidatas_activas()
                
                if fecha_min and fecha_max:
                    hoy = datetime.date.today()
                    
                    # Normalización segura a date
                    f_min_safe = fecha_min.date() if isinstance(fecha_min, datetime.datetime) else fecha_min
                    f_max_safe = fecha_max.date() if isinstance(fecha_max, datetime.datetime) else fecha_max

                    # --- LÓGICA DE SEGURIDAD ---
                    # Evitar barridos de años completos. Límite: 5 días atrás.
                    limite_atras = hoy - datetime.timedelta(days=5)
                    
                    if f_min_safe < limite_atras:
                        emitir_texto(f"Ajustando rango: {f_min_safe} es muy antiguo. Usando {limite_atras}.")
                        f_min_safe = limite_atras
                    # ---------------------------

                    fecha_tope = max(f_max_safe, hoy)
                    emitir_texto(f"Actualizando estados ({f_min_safe} al {fecha_tope})...")
                    
                    filtros = {
                        'date_from': f_min_safe.strftime('%Y-%m-%d'), 
                        'date_to': fecha_tope.strftime('%Y-%m-%d')
                    }
                    
                    # Ejecutamos Scraper de Listado (Fase 1)
                    datos_barrido = self.scraper_service.ejecutar_scraper_listado(
                        emitir_texto, filtros, max_paginas=0 
                    )
                    
                    if datos_barrido:
                        emitir_texto(f"Sincronizando {len(datos_barrido)} registros...")
                        self.db_service.insertar_o_actualizar_masivo(datos_barrido)
                        self.db_service.cerrar_licitaciones_vencidas_localmente()
                    else:
                        emitir_texto("No se detectaron cambios en candidatas.")
                else:
                    emitir_texto("No hay candidatas activas para actualizar.")

            # 2. ACTUALIZACIÓN DE DETALLE (Fase 2 Profunda)
            necesita_fase2 = 'seguimiento' in alcances or 'ofertadas' in alcances or 'all' in alcances
            
            if necesita_fase2:
                # Verificación de Sesión (si el scraper lo soporta)
                if hasattr(self.scraper_service, 'verificar_sesion'):
                    self.scraper_service.verificar_sesion(emitir_texto)

                emitir_texto("Seleccionando licitaciones para detalle...")
                listas_procesar = []
                
                if 'all' in alcances:
                    listas_procesar.append(self.db_service.obtener_licitaciones_seguimiento())
                    listas_procesar.append(self.db_service.obtener_licitaciones_ofertadas())
                else:
                    if 'seguimiento' in alcances:
                        listas_procesar.append(self.db_service.obtener_licitaciones_seguimiento())
                    if 'ofertadas' in alcances:
                        listas_procesar.append(self.db_service.obtener_licitaciones_ofertadas())
                
                # Deduplicación por ID (para no scrapear doble)
                mapa_unicos = {}
                for lst in listas_procesar:
                    for ca in lst: 
                        mapa_unicos[ca.ca_id] = ca
                
                procesar = list(mapa_unicos.values())
                
                if procesar:
                    emitir_texto(f"Actualizando detalle de {len(procesar)} CAs...")
                    self._procesar_detalle_lote(procesar, emitir_texto, emitir_porcentaje)
                elif not ('candidatas' in alcances): 
                    emitir_texto("Nada pendiente en Seguimiento/Ofertadas.")

        except Exception as e:
             raise ErrorScrapingFase2(f"Fallo actualización selectiva: {e}") from e
        
        emitir_texto("Actualización finalizada.")
        emitir_porcentaje(100)

    def _procesar_detalle_lote(self, lista_cas, emitir_texto, emitir_porcentaje):
        """Itera sobre una lista de licitaciones y extrae su detalle (Fase 2)."""
        total = len(lista_cas)
        self.score_engine.recargar_reglas_memoria() 

        for i, lic in enumerate(lista_cas):
            # Barra de progreso
            percent = int(((i+1)/total)*100)
            emitir_porcentaje(percent)
            emitir_texto(f"Actualizando: {lic.codigo_ca}")
            
            try:
                # LLAMADA AL SCRAPER 
                datos = self.scraper_service.extraer_detalle_api(None, lic.codigo_ca, emitir_texto)
                
                if datos:
                    # Recalcular Score Total con la nueva información
                    item_f1 = {
                        'nombre': lic.nombre, 
                        'estado_ca_texto': lic.estado_ca_texto, 
                        'organismo_comprador': lic.organismo.nombre if lic.organismo else ""
                    }
                    pts1, det1 = self.score_engine.calcular_puntaje_fase_1(item_f1)
                    pts2, det2 = self.score_engine.calcular_puntaje_fase_2(datos)
                    
                    self.db_service.actualizar_fase_2_detalle(
                        codigo_ca=lic.codigo_ca, 
                        datos_fase_2=datos, 
                        puntuacion_total=pts1 + pts2, 
                        detalle_completo=det1 + det2
                    )
                else:
                    logger.warning(f"Ficha no disponible/vacía para {lic.codigo_ca}")
            
            except Exception as e:
                logger.error(f"Error procesando {lic.codigo_ca}: {e}")
            
            # Pequeña pausa para no saturar
            time.sleep(0.1)

    def ejecutar_limpieza_automatica(self):
        """Tarea de mantenimiento de BD."""
        try: 
            cerradas = self.db_service.cerrar_licitaciones_vencidas_localmente()
            eliminados = self.db_service.limpiar_registros_antiguos()
            
            if eliminados > 0 or cerradas > 0:
                logger.info(f"Limpieza: {cerradas} cerradas por fecha, {eliminados} borradas por antigüedad.")
        except Exception as e:
            logger.error(f"Error en limpieza automática: {e}")
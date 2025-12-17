# -*- coding: utf-8 -*-
"""
Servicio ETL (Extract, Transform, Load).
Orquestador principal del proceso de scraping y puntuación.
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
        Flujo principal: Limpieza -> Scraping Fase 1 -> Guardado BD -> Puntuación -> Fase 2 Top.
        """
        emitir_texto, emitir_porcentaje = self._crear_emisores_progreso(callback_texto, callback_porcentaje)
        
        # --- PASO CRÍTICO 0: MANTENIMIENTO ---
        # Antes de buscar nada nuevo, marcamos todo lo anterior como "Visto" (Neutro)
        try:
            emitir_texto("Mantenimiento: Archivando organismos pendientes anteriores...")
            self.db_service.marcar_organismos_como_vistos()
        except Exception as e:
            logger.error(f"Error en mantenimiento de organismos: {e}")
        # -------------------------------------

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
        """Recalcula puntajes base, guardando SOLO si hubo cambios (Dirty Checking)."""
        emitir_texto, emitir_porcentaje = self._crear_emisores_progreso(callback_texto, callback_porcentaje)
        try:
            licitaciones_dicts = self.db_service.obtener_datos_para_recalculo_puntajes()
            if not licitaciones_dicts: return
            
            total = len(licitaciones_dicts)
            emitir_texto(f"Analizando {total} registros para puntuación...")
            
            lista_actualizaciones = []
            
            # Recargar reglas en memoria
            self.score_engine.recargar_reglas_memoria()

            cambios_detectados = 0

            for i, lic_data in enumerate(licitaciones_dicts):
                # Cálculo Fase 1
                item_f1 = { 
                    'codigo': lic_data['codigo_ca'],
                    'nombre': lic_data['nombre'], 
                    'estado_ca_texto': lic_data['estado_ca_texto'], 
                    'organismo_comprador': lic_data['organismo_nombre']
                }
                pts1, det1 = self.score_engine.calcular_puntaje_fase_1(item_f1)
                
                # Cálculo Fase 2
                pts2 = 0
                det2 = []
                desc = lic_data.get('descripcion')
                prods = lic_data.get('productos_solicitados')
                
                if desc or (prods and len(prods) > 0):
                    item_f2 = {'descripcion': desc, 'productos_solicitados': prods}
                    pts2, det2 = self.score_engine.calcular_puntaje_fase_2(item_f2)
                
                nuevo_score = pts1 + pts2
                nuevo_detalle = det1 + det2
                
                # Dirty Checking
                score_actual = lic_data.get('puntuacion_final_actual', 0)
                
                if nuevo_score != score_actual:
                    lista_actualizaciones.append((lic_data['ca_id'], nuevo_score, nuevo_detalle))
                    cambios_detectados += 1
                
                if i % 500 == 0: 
                    emitir_porcentaje(int(((i+1)/total)*100))
            
            if lista_actualizaciones:
                emitir_texto(f"Actualizando {cambios_detectados} puntajes que cambiaron...")
                self.db_service.actualizar_puntajes_en_lote(lista_actualizaciones)
            else:
                emitir_texto("No hubo cambios en los puntajes.")
            
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
        emitir_texto, emitir_porcentaje = self._crear_emisores_progreso(callback_texto, callback_porcentaje)
        alcances = alcances or ['all']
        
        try:
            # 1. ACTUALIZACIÓN MASIVA DE ESTADOS
            if 'candidatas' in alcances or 'all' in alcances:
                emitir_texto("Analizando fechas de candidatas activas...")
                fecha_min, fecha_max = self.db_service.obtener_rango_fechas_candidatas_activas()
                
                if fecha_min and fecha_max:
                    hoy = datetime.date.today()
                    f_min_safe = fecha_min.date() if isinstance(fecha_min, datetime.datetime) else fecha_min
                    f_max_safe = fecha_max.date() if isinstance(fecha_max, datetime.datetime) else fecha_max
                    limite_atras = hoy - datetime.timedelta(days=5)
                    if f_min_safe < limite_atras: f_min_safe = limite_atras

                    fecha_tope = max(f_max_safe, hoy)
                    emitir_texto(f"Actualizando estados ({f_min_safe} al {fecha_tope})...")
                    
                    filtros = {'date_from': f_min_safe.strftime('%Y-%m-%d'), 'date_to': fecha_tope.strftime('%Y-%m-%d')}
                    datos_barrido = self.scraper_service.ejecutar_scraper_listado(emitir_texto, filtros, max_paginas=0)
                    
                    if datos_barrido:
                        emitir_texto(f"Sincronizando {len(datos_barrido)} registros...")
                        self.db_service.insertar_o_actualizar_masivo(datos_barrido)
                        self.db_service.cerrar_licitaciones_vencidas_localmente()
                    else:
                        emitir_texto("No se detectaron cambios en candidatas.")

            # 2. ACTUALIZACIÓN DE DETALLE
            necesita_fase2 = 'seguimiento' in alcances or 'ofertadas' in alcances or 'all' in alcances
            if necesita_fase2:
                if hasattr(self.scraper_service, 'verificar_sesion'):
                    self.scraper_service.verificar_sesion(emitir_texto)

                emitir_texto("Seleccionando licitaciones para detalle...")
                listas_procesar = []
                if 'all' in alcances:
                    listas_procesar.append(self.db_service.obtener_licitaciones_seguimiento())
                    listas_procesar.append(self.db_service.obtener_licitaciones_ofertadas())
                else:
                    if 'seguimiento' in alcances: listas_procesar.append(self.db_service.obtener_licitaciones_seguimiento())
                    if 'ofertadas' in alcances: listas_procesar.append(self.db_service.obtener_licitaciones_ofertadas())
                
                mapa_unicos = {}
                for lst in listas_procesar:
                    for ca in lst: mapa_unicos[ca.ca_id] = ca
                
                procesar = list(mapa_unicos.values())
                
                if procesar:
                    emitir_texto(f"Actualizando detalle de {len(procesar)} CAs...")
                    self._procesar_detalle_lote(procesar, emitir_texto, emitir_porcentaje)

        except Exception as e:
             raise ErrorScrapingFase2(f"Fallo actualización selectiva: {e}") from e
        
        emitir_texto("Actualización finalizada.")
        emitir_porcentaje(100)

    def _procesar_detalle_lote(self, candidatas: List, emitir_texto, emitir_porcentaje):
        total = len(candidatas)
        procesados = 0
        
        for idx, item in enumerate(candidatas):
            codigo = item['codigo']
            
            try:
                # datos ahora es un Objeto Pydantic (LicitacionDetalleSchema)
                datos_obj = self.scraper_service.extraer_detalle_api(None, codigo)

                if datos_obj:
                    # CONVERSIÓN CRÍTICA: Transformamos a dict para compatibilidad
                    datos = datos_obj.model_dump()

                    # 1. Calcular Puntaje Fase 2 (Productos + Descripción)
                    pts_prod, det_prod = self.score_engine.calcular_puntaje_fase_2(datos)
                    
                    # 2. Recalcular total
                    puntos_base = item.get('puntos_base', 0)
                    nuevo_total = puntos_base + pts_prod
                    nuevo_detalle = (item.get('detalle_base') or []) + det_prod

                    # 3. Guardar en BD (Fase 2)
                    self.db_service.actualizar_fase_2_detalle(
                        codigo_ca=codigo,
                        datos_fase_2=datos,
                        puntuacion_total=nuevo_total,
                        detalle_completo=nuevo_detalle
                    )
                    
                    procesados += 1
                else:
                    logger.warning(f"No se pudo descargar info para {codigo}")
                
                # Pequeña pausa para no saturar CPU en bucles muy rápidos
                time.sleep(0.05) 

                if idx % 5 == 0:
                    progreso = 30 + int((idx / total) * 60)
                    emitir_porcentaje(progreso)

            except Exception as e:
                logger.error(f"Error procesando detalle {codigo}: {e}")

        emitir_texto("Fase 2 Completada.")

    def ejecutar_limpieza_automatica(self):
        try: 
            cerradas = self.db_service.cerrar_licitaciones_vencidas_localmente()
            eliminados = self.db_service.limpiar_registros_antiguos()
            if eliminados > 0 or cerradas > 0:
                logger.info(f"Limpieza: {cerradas} cerradas, {eliminados} borradas.")
        except Exception as e:
            logger.error(f"Error en limpieza automática: {e}")

    def importar_lista_manual(self, lista_codigos: List[str], destino: str, callback_texto=None, callback_porcentaje=None):
        """
        Importa manualmente una lista de códigos CA.
        destino: 'candidatas', 'seguimiento' u 'ofertadas'.
        """
        emitir_texto, emitir_porcentaje = self._crear_emisores_progreso(callback_texto, callback_porcentaje)
        
        # Limpieza de lista
        codigos_limpios = [c.strip().upper() for c in lista_codigos if c.strip()]
        total = len(codigos_limpios)
        if total == 0: return 0

        emitir_texto(f"Iniciando importación manual de {total} códigos para '{destino}'...")
        
        # Recargar reglas para puntajes
        self.score_engine.recargar_reglas_memoria()
        
        procesados = 0
        
        # Verificamos sesión una vez antes de empezar
        if hasattr(self.scraper_service, 'verificar_sesion'):
            self.scraper_service.verificar_sesion(emitir_texto)

        for i, codigo in enumerate(codigos_limpios):
            try:
                percent = int(((i+1)/total)*100)
                emitir_porcentaje(percent)
                emitir_texto(f"Procesando ({i+1}/{total}): {codigo}")

                # 1. Extraer datos (Usamos lógica de Fase 2 directa)
                datos = self.scraper_service.extraer_detalle_api(None, codigo)
                
                if datos:
                    # --- Nombre del Organismo ---
                    org_real = datos.get('organismo_nombre')
                    if not org_real or len(org_real) < 2:
                        org_real = "Importado Manual"

                    # 2. Calcular Puntajes
                    puntos1, det1 = self.score_engine.calcular_puntaje_fase_1({
                        'nombre': datos.get('descripcion', 'Importado Manualmente')[:100], 
                        'estado_ca_texto': datos.get('estado'),
                        'organismo_comprador': org_real
                    })
                    puntos2, det2 = self.score_engine.calcular_puntaje_fase_2(datos)
                    
                    # 3. Guardar en BD (CORREGIDO CON DATOS FASE 2)
                    registro_base = [{
                        "codigo": codigo,
                        "nombre": datos.get('descripcion', 'Sin Nombre (Manual)'),
                        "estado": datos.get('estado'),
                        # AQUÍ MAPEAMOS LOS NUEVOS CAMPOS:
                        "fecha_publicacion": datos.get('fecha_publicacion'),  # Fecha real extraída
                        "monto_disponible_CLP": datos.get('monto_estimado'), # Mapeamos 'presupuesto' a 'monto_clp'
                        "fecha_cierre": datos.get('fecha_cierre_p1'),
                        "organismo": org_real
                    }]
                    
                    # Paso A: Insertar/Actualizar Base
                    self.db_service.insertar_o_actualizar_masivo(registro_base)
                    
                    # Paso B: Actualizar con detalle completo
                    self.db_service.actualizar_fase_2_detalle(
                        codigo_ca=codigo,
                        datos_fase_2=datos,
                        puntuacion_total=puntos1 + puntos2,
                        detalle_completo=det1 + det2
                    )

                    # 4. Asignar al destino (Pestaña)
                    with self.db_service.session_factory() as session:
                        from src.db.db_models import CaLicitacion
                        lic = session.query(CaLicitacion).filter_by(codigo_ca=codigo).first()
                        if lic:
                            if destino == 'seguimiento':
                                self.db_service.gestionar_favorito(lic.ca_id, True)
                            elif destino == 'ofertadas':
                                self.db_service.gestionar_ofertada(lic.ca_id, True)
                            # Si es 'candidatas', no hacemos nada extra

                    procesados += 1
                else:
                    logger.warning(f"No se pudo descargar info para {codigo}")
                
                time.sleep(0.2)

            except Exception as e:
                logger.error(f"Error importando {codigo}: {e}")

        emitir_texto("Importación finalizada.")
        return procesados
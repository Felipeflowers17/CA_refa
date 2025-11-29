# -*- coding: utf-8 -*-
from typing import List, Dict, Tuple, Optional, Union, Set
from datetime import datetime, timedelta
from sqlalchemy.orm import sessionmaker, Session, joinedload
from sqlalchemy import select, delete, or_, update, func
from sqlalchemy.dialects.postgresql import insert

from .db_models import (
    CaLicitacion,
    CaSeguimiento,
    CaOrganismo,
    CaSector,
    CaKeyword,
    CaOrganismoRegla
)
from src.utils.logger import configurar_logger

logger = configurar_logger(__name__)

class DbService:
    def __init__(self, session_factory: sessionmaker[Session]):
        self.session_factory = session_factory
        logger.info("DbService inicializado.")

    # --- METODOS INTERNOS / AUXILIARES ---

    def _preparar_mapa_organismos(self, session: Session, nombres_organismos: Set[str]) -> Dict[str, int]:
        """Verifica existencia de organismos y crea los faltantes en lote."""
        if not nombres_organismos: return {}
        nombres_norm = {n.strip() for n in nombres_organismos if n}
        
        stmt = select(CaOrganismo.nombre, CaOrganismo.organismo_id).where(CaOrganismo.nombre.in_(nombres_norm))
        existentes = {nombre: oid for nombre, oid in session.execute(stmt).all()}
        
        faltantes = nombres_norm - set(existentes.keys())
        if faltantes:
            sector_default = session.scalars(select(CaSector).limit(1)).first()
            if not sector_default:
                sector_default = CaSector(nombre="General")
                session.add(sector_default)
                session.flush()
            
            nuevos_orgs = [{"nombre": nombre, "sector_id": sector_default.sector_id} for nombre in faltantes]
            session.execute(insert(CaOrganismo), nuevos_orgs)
            
            stmt_nuevos = select(CaOrganismo.nombre, CaOrganismo.organismo_id).where(CaOrganismo.nombre.in_(faltantes))
            for nombre, oid in session.execute(stmt_nuevos).all():
                existentes[nombre] = oid
                
        return existentes

    def _to_dict_safe(self, licitaciones: List[CaLicitacion]) -> List[Dict]:
        resultados = []
        for ca in licitaciones:
            resultados.append({
                "puntuacion_final": ca.puntuacion_final,
                "codigo_ca": ca.codigo_ca,
                "nombre": ca.nombre,
                "descripcion": ca.descripcion,
                "organismo_nombre": ca.organismo.nombre if ca.organismo else "N/A",
                "direccion_entrega": ca.direccion_entrega,
                "estado_ca_texto": ca.estado_ca_texto,
                "fecha_publicacion": ca.fecha_publicacion,
                "fecha_cierre": ca.fecha_cierre,
                "fecha_cierre_segundo_llamado": ca.fecha_cierre_segundo_llamado,
                "proveedores_cotizando": ca.proveedores_cotizando,
                "productos_solicitados": str(ca.productos_solicitados) if ca.productos_solicitados else "",
                "es_favorito": ca.seguimiento.es_favorito if ca.seguimiento else False,
                "es_ofertada": ca.seguimiento.es_ofertada if ca.seguimiento else False,
            })
        return resultados

    # --- INGESTIÓN DE DATOS (ETL) ---

    def insertar_o_actualizar_licitaciones_raw(self, compras: List[Dict]):
        if not compras: return
        logger.info(f"Iniciando Bulk Upsert de {len(compras)} registros...")
        
        with self.session_factory() as session:
            try:
                nombres_orgs = {c.get("organismo", "No Especificado") for c in compras}
                mapa_orgs = self._preparar_mapa_organismos(session, nombres_orgs)
                
                data_to_upsert = []
                codigos_vistos = set()
                
                for item in compras:
                    codigo = item.get("codigo", item.get("id"))
                    if not codigo or codigo in codigos_vistos: continue
                    codigos_vistos.add(codigo)
                    
                    org_nombre = item.get("organismo", "No Especificado").strip()
                    
                    record = {
                        "codigo_ca": codigo,
                        "nombre": item.get("nombre"),
                        "monto_clp": item.get("monto_disponible_CLP"),
                        "fecha_publicacion": item.get("fecha_publicacion"),
                        "fecha_cierre": item.get("fecha_cierre"),
                        "proveedores_cotizando": item.get("cantidad_provedores_cotizando"),
                        "estado_ca_texto": item.get("estado"),
                        "estado_convocatoria": item.get("estado_convocatoria"),
                        "organismo_id": mapa_orgs.get(org_nombre),
                    }
                    data_to_upsert.append(record)
                
                if data_to_upsert:
                    # Upsert: Si el codigo existe, actualiza SOLO los campos que cambian dinámicamente
                    stmt = insert(CaLicitacion).values(data_to_upsert)
                    stmt = stmt.on_conflict_do_update(
                        index_elements=['codigo_ca'],
                        set_={
                            "proveedores_cotizando": stmt.excluded.proveedores_cotizando,
                            "estado_ca_texto": stmt.excluded.estado_ca_texto, # Clave para cerrar o pasar a 2do llamado
                            "fecha_cierre": stmt.excluded.fecha_cierre,       # Clave si se extiende el plazo
                            "estado_convocatoria": stmt.excluded.estado_convocatoria,
                            "monto_clp": stmt.excluded.monto_clp
                        }
                    )
                    session.execute(stmt)
                    session.commit()
                    logger.info("Carga Masiva completada exitosamente.")
            except Exception as e:
                logger.error(f"Error en Bulk Upsert: {e}", exc_info=True)
                session.rollback()
                raise e

    def actualizar_ca_con_fase_2(self, codigo_ca: str, datos_fase_2: Dict, puntuacion_total: int, detalle_completo: List[str]):
        with self.session_factory() as session:
            try:
                stmt = select(CaLicitacion).where(CaLicitacion.codigo_ca == codigo_ca)
                licitacion = session.scalars(stmt).first()
                if not licitacion: return
                
                licitacion.descripcion = datos_fase_2.get("descripcion")
                licitacion.productos_solicitados = datos_fase_2.get("productos_solicitados")
                licitacion.direccion_entrega = datos_fase_2.get("direccion_entrega")
                licitacion.puntuacion_final = puntuacion_total
                licitacion.plazo_entrega = datos_fase_2.get("plazo_entrega")
                licitacion.puntaje_detalle = detalle_completo 
                licitacion.fecha_cierre_segundo_llamado = datos_fase_2.get("fecha_cierre_p2")
                
                if datos_fase_2.get("estado"):
                    licitacion.estado_ca_texto = datos_fase_2.get("estado")
                if datos_fase_2.get("estado_convocatoria") is not None:
                    licitacion.estado_convocatoria = datos_fase_2.get("estado_convocatoria")
                
                session.commit()
            except Exception as e: 
                logger.error(f"[Fase 2] Error actualizando {codigo_ca}: {e}")
                session.rollback()
                raise

    def actualizar_puntajes_fase_1_en_lote(self, actualizaciones: List[Union[Tuple[int, int], Tuple[int, int, List[str]]]]):
        if not actualizaciones: return
        datos_mapeados = []
        for item in actualizaciones:
            if len(item) == 3:
                ca_id, puntaje, detalle = item
            elif len(item) == 2:
                ca_id, puntaje = item
                detalle = ["Puntaje Base (Sin detalle)"]
            else:
                continue
            datos_mapeados.append({
                "ca_id": ca_id, "puntuacion_final": puntaje, "puntaje_detalle": list(detalle) 
            })
        with self.session_factory() as session:
            try: 
                session.bulk_update_mappings(CaLicitacion, datos_mapeados)
                session.commit()
            except Exception as e:
                logger.error(f"Error update lote: {e}"); session.rollback(); raise

    # --- CONSULTAS (RESTORED METHODS) ---

    def get_licitacion_by_id(self, ca_id: int) -> Optional[CaLicitacion]:
        with self.session_factory() as session:
            stmt = select(CaLicitacion).options(
                joinedload(CaLicitacion.organismo), 
                joinedload(CaLicitacion.seguimiento)
            ).where(CaLicitacion.ca_id == ca_id)
            return session.scalars(stmt).first()

    def obtener_rango_fechas_candidatas_activas(self) -> Tuple[Optional[datetime], Optional[datetime]]:
        """
        Devuelve (min_fecha_pub, max_fecha_pub) de las licitaciones en estado 'Candidata'
        (es decir, NO favoritas y NO ofertadas) que actualmente están marcadas como 'Publicada'.
        Se usa para el 'Barrido de Listado'.
        """
        with self.session_factory() as session:
            # Subquery para excluir las que ya seguimos
            subq = select(CaSeguimiento.ca_id).where(or_(CaSeguimiento.es_favorito == True, CaSeguimiento.es_ofertada == True, CaSeguimiento.es_oculta == True))
            
            stmt = select(
                func.min(CaLicitacion.fecha_publicacion),
                func.max(CaLicitacion.fecha_publicacion)
            ).filter(
                CaLicitacion.ca_id.notin_(subq),
                # Buscamos solo sobre las que creemos que están vivas
                or_(
                    CaLicitacion.estado_ca_texto.ilike('%Publicada%'),
                    CaLicitacion.estado_ca_texto.ilike('%Segundo%')
                )
            )
            return session.execute(stmt).first()

    def limpiar_registros_antiguos(self, dias_retencion: int = 30) -> int:
        fecha_limite = datetime.now() - timedelta(days=dias_retencion)
        registros_eliminados = 0
        with self.session_factory() as session:
            try:
                subq = select(CaSeguimiento.ca_id).where(CaSeguimiento.es_favorito == True)
                stmt = delete(CaLicitacion).where(
                    CaLicitacion.fecha_cierre < fecha_limite, 
                    CaLicitacion.estado_ca_texto.notin_(['Publicada', 'Publicada - Segundo llamado']),
                    CaLicitacion.ca_id.notin_(subq)
                )
                result = session.execute(stmt)
                registros_eliminados = result.rowcount
                session.commit()
                if registros_eliminados > 0:
                    logger.info(f"Limpieza automática: {registros_eliminados} registros eliminados.")
            except Exception as e:
                logger.error(f"Error limpieza: {e}")
                session.rollback()
        return registros_eliminados
    
    def cerrar_licitaciones_vencidas_localmente(self) -> int:
        """
        Busca licitaciones que siguen 'Publicadas' pero cuya fecha de cierre ya pasó.
        Las marca como 'Cerrada' forzosamente.
        """
        ahora = datetime.now()
        registros_afectados = 0
        
        with self.session_factory() as session:
            try:
                # Buscamos Publicada o 2do llamado que ya vencieron
                stmt = update(CaLicitacion).where(
                    CaLicitacion.fecha_cierre < ahora,
                    CaLicitacion.estado_ca_texto.in_(['Publicada', 'Publicada - Segundo llamado'])
                ).values(estado_ca_texto='Cerrada')
                
                result = session.execute(stmt)
                registros_afectados = result.rowcount
                session.commit()
                
                if registros_afectados > 0:
                    logger.info(f"Mantenimiento Local: Se cerraron {registros_afectados} licitaciones vencidas.")
            except Exception as e:
                logger.error(f"Error cerrando vencidas: {e}")
                session.rollback()
        return registros_afectados

    def obtener_todas_candidatas_fase_1_para_recalculo(self) -> List[Dict]:
        with self.session_factory() as session:
            stmt = select(
                CaLicitacion.ca_id, CaLicitacion.codigo_ca, CaLicitacion.nombre,
                CaLicitacion.estado_ca_texto, CaLicitacion.descripcion, CaLicitacion.productos_solicitados,
                CaOrganismo.nombre.label("organismo_nombre")
            ).outerjoin(CaOrganismo, CaLicitacion.organismo_id == CaOrganismo.organismo_id)
            rows = session.execute(stmt).all()
            return [{
                "ca_id": r.ca_id, "codigo_ca": r.codigo_ca, "nombre": r.nombre,
                "estado_ca_texto": r.estado_ca_texto, "organismo_nombre": r.organismo_nombre or "",
                "descripcion": r.descripcion, "productos_solicitados": r.productos_solicitados
            } for r in rows]

    def obtener_candidatas_para_fase_2(self, umbral_minimo: int = 10) -> List[CaLicitacion]:
        with self.session_factory() as session:
            stmt = select(CaLicitacion).filter(CaLicitacion.puntuacion_final >= umbral_minimo, CaLicitacion.descripcion.is_(None)).order_by(CaLicitacion.fecha_cierre.asc())
            return session.scalars(stmt).all()

    def obtener_candidatas_top_para_actualizar(self, umbral_minimo: int = 10) -> List[CaLicitacion]:
        # NOTA: Este método se mantiene para compatibilidad, pero la lógica fuerte
        # de actualización de candidatas se mueve al "Barrido" (Listado).
        with self.session_factory() as session:
            subq = select(CaSeguimiento.ca_id).where(or_(CaSeguimiento.es_favorito == True, CaSeguimiento.es_ofertada == True))
            stmt = select(CaLicitacion).filter(
                CaLicitacion.puntuacion_final >= umbral_minimo, 
                CaLicitacion.ca_id.notin_(subq)
            ).order_by(CaLicitacion.fecha_cierre.asc())
            return session.scalars(stmt).all()

    def obtener_datos_tab1_candidatas(self, umbral_minimo: int = 5) -> List[CaLicitacion]:
        """
        Devuelve SOLO las licitaciones 'Publicada' o 'Segundo llamado' que superan el puntaje,
        excluyendo las que ya están en seguimiento, ofertadas u ocultas.
        """
        with self.session_factory() as session:
            # 1. Subquery de exclusión (lo que ya gestionamos)
            subq = select(CaSeguimiento.ca_id).where(
                or_(
                    CaSeguimiento.es_favorito == True, 
                    CaSeguimiento.es_ofertada == True, 
                    CaSeguimiento.es_oculta == True
                )
            )
            
            # 2. Query Principal con FILTRO DE ESTADO
            stmt = select(CaLicitacion).options(
                joinedload(CaLicitacion.seguimiento), 
                joinedload(CaLicitacion.organismo).joinedload(CaOrganismo.sector)
            ).filter(
                # A. Filtro de Puntaje
                CaLicitacion.puntuacion_final >= umbral_minimo, 
                
                # B. Filtro de "No Gestionadas"
                CaLicitacion.ca_id.notin_(subq),
                
                # [cite_start]C. FILTRO NUEVO: Solo Publicadas (normal o 2do llamado) [cite: 121]
                or_(
                    CaLicitacion.estado_ca_texto == 'Publicada',
                    CaLicitacion.estado_ca_texto == 'Publicada - Segundo llamado'
                    # Nota: Si en el futuro aparecen variantes como "Publicada ", el ilike es mas seguro:
                    # CaLicitacion.estado_ca_texto.ilike('%Publicada%')
                )
            ).order_by(CaLicitacion.puntuacion_final.desc())
            
            return session.scalars(stmt).all()

    def obtener_datos_tab3_seguimiento(self) -> List[CaLicitacion]:
        with self.session_factory() as session:
            stmt = select(CaLicitacion).options(joinedload(CaLicitacion.seguimiento), joinedload(CaLicitacion.organismo).joinedload(CaOrganismo.sector)).join(CaSeguimiento, CaLicitacion.ca_id == CaSeguimiento.ca_id).filter(CaSeguimiento.es_favorito == True, CaSeguimiento.es_ofertada == False).order_by(CaLicitacion.fecha_cierre.asc())
            return session.scalars(stmt).all()

    def obtener_datos_tab4_ofertadas(self) -> List[CaLicitacion]:
        with self.session_factory() as session:
            stmt = select(CaLicitacion).options(joinedload(CaLicitacion.seguimiento), joinedload(CaLicitacion.organismo).joinedload(CaOrganismo.sector)).join(CaSeguimiento, CaLicitacion.ca_id == CaSeguimiento.ca_id).filter(CaSeguimiento.es_ofertada == True).order_by(CaLicitacion.fecha_cierre.asc())
            return session.scalars(stmt).all()

    # --- ACCIONES ---

    def gestionar_favorito(self, ca_id: int, es_favorito: bool): 
        self._gestionar_seguimiento(ca_id, es_favorito=es_favorito, es_ofertada=None)
        
    def gestionar_ofertada(self, ca_id: int, es_ofertada: bool): 
        self._gestionar_seguimiento(ca_id, es_favorito=None, es_ofertada=es_ofertada)

    def _gestionar_seguimiento(self, ca_id: int, es_favorito: Optional[bool] = None, es_ofertada: Optional[bool] = None):
        with self.session_factory() as session:
            try:
                seguimiento = session.get(CaSeguimiento, ca_id)
                if seguimiento:
                    if es_favorito is not None: seguimiento.es_favorito = es_favorito
                    if es_ofertada is not None: seguimiento.es_ofertada = es_ofertada
                    if es_ofertada: seguimiento.es_favorito = True
                elif es_favorito or es_ofertada:
                    nuevo = CaSeguimiento(ca_id=ca_id, es_favorito=es_favorito or es_ofertada, es_ofertada=es_ofertada if es_ofertada is not None else False)
                    session.add(nuevo)
                session.commit()
            except Exception as e: logger.error(f"Error seguimiento {ca_id}: {e}"); session.rollback()

    def gestionar_oculta(self, ca_id: int, ocultar: bool = True):
        with self.session_factory() as session:
            try:
                seguimiento = session.get(CaSeguimiento, ca_id)
                if seguimiento:
                    seguimiento.es_oculta = ocultar
                    if ocultar: seguimiento.es_favorito = False; seguimiento.es_ofertada = False
                else:
                    nuevo = CaSeguimiento(ca_id=ca_id, es_oculta=ocultar)
                    session.add(nuevo)
                session.commit()
            except Exception as e: logger.error(f"Error ocultando {ca_id}: {e}"); session.rollback()

    def agregar_nota(self, ca_id: int, nota: str):
        with self.session_factory() as session:
            try:
                seguimiento = session.get(CaSeguimiento, ca_id)
                if seguimiento: seguimiento.notas = nota
                else: nuevo = CaSeguimiento(ca_id=ca_id, notas=nota); session.add(nuevo)
                session.commit()
            except Exception as e: logger.error(f"Error nota {ca_id}: {e}"); session.rollback()

    # --- CONFIGURACIÓN ---

    def get_all_keywords(self) -> List[CaKeyword]:
        with self.session_factory() as session: return session.scalars(select(CaKeyword).order_by(CaKeyword.keyword)).all()

    def add_keyword(self, keyword: str, tipo: str, puntos: int) -> CaKeyword:
        with self.session_factory() as session:
            nuevo = CaKeyword(keyword=keyword.lower().strip())
            if tipo in ["titulo_pos", "titulo_neg"]: nuevo.puntos_nombre = puntos; nuevo.puntos_descripcion = puntos 
            elif tipo == "producto": nuevo.puntos_productos = puntos
            session.add(nuevo); session.commit(); session.refresh(nuevo); return nuevo

    def delete_keyword(self, keyword_id: int):
        with self.session_factory() as session: session.query(CaKeyword).filter_by(keyword_id=keyword_id).delete(); session.commit()

    def get_all_organismo_reglas(self) -> List[CaOrganismoRegla]:
        with self.session_factory() as session: return session.scalars(select(CaOrganismoRegla).options(joinedload(CaOrganismoRegla.organismo))).all()

    def set_organismo_regla(self, organismo_id: int, tipo_str: str, puntos: Optional[int] = None) -> CaOrganismoRegla:
        with self.session_factory() as session:
            stmt = select(CaOrganismoRegla).where(CaOrganismoRegla.organismo_id == organismo_id)
            regla = session.scalars(stmt).first()
            if regla: regla.tipo = tipo_str; regla.puntos = puntos
            else: regla = CaOrganismoRegla(organismo_id=organismo_id, tipo=tipo_str, puntos=puntos); session.add(regla)
            session.commit(); session.refresh(regla); return regla

    def delete_organismo_regla(self, organismo_id: int):
        with self.session_factory() as session:
            stmt = select(CaOrganismoRegla).where(CaOrganismoRegla.organismo_id == organismo_id)
            regla = session.scalars(stmt).first()
            if regla: session.delete(regla); session.commit()

    def get_all_organisms(self) -> List[CaOrganismo]:
        with self.session_factory() as session: return session.scalars(select(CaOrganismo).order_by(CaOrganismo.nombre)).all()
            
    # --- EXPORTACIÓN ---
    def obtener_datos_exportacion_tab1(self) -> List[Dict]:
        with self.session_factory() as session: objs = self.obtener_datos_tab1_candidatas(umbral_minimo=0); return self._to_dict_safe(objs)
    def obtener_datos_exportacion_tab3(self) -> List[Dict]:
        with self.session_factory() as session: objs = self.obtener_datos_tab3_seguimiento(); return self._to_dict_safe(objs)
    def obtener_datos_exportacion_tab4(self) -> List[Dict]:
        with self.session_factory() as session: objs = self.obtener_datos_tab4_ofertadas(); return self._to_dict_safe(objs)
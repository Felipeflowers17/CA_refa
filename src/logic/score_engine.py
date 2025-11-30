# -*- coding: utf-8 -*-
"""
Motor de Puntajes.

Este módulo contiene el algoritmo de priorización de licitaciones.
Trabaja en memoria (RAM) para evaluar miles de registros en milisegundos.
"""
import unicodedata
import json
from typing import Dict, List, Tuple, Any, Set
from src.utils.logger import configurar_logger
from config.config import PUNTOS_SEGUNDO_LLAMADO

logger = configurar_logger(__name__)

class MotorPuntajes:
    """
    Clase encargada de calcular el puntaje (Score) de cada licitación
    basándose en reglas configurables (Palabras clave y Organismos).
    """
    
    def __init__(self, db_service):
        self.db_service = db_service
        
        # Cache optimizado: estructuras en memoria para evitar consultas a BD por cada fila.
        self.cache_palabras_clave: List[Dict[str, Any]] = [] 
        self.reglas_prioritarias: Dict[int, int] = {}
        self.reglas_no_deseadas: Set[int] = set()
        self.mapa_nombre_id_organismo: Dict[str, int] = {}
        
        # Carga inicial de reglas
        self.recargar_reglas_memoria()

    def recargar_reglas_memoria(self):
        """
        Carga todas las reglas de negocio (Keywords y Organismos) desde la BD
        hacia la memoria RAM para un cálculo rápido.
        """
        logger.info("MotorPuntajes: Actualizando caché de reglas en memoria...")
        
        # 1. Cargar Palabras Clave
        self.cache_palabras_clave = []
        try:
            keywords_orm = self.db_service.obtener_todas_palabras_clave()
            for kw in keywords_orm:
                self.cache_palabras_clave.append({
                    "keyword": kw.keyword,
                    "norm": self._normalizar_texto(kw.keyword), # Pre-cálculo de normalización
                    "p_nom": kw.puntos_nombre or 0,
                    "p_desc": kw.puntos_descripcion or 0,
                    "p_prod": kw.puntos_productos or 0
                })
        except Exception as e: 
            logger.error(f"Error cargando palabras clave: {e}")

        # 2. Cargar Reglas de Organismos
        self.reglas_prioritarias = {}
        self.reglas_no_deseadas = set()
        try:
            reglas = self.db_service.obtener_reglas_organismos()
            for r in reglas:
                # Manejo robusto de Enum (si viene como objeto o string)
                tipo_val = r.tipo.value if hasattr(r.tipo, 'value') else r.tipo
                
                if tipo_val == 'prioritario': 
                    self.reglas_prioritarias[r.organismo_id] = r.puntos
                elif tipo_val == 'no_deseado': 
                    self.reglas_no_deseadas.add(r.organismo_id)
        except Exception as e:
            logger.error(f"Error cargando reglas de organismos: {e}")

        # 3. Mapa de Nombres de Organismos (Para Fase 1 donde a veces solo tenemos el nombre)
        self.mapa_nombre_id_organismo = {}
        try:
            orgs = self.db_service.obtener_todos_organismos()
            for o in orgs:
                if o.nombre: 
                    self.mapa_nombre_id_organismo[self._normalizar_texto(o.nombre)] = o.organismo_id
        except Exception as e:
            logger.error(f"Error mapeando nombres de organismos: {e}")

    def _normalizar_texto(self, texto: Any) -> str: 
        """
        Estandariza el texto para comparaciones:
        - Convierte a minúsculas.
        - Elimina tildes.
        - Elimina espacios duplicados.
        """
        if not texto: 
            return ""
        # Separar caracteres base de sus acentos (Mn)
        s = ''.join(c for c in unicodedata.normalize('NFD', str(texto).lower()) if unicodedata.category(c) != 'Mn')
        return " ".join(s.split())

    def calcular_puntaje_fase_1(self, licitacion_raw: dict) -> Tuple[int, List[str]]:
        """
        Calcula el puntaje base usando información preliminar:
        - Nombre de la licitación.
        - Organismo comprador.
        - Estado (ej: 2do llamado).
        """
        org_norm = self._normalizar_texto(licitacion_raw.get("organismo_comprador"))
        nom_norm = self._normalizar_texto(licitacion_raw.get("nombre"))
        
        puntaje = 0
        detalle = []

        if not nom_norm: 
            return 0, ["Error: Sin nombre"]

        # 1. Evaluar Organismo
        org_id = self.mapa_nombre_id_organismo.get(org_norm)
        
        # Fallback: Búsqueda parcial si no hay match exacto
        if not org_id:
            for name_key, oid in self.mapa_nombre_id_organismo.items():
                if name_key in org_norm: 
                    org_id = oid
                    break

        if org_id:
            if org_id in self.reglas_no_deseadas: 
                return -9999, ["Organismo No Deseado"]
            if org_id in self.reglas_prioritarias: 
                pts = self.reglas_prioritarias[org_id]
                puntaje += pts
                detalle.append(f"Org. Prioritario (+{pts})")

        # 2. Evaluar Estado (Bonificación por 2do llamado)
        est_norm = self._normalizar_texto(licitacion_raw.get("estado_ca_texto"))
        if "segundo llamado" in est_norm: 
            puntaje += PUNTOS_SEGUNDO_LLAMADO
            if PUNTOS_SEGUNDO_LLAMADO != 0:
                detalle.append(f"2° Llamado (+{PUNTOS_SEGUNDO_LLAMADO})")
        
        # 3. Evaluar Keywords en Título
        for kw_dict in self.cache_palabras_clave:
            if kw_dict["p_nom"] != 0 and kw_dict["norm"] in nom_norm:
                pts = kw_dict["p_nom"]
                puntaje += pts
                detalle.append(f"KW Título: '{kw_dict['keyword']}' (+{pts})")
                
        return max(0, puntaje), detalle

    def calcular_puntaje_fase_2(self, datos_ficha: dict) -> Tuple[int, List[str]]:
        """
        Calcula puntaje avanzado usando información profunda:
        - Descripción completa.
        - Listado de productos solicitados.
        """
        puntaje = 0
        detalle = []
        
        desc_norm = self._normalizar_texto(datos_ficha.get("descripcion"))
        
        # Procesamiento seguro de productos (puede venir como JSON string, list o None)
        prods_raw = datos_ficha.get("productos_solicitados")
        if isinstance(prods_raw, str):
            try: 
                prods_raw = json.loads(prods_raw)
            except: 
                prods_raw = []
        elif prods_raw is None:
            prods_raw = []
            
        # Aplanar lista de productos a un solo string para búsqueda rápida
        txt_prods_norm = ""
        if isinstance(prods_raw, list):
            parts = []
            for p in prods_raw:
                if isinstance(p, dict):
                    n = p.get("nombre") or ""
                    d = p.get("descripcion") or ""
                    parts.append(self._normalizar_texto(f"{n} {d}"))
            txt_prods_norm = " | ".join(parts)

        # Evaluar Keywords
        for kw_dict in self.cache_palabras_clave:
            kw_norm = kw_dict["norm"]
            if not kw_norm: continue
            
            # Revisar Descripción
            if kw_dict["p_desc"] != 0 and desc_norm and kw_norm in desc_norm:
                pts = kw_dict["p_desc"]
                puntaje += pts
                detalle.append(f"KW Descripcion: '{kw_dict['keyword']}' (+{pts})")
            
            # Revisar Productos
            if kw_dict["p_prod"] != 0 and txt_prods_norm and kw_norm in txt_prods_norm:
                pts = kw_dict["p_prod"]
                puntaje += pts
                detalle.append(f"KW Producto: '{kw_dict['keyword']}' (+{pts})")
                
        return puntaje, detalle
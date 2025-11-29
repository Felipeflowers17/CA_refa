# -*- coding: utf-8 -*-
import unicodedata
import json
from typing import Dict, List, Tuple, Optional, Any
from src.utils.logger import configurar_logger
from config.config import PUNTOS_SEGUNDO_LLAMADO

logger = configurar_logger(__name__)

class ScoreEngine:
    def __init__(self, db_service):
        self.db_service = db_service
        # Cache optimizado: lista de dicts para acceso rápido sin tocar BD
        self.keywords_cache: List[Dict[str, Any]] = [] 
        self.reglas_prioritarias: Dict[int, int] = {}
        self.reglas_no_deseadas: set = set()
        self.organismo_name_to_id_map: Dict[str, int] = {}
        
        # Carga inicial
        self.recargar_reglas()

    def recargar_reglas(self):
        """Carga todas las reglas de negocio en memoria RAM para cálculo ultrarrápido."""
        logger.info("ScoreEngine: Recargando reglas y keywords a memoria segura...")
        
        # 1. Cargar Keywords
        self.keywords_cache = []
        try:
            keywords_orm = self.db_service.get_all_keywords()
            for kw in keywords_orm:
                self.keywords_cache.append({
                    "keyword": kw.keyword,
                    "norm": self._norm(kw.keyword), # Pre-cálculo de normalización
                    "p_nom": kw.puntos_nombre or 0,
                    "p_desc": kw.puntos_descripcion or 0,
                    "p_prod": kw.puntos_productos or 0
                })
        except Exception as e: 
            logger.error(f"Error cargando keywords: {e}")

        # 2. Cargar Reglas de Organismos
        self.reglas_prioritarias = {}
        self.reglas_no_deseadas = set()
        try:
            reglas = self.db_service.get_all_organismo_reglas()
            for r in reglas:
                # Manejo robusto de Enum (si viene como objeto o string)
                tipo_val = r.tipo.value if hasattr(r.tipo, 'value') else r.tipo
                
                if tipo_val == 'prioritario': 
                    self.reglas_prioritarias[r.organismo_id] = r.puntos
                elif tipo_val == 'no_deseado': 
                    self.reglas_no_deseadas.add(r.organismo_id)
        except Exception as e:
            logger.error(f"Error cargando reglas organismos: {e}")

        # 3. Mapa de Nombres de Organismos (Para Fase 1 donde no siempre tenemos ID)
        self.organismo_name_to_id_map = {}
        try:
            orgs = self.db_service.get_all_organisms()
            for o in orgs:
                if o.nombre: 
                    self.organismo_name_to_id_map[self._norm(o.nombre)] = o.organismo_id
        except Exception as e:
            logger.error(f"Error mapeando organismos: {e}")

    def _norm(self, txt: Any) -> str: 
        """Normaliza texto: minúsculas, sin tildes, sin espacios extra."""
        if not txt: return ""
        # NFD separa caracteres base de sus acentos (Mn)
        s = ''.join(c for c in unicodedata.normalize('NFD', str(txt).lower()) if unicodedata.category(c) != 'Mn')
        return " ".join(s.split())

    def calcular_puntuacion_fase_1(self, licitacion_raw: dict) -> Tuple[int, List[str]]:
        """Calcula puntaje base usando Nombre, Organismo y Estado."""
        org_norm = self._norm(licitacion_raw.get("organismo_comprador"))
        nom_norm = self._norm(licitacion_raw.get("nombre"))
        
        puntaje = 0
        detalle = []

        if not nom_norm: 
            return 0, ["Sin nombre"]

        # 1. Evaluar Organismo
        org_id = self.organismo_name_to_id_map.get(org_norm)
        
        # Fallback: Búsqueda parcial si no hay match exacto
        if not org_id:
            for name_key, oid in self.organismo_name_to_id_map.items():
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

        # 2. Evaluar Estado (2do llamado)
        est_norm = self._norm(licitacion_raw.get("estado_ca_texto"))
        if "segundo llamado" in est_norm: 
            puntaje += PUNTOS_SEGUNDO_LLAMADO
            if PUNTOS_SEGUNDO_LLAMADO != 0:
                detalle.append(f"2° Llamado (+{PUNTOS_SEGUNDO_LLAMADO})")
        
        # 3. Evaluar Keywords en Título
        for kw_dict in self.keywords_cache:
            if kw_dict["p_nom"] != 0 and kw_dict["norm"] in nom_norm:
                pts = kw_dict["p_nom"]
                puntaje += pts
                detalle.append(f"KW Título: '{kw_dict['keyword']}' (+{pts})")
                
        return max(0, puntaje), detalle

    def calcular_puntuacion_fase_2(self, datos_ficha: dict) -> Tuple[int, List[str]]:
        """Calcula puntaje avanzado usando Descripción y Productos (detalle)."""
        puntaje = 0
        detalle = []
        
        desc_norm = self._norm(datos_ficha.get("descripcion"))
        
        # Procesamiento seguro de productos (puede venir como JSON string, list o None)
        prods_raw = datos_ficha.get("productos_solicitados")
        if isinstance(prods_raw, str):
            try: prods_raw = json.loads(prods_raw)
            except: prods_raw = []
        elif prods_raw is None:
            prods_raw = []
            
        # Aplanar lista de productos a un string buscable
        txt_prods_norm = ""
        if isinstance(prods_raw, list):
            parts = []
            for p in prods_raw:
                if isinstance(p, dict):
                    n = p.get("nombre") or ""
                    d = p.get("descripcion") or ""
                    parts.append(self._norm(f"{n} {d}"))
            txt_prods_norm = " | ".join(parts)

        # Evaluar Keywords
        for kw_dict in self.keywords_cache:
            kw_norm = kw_dict["norm"]
            if not kw_norm: continue
            
            # Check Descripción
            if kw_dict["p_desc"] != 0 and desc_norm and kw_norm in desc_norm:
                pts = kw_dict["p_desc"]
                puntaje += pts
                detalle.append(f"KW Descripcion: '{kw_dict['keyword']}' (+{pts})")
            
            # Check Productos
            if kw_dict["p_prod"] != 0 and txt_prods_norm and kw_norm in txt_prods_norm:
                pts = kw_dict["p_prod"]
                puntaje += pts
                detalle.append(f"KW Producto: '{kw_dict['keyword']}' (+{pts})")
                
        return puntaje, detalle
# -*- coding: utf-8 -*-
"""
Motor de Puntajes.

Este módulo contiene el algoritmo de priorización de licitaciones.
Implementa lógica de 'Masking' para evitar puntuación doble en frases contenidas.
"""
import unicodedata
import json
from functools import lru_cache
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
        
        self.cache_palabras_clave: List[Dict[str, Any]] = [] 
        self.reglas_prioritarias: Dict[int, int] = {}
        self.reglas_no_deseadas: Dict[int, int] = {} 
        
        self.mapa_nombre_id_organismo: Dict[str, int] = {}
        self.recargar_reglas_memoria()

    def recargar_reglas_memoria(self):
        """
        Carga reglas desde la BD y las ordena por longitud (DESC) para el masking.
        """
        logger.info("MotorPuntajes: Actualizando caché de reglas en memoria...")
        
        # 1. Cargar Palabras Clave
        self.cache_palabras_clave = []
        try:
            keywords_orm = self.db_service.obtener_todas_palabras_clave()
            for kw in keywords_orm:
                self.cache_palabras_clave.append({
                    "keyword": kw.keyword,
                    "norm": self._normalizar_texto(kw.keyword),
                    "p_nom": kw.puntos_nombre or 0,
                    "p_desc": kw.puntos_descripcion or 0,
                    "p_prod": kw.puntos_productos or 0
                })
            
            # --- ORDENAMIENTO CRÍTICO ---
            # Ordenamos por longitud descendente del texto normalizado.
            # "materiales de ferreteria" (24 chars) se evaluará antes que "ferreteria" (10 chars).
            self.cache_palabras_clave.sort(key=lambda x: len(x["norm"]), reverse=True)
            
        except Exception as e: 
            logger.error(f"Error cargando palabras clave: {e}")

        # 2. Cargar Reglas de Organismos
        self.reglas_prioritarias = {}
        self.reglas_no_deseadas = {} # Reiniciar como Diccionario
        try:
            reglas = self.db_service.obtener_reglas_organismos()
            for r in reglas:
                tipo_val = r.tipo.value if hasattr(r.tipo, 'value') else r.tipo
                
                if tipo_val == 'prioritario': 
                    self.reglas_prioritarias[r.organismo_id] = r.puntos
                elif tipo_val == 'no_deseado': 
                    # Si viene None, forzamos un -100 por defecto
                    self.reglas_no_deseadas[r.organismo_id] = r.puntos if r.puntos is not None else -100

        except Exception as e:
            logger.error(f"Error cargando reglas de organismos: {e}")

        # 3. Mapa de Nombres de Organismos
        self.mapa_nombre_id_organismo = {}
        try:
            orgs = self.db_service.obtener_todos_organismos()
            for o in orgs:
                if o.nombre: 
                    self.mapa_nombre_id_organismo[self._normalizar_texto(o.nombre)] = o.organismo_id
        except Exception as e:
            logger.error(f"Error mapeando nombres de organismos: {e}")

    @lru_cache(maxsize=4096)
    def _normalizar_texto(self, texto: Any) -> str:
        if not texto:
            return ""
        
        texto_str = str(texto)
        s = ''.join(c for c in unicodedata.normalize('NFD', texto_str.lower()) if unicodedata.category(c) != 'Mn')
        return " ".join(s.split())

    def _evaluar_con_masking(self, texto_base: str, campo_puntaje: str, etiqueta: str) -> Tuple[int, List[str]]:
        """
        Aplica la lógica de 'Masking' (Enmascaramiento).
        Si encuentra una keyword, suma puntos y la tacha del texto para que no vuelva a contar.
        """
        if not texto_base: return 0, []
        
        puntaje_acumulado = 0
        detalle_acumulado = []
        
        # Copia de trabajo para ir "tachando" (reemplazando por ####)
        texto_trabajo = texto_base
        
        for kw_dict in self.cache_palabras_clave:
            puntos = kw_dict[campo_puntaje]
            if puntos == 0: continue
            
            termino = kw_dict["norm"]
            if not termino: continue
            
            # Si el término está en el texto (que ya puede tener partes tachadas)
            if termino in texto_trabajo:
                puntaje_acumulado += puntos
                detalle_acumulado.append(f"KW {etiqueta}: '{kw_dict['keyword']}' ({'+' if puntos>0 else ''}{puntos})")
                
                # --- MASKING ---
                # Reemplazamos la ocurrencia por un marcador inútil del mismo largo.
                # Ej: "materiales de ferreteria" -> "########################"
                mascara = "#" * len(termino)
                texto_trabajo = texto_trabajo.replace(termino, mascara)
        
        return puntaje_acumulado, detalle_acumulado

    def calcular_puntaje_fase_1(self, licitacion_raw: dict) -> Tuple[int, List[str]]:
        """Calcula puntaje base (Organismo + Estado + Título)."""
        org_norm = self._normalizar_texto(licitacion_raw.get("organismo_comprador"))
        nom_norm = self._normalizar_texto(licitacion_raw.get("nombre"))
        
        puntaje = 0
        detalle = []

        if not nom_norm: 
            return 0, ["Error: Sin nombre"]

        # 1. Evaluar Organismo
        org_id = self.mapa_nombre_id_organismo.get(org_norm)
        if not org_id:
            for name_key, oid in self.mapa_nombre_id_organismo.items():
                if name_key in org_norm: 
                    org_id = oid; break

        if org_id:
            if org_id in self.reglas_no_deseadas:
                pts = self.reglas_no_deseadas[org_id]
                return pts, [f"Organismo No Deseado ({pts})"]
                
            if org_id in self.reglas_prioritarias: 
                pts = self.reglas_prioritarias[org_id]
                puntaje += pts
                detalle.append(f"Org. Prioritario ({'+' if pts>0 else ''}{pts})")

        # 2. Evaluar Estado
        est_norm = self._normalizar_texto(licitacion_raw.get("estado_ca_texto"))
        if "segundo llamado" in est_norm: 
            puntaje += PUNTOS_SEGUNDO_LLAMADO
            if PUNTOS_SEGUNDO_LLAMADO != 0:
                detalle.append(f"2° Llamado (+{PUNTOS_SEGUNDO_LLAMADO})")
        
        # 3. Evaluar Título (Con Masking)
        pts_nom, det_nom = self._evaluar_con_masking(nom_norm, "p_nom", "Título")
        puntaje += pts_nom
        detalle.extend(det_nom)
                
        return max(0, puntaje), detalle

    def calcular_puntaje_fase_2(self, datos_ficha: dict) -> Tuple[int, List[str]]:
        """Calcula puntaje avanzado (Descripción + Productos)."""
        puntaje = 0
        detalle = []
        
        # 1. Evaluar Descripción
        desc_norm = self._normalizar_texto(datos_ficha.get("descripcion"))
        if desc_norm:
            pts_desc, det_desc = self._evaluar_con_masking(desc_norm, "p_desc", "Desc.")
            puntaje += pts_desc
            detalle.extend(det_desc)
        
        # 2. Evaluar Productos
        prods_raw = datos_ficha.get("productos_solicitados")
        if isinstance(prods_raw, str):
            try: prods_raw = json.loads(prods_raw)
            except: prods_raw = []
        elif prods_raw is None:
            prods_raw = []
            
        txt_prods_norm = ""
        if isinstance(prods_raw, list):
            parts = []
            for p in prods_raw:
                if isinstance(p, dict):
                    n = p.get("nombre") or ""
                    d = p.get("descripcion") or ""
                    parts.append(self._normalizar_texto(f"{n} {d}"))
            txt_prods_norm = " | ".join(parts)

        if txt_prods_norm:
            pts_prod, det_prod = self._evaluar_con_masking(txt_prods_norm, "p_prod", "Prod.")
            puntaje += pts_prod
            detalle.extend(det_prod)
                
        return puntaje, detalle
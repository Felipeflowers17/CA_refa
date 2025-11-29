# -*- coding: utf-8 -*-
import os
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Any

import pandas as pd

# Importamos modelos solo para tipos y referencias de Pandas
from src.db.db_models import (
    CaLicitacion, CaSector, CaOrganismo, 
    CaSeguimiento, CaKeyword, CaOrganismoRegla
)

if TYPE_CHECKING:
    from src.db.db_service import DbService

from src.utils.logger import configurar_logger

logger = configurar_logger(__name__)

class ExcelService:
    def __init__(self, db_service: "DbService"):
        self.db_service = db_service
        logger.info("ExcelService inicializado.")

    def ejecutar_exportacion_lote(self, lista_tareas: List[Dict], base_path: str) -> List[str]:
        """
        Ejecuta múltiples exportaciones en una carpeta con timestamp.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        try:
            export_root = Path(base_path) / "export"
            session_folder = export_root / timestamp
            os.makedirs(session_folder, exist_ok=True)
        except Exception as e:
            return [f"ERROR CRÍTICO: No se pudo crear carpeta en {base_path}: {e}"]

        resultados = []
        for tarea in lista_tareas:
            tipo = tarea.get("tipo")
            formato = tarea.get("format", "excel")
            
            try:
                ruta = ""
                if tipo == "tabs":
                    ruta = self.generar_reporte_pestañas(tarea, session_folder)
                elif tipo == "config":
                    ruta = self.generar_reporte_configuracion(formato, session_folder)
                elif tipo == "bd_full":
                    ruta = self.generar_reporte_bd_completa(formato, session_folder)
                
                if ruta:
                    resultados.append(f"[{tipo.upper()}] -> {ruta}")
                else:
                    resultados.append(f"ERROR [{tipo.upper()}] -> Ruta vacía.")

            except Exception as e:
                logger.error(f"Error en exportación ({tipo}): {e}", exc_info=True)
                resultados.append(f"ERROR [{tipo.upper()}] -> {str(e)}")
        
        return resultados

    def _convertir_a_dataframe(self, datos_dict: List[Dict]) -> pd.DataFrame:
        """Convierte lista de diccionarios (del DbService) a DataFrame formateado."""
        datos = []
        for item in datos_dict:
            # Manejo seguro de fechas para evitar errores en Excel
            f_cierre = item.get("fecha_cierre")
            f_cierre_2 = item.get("fecha_cierre_segundo_llamado")
            
            fecha_cierre_ingenua = f_cierre.replace(tzinfo=None) if f_cierre else None
            fecha_cierre_2_ingenua = f_cierre_2.replace(tzinfo=None) if f_cierre_2 else None

            datos.append({
                "Score": item.get("puntuacion_final"),
                "Código CA": item.get("codigo_ca"),
                "Nombre": item.get("nombre"),
                "Descripcion": item.get("descripcion"),
                "Organismo": item.get("organismo_nombre"),
                "Dirección Entrega": item.get("direccion_entrega"),
                "Estado": item.get("estado_ca_texto"),
                "Fecha Publicación": item.get("fecha_publicacion"),
                "Fecha Cierre": fecha_cierre_ingenua,
                "Fecha Cierre 2do Llamado": fecha_cierre_2_ingenua,
                "Proveedores": item.get("proveedores_cotizando"),
                "Productos": str(item.get("productos_solicitados")) if item.get("productos_solicitados") else None,
                "Favorito": "Sí" if item.get("es_favorito") else "No",
                "Ofertada": "Sí" if item.get("es_ofertada") else "No",
            })
        
        columnas = [
            "Score", "Código CA", "Nombre", "Descripcion", "Organismo",
            "Dirección Entrega", "Estado", "Fecha Publicación", "Fecha Cierre",
            "Fecha Cierre 2do Llamado", "Productos", "Proveedores",
            "Favorito", "Ofertada"
        ]
        if not datos:
            return pd.DataFrame(columns=columnas)
        return pd.DataFrame(datos).reindex(columns=columnas)

    def generar_reporte_pestañas(self, options: dict, target_dir: Path) -> str:
        formato = options.get("format", "excel")
        dfs_to_export: Dict[str, pd.DataFrame] = {}

        # 1. Obtenemos datos crudos (diccionarios) desde el DbService
        datos_tab1 = self.db_service.obtener_datos_exportacion_tab1()
        datos_tab3 = self.db_service.obtener_datos_exportacion_tab3()
        datos_tab4 = self.db_service.obtener_datos_exportacion_tab4()
        
        # 2. Convertimos a DataFrames
        dfs_to_export["Candidatas"] = self._convertir_a_dataframe(datos_tab1)
        dfs_to_export["Seguimiento"] = self._convertir_a_dataframe(datos_tab3)
        dfs_to_export["Ofertadas"] = self._convertir_a_dataframe(datos_tab4)

        return self._guardar_archivos(dfs_to_export, formato, "Reporte_Gestion", target_dir)

    def generar_reporte_configuracion(self, formato: str, target_dir: Path) -> str:
        logger.info("Exportando Configuración...")
        dfs_to_export = {}
        
        # 1. Keywords (Usando DbService, sin sesión manual)
        keywords = self.db_service.get_all_keywords()
        data_kw = [{
            "Keyword": k.keyword,
            "Puntos Nombre": k.puntos_nombre,
            "Puntos Descripcion": k.puntos_descripcion,
            "Puntos Productos": k.puntos_productos
        } for k in keywords]
        dfs_to_export["Keywords"] = pd.DataFrame(data_kw)
        
        # 2. Reglas Organismos
        reglas = self.db_service.get_all_organismo_reglas()
        data_org = []
        for r in reglas:
            tipo_val = r.tipo.value if hasattr(r.tipo, 'value') else r.tipo
            data_org.append({
                "Organismo": r.organismo.nombre if r.organismo else "Desconocido",
                "Tipo Regla": tipo_val,
                "Puntos": r.puntos
            })
        dfs_to_export["Reglas_Organismos"] = pd.DataFrame(data_org)

        return self._guardar_archivos(dfs_to_export, formato, "Configuracion_Reglas", target_dir)

    def generar_reporte_bd_completa(self, formato: str, target_dir: Path) -> str:
        """Dump completo de la base de datos (Backup)."""
        dfs_to_export = {}
        tablas = [CaLicitacion, CaSeguimiento, CaOrganismo, CaSector, CaKeyword, CaOrganismoRegla]
        
        try:
            # Aquí sí necesitamos una conexión raw para pandas.read_sql
            # Usamos el session_factory inyectado en DbService
            with self.db_service.session_factory() as session:
                connection = session.connection()
                for model in tablas:
                    table_name = model.__tablename__
                    df = pd.read_sql_table(table_name, con=connection)
                    
                    # Limpieza de zonas horarias
                    for col in df.columns:
                        if pd.api.types.is_datetime64_any_dtype(df[col]):
                            try: df[col] = df[col].dt.tz_localize(None)
                            except: pass
                    
                    dfs_to_export[table_name] = df
        except Exception as e:
            logger.error(f"Error leyendo BD completa: {e}", exc_info=True)
            raise e
            
        return self._guardar_archivos(dfs_to_export, formato, "Backup_BD_Completa", target_dir)

    def _guardar_archivos(self, dfs: Dict[str, pd.DataFrame], formato: str, prefijo: str, target_dir: Path) -> str:
        if formato == "excel":
            nombre = f"{prefijo}.xlsx"
            ruta = target_dir / nombre
            try:
                with pd.ExcelWriter(ruta, engine="openpyxl") as writer:
                    for sheet, df in dfs.items():
                        safe_sheet = sheet[:30] # Limitación de Excel
                        df.to_excel(writer, sheet_name=safe_sheet, index=False)
                return str(ruta)
            except Exception as e:
                logger.error(f"Error guardando Excel: {e}")
                raise e
        else:
            # CSV: Genera múltiples archivos
            try:
                for sheet, df in dfs.items():
                    nombre_csv = f"{prefijo}_{sheet}.csv"
                    ruta_csv = target_dir / nombre_csv
                    df.to_csv(ruta_csv, index=False, encoding='utf-8-sig', sep=';') # punto y coma para Excel español
                return str(target_dir) 
            except Exception as e:
                logger.error(f"Error guardando CSVs: {e}")
                raise e
# -*- coding: utf-8 -*-
"""
Servicio de Exportación (Excel/CSV).

Gestiona la generación de reportes utilizando Pandas.
Permite exportar vistas de gestión (pestañas) y copias de seguridad de la BD.
"""
import os
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Any

import pandas as pd

# Importamos modelos solo para tipos y referencias de Pandas
from src.db.db_models import (
    CaLicitacion, CaSector, CaOrganismo, 
    CaSeguimiento, CaPalabraClave, CaOrganismoRegla
)

if TYPE_CHECKING:
    from src.db.db_service import DbService

from src.utils.logger import configurar_logger

logger = configurar_logger(__name__)

class ServicioExcel:
    def __init__(self, db_service: "DbService"):
        self.db_service = db_service
        logger.info("ServicioExcel inicializado correctamente.")

    def ejecutar_exportacion_lote(self, lista_tareas: List[Dict], ruta_base: str) -> List[str]:
        """
        Ejecuta múltiples tareas de exportación en una carpeta organizada por fecha.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        try:
            raiz_exportacion = Path(ruta_base) / "export"
            carpeta_sesion = raiz_exportacion / timestamp
            os.makedirs(carpeta_sesion, exist_ok=True)
        except Exception as e:
            return [f"ERROR CRÍTICO: No se pudo crear carpeta en {ruta_base}: {e}"]

        resultados = []
        for tarea in lista_tareas:
            tipo = tarea.get("tipo")
            formato = tarea.get("format", "excel")
            
            try:
                ruta_generada = ""
                if tipo == "tabs":
                    ruta_generada = self.generar_reporte_gestion(tarea, carpeta_sesion)
                elif tipo == "config":
                    ruta_generada = self.generar_reporte_configuracion(formato, carpeta_sesion)
                elif tipo == "bd_full":
                    ruta_generada = self.generar_backup_bd_completa(formato, carpeta_sesion)
                
                if ruta_generada:
                    resultados.append(f"[{tipo.upper()}] -> {ruta_generada}")
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
            # Manejo seguro de fechas para evitar errores de timezone en Excel
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

    def generar_reporte_gestion(self, opciones: dict, directorio_destino: Path) -> str:
        """Exporta las pestañas principales (Candidatas, Seguimiento, Ofertadas)."""
        formato = opciones.get("format", "excel")
        dfs_para_exportar: Dict[str, pd.DataFrame] = {}

        # 1. Obtenemos datos crudos (diccionarios) usando los nuevos métodos del DbService
        datos_tab1 = self.db_service.exportar_candidatas()
        datos_tab3 = self.db_service.exportar_seguimiento()
        datos_tab4 = self.db_service.exportar_ofertadas()
        
        # 2. Convertimos a DataFrames
        dfs_para_exportar["Candidatas"] = self._convertir_a_dataframe(datos_tab1)
        dfs_para_exportar["Seguimiento"] = self._convertir_a_dataframe(datos_tab3)
        dfs_para_exportar["Ofertadas"] = self._convertir_a_dataframe(datos_tab4)

        return self._guardar_archivos(dfs_para_exportar, formato, "Reporte_Gestion", directorio_destino)

    def generar_reporte_configuracion(self, formato: str, directorio_destino: Path) -> str:
        """Exporta las reglas de negocio (Keywords y Organismos) detalladas."""
        logger.info(f"Exportando Configuración en formato {formato}...")
        dfs_para_exportar = {}
        
        # 1. Keywords
        data_kw = self.db_service.exportar_config_keywords()
        dfs_para_exportar["Keywords"] = pd.DataFrame(data_kw)
        
        # 2. Organismos (Todos con su estado)
        data_org = self.db_service.exportar_config_organismos()
        dfs_para_exportar["Organismos_Reglas"] = pd.DataFrame(data_org)

        return self._guardar_archivos(dfs_para_exportar, formato, "Reporte_Configuracion_Reglas", directorio_destino)

    def generar_backup_bd_completa(self, formato: str, directorio_destino: Path) -> str:
        """Genera un volcado completo de todas las tablas (Backup)."""
        dfs_para_exportar = {}
        tablas = [CaLicitacion, CaSeguimiento, CaOrganismo, CaSector, CaPalabraClave, CaOrganismoRegla]
        
        try:
            # Usamos el session_factory inyectado para obtener conexión cruda para Pandas
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
                    
                    dfs_para_exportar[table_name] = df
        except Exception as e:
            logger.error(f"Error leyendo BD completa: {e}", exc_info=True)
            raise e
            
        return self._guardar_archivos(dfs_para_exportar, formato, "Backup_BD_Completa", directorio_destino)

    def _guardar_archivos(self, dfs: Dict[str, pd.DataFrame], formato: str, prefijo: str, directorio_destino: Path) -> str:
        if formato == "excel":
            nombre = f"{prefijo}.xlsx"
            ruta = directorio_destino / nombre
            try:
                with pd.ExcelWriter(ruta, engine="openpyxl") as writer:
                    for sheet, df in dfs.items():
                        safe_sheet = sheet[:30] # Limitación de Excel (31 caracteres)
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
                    ruta_csv = directorio_destino / nombre_csv
                    # encoding 'utf-8-sig' ayuda a que Excel abra bien los caracteres especiales
                    df.to_csv(ruta_csv, index=False, encoding='utf-8-sig', sep=';') 
                return str(directorio_destino) 
            except Exception as e:
                logger.error(f"Error guardando CSVs: {e}")
                raise e
# -*- coding: utf-8 -*-
from PySide6.QtWidgets import QMessageBox, QSystemTrayIcon
from PySide6.QtCore import Slot, Qt
import datetime 

from src.gui.gui_scraping_dialog import ScrapingDialog
from src.gui.gui_export_dialog import GuiExportDialog 
from src.utils.logger import configurar_logger

logger = configurar_logger(__name__)

class MainSlotsMixin:
    """
    Controlador principal de acciones de la barra de herramientas.
    """
    
    # --- ACCIONES DE TABLA ---
    @Slot(object)
    def on_table_double_clicked(self, index):
        if not index.isValid(): return
        proxy = index.model()
        
        # Columna Nota (7)
        if index.column() == 7:
            nota = index.data(Qt.UserRole)
            if nota and str(nota).strip(): QMessageBox.information(self, "Nota", str(nota))
            return

        # Recuperar ID
        ca_id = None
        # Intento 1: UserRole en col 0 o 1
        for c in [0, 1]:
            val = proxy.data(proxy.index(index.row(), c), Qt.UserRole + 1)
            if not val: val = proxy.data(proxy.index(index.row(), c), Qt.UserRole)
            if isinstance(val, int): ca_id = val; break
            
        if not ca_id:
             logger.warning(f"No se pudo identificar la licitación en fila {index.row()}")
             return

        # Cargar detalle
        self.start_task(self.db_service.get_licitacion_by_id, self.on_detail_data_loaded, task_args=(ca_id,))

    def on_detail_data_loaded(self, lic):
        if lic and hasattr(self, 'detail_drawer'):
            self.detail_drawer.set_data(lic)
            self.detail_drawer.open_drawer()

    # --- ACCIONES DE SCRAPING ---
    @Slot()
    def on_open_scraping_dialog(self):
        if self.is_task_running: return
        d = ScrapingDialog(self)
        d.start_scraping.connect(self.on_start_full_scraping)
        d.exec()

    @Slot(dict)
    def on_start_full_scraping(self, config: dict):
        """Maneja el inicio del scraping (manual o desde diálogo)."""
        logger.info(f"Iniciando scraping: {config}")
        
        # Definimos callback interno para manejar el resultado INT
        def handle_etl_result(count):
            logger.info(f"ETL finalizado. Registros: {count}")
            if isinstance(count, int) and count > 0:
                QMessageBox.information(self, "Proceso Completado", f"Se procesaron {count} registros nuevos.")
            elif count == 0:
                QMessageBox.information(self, "Sin Novedades", "No se encontraron licitaciones nuevas.")

        self.start_task(
            task=self.etl_service.run_etl_live_to_db,
            on_result=handle_etl_result, 
            on_error=self.on_task_error,
            on_finished=self.on_scraping_completed,
            on_progress=self.on_progress_update,
            on_progress_percent=self.on_progress_percent_update,
            task_kwargs={"config": config}
        )

    @Slot()
    def on_start_full_scraping_auto(self):
        """Piloto Automático (Fase 1)."""
        if self.is_task_running: return
        
        y = datetime.date.today() - datetime.timedelta(days=1)
        cfg = { "mode": "to_db", "date_from": y, "date_to": datetime.date.today(), "max_paginas": 100 }
        
        self.start_task(
            task=self.etl_service.run_etl_live_to_db,
            on_result=lambda x: logger.info(f"Auto ETL: {x} registros."), 
            on_finished=self.on_auto_task_finished,
            task_kwargs={"config": cfg}
        )

    @Slot()
    def on_scraping_completed(self):
        self.set_ui_busy(False)
        self.on_load_data_thread() # Refrescar tabla
        if self.tray_icon and not self.last_error:
            self.tray_icon.showMessage("Monitor CA", "Scraping finalizado.", QSystemTrayIcon.Information, 3000)

    # --- OTRAS ACCIONES ---
    
    @Slot()
    def on_open_settings_dialog(self):
        if hasattr(self, 'switchTo') and hasattr(self, 'toolsInterface'):
            self.switchTo(self.toolsInterface)
        else:
            QMessageBox.information(self, "Configuración", "Ve a la pestaña 'Herramientas' para configurar reglas.")

    @Slot()
    def on_settings_changed(self):
        logger.info("Configuración actualizada por el usuario.")
        try:
            self.score_engine.recargar_reglas()
            logger.info("Reglas de ScoreEngine recargadas.")
        except Exception as e:
            logger.error(f"Error al recargar reglas: {e}")

    @Slot()
    def on_run_recalculate_thread(self):
        if self.is_task_running: return
        self.start_task(
            task=self.etl_service.run_recalculo_total_fase_1,
            on_finished=self.on_recalculate_finished
        )
        
    @Slot()
    def on_recalculate_finished(self):
        self.set_ui_busy(False)
        self.on_load_data_thread()
        QMessageBox.information(self, "Éxito", "Puntajes recalculados.")

    # --- ESTE ES EL MÉTODO QUE FALTABA ---
    @Slot()
    def on_fase2_update_finished(self):
        self.set_ui_busy(False)
        self.on_load_data_thread() # Refrescar datos
        
        if self.last_error:
            logger.warning(f"Actualización Fase 2 con errores: {self.last_error}")
            QMessageBox.warning(self, "Actualización incompleta", f"Hubo errores: {self.last_error}")
        else:
            logger.info("Actualización Fase 2 terminada.")
            QMessageBox.information(self, "Éxito", "Información actualizada correctamente.")
    # -------------------------------------

    @Slot()
    def on_auto_task_finished(self):
        self.set_ui_busy(False)
        self.on_load_data_thread()
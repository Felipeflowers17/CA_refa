# -*- coding: utf-8 -*-
from PySide6.QtWidgets import QMessageBox, QSystemTrayIcon
from PySide6.QtCore import Slot, Qt
import datetime 
from src.gui.gui_import_dialog import DialogoImportacionManual
from src.gui.gui_scraping_dialog import DialogoScraping
from src.utils.logger import configurar_logger

logger = configurar_logger(__name__)

class MixinSlotsPrincipales:
    """
    Controlador principal que reacciona a los eventos del usuario
    (clics, menús, botones).
    """
    
    # --- ACCIONES DE TABLA (DOBLE CLIC) ---
    @Slot(object)
    def on_table_double_clicked(self, index):
        if not index.isValid(): return
        proxy = index.model()
        

        if index.column() == 7:
            nota = index.data(Qt.UserRole)
            if nota and str(nota).strip(): QMessageBox.information(self, "Nota Guardada", str(nota))
            return

        # Recuperar ID de la licitación
        ca_id = None
        for c in [0, 1]:
            val = proxy.data(proxy.index(index.row(), c), Qt.UserRole + 1)
            if not val: val = proxy.data(proxy.index(index.row(), c), Qt.UserRole)
            if isinstance(val, int): ca_id = val; break
            
        if not ca_id:
             logger.warning(f"No se pudo identificar la licitación en fila {index.row()}")
             return

        # Cargar detalle completo usando DbService 
        self.start_task(self.db_service.obtener_licitacion_por_id, self.on_detail_data_loaded, task_args=(ca_id,))

    def on_detail_data_loaded(self, lic):
        if lic and hasattr(self, 'detail_drawer'):
            self.detail_drawer.set_data(lic)
            self.detail_drawer.open_drawer()

    # --- ACCIONES DE SCRAPING ---
    @Slot()
    def on_open_scraping_dialog(self):
        if self.tarea_en_ejecucion: return
        d = DialogoScraping(self)
        d.start_scraping.connect(self.on_start_full_scraping)
        d.exec()

    @Slot(dict)
    def on_start_full_scraping(self, config: dict):
        """Maneja el inicio del scraping (manual o desde diálogo)."""
        logger.info(f"Iniciando scraping con config: {config}")
        
        # Callback para mostrar mensaje al usuario
        def manejar_resultado_etl(cantidad):
            logger.info(f"ETL finalizado. Registros procesados: {cantidad}")
            if isinstance(cantidad, int) and cantidad > 0:
                QMessageBox.information(self, "Proceso Completado", f"Se procesaron {cantidad} registros nuevos.")
            elif cantidad == 0:
                QMessageBox.information(self, "Sin Novedades", "No se encontraron licitaciones nuevas.")


        self.start_task(
            task=self.servicio_etl.ejecutar_etl_completo,
            on_result=manejar_resultado_etl, 
            on_error=self.on_task_error,
            on_finished=self.on_scraping_completed,
            on_progress=self.on_progress_update,
            on_progress_percent=self.on_progress_percent_update,
            task_kwargs={"configuracion": config}
        )

    @Slot()
    def on_scraping_completed(self):
        self.set_ui_busy(False)
        self.on_load_data_thread() # Refrescar tabla principal de licitaciones
        
        # Si la interfaz de herramientas existe, recargamos la lista de organismos
        if hasattr(self, 'interfazHerramientas'):
            self.interfazHerramientas.cargar_datos_config()
        # ---------------------

        if self.tray_icon and not self.ultimo_error:
            self.tray_icon.showMessage("Monitor CA", "Scraping finalizado exitosamente.", QSystemTrayIcon.Information, 3000)


    @Slot()
    def on_run_recalculate_thread(self):
        if self.tarea_en_ejecucion: return
        # Llamada al recálculo total 
        self.start_task(
            task=self.servicio_etl.ejecutar_recalculo_total,
            on_finished=self.on_recalculate_finished
        )
        
    @Slot()
    def on_recalculate_finished(self):
        self.set_ui_busy(False)
        self.on_load_data_thread()
        QMessageBox.information(self, "Éxito", "Todos los puntajes han sido recalculados.")

    @Slot()
    def on_fase2_update_finished(self):
        self.set_ui_busy(False)
        self.on_load_data_thread() # Refrescar datos
        
        if self.ultimo_error:
            logger.warning(f"Actualización Fase 2 con errores: {self.ultimo_error}")
            QMessageBox.warning(self, "Actualización incompleta", f"Hubo errores: {self.ultimo_error}")
        else:
            logger.info("Actualización Fase 2 terminada.")
            QMessageBox.information(self, "Éxito", "Información actualizada correctamente desde Mercado Público.")
            
    @Slot()
    def on_auto_task_finished(self):
        """Callback genérico para tareas automáticas."""
        self.set_ui_busy(False)
        self.on_load_data_thread()

    @Slot(str)
    def abrir_importacion_manual(self, destino: str):
        """Abre el diálogo para importar códigos a una pestaña específica."""
        if self.tarea_en_ejecucion: 
            QMessageBox.warning(self, "Ocupado", "Hay una tarea en curso. Espera a que termine.")
            return

        d = DialogoImportacionManual(destino, self)
        d.start_import.connect(lambda lista: self._ejecutar_importacion_backend(lista, destino))
        d.exec()

    def _ejecutar_importacion_backend(self, lista_codigos, destino):
        logger.info(f"Importando {len(lista_codigos)} códigos a {destino}")
        
        def on_import_finished():
            self.set_ui_busy(False)
            self.on_load_data_thread()
            QMessageBox.information(self, "Importación Completa", "Se han procesado los códigos ingresados.")

        self.start_task(
            task=self.servicio_etl.importar_lista_manual,
            on_finished=on_import_finished,
            on_progress=self.on_progress_update,
            on_progress_percent=self.on_progress_percent_update,
            task_kwargs={"lista_codigos": lista_codigos, "destino": destino}
        )
# -*- coding: utf-8 -*-
from PySide6.QtCore import Slot
from src.utils.logger import configurar_logger

logger = configurar_logger(__name__)

class MixinCargaDatos:
    """
    Maneja la carga secuencial de datos en las tablas.
    """

    @Slot()
    def on_load_data_thread(self):
        self.cargar_candidatas()

    def cargar_candidatas(self):
        # 1. Obtener umbral de configuración
        try:
            self.settings_manager.cargar_configuracion()
            umbral = int(self.settings_manager.obtener_valor("umbral_puntaje_minimo") or 5)
        except:
            umbral = 5
        
        # 2. Definir tarea
        tarea = lambda: self.db_service.obtener_candidatas_filtradas(umbral_minimo=umbral)
        
        self.start_task(
            task=tarea,
            on_result=self.poblar_tab_unificada,
            on_error=self.on_task_error
        )

    def poblar_tab_unificada(self, data):
        logger.info(f"DATA LOADER: Cargando {len(data)} licitaciones en Candidatas.")
        self.poblar_tabla_generica(self.modelo_tab1, data)
        self.cargar_seguimiento()

    def cargar_seguimiento(self):
        self.start_task(
            task=self.db_service.obtener_licitaciones_seguimiento, 
            on_result=self.poblar_tab_seguimiento, 
            on_error=self.on_task_error
        )

    def poblar_tab_seguimiento(self, data):
        self.poblar_tabla_generica(self.modelo_tab3, data)
        self.cargar_ofertadas()

    def cargar_ofertadas(self):
        self.start_task(
            task=self.db_service.obtener_licitaciones_ofertadas, 
            on_result=self.poblar_tab_ofertadas, 
            on_error=self.on_task_error
        )

    def poblar_tab_ofertadas(self, data):
        self.poblar_tabla_generica(self.modelo_tab4, data)
        
    @Slot()
    def on_auto_task_finished(self):
        logger.info("Tarea automática finalizada. Recargando datos visuales...")
        self.on_load_data_thread()
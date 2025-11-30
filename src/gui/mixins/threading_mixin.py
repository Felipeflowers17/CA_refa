# -*- coding: utf-8 -*-
from PySide6.QtCore import Slot
from src.gui.gui_worker import Trabajador
from src.utils.logger import configurar_logger

logger = configurar_logger(__name__)

class MixinHilos:
    """
    Mixin para manejar tareas en segundo plano usando QThreadPool.
    Mantiene la UI fluida delegando el trabajo pesado a hilos secundarios.
    """

    def start_task(
        self,
        task,
        on_result=None,
        on_error=None,
        on_finished=None,
        on_progress=None,
        on_progress_percent=None,
        task_args=(),
        task_kwargs=None,
    ):
        """
        Lanza una tarea asíncrona.
        
        Args:
            task: La función a ejecutar (del Backend).
            on_result: Función a llamar con el return de 'task'.
            on_error: Función a llamar si ocurre una excepción.
            on_finished: Función a llamar siempre al finalizar.
            on_progress: Función para recibir actualizaciones de texto.
            on_progress_percent: Función para recibir actualizaciones de barra de carga (0-100).
        """
        if task_kwargs is None: task_kwargs = {}

        if hasattr(self, 'set_ui_busy'):
            self.set_ui_busy(True)

        necesita_texto = bool(on_progress)
        necesita_porcentaje = bool(on_progress_percent)
        
        try:
            trabajador = Trabajador(task, necesita_texto, necesita_porcentaje, *task_args, **task_kwargs)
            
            # CRÍTICO: Evita que C++ borre el objeto antes de emitir señales
            trabajador.setAutoDelete(False) 
            
            # Conexión de señales 
            if on_result: 
                trabajador.senales.resultado.connect(on_result)
            
            if on_error: 
                trabajador.senales.error.connect(on_error)
            else: 
                trabajador.senales.error.connect(self.on_task_error)
            
            # Limpieza y UI
            trabajador.senales.finalizado.connect(self.on_task_finished_common)
            trabajador.senales.finalizado.connect(lambda: self._limpiar_trabajador(trabajador))
            if on_finished: 
                trabajador.senales.finalizado.connect(on_finished)
                
            # Progreso
            if on_progress: 
                trabajador.senales.progreso_texto.connect(on_progress)
            else: 
                trabajador.senales.progreso_texto.connect(self.on_progress_update) 

            if on_progress_percent: 
                trabajador.senales.progreso_porcentaje.connect(on_progress_percent)
            else: 
                trabajador.senales.progreso_porcentaje.connect(self.on_progress_percent_update) 

            self.thread_pool.start(trabajador)
            self.trabajadores_activos.append(trabajador)
            
        except Exception as e:
            if hasattr(self, 'set_ui_busy'): self.set_ui_busy(False)
            logger.critical(f"Error al iniciar Trabajador: {e}")
            if on_error: on_error(e)

    def _limpiar_trabajador(self, trabajador):
        if trabajador in self.trabajadores_activos:
            self.trabajadores_activos.remove(trabajador)

    @Slot()
    def on_task_finished_common(self):
        if hasattr(self, 'set_ui_busy'):
            self.set_ui_busy(False)

    @Slot(str)
    def on_progress_update(self, message: str):
        # Implementación por defecto si la clase principal no la tiene
        if hasattr(self, 'lbl_estado_progreso'):
             self.lbl_estado_progreso.setText(message)

    @Slot(int)
    def on_progress_percent_update(self, value: int):
        if hasattr(self, 'barra_progreso'):
            self.barra_progreso.setValue(value)
            if value >= 100: self.barra_progreso.hide()
            else: self.barra_progreso.show()

    @Slot(object) 
    def on_task_error(self, error):
        if hasattr(self, 'set_ui_busy'): self.set_ui_busy(False)
        self.ultimo_error = error
        logger.error(f"Error no manejado en tarea: {error}")
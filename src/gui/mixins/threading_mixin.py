# -*- coding: utf-8 -*-
from PySide6.QtCore import Slot
from src.gui.gui_worker import Worker
from src.utils.logger import configurar_logger

logger = configurar_logger(__name__)

class ThreadingMixin:
    """
    Mixin para manejar tareas en segundo plano usando QThreadPool.
    Mantiene la UI fluida.
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
        if task_kwargs is None: task_kwargs = {}

        if hasattr(self, 'set_ui_busy'):
            self.set_ui_busy(True)

        needs_text = bool(on_progress)
        needs_percent = bool(on_progress_percent)
        
        try:
            worker = Worker(task, needs_text, needs_percent, *task_args, **task_kwargs)
            
            # CRÍTICO: Evita que C++ borre el objeto antes de emitir señales
            worker.setAutoDelete(False) 
            
            if on_result: worker.signals.result.connect(on_result)
            
            # Error Handling
            if on_error: worker.signals.error.connect(on_error)
            else: worker.signals.error.connect(self.on_task_error)
            
            # Limpieza y UI
            worker.signals.finished.connect(self.on_task_finished_common)
            worker.signals.finished.connect(lambda: self._cleanup_worker(worker))
            if on_finished: worker.signals.finished.connect(on_finished)
                
            # Progreso
            if on_progress: worker.signals.progress.connect(on_progress)
            else: worker.signals.progress.connect(self.on_progress_update) 

            if on_progress_percent: worker.signals.progress_percent.connect(on_progress_percent)
            else: worker.signals.progress_percent.connect(self.on_progress_percent_update) 

            self.thread_pool.start(worker)
            self.running_workers.append(worker)
            
        except Exception as e:
            if hasattr(self, 'set_ui_busy'): self.set_ui_busy(False)
            logger.critical(f"Error al iniciar Worker: {e}")
            # No relanzamos para no cerrar la GUI, solo logueamos
            if on_error: on_error(e)

    def _cleanup_worker(self, worker):
        if worker in self.running_workers:
            self.running_workers.remove(worker)

    @Slot()
    def on_task_finished_common(self):
        if hasattr(self, 'set_ui_busy'):
            self.set_ui_busy(False)

    @Slot(str)
    def on_progress_update(self, message: str):
        # Implementación por defecto si la clase principal no la tiene
        if hasattr(self, 'lbl_progress_status'):
             self.lbl_progress_status.setText(message)

    @Slot(int)
    def on_progress_percent_update(self, value: int):
        if hasattr(self, 'progress_bar'):
            self.progress_bar.setValue(value)
            if value >= 100: self.progress_bar.hide()
            else: self.progress_bar.show()

    @Slot(object) 
    def on_task_error(self, error):
        if hasattr(self, 'set_ui_busy'): self.set_ui_busy(False)
        self.last_error = error
        logger.error(f"Error no manejado en tarea: {error}")
        # Opcional: Mostrar alerta visual aquí
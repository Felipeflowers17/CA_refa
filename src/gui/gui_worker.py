# -*- coding: utf-8 -*-
"""
Worker de Hilos (QRunnable).
Este archivo NO DEBE importar nada de 'src.gui.gui_main' ni de 'src.gui.mixins'.
Solo librerías estándar y utils.
"""

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QRunnable, Signal, Slot

# Única dependencia interna permitida: logger
from src.utils.logger import configurar_logger

logger = configurar_logger(__name__)


class WorkerSignals(QObject):
    """
    Define las señales disponibles para un worker.
    """
    finished = Signal()
    error = Signal(Exception)
    result = Signal(object)
    progress = Signal(str)
    progress_percent = Signal(int) 


class Worker(QRunnable):
    """
    Worker genérico que hereda de QRunnable.
    """

    def __init__(
        self,
        task: Callable[..., Any],
        needs_progress_text: bool,  
        needs_progress_percent: bool, 
        *args,
        **kwargs,
    ):
        super().__init__()
        self.task = task
        self.needs_progress_text = needs_progress_text
        self.needs_progress_percent = needs_progress_percent
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        """
        El método principal que se ejecuta en el hilo secundario.
        """
        logger.debug(f"Hilo (QRunnable) iniciando tarea: {self.task.__name__}")

        try:
            # Inyección Segura por Keyword Arguments (Kwargs)
            if self.needs_progress_text:
                self.kwargs['progress_callback_text'] = self.signals.progress.emit
            
            if self.needs_progress_percent:
                self.kwargs['progress_callback_percent'] = self.signals.progress_percent.emit
            
            # Ejecutar la tarea
            resultado = self.task(*self.args, **self.kwargs)

            if resultado is not None:
                self.signals.result.emit(resultado)

        except Exception as e:
            logger.error(f"Error en el hilo (QRunnable): {e}", exc_info=True)
            self.signals.error.emit(e)
        finally:
            self.signals.finished.emit()
            logger.debug(f"Hilo (QRunnable) finalizó tarea: {self.task.__name__}")
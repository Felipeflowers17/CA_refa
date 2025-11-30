# -*- coding: utf-8 -*-
"""
Trabajador de Hilos (Worker / QRunnable).

Este módulo gestiona la ejecución de tareas pesadas en segundo plano
para evitar congelar la interfaz gráfica.
"""

from collections.abc import Callable
from typing import Any
from PySide6.QtCore import QObject, QRunnable, Signal, Slot
from src.utils.logger import configurar_logger

logger = configurar_logger(__name__)

class SenalesTrabajador(QObject):
    """
    Define las señales que emite un trabajador hacia la GUI.
    """
    finalizado = Signal()
    error = Signal(Exception)
    resultado = Signal(object)
    progreso_texto = Signal(str)
    progreso_porcentaje = Signal(int) 

class Trabajador(QRunnable):
    """
    Clase genérica que ejecuta una función en un hilo separado.
    """

    def __init__(
        self,
        tarea: Callable[..., Any],
        requiere_progreso_texto: bool,  
        requiere_progreso_porcentaje: bool, 
        *args,
        **kwargs,
    ):
        super().__init__()
        self.tarea = tarea
        self.requiere_progreso_texto = requiere_progreso_texto
        self.requiere_progreso_porcentaje = requiere_progreso_porcentaje
        self.args = args
        self.kwargs = kwargs
        self.senales = SenalesTrabajador()

    @Slot()
    def run(self):
        """
        Método principal ejecutado por QThreadPool.
        """
        logger.debug(f"Hilo iniciando tarea: {self.tarea.__name__}")

        try:
            # Inyección de Callbacks para reporte de progreso
            # Esto permite que la lógica de negocio (Backend) actualice la GUI sin conocerla
            if self.requiere_progreso_texto:
                self.kwargs['callback_texto'] = self.senales.progreso_texto.emit
            
            if self.requiere_progreso_porcentaje:
                self.kwargs['callback_porcentaje'] = self.senales.progreso_porcentaje.emit
            
            # Ejecutar la lógica de negocio
            resultado = self.tarea(*self.args, **self.kwargs)

            if resultado is not None:
                self.senales.resultado.emit(resultado)

        except Exception as e:
            logger.error(f"Excepción en hilo de trabajo: {e}", exc_info=True)
            self.senales.error.emit(e)
        finally:
            self.senales.finalizado.emit()
            logger.debug(f"Hilo finalizó tarea: {self.tarea.__name__}")
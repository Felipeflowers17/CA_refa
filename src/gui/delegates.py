# -*- coding: utf-8 -*-
from PySide6.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem
from PySide6.QtCore import Qt, QModelIndex
from PySide6.QtGui import QPainter

class DelegadoTextoElidido(QStyledItemDelegate):
    """
    Delegado gráfico que recorta el texto con puntos suspensivos (...)
    si es más largo que la celda, mejorando la estética de la tabla.
    """
    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        if not index.isValid(): return
        
        opcion_estilo = QStyleOptionViewItem(option)
        self.initStyleOption(opcion_estilo, index)
        
        painter.save()
        
        texto = index.data(Qt.DisplayRole)
        if texto:
            ancho_disponible = opcion_estilo.rect.width() - 10
            # ElideRight pone los puntos al final: "Texto muy lar..."
            texto_cortado = opcion_estilo.fontMetrics.elidedText(texto, Qt.ElideRight, ancho_disponible)
            painter.drawText(opcion_estilo.rect.adjusted(5, 0, -5, 0), opcion_estilo.displayAlignment, texto_cortado)
            
        painter.restore()
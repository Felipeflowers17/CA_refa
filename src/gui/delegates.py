# -*- coding: utf-8 -*-
from PySide6.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem
from PySide6.QtCore import Qt, QModelIndex
from PySide6.QtGui import QPainter

class ElidedTextDelegate(QStyledItemDelegate):
    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        if not index.isValid(): return
        option = QStyleOptionViewItem(option)
        self.initStyleOption(option, index)
        painter.save()
        text = index.data(Qt.DisplayRole)
        if text:
            available_width = option.rect.width() - 10
            elided_text = option.fontMetrics.elidedText(text, Qt.ElideRight, available_width)
            painter.drawText(option.rect.adjusted(5, 0, -5, 0), option.displayAlignment, elided_text)
        painter.restore()
# -*- coding: utf-8 -*-
"""
Diálogo de Exportación.
"""

from PySide6.QtCore import Slot
from qfluentwidgets import MessageBoxBase, SubtitleLabel, RadioButton, BodyLabel

class DialogoExportacion(MessageBoxBase):
    def __init__(self, nombre_tab_actual: str, parent=None):
        super().__init__(parent)
        self.nombre_tab_actual = nombre_tab_actual
        self.lbl_titulo = SubtitleLabel("Opciones de Exportación", self)
        
        # Widgets
        self.lbl_fmt = BodyLabel("Formato de Archivo:", self)
        self.rad_excel = RadioButton("Excel (.xlsx)", self)
        self.rad_csv = RadioButton("CSV (.csv)", self)
        self.rad_excel.setChecked(True)
        
        self.lbl_alcance = BodyLabel("Alcance:", self)
        self.rad_todo = RadioButton("Todas las pestañas", self)
        self.rad_actual = RadioButton(f"Solo actual ({nombre_tab_actual})", self)
        self.rad_todo.setChecked(True)
        
        # Layout
        self.viewLayout.addWidget(self.lbl_titulo)
        self.viewLayout.addSpacing(10)
        
        self.viewLayout.addWidget(self.lbl_fmt)
        self.viewLayout.addWidget(self.rad_excel)
        self.viewLayout.addWidget(self.rad_csv)
        
        self.viewLayout.addSpacing(15)
        
        self.viewLayout.addWidget(self.lbl_alcance)
        self.viewLayout.addWidget(self.rad_todo)
        self.viewLayout.addWidget(self.rad_actual)
        
        self.yesButton.setText("Exportar")
        self.cancelButton.setText("Cancelar")
        
    def obtener_opciones(self) -> dict:
        return {
            "format": "excel" if self.rad_excel.isChecked() else "csv",
            "scope": "all" if self.rad_todo.isChecked() else "current",
            "tab_name": self.nombre_tab_actual
        }
# -*- coding: utf-8 -*-
# src/gui/gui_import_dialog.py

from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPlainTextEdit
from PySide6.QtCore import Signal
from qfluentwidgets import SubtitleLabel, BodyLabel, PrimaryPushButton, PushButton, InfoBar

class DialogoImportacionManual(QDialog):
    """
    Diálogo para pegar una lista de códigos CA y procesarlos.
    """
    start_import = Signal(list)

    def __init__(self, tab_destino: str, parent=None):
        super().__init__(parent)
        self.tab_destino = tab_destino
        self.setWindowTitle(f"Agregar a {tab_destino.capitalize()}")
        self.resize(500, 400)
        self.setStyleSheet("QDialog { background-color: #ffffff; }")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        layout.addWidget(SubtitleLabel(f"Importar Licitaciones a {tab_destino.capitalize()}", self))
        layout.addWidget(BodyLabel("Pega los códigos de Compra Ágil (uno por línea o separados por coma):", self))

        self.txt_input = QPlainTextEdit(self)
        self.txt_input.setPlaceholderText("Ejemplo:\n1234-56-L123\n5555-66-CM24")
        layout.addWidget(self.txt_input)

        h_btn = QHBoxLayout()
        h_btn.addStretch()
        btn_cancel = PushButton("Cancelar", self)
        btn_cancel.clicked.connect(self.reject)
        
        btn_ok = PrimaryPushButton("Procesar Lista", self)
        btn_ok.clicked.connect(self.on_procesar)
        
        h_btn.addWidget(btn_cancel)
        h_btn.addWidget(btn_ok)
        layout.addLayout(h_btn)

    def on_procesar(self):
        texto = self.txt_input.toPlainText()
        if not texto.strip():
            InfoBar.warning("Campo vacío", "Ingresa al menos un código.", parent=self)
            return

        # Limpieza de texto: Reemplazar comas por saltos de linea y dividir
        texto = texto.replace(",", "\n").replace(";", "\n")
        lista = [linea.strip() for linea in texto.split("\n") if linea.strip()]
        
        if not lista:
             InfoBar.warning("Sin códigos", "No se detectaron códigos válidos.", parent=self)
             return

        self.start_import.emit(lista)
        self.accept()
# -*- coding: utf-8 -*-
"""
Diálogo de Configuración de Scraping.
"""

from datetime import date
from PySide6.QtCore import QDate, Signal, Slot, Qt
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QWidget

from qfluentwidgets import (
    SubtitleLabel, BodyLabel, CalendarPicker, 
    SpinBox, ComboBox, PrimaryPushButton, PushButton
)
from src.utils.logger import configurar_logger

logger = configurar_logger(__name__)

class DialogoScraping(QDialog):
    """
    Ventana modal para configurar los parámetros de búsqueda (Fechas, Páginas).
    """

    senal_iniciar_scraping = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configurar Búsqueda")
        self.resize(450, 400)
        self.setObjectName("ScrapingDialog")
        self.setStyleSheet("QDialog { background-color: palette(window); }")

        self.layout_principal = QVBoxLayout(self)
        self.layout_principal.setContentsMargins(24, 24, 24, 24)
        self.layout_principal.setSpacing(16)

        self.lbl_titulo = SubtitleLabel("Parámetros de Extracción", self)
        self.layout_principal.addWidget(self.lbl_titulo)

        # --- FECHAS ---
        self.contenedor_fechas = QWidget()
        self.layout_fechas = QHBoxLayout(self.contenedor_fechas)
        self.layout_fechas.setContentsMargins(0, 0, 0, 0)
        
        # Desde
        v_desde = QVBoxLayout(); lbl_d = BodyLabel("Desde:", self)
        self.cal_desde = CalendarPicker(self)
        self.cal_desde.setDate(QDate.currentDate().addDays(-7))
        self.cal_desde.setDateFormat(Qt.ISODate) 
        v_desde.addWidget(lbl_d); v_desde.addWidget(self.cal_desde)
        
        # Hasta
        v_hasta = QVBoxLayout(); lbl_h = BodyLabel("Hasta:", self)
        self.cal_hasta = CalendarPicker(self)
        self.cal_hasta.setDate(QDate.currentDate())
        self.cal_hasta.setDateFormat(Qt.ISODate)
        v_hasta.addWidget(lbl_h); v_hasta.addWidget(self.cal_hasta)
        
        self.layout_fechas.addLayout(v_desde)
        self.layout_fechas.addSpacing(20)
        self.layout_fechas.addLayout(v_hasta)
        self.layout_principal.addWidget(self.contenedor_fechas)

        # --- LÍMITE ---
        v_limite = QVBoxLayout()
        self.spin_paginas = SpinBox(self)
        self.spin_paginas.setRange(0, 1000); self.spin_paginas.setValue(0)
        v_limite.addWidget(BodyLabel("Límite de páginas (0 = Todo):", self))
        v_limite.addWidget(self.spin_paginas)
        self.layout_principal.addLayout(v_limite)

        # --- MODO ---
        v_modo = QVBoxLayout()
        self.combo_modo = ComboBox(self)
        self.combo_modo.addItem("Guardar en BD")
        self.combo_modo.addItem("Solo JSON (Debug)")
        self.combo_modo.setCurrentIndex(0)
        v_modo.addWidget(BodyLabel("Destino:", self))
        v_modo.addWidget(self.combo_modo)
        self.layout_principal.addLayout(v_modo)

        self.layout_principal.addStretch(1)

        # --- BOTONES ---
        l_botones = QHBoxLayout(); l_botones.addStretch(1)
        btn_cancelar = PushButton("Cancelar", self); btn_cancelar.clicked.connect(self.reject)
        btn_ejecutar = PrimaryPushButton("Ejecutar", self); btn_ejecutar.clicked.connect(self.on_accept)
        l_botones.addWidget(btn_cancelar); l_botones.addWidget(btn_ejecutar)
        self.layout_principal.addLayout(l_botones)

    @Slot()
    def on_accept(self):
        try:
            f_desde = self.cal_desde.date.toPython()
            f_hasta = self.cal_hasta.date.toPython()
        except:
            f_desde = self.cal_desde.getDate().toPython()
            f_hasta = self.cal_hasta.getDate().toPython()

        config = {
            "date_from": f_desde,
            "date_to": f_hasta,
            "max_paginas": self.spin_paginas.value(),
            "mode": "to_db" if self.combo_modo.currentIndex() == 0 else "to_json",
        }
        
        self.senal_iniciar_scraping.emit(config)
        self.accept()
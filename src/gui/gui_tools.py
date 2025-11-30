# -*- coding: utf-8 -*-
from PySide6.QtCore import Qt, Signal, QDate, QTime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget, QHeaderView, 
    QTableWidgetItem, QMenu, QGroupBox, QSplitter, QDialog, QAbstractSpinBox, QSpinBox
)
from PySide6.QtGui import QColor, QBrush

from qfluentwidgets import (
    SegmentedWidget, TitleLabel, BodyLabel, CalendarPicker, 
    SpinBox, PrimaryPushButton, CheckBox, TimePicker,
    TableWidget, LineEdit, PushButton, SubtitleLabel,
    InfoBar, InfoBarPosition, StrongBodyLabel
)

from sqlalchemy import update
from src.utils.logger import configurar_logger
from src.db.db_service import DbService
from src.db.db_models import TipoReglaOrganismo, CaPalabraClave

logger = configurar_logger(__name__)

COLOR_PRIORITARIO = QColor(230, 255, 230)
COLOR_NO_DESEADO = QColor(255, 230, 230)
COLOR_NEUTRO = QColor(255, 255, 255)

# --- CLASES AUXILIARES ---
class ItemTablaNumerico(QTableWidgetItem):
    def __lt__(self, other):
        try: return float(self.text()) < float(other.text())
        except: return False

class DialogoEditarPuntos(QDialog):
    def __init__(self, nombre_org, valor_actual, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Editar Puntos")
        self.resize(300, 180)
        self.setStyleSheet("QDialog { background-color: #ffffff; }")
        
        layout = QVBoxLayout(self); layout.setSpacing(15)
        layout.addWidget(SubtitleLabel("Asignar Puntaje", self))
        layout.addWidget(BodyLabel(f"Organismo:\n{nombre_org}", self))
        
        h = QHBoxLayout()
        self.spin = QSpinBox()
        self.spin.setRange(1, 1000); self.spin.setValue(int(valor_actual))
        h.addWidget(StrongBodyLabel("Puntos:", self)); h.addWidget(self.spin)
        layout.addLayout(h)
        
        h_btn = QHBoxLayout()
        btn_save = PrimaryPushButton("Guardar", self); btn_save.clicked.connect(self.accept)
        h_btn.addStretch(); h_btn.addWidget(btn_save); layout.addLayout(h_btn)

    def obtener_valor(self): return self.spin.value()

class DialogoEditarKeyword(QDialog):
    def __init__(self, kw_id, nombre, p_nom, p_desc, p_prod, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Editar Palabra Clave")
        self.resize(400, 300)
        self.kw_id = kw_id; self.solicita_borrar = False
        self.setStyleSheet("QDialog { background-color: #ffffff; }")
        
        l = QVBoxLayout(self); l.setSpacing(15)
        l.addWidget(StrongBodyLabel("Palabra Clave:", self))
        
        self.txtNombre = LineEdit()
        self.txtNombre.setText(str(nombre)) 
        
        l.addWidget(self.txtNombre)
        
        g = QGroupBox("Puntajes"); vg = QVBoxLayout()
        self.cNom, self.sNom = self._crear_fila("Título", p_nom, vg)
        self.cDesc, self.sDesc = self._crear_fila("Descripción", p_desc, vg)
        self.cProd, self.sProd = self._crear_fila("Productos", p_prod, vg)
        g.setLayout(vg); l.addWidget(g)
        
        h = QHBoxLayout()
        btnDel = PushButton("Eliminar", self); btnDel.setStyleSheet("color: red;")
        btnDel.clicked.connect(self.on_delete)
        btnSave = PrimaryPushButton("Guardar", self); btnSave.clicked.connect(self.accept)
        h.addWidget(btnDel); h.addStretch(); h.addWidget(btnSave); l.addLayout(h)

    def _crear_fila(self, txt, val, layout):
        h = QHBoxLayout(); c = CheckBox(txt); s = QSpinBox(); s.setRange(-100, 100)
        activo = (val != 0); c.setChecked(activo); s.setEnabled(activo); s.setValue(val if val!=0 else 5)
        c.stateChanged.connect(lambda: s.setEnabled(c.isChecked()))
        h.addWidget(c); h.addStretch(); h.addWidget(s); layout.addLayout(h)
        return c, s

    def on_delete(self): self.solicita_borrar = True; self.accept()
    def obtener_datos(self):
        return (self.txtNombre.text(), 
                self.sNom.value() if self.cNom.isChecked() else 0,
                self.sDesc.value() if self.cDesc.isChecked() else 0,
                self.sProd.value() if self.cProd.isChecked() else 0)

# --- WIDGET PRINCIPAL ---
class WidgetHerramientas(QWidget):
    senal_iniciar_scraping = Signal(dict)
    senal_iniciar_exportacion = Signal(list)
    senal_iniciar_recalculo = Signal()
    senal_configuracion_cambiada = Signal()
    senal_config_autopiloto_cambiada = Signal()

    def __init__(self, db_service, settings_manager, parent=None):
        super().__init__(parent)
        self.setObjectName("widget_herramientas") 
        self.db_service = db_service
        self.settings_manager = settings_manager
        
        layout = QVBoxLayout(self); layout.setContentsMargins(20,20,20,20); layout.setSpacing(15)
        layout.addWidget(TitleLabel("Herramientas", self))
        
        self.pivot = SegmentedWidget(self)
        for k,v in [("extraer","Extraer"), ("exportar","Exportar"), ("config","Puntajes"), ("auto","Avanzado")]: self.pivot.addItem(k,v)
        self.pivot.setCurrentItem("extraer"); layout.addWidget(self.pivot)
        
        self.stack = QStackedWidget(self); layout.addWidget(self.stack)
        self.stack.addWidget(self._pag_extraer())
        self.stack.addWidget(self._pag_exportar())
        self.stack.addWidget(self._pag_config())
        self.stack.addWidget(self._pag_auto())
        
        self.pivot.currentItemChanged.connect(lambda k: self.stack.setCurrentIndex(["extraer", "exportar", "config", "auto"].index(k)))

    # 1. PESTAÑA EXTRAER
    def _pag_extraer(self):
        w = QWidget(); l = QVBoxLayout(w); l.setSpacing(20)
        l.addWidget(SubtitleLabel("Scraping Manual", w))
        
        hD = QHBoxLayout()
        v1 = QVBoxLayout(); v1.addWidget(BodyLabel("Desde", w)); self.dFrom = CalendarPicker(w); self.dFrom.setDate(QDate.currentDate().addDays(-7)); v1.addWidget(self.dFrom)
        v2 = QVBoxLayout(); v2.addWidget(BodyLabel("Hasta", w)); self.dTo = CalendarPicker(w); self.dTo.setDate(QDate.currentDate()); v2.addWidget(self.dTo)
        hD.addLayout(v1); hD.addSpacing(20); hD.addLayout(v2); hD.addStretch(); l.addLayout(hD)
        
        hP = QHBoxLayout(); hP.addWidget(BodyLabel("Máx Páginas (0=Todas):", w))
        self.sPages = SpinBox(); self.sPages.setRange(0, 1000); self.sPages.setValue(0); hP.addWidget(self.sPages); hP.addStretch(); l.addLayout(hP)
        
        btn = PrimaryPushButton("Iniciar Scraping", w); btn.clicked.connect(self._ejecutar_scraping); l.addWidget(btn); l.addStretch()
        return w

    def _ejecutar_scraping(self):
        try: d_from = self.dFrom.date.toPython(); d_to = self.dTo.date.toPython()
        except: d_from = self.dFrom.getDate().toPython(); d_to = self.dTo.getDate().toPython()
        self.senal_iniciar_scraping.emit({"mode": "to_db", "date_from": d_from, "date_to": d_to, "max_paginas": self.sPages.value()})

    # 2. PESTAÑA EXPORTAR
    def _pag_exportar(self):
        w = QWidget(); l = QVBoxLayout(w); l.setSpacing(15)
        l.addWidget(SubtitleLabel("Exportación", w))
        self.chk_bd = CheckBox("Base de Datos Completa", w)
        self.chk_tabs = CheckBox("Pestañas Visibles", w); self.chk_tabs.setChecked(True)
        l.addWidget(self.chk_bd); l.addWidget(self.chk_tabs)
        
        h = QHBoxLayout(); self.cExcel = CheckBox("Excel", w); self.cCsv = CheckBox("CSV", w); self.cExcel.setChecked(True)
        h.addWidget(self.cExcel); h.addWidget(self.cCsv); h.addStretch(); l.addLayout(h)
        
        btn = PrimaryPushButton("Generar", w); btn.clicked.connect(self._ejecutar_exportacion); l.addWidget(btn); l.addStretch()
        return w

    def _ejecutar_exportacion(self):
        tasks = []
        fmt = "excel" if self.cExcel.isChecked() else "csv"
        if self.chk_bd.isChecked(): tasks.append({"tipo": "bd_full", "format": fmt, "scope": "all"})
        if self.chk_tabs.isChecked(): tasks.append({"tipo": "tabs", "format": fmt, "scope": "all"})
        if tasks: self.senal_iniciar_exportacion.emit(tasks)

    # 3. PESTAÑA CONFIG (PUNTAJES)
    def _pag_config(self):
        w = QWidget(); l = QVBoxLayout(w)
        splitter = QSplitter(Qt.Vertical)
        
        # Organismos
        wO = QWidget(); lO = QVBoxLayout(wO)
        h = QHBoxLayout(); h.addWidget(StrongBodyLabel("Organismos", w)); self.txtFilt = LineEdit(); self.txtFilt.setPlaceholderText("Filtrar..."); self.txtFilt.textChanged.connect(self._filtrar_org)
        h.addWidget(self.txtFilt); lO.addLayout(h)
        self.tabOrg = TableWidget(w); self.tabOrg.setColumnCount(4); self.tabOrg.setHorizontalHeaderLabels(["ID", "Nombre", "Estado", "Pts"])
        self.tabOrg.verticalHeader().hide(); self.tabOrg.setColumnHidden(0, True); self.tabOrg.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tabOrg.cellDoubleClicked.connect(self._doble_click_org); lO.addWidget(self.tabOrg); splitter.addWidget(wO)
        
        # Keywords
        wK = QWidget(); lK = QVBoxLayout(wK)
        hK = QHBoxLayout(); self.txtKw = LineEdit(); self.txtKw.setPlaceholderText("Nueva keyword...")
        self.sKw = SpinBox(); self.sKw.setRange(-50, 50); self.sKw.setValue(5)
        btnK = PushButton("Agregar"); btnK.clicked.connect(self._agregar_kw)
        hK.addWidget(self.txtKw); hK.addWidget(self.sKw); hK.addWidget(btnK); lK.addLayout(hK)
        
        self.tabKw = TableWidget(w); self.tabKw.setColumnCount(5); self.tabKw.setHorizontalHeaderLabels(["ID", "KW", "N", "D", "P"])
        self.tabKw.verticalHeader().hide(); self.tabKw.setColumnHidden(0, True); self.tabKw.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tabKw.cellDoubleClicked.connect(self._doble_click_kw); lK.addWidget(self.tabKw); splitter.addWidget(wK)
        
        l.addWidget(splitter)
        btnRecalc = PrimaryPushButton("Guardar y Recalcular"); btnRecalc.clicked.connect(lambda: [self.senal_configuracion_cambiada.emit(), self.senal_iniciar_recalculo.emit()])
        l.addWidget(btnRecalc)
        
        self._cargar_orgs(); self._cargar_kws()
        return w

    def _cargar_orgs(self):
        self.tabOrg.setSortingEnabled(False); self.tabOrg.setRowCount(0)
        orgs = self.db_service.obtener_todos_organismos()
        reglas = {r.organismo_id: r for r in self.db_service.obtener_reglas_organismos()}
        
        self.tabOrg.setRowCount(len(orgs))
        for r, o in enumerate(orgs):
            reg = reglas.get(o.organismo_id)
            st, pts, col = "Neutro", "0", COLOR_NEUTRO
            if reg:
                if reg.tipo == TipoReglaOrganismo.PRIORITARIO: st, pts, col = "Prioritario", str(reg.puntos), COLOR_PRIORITARIO
                elif reg.tipo == TipoReglaOrganismo.NO_DESEADO: st, pts, col = "No Deseado", "N/A", COLOR_NO_DESEADO
            
            for c, txt in enumerate([str(o.organismo_id), o.nombre, st, pts]):
                it = ItemTablaNumerico(txt) if c==3 else QTableWidgetItem(txt)
                it.setBackground(QBrush(col)); self.tabOrg.setItem(r, c, it)
        self.tabOrg.setSortingEnabled(True)

    def _filtrar_org(self, t):
        t = t.lower(); [self.tabOrg.setRowHidden(r, t not in self.tabOrg.item(r, 1).text().lower()) for r in range(self.tabOrg.rowCount())]

    def _doble_click_org(self, r, c):
        oid = int(self.tabOrg.item(r, 0).text())
        if c == 3: 
            curr = self.tabOrg.item(r, 3).text()
            if curr == "N/A": return
            d = DialogoEditarPuntos(self.tabOrg.item(r, 1).text(), curr, self)
            if d.exec(): self.db_service.establecer_regla_organismo(oid, TipoReglaOrganismo.PRIORITARIO, d.obtener_valor()); self._cargar_orgs()
        else: 
            m = QMenu()
            m.addAction("Prioritario").triggered.connect(lambda: [self.db_service.establecer_regla_organismo(oid, TipoReglaOrganismo.PRIORITARIO, 5), self._cargar_orgs()])
            m.addAction("No Deseado").triggered.connect(lambda: [self.db_service.establecer_regla_organismo(oid, TipoReglaOrganismo.NO_DESEADO), self._cargar_orgs()])
            m.addAction("Neutro").triggered.connect(lambda: [self.db_service.eliminar_regla_organismo(oid), self._cargar_orgs()])
            m.exec(self.cursor().pos())

    def _cargar_kws(self):
        self.tabKw.setSortingEnabled(False); self.tabKw.setRowCount(0)
        kws = self.db_service.obtener_todas_palabras_clave()
        self.tabKw.setRowCount(len(kws))
        for r, k in enumerate(kws):
            for c, v in enumerate([str(k.keyword_id), k.keyword, str(k.puntos_nombre), str(k.puntos_descripcion), str(k.puntos_productos)]):
                self.tabKw.setItem(r, c, ItemTablaNumerico(v) if c>1 else QTableWidgetItem(v))
        self.tabKw.setSortingEnabled(True)

    def _agregar_kw(self):
        txt = self.txtKw.text().strip()
        if txt: self.db_service.agregar_palabra_clave(txt, "titulo_pos", self.sKw.value()); self.txtKw.clear(); self._cargar_kws()

    def _doble_click_kw(self, r, c):
        kid = int(self.tabKw.item(r, 0).text())
        k = self.tabKw.item(r, 1).text()
        p1 = int(self.tabKw.item(r, 2).text()); p2 = int(self.tabKw.item(r, 3).text()); p3 = int(self.tabKw.item(r, 4).text())
        d = DialogoEditarKeyword(kid, k, p1, p2, p3, self)
        if d.exec():
            if d.solicita_borrar: self.db_service.eliminar_palabra_clave(kid)
            else:
                n, a, b, c_prod = d.obtener_datos()
                with self.db_service.session_factory() as s:
                    s.execute(update(CaPalabraClave).where(CaPalabraClave.keyword_id==kid).values(keyword=n, puntos_nombre=a, puntos_descripcion=b, puntos_productos=c_prod))
                    s.commit()
            self._cargar_kws()

    # 4. PESTAÑA AUTOMATIZACIÓN 
    def _pag_auto(self):
        w = QWidget(); l = QVBoxLayout(w)
        l.addWidget(SubtitleLabel("Piloto Automático", w))
        
        self.chkAuto = CheckBox("Extracción Diaria (Ayer)", w)
        self.chkAuto.setChecked(bool(self.settings_manager.obtener_valor("auto_extract_enabled")))
        
        self.tAuto = TimePicker(w, showSeconds=False)
        self.tAuto.setTime(QTime.fromString(self.settings_manager.obtener_valor("auto_extract_time") or "08:00", "HH:mm"))
        
        l.addWidget(self.chkAuto); l.addWidget(self.tAuto)
        
        btn = PrimaryPushButton("Guardar Config"); btn.clicked.connect(self._guardar_auto); l.addWidget(btn); l.addStretch()
        return w

    def _guardar_auto(self):
        self.settings_manager.establecer_valor("auto_extract_enabled", self.chkAuto.isChecked())
        
        try: t = self.tAuto.time.toString("HH:mm")
        except: t = self.tAuto.getTime().toString("HH:mm")
        
        self.settings_manager.establecer_valor("auto_extract_time", t)
        
        self.settings_manager.guardar_configuracion(self.settings_manager.config)
        
        self.senal_config_autopiloto_cambiada.emit()
        InfoBar.success("Guardado", "Configuración actualizada.", parent=self.window())
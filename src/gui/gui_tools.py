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
from src.db.db_models import TipoReglaOrganismo, CaKeyword

logger = configurar_logger(__name__)

COLOR_PRIORITARIO = QColor(230, 255, 230)
COLOR_NO_DESEADO = QColor(255, 230, 230)
COLOR_NEUTRO = QColor(255, 255, 255)

# --- CLASES AUXILIARES ---
class NumericTableWidgetItem(QTableWidgetItem):
    """Permite ordenar columnas numéricas correctamente."""
    def __lt__(self, other):
        try: return float(self.text()) < float(other.text())
        except: return False

class EditScoreDialog(QDialog):
    def __init__(self, org_name, current_val, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Editar Puntos")
        self.resize(300, 180)
        self.setStyleSheet("QDialog { background-color: #ffffff; }")
        
        layout = QVBoxLayout(self); layout.setSpacing(15)
        layout.addWidget(SubtitleLabel("Asignar Puntaje", self))
        layout.addWidget(BodyLabel(f"Organismo:\n{org_name}", self))
        
        h = QHBoxLayout()
        self.spin = QSpinBox()
        self.spin.setRange(1, 1000); self.spin.setValue(int(current_val))
        h.addWidget(StrongBodyLabel("Puntos:", self)); h.addWidget(self.spin)
        layout.addLayout(h)
        
        h_btn = QHBoxLayout()
        btn_save = PrimaryPushButton("Guardar", self); btn_save.clicked.connect(self.accept)
        h_btn.addStretch(); h_btn.addWidget(btn_save); layout.addLayout(h_btn)

    def get_value(self): return self.spin.value()

class EditKeywordDialog(QDialog):
    def __init__(self, kw_id, name, p_nom, p_desc, p_prod, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Editar Keyword")
        self.resize(400, 300)
        self.kw_id = kw_id; self.delete_requested = False
        self.setStyleSheet("QDialog { background-color: #ffffff; }")
        
        l = QVBoxLayout(self); l.setSpacing(15)
        l.addWidget(StrongBodyLabel("Keyword:", self))
        
        # --- CORRECCIÓN AQUÍ ---
        # Antes: self.txtName = LineEdit(name)  <- ESTO CAUSABA EL ERROR
        # Ahora: Inicializamos vacío y seteamos el texto después.
        self.txtName = LineEdit()
        self.txtName.setText(str(name)) 
        # -----------------------
        
        l.addWidget(self.txtName)
        
        g = QGroupBox("Puntajes"); vg = QVBoxLayout()
        self.cNom, self.sNom = self._row("Título", p_nom, vg)
        self.cDesc, self.sDesc = self._row("Descripción", p_desc, vg)
        self.cProd, self.sProd = self._row("Productos", p_prod, vg)
        g.setLayout(vg); l.addWidget(g)
        
        h = QHBoxLayout()
        btnDel = PushButton("Eliminar", self); btnDel.setStyleSheet("color: red;")
        btnDel.clicked.connect(self.on_delete)
        btnSave = PrimaryPushButton("Guardar", self); btnSave.clicked.connect(self.accept)
        h.addWidget(btnDel); h.addStretch(); h.addWidget(btnSave); l.addLayout(h)

    def _row(self, txt, val, layout):
        h = QHBoxLayout(); c = CheckBox(txt); s = QSpinBox(); s.setRange(-100, 100)
        active = (val != 0); c.setChecked(active); s.setEnabled(active); s.setValue(val if val!=0 else 5)
        c.stateChanged.connect(lambda: s.setEnabled(c.isChecked()))
        h.addWidget(c); h.addStretch(); h.addWidget(s); layout.addLayout(h)
        return c, s

    def on_delete(self): self.delete_requested = True; self.accept()
    def get_data(self):
        return (self.txtName.text(), 
                self.sNom.value() if self.cNom.isChecked() else 0,
                self.sDesc.value() if self.cDesc.isChecked() else 0,
                self.sProd.value() if self.cProd.isChecked() else 0)

# --- WIDGET PRINCIPAL ---
class GuiToolsWidget(QWidget):
    start_scraping_signal = Signal(dict); start_export_signal = Signal(list); start_recalculate_signal = Signal(); settings_changed_signal = Signal(); autopilot_config_changed_signal = Signal()

    def __init__(self, db_service, settings_manager, parent=None):
        super().__init__(parent)
        self.setObjectName("gui_tools_widget") 
        self.db_service = db_service; self.settings_manager = settings_manager
        
        layout = QVBoxLayout(self); layout.setContentsMargins(20,20,20,20); layout.setSpacing(15)
        layout.addWidget(TitleLabel("Herramientas", self))
        
        self.pivot = SegmentedWidget(self)
        for k,v in [("extraer","Extraer"), ("exportar","Exportar"), ("config","Puntajes"), ("auto","Avanzado")]: self.pivot.addItem(k,v)
        self.pivot.setCurrentItem("extraer"); layout.addWidget(self.pivot)
        
        self.stack = QStackedWidget(self); layout.addWidget(self.stack)
        self.stack.addWidget(self._page_extract())
        self.stack.addWidget(self._page_export())
        self.stack.addWidget(self._page_config())
        self.stack.addWidget(self._page_auto())
        
        self.pivot.currentItemChanged.connect(lambda k: self.stack.setCurrentIndex(["extraer", "exportar", "config", "auto"].index(k)))

    # 1. EXTRACT
    def _page_extract(self):
        w = QWidget(); l = QVBoxLayout(w); l.setSpacing(20)
        l.addWidget(SubtitleLabel("Scraping Manual", w))
        
        hD = QHBoxLayout()
        v1 = QVBoxLayout(); v1.addWidget(BodyLabel("Desde", w)); self.dFrom = CalendarPicker(w); self.dFrom.setDate(QDate.currentDate().addDays(-7)); v1.addWidget(self.dFrom)
        v2 = QVBoxLayout(); v2.addWidget(BodyLabel("Hasta", w)); self.dTo = CalendarPicker(w); self.dTo.setDate(QDate.currentDate()); v2.addWidget(self.dTo)
        hD.addLayout(v1); hD.addSpacing(20); hD.addLayout(v2); hD.addStretch(); l.addLayout(hD)
        
        hP = QHBoxLayout(); hP.addWidget(BodyLabel("Máx Páginas (0=Todas):", w))
        self.sPages = SpinBox(); self.sPages.setRange(0, 1000); self.sPages.setValue(0); hP.addWidget(self.sPages); hP.addStretch(); l.addLayout(hP)
        
        btn = PrimaryPushButton("Iniciar Scraping", w); btn.clicked.connect(self._run_scraping); l.addWidget(btn); l.addStretch()
        return w

    def _run_scraping(self):
        try: d_from = self.dFrom.date.toPython(); d_to = self.dTo.date.toPython()
        except: d_from = self.dFrom.getDate().toPython(); d_to = self.dTo.getDate().toPython()
        self.start_scraping_signal.emit({"mode": "to_db", "date_from": d_from, "date_to": d_to, "max_paginas": self.sPages.value()})

    # 2. EXPORT
    def _page_export(self):
        w = QWidget(); l = QVBoxLayout(w); l.setSpacing(15)
        l.addWidget(SubtitleLabel("Exportación", w))
        self.chk_bd = CheckBox("Base de Datos Completa", w)
        self.chk_tabs = CheckBox("Pestañas Visibles", w); self.chk_tabs.setChecked(True)
        l.addWidget(self.chk_bd); l.addWidget(self.chk_tabs)
        
        h = QHBoxLayout(); self.cExcel = CheckBox("Excel", w); self.cCsv = CheckBox("CSV", w); self.cExcel.setChecked(True)
        h.addWidget(self.cExcel); h.addWidget(self.cCsv); h.addStretch(); l.addLayout(h)
        
        btn = PrimaryPushButton("Generar", w); btn.clicked.connect(self._run_export); l.addWidget(btn); l.addStretch()
        return w

    def _run_export(self):
        tasks = []
        fmt = "excel" if self.cExcel.isChecked() else "csv" # Prioridad Excel
        if self.chk_bd.isChecked(): tasks.append({"tipo": "bd_full", "format": fmt, "scope": "all"})
        if self.chk_tabs.isChecked(): tasks.append({"tipo": "tabs", "format": fmt, "scope": "all"})
        if tasks: self.start_export_signal.emit(tasks)

    # 3. CONFIG (PUNTAJES)
    def _page_config(self):
        w = QWidget(); l = QVBoxLayout(w)
        splitter = QSplitter(Qt.Vertical)
        
        # Org
        wO = QWidget(); lO = QVBoxLayout(wO)
        h = QHBoxLayout(); h.addWidget(StrongBodyLabel("Organismos", w)); self.txtFilt = LineEdit(); self.txtFilt.setPlaceholderText("Filtrar..."); self.txtFilt.textChanged.connect(self._filter_org)
        h.addWidget(self.txtFilt); lO.addLayout(h)
        self.tabOrg = TableWidget(w); self.tabOrg.setColumnCount(4); self.tabOrg.setHorizontalHeaderLabels(["ID", "Nombre", "Estado", "Pts"])
        self.tabOrg.verticalHeader().hide(); self.tabOrg.setColumnHidden(0, True); self.tabOrg.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tabOrg.cellDoubleClicked.connect(self._dbl_org); lO.addWidget(self.tabOrg); splitter.addWidget(wO)
        
        # Keyword
        wK = QWidget(); lK = QVBoxLayout(wK)
        hK = QHBoxLayout(); self.txtKw = LineEdit(); self.txtKw.setPlaceholderText("Nueva keyword...")
        self.sKw = SpinBox(); self.sKw.setRange(-50, 50); self.sKw.setValue(5)
        btnK = PushButton("Agregar"); btnK.clicked.connect(self._add_kw)
        hK.addWidget(self.txtKw); hK.addWidget(self.sKw); hK.addWidget(btnK); lK.addLayout(hK)
        
        self.tabKw = TableWidget(w); self.tabKw.setColumnCount(5); self.tabKw.setHorizontalHeaderLabels(["ID", "KW", "N", "D", "P"])
        self.tabKw.verticalHeader().hide(); self.tabKw.setColumnHidden(0, True); self.tabKw.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tabKw.cellDoubleClicked.connect(self._dbl_kw); lK.addWidget(self.tabKw); splitter.addWidget(wK)
        
        l.addWidget(splitter)
        btnRecalc = PrimaryPushButton("Guardar y Recalcular"); btnRecalc.clicked.connect(lambda: [self.settings_changed_signal.emit(), self.start_recalculate_signal.emit()])
        l.addWidget(btnRecalc)
        
        self._load_orgs(); self._load_kws()
        return w

    def _load_orgs(self):
        self.tabOrg.setSortingEnabled(False); self.tabOrg.setRowCount(0)
        orgs = self.db_service.get_all_organisms()
        reglas = {r.organismo_id: r for r in self.db_service.get_all_organismo_reglas()}
        self.tabOrg.setRowCount(len(orgs))
        for r, o in enumerate(orgs):
            reg = reglas.get(o.organismo_id)
            st, pts, col = "Neutro", "0", COLOR_NEUTRO
            if reg:
                if reg.tipo == TipoReglaOrganismo.PRIORITARIO: st, pts, col = "Prioritario", str(reg.puntos), COLOR_PRIORITARIO
                elif reg.tipo == TipoReglaOrganismo.NO_DESEADO: st, pts, col = "No Deseado", "N/A", COLOR_NO_DESEADO
            
            for c, txt in enumerate([str(o.organismo_id), o.nombre, st, pts]):
                it = NumericTableWidgetItem(txt) if c==3 else QTableWidgetItem(txt)
                it.setBackground(QBrush(col)); self.tabOrg.setItem(r, c, it)
        self.tabOrg.setSortingEnabled(True)

    def _filter_org(self, t):
        t = t.lower(); [self.tabOrg.setRowHidden(r, t not in self.tabOrg.item(r, 1).text().lower()) for r in range(self.tabOrg.rowCount())]

    def _dbl_org(self, r, c):
        oid = int(self.tabOrg.item(r, 0).text())
        if c == 3: # Editar Puntos
            curr = self.tabOrg.item(r, 3).text()
            if curr == "N/A": return
            d = EditScoreDialog(self.tabOrg.item(r, 1).text(), curr, self)
            if d.exec(): self.db_service.set_organismo_regla(oid, TipoReglaOrganismo.PRIORITARIO, d.get_value()); self._load_orgs()
        else: # Menu
            m = QMenu(); m.addAction("Prioritario").triggered.connect(lambda: [self.db_service.set_organismo_regla(oid, TipoReglaOrganismo.PRIORITARIO, 5), self._load_orgs()])
            m.addAction("No Deseado").triggered.connect(lambda: [self.db_service.set_organismo_regla(oid, TipoReglaOrganismo.NO_DESEADO), self._load_orgs()])
            m.addAction("Neutro").triggered.connect(lambda: [self.db_service.delete_organismo_regla(oid), self._load_orgs()])
            m.exec(self.cursor().pos())

    def _load_kws(self):
        self.tabKw.setSortingEnabled(False); self.tabKw.setRowCount(0); kws = self.db_service.get_all_keywords(); self.tabKw.setRowCount(len(kws))
        for r, k in enumerate(kws):
            for c, v in enumerate([str(k.keyword_id), k.keyword, str(k.puntos_nombre), str(k.puntos_descripcion), str(k.puntos_productos)]):
                self.tabKw.setItem(r, c, NumericTableWidgetItem(v) if c>1 else QTableWidgetItem(v))
        self.tabKw.setSortingEnabled(True)

    def _add_kw(self):
        txt = self.txtKw.text().strip()
        if txt: self.db_service.add_keyword(txt, "titulo_pos", self.sKw.value()); self.txtKw.clear(); self._load_kws()

    def _dbl_kw(self, r, c):
        kid = int(self.tabKw.item(r, 0).text())
        k = self.tabKw.item(r, 1).text()
        p1 = int(self.tabKw.item(r, 2).text()); p2 = int(self.tabKw.item(r, 3).text()); p3 = int(self.tabKw.item(r, 4).text())
        d = EditKeywordDialog(kid, k, p1, p2, p3, self)
        if d.exec():
            if d.delete_requested: self.db_service.delete_keyword(kid)
            else:
                n, a, b, c = d.get_data()
                # Uso seguro de session factory
                with self.db_service.session_factory() as s:
                    s.execute(update(CaKeyword).where(CaKeyword.keyword_id==kid).values(keyword=n, puntos_nombre=a, puntos_descripcion=b, puntos_productos=c))
                    s.commit()
            self._load_kws()

    # 4. AUTO
    def _page_auto(self):
        w = QWidget(); l = QVBoxLayout(w)
        l.addWidget(SubtitleLabel("Piloto Automático", w))
        self.chkAuto = CheckBox("Extracción Diaria (Ayer)", w)
        self.chkAuto.setChecked(bool(self.settings_manager.get_setting("auto_extract_enabled")))
        self.tAuto = TimePicker(w, showSeconds=False)
        self.tAuto.setTime(QTime.fromString(self.settings_manager.get_setting("auto_extract_time") or "08:00", "HH:mm"))
        l.addWidget(self.chkAuto); l.addWidget(self.tAuto)
        
        btn = PrimaryPushButton("Guardar Config"); btn.clicked.connect(self._save_auto); l.addWidget(btn); l.addStretch()
        return w

    def _save_auto(self):
        self.settings_manager.set_setting("auto_extract_enabled", self.chkAuto.isChecked())
        try: t = self.tAuto.time.toString("HH:mm")
        except: t = self.tAuto.getTime().toString("HH:mm")
        self.settings_manager.set_setting("auto_extract_time", t)
        self.settings_manager.save_settings(self.settings_manager.config)
        self.autopilot_config_changed_signal.emit()
        InfoBar.success("Guardado", "Configuración actualizada.", parent=self.window())
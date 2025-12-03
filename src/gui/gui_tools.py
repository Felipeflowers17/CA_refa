# -*- coding: utf-8 -*-
from PySide6.QtCore import Qt, Signal, QDate, QTime, QAbstractTableModel, QModelIndex, QSortFilterProxyModel
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget, QHeaderView, 
    QTableView, QMenu, QAbstractItemView, QFrame, QDialog
)
from PySide6.QtGui import QColor, QBrush, QAction, QIcon

from qfluentwidgets import (
    SegmentedWidget, TitleLabel, BodyLabel, CalendarPicker, 
    SpinBox, PrimaryPushButton, CheckBox, TimePicker,
    LineEdit, PushButton, SubtitleLabel, ComboBox,
    InfoBar, StrongBodyLabel, Pivot, DropDownPushButton,
    FluentIcon as FIF, SwitchButton, RoundMenu, Action
)

from sqlalchemy import update
from src.utils.logger import configurar_logger
from src.db.db_models import TipoReglaOrganismo, CaPalabraClave

logger = configurar_logger(__name__)

# Colores de fondo suaves para las filas
COLOR_PRIORITARIO = QColor(230, 255, 230) # Verde suave
COLOR_NO_DESEADO = QColor(255, 230, 230)  # Rojo suave
COLOR_NEUTRO = QColor(245, 245, 245)      # Gris muy suave (Ya revisado)
COLOR_PENDIENTE = QColor(255, 255, 255)   # Blanco puro (Nuevo)

# --- MODELOS DE DATOS OPTIMIZADOS (MVC) ---

class ModeloOrganismos(QAbstractTableModel):
    """
    Modelo virtual optimizado. Se han eliminado los iconos de estado (emojis)
    para una apariencia más limpia y profesional.
    """
    RolOrdenamiento = Qt.UserRole + 10
    
    def __init__(self, organismos, reglas_dict):
        super().__init__()
        self._datos = organismos
        self._reglas = reglas_dict
        self._headers = ["ID", "Nombre del Organismo", "Estado", "Puntos"]

    def rowCount(self, parent=QModelIndex()): return len(self._datos)
    def columnCount(self, parent=QModelIndex()): return 4
    
    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid(): return None
        
        org = self._datos[index.row()]
        regla = self._reglas.get(org.organismo_id)
        es_nuevo = getattr(org, 'es_nuevo', False)
        
        col = index.column()
        
        # --- ROL DE ORDENAMIENTO ---
        if role == self.RolOrdenamiento:
            if col == 2: 
                if regla:
                    if regla.tipo == TipoReglaOrganismo.PRIORITARIO: return 0
                    if regla.tipo == TipoReglaOrganismo.NO_DESEADO: return 4
                    return 3 
                if es_nuevo: return 1 
                return 2 

            if col == 0: return org.organismo_id
            if col == 1: return org.nombre
            if col == 3: return regla.puntos if regla else 0

        # --- ROL DE VISUALIZACIÓN (TEXTO) ---
        if role == Qt.DisplayRole:
            if col == 0: return str(org.organismo_id)
            if col == 1: return org.nombre
            if col == 2: 
                if regla:
                    if regla.tipo == TipoReglaOrganismo.PRIORITARIO: return "Prioritario"
                    if regla.tipo == TipoReglaOrganismo.NO_DESEADO: return "No Deseado"
                    return "Neutro"
                return "Pendiente (Nuevo)" if es_nuevo else "Neutro"
            
            if col == 3:
                if not regla: return "0"
                return str(regla.puntos)
        
        # --- ROL DE DECORACIÓN (ICONOS) ---
        elif role == Qt.DecorationRole:
            # Solo mantenemos el icono de "Info" en la columna Nombre para los nuevos
            if col == 1 and not regla and es_nuevo:
                return FIF.INFO.icon()
            
            # ELIMINADO: Ya no devolvemos iconos para la columna 2 (Estado)
            return None

        # --- ROL DE FONDO (COLORES) ---
        elif role == Qt.BackgroundRole:
            if regla:
                if regla.tipo == TipoReglaOrganismo.PRIORITARIO: return QBrush(COLOR_PRIORITARIO)
                if regla.tipo == TipoReglaOrganismo.NO_DESEADO: return QBrush(COLOR_NO_DESEADO)
                return QBrush(COLOR_NEUTRO)
            
            return QBrush(COLOR_PENDIENTE) if es_nuevo else QBrush(COLOR_NEUTRO)
            
        return None

    def headerData(self, section, orientation, role):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self._headers[section]
        return None

    def actualizar_datos(self, organismos, reglas_dict):
        self.beginResetModel()
        self._datos = organismos
        self._reglas = reglas_dict
        self.endResetModel()

    def get_organismo_at(self, row):
        return self._datos[row]
    
    
class ModeloKeywords(QAbstractTableModel):
    def __init__(self, keywords):
        super().__init__()
        self._datos = keywords
        self._headers = ["ID", "Palabra Clave", "Pts. Título", "Pts. Desc.", "Pts. Prod."]

    def rowCount(self, parent=QModelIndex()): return len(self._datos)
    def columnCount(self, parent=QModelIndex()): return 5
    
    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid(): return None
        kw = self._datos[index.row()]
        col = index.column()
        
        if role == Qt.DisplayRole:
            if col == 0: return str(kw.keyword_id)
            if col == 1: return kw.keyword
            if col == 2: return str(kw.puntos_nombre)
            if col == 3: return str(kw.puntos_descripcion)
            if col == 4: return str(kw.puntos_productos)
        
        elif role == Qt.TextAlignmentRole:
            if col >= 2: return Qt.AlignCenter
            return Qt.AlignLeft | Qt.AlignVCenter
            
        return None

    def headerData(self, section, orientation, role):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self._headers[section]
        return None
        
    def actualizar_datos(self, keywords):
        self.beginResetModel()
        self._datos = keywords
        self.endResetModel()
        
    def get_keyword_at(self, row):
        return self._datos[row]

# --- PROXY ORDENAMIENTO PERSONALIZADO ---
class ProxyOrdenamiento(QSortFilterProxyModel):
    def lessThan(self, left, right):
        left_data = self.sourceModel().data(left, ModeloOrganismos.RolOrdenamiento)
        right_data = self.sourceModel().data(right, ModeloOrganismos.RolOrdenamiento)
        if left_data is None: return False
        if right_data is None: return True
        return left_data < right_data

# --- DIÁLOGOS DE EDICIÓN ---

class DialogoEditarPuntos(QDialog):
    def __init__(self, nombre_org, valor_actual, parent=None, es_negativo=False):
        super().__init__(parent)
        self.setWindowTitle("Asignar Puntaje")
        self.resize(300, 180)
        self.setStyleSheet("QDialog { background-color: #ffffff; }")
        
        layout = QVBoxLayout(self); layout.setSpacing(15)
        layout.addWidget(SubtitleLabel("Definir Importancia", self))
        layout.addWidget(BodyLabel(f"Organismo:\n{nombre_org}", self))
        
        h = QHBoxLayout()
        self.spin = SpinBox()
        
        # Configuración según si es Prioritario o No Deseado
        if es_negativo:
            self.spin.setRange(-1000, -1)
            self.spin.setValue(int(valor_actual) if int(valor_actual) < 0 else -100)
            lbl_desc = "Puntos (Negativo):"
        else:
            self.spin.setRange(1, 1000)
            self.spin.setValue(int(valor_actual) if int(valor_actual) > 0 else 5)
            lbl_desc = "Puntos (Positivo):"
            
        h.addWidget(StrongBodyLabel(lbl_desc, self)); h.addWidget(self.spin)
        layout.addLayout(h)
        
        h_btn = QHBoxLayout(); btn_save = PrimaryPushButton("Guardar", self); btn_save.clicked.connect(self.accept)
        h_btn.addStretch(); h_btn.addWidget(btn_save); layout.addLayout(h_btn)
    
    def obtener_valor(self): return self.spin.value()

class DialogoEditarKeyword(QDialog):
    def __init__(self, kw_obj, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Editar Palabra Clave")
        self.resize(400, 300)
        self.solicita_borrar = False
        self.setStyleSheet("QDialog { background-color: #ffffff; }")
        l = QVBoxLayout(self); l.setSpacing(15)
        l.addWidget(StrongBodyLabel("Palabra Clave:", self))
        self.txtNombre = LineEdit(); self.txtNombre.setText(kw_obj.keyword); l.addWidget(self.txtNombre)
        
        def row(lbl, val):
            h = QHBoxLayout(); chk = CheckBox(lbl); spin = SpinBox(); spin.setRange(-100, 100)
            chk.setChecked(val != 0); spin.setValue(val if val!=0 else 5); spin.setEnabled(chk.isChecked())
            chk.stateChanged.connect(lambda: spin.setEnabled(chk.isChecked()))
            h.addWidget(chk); h.addStretch(); h.addWidget(spin); l.addLayout(h)
            return chk, spin
        self.cN, self.sN = row("Título", kw_obj.puntos_nombre)
        self.cD, self.sD = row("Descripción", kw_obj.puntos_descripcion)
        self.cP, self.sP = row("Productos", kw_obj.puntos_productos)
        h = QHBoxLayout()
        btnDel = PushButton("Eliminar", self); btnDel.setStyleSheet("color: red;"); btnDel.clicked.connect(self.on_delete)
        btnSave = PrimaryPushButton("Guardar", self); btnSave.clicked.connect(self.accept)
        h.addWidget(btnDel); h.addStretch(); h.addWidget(btnSave); l.addLayout(h)

    def on_delete(self): self.solicita_borrar = True; self.accept()
    def obtener_datos(self):
        return (self.txtNombre.text(), self.sN.value() if self.cN.isChecked() else 0,
                self.sD.value() if self.cD.isChecked() else 0, self.sP.value() if self.cP.isChecked() else 0)

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
        for k,v in [("extraer","Extraer"), ("exportar","Exportar"), ("config","Puntajes"), ("auto","Avanzado")]: 
            self.pivot.addItem(k,v)
        self.pivot.setCurrentItem("extraer")
        layout.addWidget(self.pivot)
        
        self.stack = QStackedWidget(self); layout.addWidget(self.stack)
        self.stack.addWidget(self._pag_extraer())
        self.stack.addWidget(self._pag_exportar())
        self.stack.addWidget(self._pag_config())
        self.stack.addWidget(self._pag_auto())
        
        self.pivot.currentItemChanged.connect(lambda k: self.stack.setCurrentIndex(["extraer", "exportar", "config", "auto"].index(k)))

    # --- PÁGINAS BÁSICAS ---
    def _pag_extraer(self):
        w = QWidget(); l = QVBoxLayout(w); l.setSpacing(20)
        l.addWidget(SubtitleLabel("Scraping Manual", w))
        hD = QHBoxLayout()
        v1 = QVBoxLayout(); v1.addWidget(BodyLabel("Desde", w)); self.dFrom = CalendarPicker(w); self.dFrom.setDate(QDate.currentDate().addDays(-7)); v1.addWidget(self.dFrom)
        v2 = QVBoxLayout(); v2.addWidget(BodyLabel("Hasta", w)); self.dTo = CalendarPicker(w); self.dTo.setDate(QDate.currentDate()); v2.addWidget(self.dTo)
        hD.addLayout(v1); hD.addSpacing(20); hD.addLayout(v2); hD.addStretch(); l.addLayout(hD)
        hP = QHBoxLayout(); hP.addWidget(BodyLabel("Máx Páginas:", w)); self.sPages = SpinBox(); self.sPages.setValue(0); hP.addWidget(self.sPages); hP.addStretch(); l.addLayout(hP)
        btn = PrimaryPushButton("Iniciar Scraping", w); btn.clicked.connect(self._ejecutar_scraping); l.addWidget(btn); l.addStretch()
        return w
    def _ejecutar_scraping(self):
        try: d_from = self.dFrom.date.toPython(); d_to = self.dTo.date.toPython()
        except: d_from = self.dFrom.getDate().toPython(); d_to = self.dTo.getDate().toPython()
        self.senal_iniciar_scraping.emit({"mode": "to_db", "date_from": d_from, "date_to": d_to, "max_paginas": self.sPages.value()})

    def _pag_exportar(self):
        w = QWidget(); l = QVBoxLayout(w); l.setSpacing(20)
        l.addWidget(SubtitleLabel("Configuración de Exportación", w))
        
        # Sección 1: Qué exportar
        l.addWidget(StrongBodyLabel("1. Selecciona los datos:", w))
        
        container_data = QWidget(); h_data = QHBoxLayout(container_data); h_data.setContentsMargins(10,0,0,0)
        self.chk_bd = CheckBox("Base de Datos Completa (Backup)", w)
        self.chk_tabs = CheckBox("Pestañas Visibles (Gestión)", w); self.chk_tabs.setChecked(True)
        self.chk_config = CheckBox("Keywords y Organismos (Reglas)", w) # NUEVO
        
        h_data.addWidget(self.chk_bd); h_data.addWidget(self.chk_tabs); h_data.addWidget(self.chk_config)
        l.addWidget(container_data)
        
        l.addWidget(QFrame(frameShape=QFrame.HLine)) # Separador visual
        
        # Sección 2: Formatos
        l.addWidget(StrongBodyLabel("2. Selecciona formatos:", w))
        
        container_fmt = QWidget(); h_fmt = QHBoxLayout(container_fmt); h_fmt.setContentsMargins(10,0,0,0)
        self.chk_excel = CheckBox("Excel (.xlsx)", w); self.chk_excel.setChecked(True)
        self.chk_csv = CheckBox("CSV (.csv)", w) # NUEVO
        
        h_fmt.addWidget(self.chk_excel); h_fmt.addWidget(self.chk_csv); h_fmt.addStretch()
        l.addWidget(container_fmt)
        
        l.addStretch()
        
        # Botón Generar
        btn = PrimaryPushButton("Generar Archivos", w)
        btn.clicked.connect(self._generar_tareas_exportacion)
        l.addWidget(btn)
        
        return w
    
    def _generar_tareas_exportacion(self):
        # 1. Detectar Tipos de Datos
        tipos_seleccionados = []
        if self.chk_bd.isChecked(): tipos_seleccionados.append("bd_full")
        if self.chk_tabs.isChecked(): tipos_seleccionados.append("tabs")
        if self.chk_config.isChecked(): tipos_seleccionados.append("config")
        
        # 2. Detectar Formatos
        formatos_seleccionados = []
        if self.chk_excel.isChecked(): formatos_seleccionados.append("excel")
        if self.chk_csv.isChecked(): formatos_seleccionados.append("csv")
        
        # Validaciones
        if not tipos_seleccionados:
            InfoBar.warning("Falta selección", "Selecciona al menos un tipo de datos.", parent=self.window())
            return
        if not formatos_seleccionados:
            InfoBar.warning("Falta formato", "Selecciona al menos un formato (Excel o CSV).", parent=self.window())
            return
            
        # 3. Generar Matriz de Tareas (Producto Cartesiano)
        # Si selecciona 2 tipos y 2 formatos, se generan 4 tareas.
        lista_tareas = []
        for tipo in tipos_seleccionados:
            for fmt in formatos_seleccionados:
                lista_tareas.append({
                    "tipo": tipo,
                    "format": fmt,
                    "scope": "all"
                })
        
        # Emitir señal con todas las tareas
        self.senal_iniciar_exportacion.emit(lista_tareas)

    def _pag_auto(self):
        w = QWidget(); l = QVBoxLayout(w); l.addWidget(SubtitleLabel("Piloto Automático", w))
        self.chkAuto = CheckBox("Extracción Diaria (Ayer)", w); self.chkAuto.setChecked(bool(self.settings_manager.obtener_valor("auto_extract_enabled")))
        self.tAuto = TimePicker(w, showSeconds=False); self.tAuto.setTime(QTime.fromString(self.settings_manager.obtener_valor("auto_extract_time") or "08:00", "HH:mm"))
        l.addWidget(self.chkAuto); l.addWidget(self.tAuto)
        btn = PrimaryPushButton("Guardar Config"); btn.clicked.connect(self._guardar_auto); l.addWidget(btn); l.addStretch(); return w
    def _guardar_auto(self):
        self.settings_manager.establecer_valor("auto_extract_enabled", self.chkAuto.isChecked())
        try: t = self.tAuto.time.toString("HH:mm")
        except: t = self.tAuto.getTime().toString("HH:mm")
        self.settings_manager.establecer_valor("auto_extract_time", t)
        self.settings_manager.guardar_configuracion(self.settings_manager.config)
        self.senal_config_autopiloto_cambiada.emit()
        InfoBar.success("Guardado", "Configuración actualizada.", parent=self.window())

    # --- PÁGINA CONFIGURACIÓN (PUNTAJES) ---
    
    def _pag_config(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(10)

        # Pivote Interno
        self.pivot_conf = Pivot(w)
        self.pivot_conf.addItem("orgs", "Organismos")
        self.pivot_conf.addItem("kws", "Palabras Clave")
        self.pivot_conf.setCurrentItem("orgs")
        
        self.stack_conf = QStackedWidget(w)
        
        # --- TAB ORGANISMOS ---
        w_org = QWidget(); l_org = QVBoxLayout(w_org)
        
        # 1. Barra de Herramientas Superior
        h_tools = QHBoxLayout()
        self.txtFiltroOrg = LineEdit(); self.txtFiltroOrg.setPlaceholderText("Buscar organismo...")
        self.txtFiltroOrg.textChanged.connect(self._filtrar_orgs)
        
        # Filtro de Estado (Ver Nuevos)
        self.switchNuevos = SwitchButton(w_org)
        self.switchNuevos.setOnText("Solo Pendientes")
        self.switchNuevos.setOffText("Todos")
        self.switchNuevos.checkedChanged.connect(self._toggle_solo_nuevos)
        
        # Botón Acción Masiva (DropDown)
        self.btnMasivo = DropDownPushButton(FIF.EDIT, "Gestión Masiva", w_org)
        menu_masivo = RoundMenu(parent=self.btnMasivo)
        
        # Acciones Masivas (EDITADO: Se eliminó Restablecer a Pendiente)
        menu_masivo.addAction(Action(FIF.HEART, "Marcar Prioritario (+5)", triggered=lambda: self._accion_masiva_tipo(TipoReglaOrganismo.PRIORITARIO)))
        menu_masivo.addAction(Action(FIF.ACCEPT, "Marcar Neutro (0)", triggered=lambda: self._accion_masiva_tipo(TipoReglaOrganismo.NEUTRO)))
        menu_masivo.addAction(Action(FIF.DELETE, "Marcar No Deseado (-100)", triggered=lambda: self._accion_masiva_tipo(TipoReglaOrganismo.NO_DESEADO)))
        
        self.btnMasivo.setMenu(menu_masivo)
        
        h_tools.addWidget(self.txtFiltroOrg, 1)
        h_tools.addSpacing(10)
        h_tools.addWidget(self.switchNuevos)
        h_tools.addSpacing(10)
        h_tools.addWidget(self.btnMasivo)
        l_org.addLayout(h_tools)

        # 2. Tabla Organismos
        self.tblOrgs = QTableView()
        self.tblOrgs.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tblOrgs.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tblOrgs.setAlternatingRowColors(True)
        self.tblOrgs.verticalHeader().hide()
        self.tblOrgs.setSortingEnabled(True) 
        
        self.modeloOrgs = ModeloOrganismos([], {})
        self.proxyOrgs = ProxyOrdenamiento(self)
        self.proxyOrgs.setSourceModel(self.modeloOrgs)
        self.proxyOrgs.setFilterKeyColumn(1)
        self.proxyOrgs.setFilterCaseSensitivity(Qt.CaseInsensitive)
        
        self.tblOrgs.setModel(self.proxyOrgs)
        
        self.tblOrgs.setColumnHidden(0, True) 
        self.tblOrgs.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tblOrgs.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self.tblOrgs.setColumnWidth(2, 160)
        
        self.tblOrgs.doubleClicked.connect(self._doble_click_org)
        l_org.addWidget(self.tblOrgs)
        self.stack_conf.addWidget(w_org)

        # --- TAB KEYWORDS ---
        w_kw = QWidget(); l_kw = QVBoxLayout(w_kw)
        
        # Barra Crear Keyword
        h_create = QHBoxLayout()
        self.txtNewKw = LineEdit(); self.txtNewKw.setPlaceholderText("Nueva palabra clave...")
        btnNewKw = PrimaryPushButton("Agregar")
        btnNewKw.clicked.connect(self._crear_kw)
        h_create.addWidget(self.txtNewKw); h_create.addWidget(btnNewKw)
        l_kw.addLayout(h_create)
        
        # Tabla Keywords
        self.tblKws = QTableView()
        self.tblKws.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tblKws.setAlternatingRowColors(True)
        self.tblKws.verticalHeader().hide()
        self.tblKws.setShowGrid(False)
        
        self.modeloKws = ModeloKeywords([])
        self.tblKws.setModel(self.modeloKws)
        
        self.tblKws.setColumnHidden(0, True) 
        self.tblKws.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tblKws.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.tblKws.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.tblKws.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        
        self.tblKws.doubleClicked.connect(self._doble_click_kw)
        l_kw.addWidget(self.tblKws)
        self.stack_conf.addWidget(w_kw)

        # Layout Final
        layout.addWidget(self.pivot_conf)
        layout.addWidget(self.stack_conf)
        
        btnRecalc = PrimaryPushButton("Guardar y Recalcular")
        btnRecalc.clicked.connect(lambda: [self.senal_configuracion_cambiada.emit(), self.senal_iniciar_recalculo.emit()])
        layout.addWidget(btnRecalc)

        self.pivot_conf.currentItemChanged.connect(lambda k: self.stack_conf.setCurrentIndex(0 if k == "orgs" else 1))
        
        self._cargar_datos_config()
        return w

    def _cargar_datos_config(self):
        orgs = self.db_service.obtener_todos_organismos()
        reglas = {r.organismo_id: r for r in self.db_service.obtener_reglas_organismos()}
        self.modeloOrgs.actualizar_datos(orgs, reglas)
        kws = self.db_service.obtener_todas_palabras_clave()
        self.modeloKws.actualizar_datos(kws)

    # --- LÓGICA ORGANISMOS ---
    def _filtrar_orgs(self, texto):
        self.proxyOrgs.setFilterFixedString(texto)

    def _toggle_solo_nuevos(self, checked):
        if checked:
            # Filtro exacto para "Pendiente (Nuevo)" en columna Estado (idx 2)
            self.proxyOrgs.setFilterKeyColumn(2)
            self.proxyOrgs.setFilterFixedString("Pendiente (Nuevo)")
        else:
            self.proxyOrgs.setFilterKeyColumn(1)
            self.proxyOrgs.setFilterFixedString(self.txtFiltroOrg.text())

    def _doble_click_org(self, index):
        real_idx = self.proxyOrgs.mapToSource(index)
        org = self.modeloOrgs.get_organismo_at(real_idx.row())
        
        menu = RoundMenu(parent=self)
        
        menu.addAction(Action(FIF.HEART, "Prioritario...", triggered=lambda: self._dialogo_puntos(org, negativo=False)))
        menu.addAction(Action(FIF.DELETE, "No Deseado...", triggered=lambda: self._dialogo_puntos(org, negativo=True)))
        menu.addSeparator()
        # Se mantiene solo la opción de Marcar Neutro
        menu.addAction(Action(FIF.ACCEPT, "Marcar Neutro (0)", triggered=lambda: self._set_org_regla(org.organismo_id, TipoReglaOrganismo.NEUTRO, 0)))
        
        menu.exec(self.cursor().pos())

    def _dialogo_puntos(self, org, negativo=False):
        # Valor por defecto sugerido
        val_default = "-100" if negativo else "5"
        d = DialogoEditarPuntos(org.nombre, val_default, self, es_negativo=negativo)
        
        if d.exec():
            tipo = TipoReglaOrganismo.NO_DESEADO if negativo else TipoReglaOrganismo.PRIORITARIO
            self._set_org_regla(org.organismo_id, tipo, d.obtener_valor())

    def _set_org_regla(self, oid, tipo, pts=None):
        if tipo is None: self.db_service.eliminar_regla_organismo(oid)
        else: self.db_service.establecer_regla_organismo(oid, tipo, pts)
        self._cargar_datos_config()

    def _accion_masiva_tipo(self, tipo):
        indices = self.tblOrgs.selectionModel().selectedRows()
        if not indices:
            InfoBar.warning("Sin selección", "Selecciona al menos un organismo.", parent=self.window())
            return
        
        ids = []
        for idx in indices:
            real_idx = self.proxyOrgs.mapToSource(idx)
            org = self.modeloOrgs.get_organismo_at(real_idx.row())
            ids.append(org.organismo_id)
            
        for oid in ids:
            if tipo is None: 
                self.db_service.eliminar_regla_organismo(oid)
            else: 
                # Puntos por defecto para masivo
                pts = 0
                if tipo == TipoReglaOrganismo.PRIORITARIO: pts = 5
                elif tipo == TipoReglaOrganismo.NO_DESEADO: pts = -100
                elif tipo == TipoReglaOrganismo.NEUTRO: pts = 0
                
                self.db_service.establecer_regla_organismo(oid, tipo, pts)
            
        self._cargar_datos_config()
        InfoBar.success("Proceso completado", f"Se actualizaron {len(ids)} organismos.", parent=self.window())

    # --- LÓGICA KEYWORDS ---
    def _crear_kw(self):
        txt = self.txtNewKw.text().strip()
        if txt:
            self.db_service.agregar_palabra_clave(txt, "titulo_pos", 5)
            self.txtNewKw.clear()
            self._cargar_datos_config()

    def _doble_click_kw(self, index):
        real_idx = index 
        kw = self.modeloKws.get_keyword_at(real_idx.row())
        d = DialogoEditarKeyword(kw, self)
        if d.exec():
            if d.solicita_borrar:
                self.db_service.eliminar_palabra_clave(kw.keyword_id)
            else:
                n, a, b, c = d.obtener_datos()
                with self.db_service.session_factory() as s:
                    s.execute(update(CaPalabraClave).where(CaPalabraClave.keyword_id==kw.keyword_id).values(keyword=n, puntos_nombre=a, puntos_descripcion=b, puntos_productos=c))
                    s.commit()
            self._cargar_datos_config()
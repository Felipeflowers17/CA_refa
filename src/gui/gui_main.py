# -*- coding: utf-8 -*-
import sys
import os
import datetime
from typing import List

from PySide6.QtCore import QThreadPool, QTimer, Qt, Slot, QTime, QDate
from PySide6.QtGui import QStandardItemModel, QIcon, QFont
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QTableView, QFrame, QSystemTrayIcon, QMenu, QStyle, QFileDialog,
    QMessageBox, QAbstractSpinBox, QComboBox
)

from qfluentwidgets import (
    FluentWindow, NavigationItemPosition, FluentIcon as FIF,
    ProgressBar, InfoBar, CheckBox, SpinBox, BodyLabel, LineEdit,
    ToolButton, Flyout, FlyoutAnimationType, SwitchButton, StrongBodyLabel, 
    CalendarPicker, PrimaryPushButton
)

# Componentes Propios
from src.gui.gui_detail_drawer import PanelLateralDetalle
from src.gui.gui_tools import WidgetHerramientas
from src.utils.logger import configurar_logger
from src.utils.settings_manager import GestorConfiguracion

# Servicios Backend
from src.db.session import SessionLocal
from src.db.db_service import DbService
from src.logic.etl_service import ServicioEtl
from src.logic.excel_service import ServicioExcel
from src.logic.score_engine import MotorPuntajes
from src.scraper.scraper_service import ServicioScraper
from src.gui.gui_models import ModeloProxyLicitacion

# Mixins
from .mixins.threading_mixin import MixinHilos
from .mixins.main_slots_mixin import MixinSlotsPrincipales
from .mixins.data_loader_mixin import MixinCargaDatos
from .mixins.context_menu_mixin import MixinMenuContextual
from .mixins.table_manager_mixin import MixinGestorTabla, COLUMN_HEADERS

logger = configurar_logger(__name__)

# --- Clases Auxiliares de UI ---

class CheckableComboBox(QComboBox):
    from PySide6.QtCore import Signal
    checkedChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.view().pressed.connect(self.handleItemPressed)
        self._changed = False
        self.setMaxVisibleItems(10)
        self.setStyleSheet("QComboBox { padding: 5px; }") 
        valid_font = QFont("Segoe UI", 10)
        self.setFont(valid_font)

    def handleItemPressed(self, index):
        item = self.model().itemFromIndex(index)
        if item.checkState() == Qt.Checked:
            item.setCheckState(Qt.Unchecked)
        else:
            item.setCheckState(Qt.Checked)
        self.checkedChanged.emit()
        self._changed = True

    def hidePopup(self):
        if not self._changed:
            super().hidePopup()
        self._changed = False

    def addItem(self, text, userData=None):
        super().addItem(text, userData)
        item = self.model().item(self.count() - 1, 0)
        item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
        item.setCheckState(Qt.Unchecked)

    def addItems(self, texts):
        for t in texts:
            self.addItem(t)

    def checkedItems(self):
        items = []
        for i in range(self.count()):
            item = self.model().item(i, 0)
            if item.checkState() == Qt.Checked:
                items.append(item)
        return items

    def setItemChecked(self, index, checked):
        if index < 0 or index >= self.count(): return
        item = self.model().item(index, 0)
        item.setCheckState(Qt.Checked if checked else Qt.Unchecked)

class ClickableContainer(QWidget):
    from PySide6.QtCore import Signal
    clicked = Signal() 
    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)
    def setSelected(self, isSelected: bool): pass
    def setCompacted(self, compacted: bool): pass 

class InterfazTabla(QWidget):
    from PySide6.QtCore import Signal
    filtrosCambios = Signal()

    def __init__(self, object_name, parent=None):
        super().__init__(parent=parent)
        self.setObjectName(object_name)
        
        self.estado_filtro = {
            "2do_llamado": False, "monto": 0, "show_zeros": False, 
            "selected_states": [], "pub_from": None, "pub_to": None,
            "close_from": None, "close_to": None
        }
        
        self.estados_disponibles = [
            "Publicada", "Cerrada", "Desierta", "Adjudicada", 
            "OC Emitida", "Cancelada", "Revocada", "Suspendida"
        ]

        self.vBoxLayout = QVBoxLayout(self)
        self.vBoxLayout.setContentsMargins(20, 20, 20, 20)
        self.vBoxLayout.setSpacing(10)
        
        self.topLayout = QHBoxLayout()
        self.barraBusqueda = LineEdit()
        self.barraBusqueda.setPlaceholderText("Buscar por Código, Nombre u Organismo...")
        self.barraBusqueda.setClearButtonEnabled(True)
        
        self.botonFiltro = ToolButton(FIF.FILTER, self)
        self.botonFiltro.setToolTip("Filtros Avanzados")
        self.botonFiltro.clicked.connect(self._mostrar_popup_filtros)
        
        self.topLayout.addWidget(self.barraBusqueda, 1)
        self.topLayout.addWidget(self.botonFiltro)
        self.vBoxLayout.addLayout(self.topLayout)

        self.contenedorTabla = QFrame()
        self.layoutTabla = QVBoxLayout(self.contenedorTabla)
        self.layoutTabla.setContentsMargins(0, 5, 0, 0)
        self.vBoxLayout.addWidget(self.contenedorTabla)

    def _mostrar_popup_filtros(self):
        self.vista_filtro = QFrame()
        self.vista_filtro.setObjectName("FilterFlyout")
        self.vista_filtro.setFixedWidth(450) 
        self.vista_filtro.setStyleSheet("QFrame#FilterFlyout { background-color: #ffffff; border: 1px solid #e5e5e5; border-radius: 8px; } QLabel { background-color: transparent; }")
        
        layout = QVBoxLayout(self.vista_filtro)
        layout.setSpacing(15); layout.setContentsMargins(20, 20, 20, 20)
        
        h_top = QHBoxLayout()
        lbl_zeros = BodyLabel("Mostrar Puntajes 0")
        switch_zeros = SwitchButton()
        switch_zeros.setOnText("Sí"); switch_zeros.setOffText("No")
        switch_zeros.setChecked(self.estado_filtro["show_zeros"])
        switch_zeros.checkedChanged.connect(lambda c: self._actualizar_filtro("show_zeros", c))
        h_top.addWidget(lbl_zeros); h_top.addStretch(); h_top.addWidget(switch_zeros)
        layout.addLayout(h_top); layout.addWidget(self._sep())

        h_monto = QHBoxLayout()
        h_monto.addWidget(StrongBodyLabel("Monto Mínimo ($):"))
        h_monto.addStretch()
        spin_monto = SpinBox()
        spin_monto.setRange(0, 999999999); spin_monto.setSingleStep(100000); spin_monto.setFixedWidth(140)
        spin_monto.setButtonSymbols(QAbstractSpinBox.NoButtons)
        spin_monto.setValue(self.estado_filtro["monto"])
        spin_monto.valueChanged.connect(lambda v: self._actualizar_filtro("monto", v))
        h_monto.addWidget(spin_monto)
        layout.addLayout(h_monto); layout.addWidget(self._sep())

        layout.addWidget(StrongBodyLabel("Filtro de Estados"))
        chk_2do = CheckBox("Solo 2° Llamado")
        chk_2do.setChecked(self.estado_filtro["2do_llamado"])
        chk_2do.stateChanged.connect(lambda s: self._actualizar_filtro("2do_llamado", chk_2do.isChecked()))
        layout.addWidget(chk_2do)
        
        self.combo_states = CheckableComboBox()
        self.combo_states.setPlaceholderText("Seleccionar estados...")
        self.combo_states.addItems(self.estados_disponibles)
        for i, state in enumerate(self.estados_disponibles):
            if state in self.estado_filtro["selected_states"]:
                self.combo_states.setItemChecked(i, True)
        self.combo_states.checkedChanged.connect(self._al_cambiar_combo_estados)
        layout.addWidget(self.combo_states); layout.addWidget(self._sep())

        def crear_bloque_fecha(titulo, key_from, key_to, cal_from_attr, cal_to_attr):
            container = QWidget(); v_layout = QVBoxLayout(container); v_layout.setContentsMargins(0,0,0,0); v_layout.setSpacing(8)
            v_layout.addWidget(StrongBodyLabel(titulo))
            h_inputs = QHBoxLayout(); h_inputs.setSpacing(15)
            v_from = QVBoxLayout(); v_from.setSpacing(2); v_from.addWidget(BodyLabel("Desde", self))
            cal_from = CalendarPicker(); cal_from.setDateFormat(Qt.ISODate); setattr(self, cal_from_attr, cal_from) 
            v_from.addWidget(cal_from)
            v_to = QVBoxLayout(); v_to.setSpacing(2); v_to.addWidget(BodyLabel("Hasta", self))
            cal_to = CalendarPicker(); cal_to.setDateFormat(Qt.ISODate); setattr(self, cal_to_attr, cal_to) 
            v_to.addWidget(cal_to)
            h_inputs.addLayout(v_from); h_inputs.addLayout(v_to); v_layout.addLayout(h_inputs)
            return container

        block_pub = crear_bloque_fecha("Fecha de Publicación", "pub_from", "pub_to", "cal_pub_from", "cal_pub_to")
        layout.addWidget(block_pub)
        # Uso de QDate
        if self.estado_filtro["pub_from"]: self.cal_pub_from.setDate(QDate(self.estado_filtro["pub_from"]))
        if self.estado_filtro["pub_to"]: self.cal_pub_to.setDate(QDate(self.estado_filtro["pub_to"]))
        self.cal_pub_from.dateChanged.connect(lambda d: self._actualizar_fecha("pub_from", d))
        self.cal_pub_to.dateChanged.connect(lambda d: self._actualizar_fecha("pub_to", d))

        layout.addSpacing(5)
        block_close = crear_bloque_fecha("Fecha de Cierre", "close_from", "close_to", "cal_close_from", "cal_close_to")
        layout.addWidget(block_close)
        if self.estado_filtro["close_from"]: self.cal_close_from.setDate(QDate(self.estado_filtro["close_from"]))
        if self.estado_filtro["close_to"]: self.cal_close_to.setDate(QDate(self.estado_filtro["close_to"]))
        self.cal_close_from.dateChanged.connect(lambda d: self._actualizar_fecha("close_from", d))
        self.cal_close_to.dateChanged.connect(lambda d: self._actualizar_fecha("close_to", d))

        layout.addStretch()
        h_reset = QHBoxLayout(); h_reset.addStretch()
        btn_reset = ToolButton(FIF.DELETE, self); btn_reset.setToolTip("Limpiar Filtros")
        btn_reset.clicked.connect(self._resetear_filtros)
        h_reset.addWidget(btn_reset); layout.addLayout(h_reset)
        Flyout.make(self.vista_filtro, self.botonFiltro, self, FlyoutAnimationType.DROP_DOWN)

    def _sep(self):
        sep = QFrame(); sep.setFrameShape(QFrame.HLine); sep.setStyleSheet("background-color: #eee; margin: 4px 0;")
        return sep

    def _actualizar_filtro(self, key, value):
        self.estado_filtro[key] = value
        self.filtrosCambios.emit()
        
    def _actualizar_fecha(self, key, qdate: QDate):
        self.estado_filtro[key] = qdate.toPython()
        self.filtrosCambios.emit()

    def _al_cambiar_combo_estados(self):
        items = self.combo_states.checkedItems()
        self.estado_filtro["selected_states"] = [item.text() for item in items]
        self.filtrosCambios.emit()

    def _resetear_filtros(self):
        self.estado_filtro = { "2do_llamado": False, "monto": 0, "show_zeros": False, "selected_states": [], "pub_from": None, "pub_to": None, "close_from": None, "close_to": None }
        self.filtrosCambios.emit()

# --- CLASE PRINCIPAL ---
class MainWindow(FluentWindow, MixinHilos, MixinSlotsPrincipales, MixinCargaDatos, MixinMenuContextual, MixinGestorTabla):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Monitor CA - Gestión Licitaciones")
        self.resize(1280, 800)
        self.forzar_cierre = False
        self.thread_pool = QThreadPool.globalInstance()
        self.trabajadores_activos = []
        self.tarea_en_ejecucion = False
        self.ultimo_error = None
        self.log_tareas_ejecutadas = set()
        
        # INICIALIZACIÓN DE SERVICIOS (BACKEND)
        try:
            self.settings_manager = GestorConfiguracion()
            self.db_service = DbService(SessionLocal) 
            self.servicio_scraper = ServicioScraper()
            self.servicio_excel = ServicioExcel(self.db_service)
            self.motor_puntajes = MotorPuntajes(self.db_service)
            self.servicio_etl = ServicioEtl(self.db_service, self.servicio_scraper, self.motor_puntajes)
        except Exception as e:
            logger.critical(f"Error fatal iniciando servicios: {e}")
            sys.exit(1)

        # Timers
        self.timer_programador = QTimer(self)
        self.timer_programador.timeout.connect(self.verificar_tareas_programadas)
        
        # Barra de estado inferior
        self.contenedor_progreso = ClickableContainer(self)
        self.layout_progreso = QVBoxLayout(self.contenedor_progreso)
        self.layout_progreso.setContentsMargins(10, 0, 10, 0); self.layout_progreso.setSpacing(5)
        self.lbl_estado_progreso = BodyLabel("Listo", self); self.lbl_estado_progreso.setStyleSheet("color: gray; font-size: 12px;")
        self.barra_progreso = ProgressBar(self); self.barra_progreso.setRange(0, 100); self.barra_progreso.setValue(0); self.barra_progreso.hide()
        self.layout_progreso.addWidget(self.lbl_estado_progreso); self.layout_progreso.addWidget(self.barra_progreso)

        self.tray_icon = None

        # 1. Tab Candidatas
        self.interfazCandidatas = InterfazTabla("tab_unified", self)
        self.modelo_tab1 = QStandardItemModel(0, len(COLUMN_HEADERS))
        self.proxy_tab1 = ModeloProxyLicitacion(self)
        self.proxy_tab1.setSourceModel(self.modelo_tab1)
        self.tabla_unificada = self.crear_tabla_view(self.modelo_tab1, "tab_unified")
        self.tabla_unificada.setModel(self.proxy_tab1) 
        self.interfazCandidatas.layoutTabla.addWidget(self.tabla_unificada)
        
        # 2. Tab Seguimiento
        self.interfazSeguimiento = InterfazTabla("tab_seguimiento", self)
        self.modelo_tab3 = QStandardItemModel(0, len(COLUMN_HEADERS))
        self.proxy_tab3 = ModeloProxyLicitacion(self)
        self.proxy_tab3.setSourceModel(self.modelo_tab3)
        self.tabla_seguimiento = self.crear_tabla_view(self.modelo_tab3, "tab_seguimiento")
        self.tabla_seguimiento.setModel(self.proxy_tab3)
        self.interfazSeguimiento.layoutTabla.addWidget(self.tabla_seguimiento)
        
        # 3. Tab Ofertadas
        self.interfazOfertadas = InterfazTabla("tab_ofertadas", self)
        self.modelo_tab4 = QStandardItemModel(0, len(COLUMN_HEADERS))
        self.proxy_tab4 = ModeloProxyLicitacion(self)
        self.proxy_tab4.setSourceModel(self.modelo_tab4)
        self.tabla_ofertadas = self.crear_tabla_view(self.modelo_tab4, "tab_ofertadas")
        self.tabla_ofertadas.setModel(self.proxy_tab4)
        self.interfazOfertadas.layoutTabla.addWidget(self.tabla_ofertadas)

        # Herramientas
        self.interfazHerramientas = WidgetHerramientas(self.db_service, self.settings_manager, self)
        self.interfazHerramientas.senal_iniciar_scraping.connect(self.on_start_full_scraping)
        self.interfazHerramientas.senal_iniciar_exportacion.connect(self.on_start_export_dispatch)
        self.interfazHerramientas.senal_iniciar_recalculo.connect(lambda: self.on_run_recalculate_thread(silent=True))
        self.interfazHerramientas.senal_configuracion_cambiada.connect(self.on_settings_changed)
        self.interfazHerramientas.senal_config_autopiloto_cambiada.connect(lambda: self.settings_manager.cargar_configuracion())
        
        self.detail_drawer = PanelLateralDetalle(self)

        self.initNavigation()
        self._configurar_bandeja()
        self._conectar_senales_tablas()
        
        # Arranque automático
        self.timer_programador.start(30000)
        QTimer.singleShot(500, self.on_load_data_thread)
        QTimer.singleShot(3000, self.iniciar_limpieza_silenciosa)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'detail_drawer'):
            self.detail_drawer.resize(self.detail_drawer.width(), self.height())

    def initNavigation(self):
        self.addSubInterface(self.interfazCandidatas, FIF.HOME, "Candidatas", NavigationItemPosition.TOP)
        self.addSubInterface(self.interfazSeguimiento, FIF.HEART, "Seguimiento", NavigationItemPosition.TOP)
        self.addSubInterface(self.interfazOfertadas, FIF.SHOPPING_CART, "Ofertadas", NavigationItemPosition.TOP)
        self.navigationInterface.addSeparator()
        self.navigationInterface.addItem(routeKey="update_web", icon=FIF.GLOBE, text="Actualizar info pestañas", onClick=self._mostrar_flyout_actualizacion, position=NavigationItemPosition.TOP)
        self.addSubInterface(self.interfazHerramientas, FIF.TILES, "Herramientas", NavigationItemPosition.TOP)
        self.navigationInterface.addWidget(routeKey="progress_widget", widget=self.contenedor_progreso, onClick=lambda: None, position=NavigationItemPosition.BOTTOM)
        self.navigationInterface.addItem(routeKey="refresh", icon=FIF.SYNC, text="Refrescar Tablas", onClick=self.on_load_data_thread, position=NavigationItemPosition.BOTTOM)

    def _mostrar_flyout_actualizacion(self):
        view = QFrame(); view.setObjectName("UpdateFlyout"); view.setFixedWidth(300)
        view.setStyleSheet("QFrame#UpdateFlyout { background-color: #ffffff; border: 1px solid #e5e5e5; border-radius: 8px; } QLabel { background-color: transparent; }")
        layout = QVBoxLayout(view); layout.setSpacing(10); layout.setContentsMargins(15, 15, 15, 15)
        layout.addWidget(StrongBodyLabel("Seleccionar qué actualizar:")); layout.addWidget(BodyLabel("Busca info nueva en Mercado Público.", self))
        self.chk_upd_candidatas = CheckBox("Candidatas"); self.chk_upd_seguimiento = CheckBox("Seguimiento"); self.chk_upd_ofertadas = CheckBox("Ofertadas")
        self.chk_upd_seguimiento.setChecked(True); self.chk_upd_ofertadas.setChecked(True)
        layout.addWidget(self.chk_upd_candidatas); layout.addWidget(self.chk_upd_seguimiento); layout.addWidget(self.chk_upd_ofertadas); layout.addSpacing(10)
        btn_run = PrimaryPushButton("Actualizar Ahora"); btn_run.clicked.connect(lambda: self._ejecutar_actualizacion_selectiva(view)); layout.addWidget(btn_run)
        target = self.navigationInterface.widget(routeKey="update_web")
        Flyout.make(view, target, self, FlyoutAnimationType.PULL_UP)

    def _ejecutar_actualizacion_selectiva(self, flyout_view):
        scopes = []
        if self.chk_upd_candidatas.isChecked(): scopes.append("candidatas")
        if self.chk_upd_seguimiento.isChecked(): scopes.append("seguimiento")
        if self.chk_upd_ofertadas.isChecked(): scopes.append("ofertadas")
        if not scopes: InfoBar.warning("Atención", "Debes seleccionar al menos una opción.", parent=self); return
        flyout_view.parent().close()
        if self.tarea_en_ejecucion: InfoBar.warning("Ocupado", "Ya hay una tarea en ejecución.", parent=self); return
        logger.info(f"Iniciando actualización selectiva para: {scopes}")
        
        self.start_task(task=self.servicio_etl.ejecutar_actualizacion_selectiva, on_result=lambda: logger.info("Actualización selectiva OK"), on_error=self.on_task_error, on_finished=self.on_fase2_update_finished, on_progress=self.on_progress_update, on_progress_percent=self.on_progress_percent_update, task_kwargs={"alcances": scopes})

    def _conectar_senales_tablas(self):
        ui = self.interfazCandidatas
        ui.barraBusqueda.textChanged.connect(lambda: self.actualizar_filtro_proxy(self.proxy_tab1, ui))
        ui.filtrosCambios.connect(lambda: self.actualizar_filtro_proxy(self.proxy_tab1, ui))
        self.tabla_unificada.customContextMenuRequested.connect(self.mostrar_menu_contextual)
        
        ui3 = self.interfazSeguimiento
        ui3.barraBusqueda.textChanged.connect(lambda: self.actualizar_filtro_proxy(self.proxy_tab3, ui3))
        ui3.filtrosCambios.connect(lambda: self.actualizar_filtro_proxy(self.proxy_tab3, ui3))
        self.tabla_seguimiento.customContextMenuRequested.connect(self.mostrar_menu_contextual)
        
        ui4 = self.interfazOfertadas
        ui4.barraBusqueda.textChanged.connect(lambda: self.actualizar_filtro_proxy(self.proxy_tab4, ui4))
        ui4.filtrosCambios.connect(lambda: self.actualizar_filtro_proxy(self.proxy_tab4, ui4))
        self.tabla_ofertadas.customContextMenuRequested.connect(self.mostrar_menu_contextual)

        self.tabla_unificada.doubleClicked.connect(self.on_table_double_clicked)
        self.tabla_seguimiento.doubleClicked.connect(self.on_table_double_clicked)
        self.tabla_ofertadas.doubleClicked.connect(self.on_table_double_clicked)

    def actualizar_filtro_proxy(self, proxy_model, ui_obj):
        proxy_model.establecer_parametros_filtro(
            ui_obj.barraBusqueda.text(), ui_obj.estado_filtro["monto"], ui_obj.estado_filtro["show_zeros"], ui_obj.estado_filtro["2do_llamado"],
            ui_obj.estado_filtro["selected_states"], ui_obj.estado_filtro["pub_from"], ui_obj.estado_filtro["pub_to"],
            ui_obj.estado_filtro["close_from"], ui_obj.estado_filtro["close_to"]
        )

    def poblar_tab_unificada(self, data):
        super().poblar_tab_unificada(data)
        self.actualizar_filtro_proxy(self.proxy_tab1, self.interfazCandidatas)

    @Slot()
    def on_settings_changed(self):
        logger.info("Configuración interna actualizada."); self.motor_puntajes.recargar_reglas_memoria()

    @Slot()
    def on_run_recalculate_thread(self, silent=False):
        if self.tarea_en_ejecucion: return
        if not silent:
            if QMessageBox.question(self, "Confirmar Recálculo", "Se recalcularán todos los puntajes.", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
                self._iniciar_tarea_recalculo(silent)
        else: self._iniciar_tarea_recalculo(silent)
    
    def _iniciar_tarea_recalculo(self, silent): 
        self.start_task(task=self.servicio_etl.ejecutar_recalculo_total, on_finished=lambda: self.on_recalculate_finished_custom(silent))
        
    def on_recalculate_finished_custom(self, silent): self.set_ui_busy(False); self.on_load_data_thread(); InfoBar.success("Proceso Completado", "Puntajes actualizados.", parent=self)
    
    @Slot(list)
    def on_start_export_dispatch(self, lista_tareas):
        if self.tarea_en_ejecucion: return
        saved_path = self.settings_manager.obtener_valor("user_export_path")
        if not saved_path or not os.path.exists(saved_path):
            folder = QFileDialog.getExistingDirectory(self, "Seleccionar Carpeta Base")
            if not folder: return
            self.settings_manager.establecer_valor("user_export_path", folder); self.settings_manager.guardar_configuracion(self.settings_manager.config); saved_path = folder
        
        self.start_task(task=self.servicio_excel.ejecutar_exportacion_lote, on_result=lambda r: self._mostrar_exito_exportacion(r, saved_path), on_error=self.on_task_error, task_args=(lista_tareas, saved_path))
    
    def _mostrar_exito_exportacion(self, resultados: List[str], base_path: str):
        exitos = [r for r in resultados if not r.startswith("ERROR")]
        if exitos: InfoBar.success("Exportación Finalizada", f"Archivos en: {base_path}", parent=self)
    
    def verificar_tareas_programadas(self):
        if self.tarea_en_ejecucion: return 
        self.settings_manager.cargar_configuracion()
        now_str = QTime.currentTime().toString("HH:mm"); today_str = datetime.date.today().strftime("%Y-%m-%d")
        if self.settings_manager.obtener_valor("auto_extract_enabled"):
            if now_str == self.settings_manager.obtener_valor("auto_extract_time") and f"{today_str}_extract" not in self.log_tareas_ejecutadas:
                self.log_tareas_ejecutadas.add(f"{today_str}_extract"); self.on_auto_extract_yesterday()
        if self.settings_manager.obtener_valor("auto_update_enabled"):
            if now_str == self.settings_manager.obtener_valor("auto_update_time") and f"{today_str}_update" not in self.log_tareas_ejecutadas:
                self.log_tareas_ejecutadas.add(f"{today_str}_update"); self.on_run_fase2_update_thread_auto()

    @Slot()
    def on_auto_extract_yesterday(self):
        y = datetime.date.today() - datetime.timedelta(days=1)
        self.start_task(
            task=self.servicio_etl.ejecutar_etl_completo, 
            on_finished=self.on_auto_task_finished, 
            task_kwargs={"configuracion": {"mode":"to_db", "date_from":y, "date_to":y, "max_paginas":0}}
        )
    
    @Slot(dict)
    def on_start_full_scraping(self, config: dict):
        """Inicia el proceso de scraping desde la herramienta."""
        logger.info(f"Recibida configuración de scraping: {config}")
        
        tarea_a_correr = self.servicio_etl.ejecutar_etl_completo 
        
        def al_recibir_resultado_etl(cantidad_procesada):
            logger.info("Proceso ETL completo OK")
            if isinstance(cantidad_procesada, int) and cantidad_procesada > 0:
                msg = f"Se procesaron {cantidad_procesada} registros exitosamente."
                QMessageBox.information(self, "Proceso Completado", msg)
            elif cantidad_procesada == 0:
                 QMessageBox.information(self, "Sin Resultados", "No se encontraron licitaciones nuevas en el periodo.")

        self.start_task(
            task=tarea_a_correr,
            on_result=al_recibir_resultado_etl, 
            on_error=self.on_task_error,
            on_finished=self.on_scraping_completed,
            on_progress=self.on_progress_update,
            on_progress_percent=self.on_progress_percent_update,
            task_kwargs={"configuracion": config}, 
        )

    @Slot()
    def iniciar_limpieza_silenciosa(self): 
        self.start_task(task=self.servicio_etl.ejecutar_limpieza_automatica, on_result=lambda: None)
        
    def set_ui_busy(self, busy: bool):
        self.tarea_en_ejecucion = busy
        if busy: self.barra_progreso.show(); self.lbl_estado_progreso.setText("Iniciando..."); self.setCursor(Qt.WaitCursor)
        else: self.barra_progreso.hide(); self.lbl_estado_progreso.setText("Listo"); self.barra_progreso.setValue(0); self.setCursor(Qt.ArrowCursor)
    @Slot(str)
    def on_progress_update(self, message: str): self.lbl_estado_progreso.setText(message)
    def _configurar_bandeja(self):
        self.tray_icon = QSystemTrayIcon(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)), self)
        menu = QMenu(); menu.addAction("Restaurar").triggered.connect(self.showNormal); menu.addAction("Salir").triggered.connect(self.forzar_salida)
        self.tray_icon.setContextMenu(menu); self.tray_icon.show(); self.tray_icon.activated.connect(lambda r: self.showNormal() if r == QSystemTrayIcon.DoubleClick else None)
    def forzar_salida(self): self.forzar_cierre = True; self.close(); QApplication.instance().quit()
    def closeEvent(self, event):
        if self.forzar_cierre: event.accept()
        else: event.ignore(); self.hide(); InfoBar.info("Minimizado", "La aplicación sigue en la bandeja.", parent=self)

def run_gui():
    app = QApplication(sys.argv)
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    app.setQuitOnLastWindowClosed(False)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
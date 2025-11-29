# -*- coding: utf-8 -*-
import sys
import os
import datetime
from pathlib import Path
from typing import List, Any

from PySide6.QtCore import QThreadPool, QTimer, Qt, Slot, QTime, Signal, QDate
from PySide6.QtGui import QStandardItemModel, QIcon, QAction, QFont
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QTableView, QFrame, QSystemTrayIcon, QMenu, QStyle, QFileDialog,
    QLabel, QScrollArea, QComboBox, QMessageBox, QAbstractSpinBox
)

# Librería Fluent Widgets
from qfluentwidgets import (
    FluentWindow, NavigationItemPosition, FluentIcon as FIF,
    ProgressBar, InfoBar, InfoBarPosition, CheckBox, SpinBox, BodyLabel, LineEdit,
    ToolButton, Flyout, FlyoutAnimationType, SwitchButton, StrongBodyLabel, 
    CalendarPicker, PrimaryPushButton
)

# Componentes Propios
from src.gui.gui_detail_drawer import DetailDrawer
from src.gui.gui_worker import Worker
from src.gui.gui_tools import GuiToolsWidget
from src.utils.logger import configurar_logger
from src.utils.settings_manager import SettingsManager

# Backend Services
from src.db.session import SessionLocal
from src.db.db_service import DbService
from src.logic.etl_service import EtlService
from src.logic.excel_service import ExcelService
from src.logic.score_engine import ScoreEngine
from src.scraper.scraper_service import ScraperService
from src.gui.gui_models import LicitacionProxyModel

# Mixins
from .mixins.threading_mixin import ThreadingMixin
from .mixins.main_slots_mixin import MainSlotsMixin
from .mixins.data_loader_mixin import DataLoaderMixin
from .mixins.context_menu_mixin import ContextMenuMixin
from .mixins.table_manager_mixin import TableManagerMixin, COLUMN_HEADERS

logger = configurar_logger(__name__)

# --- Clases Auxiliares de UI ---

class CheckableComboBox(QComboBox):
    checkedChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.view().pressed.connect(self.handleItemPressed)
        self._changed = False
        self.setMaxVisibleItems(10)
        self.setStyleSheet("QComboBox { padding: 5px; }") 
        
        # --- CORRECCIÓN DEFINITIVA DE FONT ---
        # En lugar de leer self.font() que puede venir rota (-1),
        # forzamos una fuente válida desde el inicio.
        valid_font = QFont("Segoe UI", 10)
        self.setFont(valid_font)
        # -------------------------------------

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
    """
    Contenedor para la barra de progreso en el menú lateral.
    """
    clicked = Signal() 
    
    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)

    def setSelected(self, isSelected: bool):
        pass
        
    # --- CORRECCIÓN CRÍTICA ---
    # Este método es requerido por FluentWindow cuando el menú se contrae.
    def setCompacted(self, compacted: bool):
        """
        Llamado por la librería cuando el menú lateral se expande o contrae.
        Podemos ocultar la barra si está compactado, o dejarlo así.
        """
        # Opcional: Ocultar contenido si está compactado
        # self.setVisible(not compacted)
        pass 
    # --------------------------

class TableInterface(QWidget):
    filtersChanged = Signal()

    def __init__(self, object_name, parent=None):
        super().__init__(parent=parent)
        self.setObjectName(object_name)
        
        self.filter_state = {
            "2do_llamado": False, "monto": 0, "show_zeros": False, 
            "selected_states": [], "pub_from": None, "pub_to": None,
            "close_from": None, "close_to": None
        }
        
        self.available_states = [
            "Publicada", "Cerrada", "Desierta", "Adjudicada", 
            "OC Emitida", "Cancelada", "Revocada", "Suspendida"
        ]

        self.vBoxLayout = QVBoxLayout(self)
        self.vBoxLayout.setContentsMargins(20, 20, 20, 20)
        self.vBoxLayout.setSpacing(10)
        
        self.topLayout = QHBoxLayout()
        self.searchBar = LineEdit()
        self.searchBar.setPlaceholderText("Buscar por Código, Nombre u Organismo...")
        self.searchBar.setClearButtonEnabled(True)
        
        self.filterButton = ToolButton(FIF.FILTER, self)
        self.filterButton.setToolTip("Filtros Avanzados")
        self.filterButton.clicked.connect(self._show_filter_flyout)
        
        self.topLayout.addWidget(self.searchBar, 1)
        self.topLayout.addWidget(self.filterButton)
        self.vBoxLayout.addLayout(self.topLayout)

        self.tableContainer = QFrame()
        self.tableLayout = QVBoxLayout(self.tableContainer)
        self.tableLayout.setContentsMargins(0, 5, 0, 0)
        self.vBoxLayout.addWidget(self.tableContainer)

    def _show_filter_flyout(self):
        self.filter_view = QFrame()
        self.filter_view.setObjectName("FilterFlyout")
        self.filter_view.setFixedWidth(450) 
        self.filter_view.setStyleSheet("QFrame#FilterFlyout { background-color: #ffffff; border: 1px solid #e5e5e5; border-radius: 8px; } QLabel { background-color: transparent; }")
        
        layout = QVBoxLayout(self.filter_view)
        layout.setSpacing(15); layout.setContentsMargins(20, 20, 20, 20)
        
        h_top = QHBoxLayout()
        lbl_zeros = BodyLabel("Mostrar Puntajes 0")
        switch_zeros = SwitchButton()
        switch_zeros.setOnText("Sí"); switch_zeros.setOffText("No")
        switch_zeros.setChecked(self.filter_state["show_zeros"])
        switch_zeros.checkedChanged.connect(lambda c: self._update_filter("show_zeros", c))
        h_top.addWidget(lbl_zeros); h_top.addStretch(); h_top.addWidget(switch_zeros)
        layout.addLayout(h_top); layout.addWidget(self._sep())

        h_monto = QHBoxLayout()
        h_monto.addWidget(StrongBodyLabel("Monto Mínimo ($):"))
        h_monto.addStretch()
        spin_monto = SpinBox()
        spin_monto.setRange(0, 999999999); spin_monto.setSingleStep(100000); spin_monto.setFixedWidth(140)
        spin_monto.setButtonSymbols(QAbstractSpinBox.NoButtons)
        spin_monto.setValue(self.filter_state["monto"])
        spin_monto.valueChanged.connect(lambda v: self._update_filter("monto", v))
        h_monto.addWidget(spin_monto)
        layout.addLayout(h_monto); layout.addWidget(self._sep())

        layout.addWidget(StrongBodyLabel("Filtro de Estados"))
        chk_2do = CheckBox("Solo 2° Llamado")
        chk_2do.setChecked(self.filter_state["2do_llamado"])
        chk_2do.stateChanged.connect(lambda s: self._update_filter("2do_llamado", chk_2do.isChecked()))
        layout.addWidget(chk_2do)
        
        self.combo_states = CheckableComboBox()
        self.combo_states.setPlaceholderText("Seleccionar estados...")
        self.combo_states.addItems(self.available_states)
        for i, state in enumerate(self.available_states):
            if state in self.filter_state["selected_states"]:
                self.combo_states.setItemChecked(i, True)
        self.combo_states.checkedChanged.connect(self._on_combo_states_changed)
        layout.addWidget(self.combo_states); layout.addWidget(self._sep())

        def create_date_block(title, key_from, key_to, cal_from_attr, cal_to_attr):
            container = QWidget(); v_layout = QVBoxLayout(container); v_layout.setContentsMargins(0,0,0,0); v_layout.setSpacing(8)
            v_layout.addWidget(StrongBodyLabel(title))
            h_inputs = QHBoxLayout(); h_inputs.setSpacing(15)
            v_from = QVBoxLayout(); v_from.setSpacing(2); v_from.addWidget(BodyLabel("Desde", self))
            cal_from = CalendarPicker(); cal_from.setDateFormat(Qt.ISODate); setattr(self, cal_from_attr, cal_from) 
            v_from.addWidget(cal_from)
            v_to = QVBoxLayout(); v_to.setSpacing(2); v_to.addWidget(BodyLabel("Hasta", self))
            cal_to = CalendarPicker(); cal_to.setDateFormat(Qt.ISODate); setattr(self, cal_to_attr, cal_to) 
            v_to.addWidget(cal_to)
            h_inputs.addLayout(v_from); h_inputs.addLayout(v_to); v_layout.addLayout(h_inputs)
            return container

        block_pub = create_date_block("Fecha de Publicación", "pub_from", "pub_to", "cal_pub_from", "cal_pub_to")
        layout.addWidget(block_pub)
        if self.filter_state["pub_from"]: self.cal_pub_from.setDate(QDate(self.filter_state["pub_from"]))
        if self.filter_state["pub_to"]: self.cal_pub_to.setDate(QDate(self.filter_state["pub_to"]))
        self.cal_pub_from.dateChanged.connect(lambda d: self._update_date("pub_from", d))
        self.cal_pub_to.dateChanged.connect(lambda d: self._update_date("pub_to", d))

        layout.addSpacing(5)
        block_close = create_date_block("Fecha de Cierre", "close_from", "close_to", "cal_close_from", "cal_close_to")
        layout.addWidget(block_close)
        if self.filter_state["close_from"]: self.cal_close_from.setDate(QDate(self.filter_state["close_from"]))
        if self.filter_state["close_to"]: self.cal_close_to.setDate(QDate(self.filter_state["close_to"]))
        self.cal_close_from.dateChanged.connect(lambda d: self._update_date("close_from", d))
        self.cal_close_to.dateChanged.connect(lambda d: self._update_date("close_to", d))

        layout.addStretch()
        h_reset = QHBoxLayout(); h_reset.addStretch()
        btn_reset = ToolButton(FIF.DELETE, self); btn_reset.setToolTip("Limpiar Filtros")
        btn_reset.clicked.connect(self._reset_filters)
        h_reset.addWidget(btn_reset); layout.addLayout(h_reset)
        Flyout.make(self.filter_view, self.filterButton, self, FlyoutAnimationType.DROP_DOWN)

    def _sep(self):
        sep = QFrame(); sep.setFrameShape(QFrame.HLine); sep.setStyleSheet("background-color: #eee; margin: 4px 0;")
        return sep

    def _update_filter(self, key, value):
        self.filter_state[key] = value
        self.filtersChanged.emit()
        
    def _update_date(self, key, qdate: QDate):
        self.filter_state[key] = qdate.toPython()
        self.filtersChanged.emit()

    def _on_combo_states_changed(self):
        items = self.combo_states.checkedItems()
        self.filter_state["selected_states"] = [item.text() for item in items]
        self.filtersChanged.emit()

    def _reset_filters(self):
        self.filter_state = { "2do_llamado": False, "monto": 0, "show_zeros": False, "selected_states": [], "pub_from": None, "pub_to": None, "close_from": None, "close_to": None }
        self.filtersChanged.emit()

# --- CLASE PRINCIPAL ---
class MainWindow(FluentWindow, ThreadingMixin, MainSlotsMixin, DataLoaderMixin, ContextMenuMixin, TableManagerMixin):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Monitor CA")
        self.resize(1280, 800)
        self.force_close = False
        self.thread_pool = QThreadPool.globalInstance()
        self.running_workers = []
        self.is_task_running = False
        self.last_error = None
        self.executed_tasks_log = set()
        
        # Inyección de Dependencias
        try:
            self.settings_manager = SettingsManager()
            self.db_service = DbService(SessionLocal) 
            self.scraper_service = ScraperService()
            self.excel_service = ExcelService(self.db_service)
            self.score_engine = ScoreEngine(self.db_service)
            self.etl_service = EtlService(self.db_service, self.scraper_service, self.score_engine)
        except Exception as e:
            logger.critical(f"Error fatal iniciando servicios: {e}")
            sys.exit(1)

        # Timers
        self.scheduler_timer = QTimer(self)
        self.scheduler_timer.timeout.connect(self.check_scheduled_tasks)
        
        # Barra de estado inferior (Progress)
        self.progress_container = ClickableContainer(self)
        self.progress_layout = QVBoxLayout(self.progress_container)
        self.progress_layout.setContentsMargins(10, 0, 10, 0); self.progress_layout.setSpacing(5)
        self.lbl_progress_status = BodyLabel("Listo", self); self.lbl_progress_status.setStyleSheet("color: gray; font-size: 12px;")
        self.progress_bar = ProgressBar(self); self.progress_bar.setRange(0, 100); self.progress_bar.setValue(0); self.progress_bar.hide()
        self.progress_layout.addWidget(self.lbl_progress_status); self.progress_layout.addWidget(self.progress_bar)

        self.tray_icon = None

        # 1. Tab Unificada
        self.unifiedInterface = TableInterface("tab_unified", self)
        self.model_tab1 = QStandardItemModel(0, len(COLUMN_HEADERS))
        self.proxy_tab1 = LicitacionProxyModel(self)
        self.proxy_tab1.setSourceModel(self.model_tab1)
        self.table_unified = self.crear_tabla_view(self.model_tab1, "tab_unified")
        self.table_unified.setModel(self.proxy_tab1) 
        self.unifiedInterface.tableLayout.addWidget(self.table_unified)
        
        # 2. Tab Seguimiento
        self.seguimientoInterface = TableInterface("tab_seguimiento", self)
        self.model_tab3 = QStandardItemModel(0, len(COLUMN_HEADERS))
        self.proxy_tab3 = LicitacionProxyModel(self)
        self.proxy_tab3.setSourceModel(self.model_tab3)
        self.table_seguimiento = self.crear_tabla_view(self.model_tab3, "tab_seguimiento")
        self.table_seguimiento.setModel(self.proxy_tab3)
        self.seguimientoInterface.tableLayout.addWidget(self.table_seguimiento)
        
        # 3. Tab Ofertadas
        self.ofertadasInterface = TableInterface("tab_ofertadas", self)
        self.model_tab4 = QStandardItemModel(0, len(COLUMN_HEADERS))
        self.proxy_tab4 = LicitacionProxyModel(self)
        self.proxy_tab4.setSourceModel(self.model_tab4)
        self.table_ofertadas = self.crear_tabla_view(self.model_tab4, "tab_ofertadas")
        self.table_ofertadas.setModel(self.proxy_tab4)
        self.ofertadasInterface.tableLayout.addWidget(self.table_ofertadas)

        # Herramientas
        self.toolsInterface = GuiToolsWidget(self.db_service, self.settings_manager, self)
        self.toolsInterface.start_scraping_signal.connect(self.on_start_full_scraping)
        self.toolsInterface.start_export_signal.connect(self.on_start_export_dispatch)
        self.toolsInterface.start_recalculate_signal.connect(lambda: self.on_run_recalculate_thread(silent=True))
        self.toolsInterface.settings_changed_signal.connect(self.on_settings_changed)
        self.toolsInterface.autopilot_config_changed_signal.connect(lambda: self.settings_manager.load_settings())
        
        self.detail_drawer = DetailDrawer(self)

        self.initNavigation()
        self._setup_tray_icon()
        self._connect_table_signals()
        
        # Arranque automático
        self.scheduler_timer.start(30000)
        QTimer.singleShot(500, self.on_load_data_thread)
        QTimer.singleShot(3000, self.iniciar_limpieza_silenciosa)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'detail_drawer'):
            self.detail_drawer.resize(self.detail_drawer.width(), self.height())

    def initNavigation(self):
        self.addSubInterface(self.unifiedInterface, FIF.HOME, "Candidatas", NavigationItemPosition.TOP)
        self.addSubInterface(self.seguimientoInterface, FIF.HEART, "Seguimiento", NavigationItemPosition.TOP)
        self.addSubInterface(self.ofertadasInterface, FIF.SHOPPING_CART, "Ofertadas", NavigationItemPosition.TOP)
        self.navigationInterface.addSeparator()
        self.navigationInterface.addItem(routeKey="update_web", icon=FIF.GLOBE, text="Actualizar info pestañas", onClick=self._show_update_flyout, position=NavigationItemPosition.TOP)
        self.addSubInterface(self.toolsInterface, FIF.TILES, "Herramientas", NavigationItemPosition.TOP)
        self.navigationInterface.addWidget(routeKey="progress_widget", widget=self.progress_container, onClick=lambda: None, position=NavigationItemPosition.BOTTOM)
        self.navigationInterface.addItem(routeKey="refresh", icon=FIF.SYNC, text="Refrescar Tablas", onClick=self.on_load_data_thread, position=NavigationItemPosition.BOTTOM)

    def _show_update_flyout(self):
        view = QFrame(); view.setObjectName("UpdateFlyout"); view.setFixedWidth(300)
        view.setStyleSheet("QFrame#UpdateFlyout { background-color: #ffffff; border: 1px solid #e5e5e5; border-radius: 8px; } QLabel { background-color: transparent; }")
        layout = QVBoxLayout(view); layout.setSpacing(10); layout.setContentsMargins(15, 15, 15, 15)
        layout.addWidget(StrongBodyLabel("Seleccionar qué actualizar:")); layout.addWidget(BodyLabel("Busca info nueva en Mercado Público.", self))
        self.chk_upd_candidatas = CheckBox("Candidatas"); self.chk_upd_seguimiento = CheckBox("Seguimiento"); self.chk_upd_ofertadas = CheckBox("Ofertadas")
        self.chk_upd_seguimiento.setChecked(True); self.chk_upd_ofertadas.setChecked(True)
        layout.addWidget(self.chk_upd_candidatas); layout.addWidget(self.chk_upd_seguimiento); layout.addWidget(self.chk_upd_ofertadas); layout.addSpacing(10)
        btn_run = PrimaryPushButton("Actualizar Ahora"); btn_run.clicked.connect(lambda: self._on_run_selective_update(view)); layout.addWidget(btn_run)
        target = self.navigationInterface.widget(routeKey="update_web")
        Flyout.make(view, target, self, FlyoutAnimationType.PULL_UP)

    def _on_run_selective_update(self, flyout_view):
        scopes = []
        if self.chk_upd_candidatas.isChecked(): scopes.append("candidatas")
        if self.chk_upd_seguimiento.isChecked(): scopes.append("seguimiento")
        if self.chk_upd_ofertadas.isChecked(): scopes.append("ofertadas")
        if not scopes: InfoBar.warning("Atención", "Debes seleccionar al menos una opción.", parent=self); return
        flyout_view.parent().close()
        if self.is_task_running: InfoBar.warning("Ocupado", "Ya hay una tarea en ejecución.", parent=self); return
        logger.info(f"Iniciando actualización selectiva para: {scopes}")
        self.start_task(task=self.etl_service.run_fase2_update, on_result=lambda: logger.info("Actualización selectiva OK"), on_error=self.on_task_error, on_finished=self.on_fase2_update_finished, on_progress=self.on_progress_update, on_progress_percent=self.on_progress_percent_update, task_kwargs={"scopes": scopes})

    def _connect_table_signals(self):
        ui = self.unifiedInterface
        ui.searchBar.textChanged.connect(lambda: self.update_proxy_filter(self.proxy_tab1, ui))
        ui.filtersChanged.connect(lambda: self.update_proxy_filter(self.proxy_tab1, ui))
        self.table_unified.customContextMenuRequested.connect(self.mostrar_menu_contextual)
        
        ui3 = self.seguimientoInterface
        ui3.searchBar.textChanged.connect(lambda: self.update_proxy_filter(self.proxy_tab3, ui3))
        ui3.filtersChanged.connect(lambda: self.update_proxy_filter(self.proxy_tab3, ui3))
        self.table_seguimiento.customContextMenuRequested.connect(self.mostrar_menu_contextual)
        
        ui4 = self.ofertadasInterface
        ui4.searchBar.textChanged.connect(lambda: self.update_proxy_filter(self.proxy_tab4, ui4))
        ui4.filtersChanged.connect(lambda: self.update_proxy_filter(self.proxy_tab4, ui4))
        self.table_ofertadas.customContextMenuRequested.connect(self.mostrar_menu_contextual)

        self.table_unified.doubleClicked.connect(self.on_table_double_clicked)
        self.table_seguimiento.doubleClicked.connect(self.on_table_double_clicked)
        self.table_ofertadas.doubleClicked.connect(self.on_table_double_clicked)

    def update_proxy_filter(self, proxy_model, ui_obj):
        proxy_model.set_filter_parameters(
            ui_obj.searchBar.text(), ui_obj.filter_state["monto"], ui_obj.filter_state["show_zeros"], ui_obj.filter_state["2do_llamado"],
            ui_obj.filter_state["selected_states"], ui_obj.filter_state["pub_from"], ui_obj.filter_state["pub_to"],
            ui_obj.filter_state["close_from"], ui_obj.filter_state["close_to"]
        )

    def poblar_tab_unificada(self, data):
        super().poblar_tab_unificada(data)
        self.update_proxy_filter(self.proxy_tab1, self.unifiedInterface)

    @Slot()
    def on_settings_changed(self):
        logger.info("Configuración interna actualizada."); self.score_engine.recargar_reglas()

    @Slot()
    def on_run_recalculate_thread(self, silent=False):
        if self.is_task_running: return
        if not silent:
            if QMessageBox.question(self, "Confirmar Recálculo", "Se recalcularán todos los puntajes.", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
                self._start_recalc_task(silent)
        else: self._start_recalc_task(silent)
    
    def _start_recalc_task(self, silent): self.start_task(task=self.etl_service.run_recalculo_total_fase_1, on_finished=lambda: self.on_recalculate_finished_custom(silent))
    def on_recalculate_finished_custom(self, silent): self.set_ui_busy(False); self.on_load_data_thread(); InfoBar.success("Proceso Completado", "Puntajes actualizados.", parent=self)
    
    @Slot(list)
    def on_start_export_dispatch(self, lista_tareas):
        if self.is_task_running: return
        saved_path = self.settings_manager.get_setting("user_export_path")
        if not saved_path or not os.path.exists(saved_path):
            folder = QFileDialog.getExistingDirectory(self, "Seleccionar Carpeta Base")
            if not folder: return
            self.settings_manager.set_setting("user_export_path", folder); self.settings_manager.save_settings(self.settings_manager.config); saved_path = folder
        self.start_task(task=self.excel_service.ejecutar_exportacion_lote, on_result=lambda r: self._show_export_success(r, saved_path), on_error=self.on_task_error, task_args=(lista_tareas, saved_path))
    
    def _show_export_success(self, resultados: List[str], base_path: str):
        exitos = [r for r in resultados if not r.startswith("ERROR")]
        if exitos: InfoBar.success("Exportación Finalizada", f"Archivos en: {base_path}", parent=self)
    
    def check_scheduled_tasks(self):
        if self.is_task_running: return 
        self.settings_manager.load_settings()
        now_str = QTime.currentTime().toString("HH:mm"); today_str = datetime.date.today().strftime("%Y-%m-%d")
        if self.settings_manager.get_setting("auto_extract_enabled"):
            if now_str == self.settings_manager.get_setting("auto_extract_time") and f"{today_str}_extract" not in self.executed_tasks_log:
                self.executed_tasks_log.add(f"{today_str}_extract"); self.on_auto_extract_yesterday()
        if self.settings_manager.get_setting("auto_update_enabled"):
            if now_str == self.settings_manager.get_setting("auto_update_time") and f"{today_str}_update" not in self.executed_tasks_log:
                self.executed_tasks_log.add(f"{today_str}_update"); self.on_run_fase2_update_thread_auto()

    @Slot()
    def on_auto_extract_yesterday(self):
        y = datetime.date.today() - datetime.timedelta(days=1)
        self.start_task(
            task=self.etl_service.run_etl_live_to_db, 
            on_finished=self.on_auto_task_finished, 
            task_kwargs={"config": {"mode":"to_db", "date_from":y, "date_to":y, "max_paginas":0}}
        )
    
    @Slot(dict)
    def on_start_full_scraping(self, config: dict):
        """Inicia el proceso de scraping desde la herramienta."""
        logger.info(f"Recibida configuración de scraping: {config}")
        
        task_to_run = self.etl_service.run_etl_live_to_db 
        
        # Callback para manejar el resultado numérico
        def on_etl_result(cantidad_procesada):
            logger.info("Proceso ETL completo OK")
            if isinstance(cantidad_procesada, int) and cantidad_procesada > 0:
                msg = f"Se procesaron {cantidad_procesada} registros exitosamente."
                QMessageBox.information(self, "Proceso Completado", msg)
            elif cantidad_procesada == 0:
                 QMessageBox.information(self, "Sin Resultados", "No se encontraron licitaciones nuevas en el periodo.")

        self.start_task(
            task=task_to_run,
            on_result=on_etl_result, # Ahora espera un INT
            on_error=self.on_task_error,
            on_finished=self.on_scraping_completed,
            on_progress=self.on_progress_update,
            on_progress_percent=self.on_progress_percent_update,
            task_kwargs={"config": config}, 
        )

    @Slot()
    def iniciar_limpieza_silenciosa(self): self.start_task(task=self.etl_service.run_limpieza_automatica, on_result=lambda: None)
    def set_ui_busy(self, busy: bool):
        self.is_task_running = busy
        if busy: self.progress_bar.show(); self.lbl_progress_status.setText("Iniciando..."); self.setCursor(Qt.WaitCursor)
        else: self.progress_bar.hide(); self.lbl_progress_status.setText("Listo"); self.progress_bar.setValue(0); self.setCursor(Qt.ArrowCursor)
    @Slot(str)
    def on_progress_update(self, message: str): self.lbl_progress_status.setText(message)
    def _setup_tray_icon(self):
        self.tray_icon = QSystemTrayIcon(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)), self)
        menu = QMenu(); menu.addAction("Restaurar").triggered.connect(self.showNormal); menu.addAction("Salir").triggered.connect(self.force_quit)
        self.tray_icon.setContextMenu(menu); self.tray_icon.show(); self.tray_icon.activated.connect(lambda r: self.showNormal() if r == QSystemTrayIcon.DoubleClick else None)
    def force_quit(self): self.force_close = True; self.close(); QApplication.instance().quit()
    def closeEvent(self, event):
        if self.force_close: event.accept()
        else: event.ignore(); self.hide(); InfoBar.info("Minimizado", "La aplicación sigue en la bandeja.", parent=self)

def run_gui():
    app = QApplication(sys.argv)
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    app.setQuitOnLastWindowClosed(False)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
# -*- coding: utf-8 -*-
from PySide6.QtCore import Qt, Slot, QUrl
from PySide6.QtGui import QDesktopServices, QAction
from PySide6.QtWidgets import QMenu, QMessageBox, QWidgetAction, QPushButton, QInputDialog
from qfluentwidgets import FluentIcon as FIF
from src.utils.logger import configurar_logger

logger = configurar_logger(__name__)

class MixinMenuContextual:
    @Slot(object)
    def mostrar_menu_contextual(self, pos):
        vista_origen = self.sender()
        if not vista_origen: return
        indice = vista_origen.indexAt(pos)
        if not indice.isValid(): return

        # Recuperar ID robustamente
        modelo_proxy = vista_origen.model()
        fila = indice.row()
        idx_score = modelo_proxy.index(fila, 0)
        
        # Intentar obtener ID de UserRole+1 
        ca_id = modelo_proxy.data(idx_score, Qt.UserRole + 1)
        # Fallback
        if not ca_id: ca_id = modelo_proxy.data(idx_score, Qt.UserRole)
            
        if not ca_id: return
        
        nombre_ca = modelo_proxy.data(modelo_proxy.index(fila, 1), Qt.DisplayRole)
        nombre_objeto = vista_origen.objectName()

        menu = QMenu()
        menu.setStyleSheet("""
            QMenu { background-color: #ffffff; border: 1px solid #e0e0e0; border-radius: 8px; padding: 5px; }
            QMenu::item { padding: 6px 24px; border-radius: 4px; color: black; }
            QMenu::item:selected { background-color: #f0f0f0; }
            QMenu::separator { height: 1px; background: #e0e0e0; margin: 4px 10px; }
        """)

        # Acciones Generales
        accion_web = QAction(FIF.GLOBE.icon(), "Ver ficha web", self)
        accion_web.triggered.connect(lambda: self._abrir_web_por_id(ca_id))
        
        accion_nota = QAction(FIF.EDIT.icon(), "Agregar/Editar nota", self)
        accion_nota.triggered.connect(lambda: self._dialogo_nota(ca_id))
        
        accion_borrar_nota = QAction(FIF.DELETE.icon(), "Borrar nota", self)
        accion_borrar_nota.triggered.connect(lambda: self._borrar_nota(ca_id))

        accion_mover_ofer = QAction(FIF.SHOPPING_CART.icon(), "Mover a Ofertada", self)
        accion_mover_ofer.triggered.connect(lambda: self._marcar_ofertada(ca_id))
        
        accion_mover_fav = QAction(FIF.HEART.icon(), "Mover a Favoritas", self)
        accion_mover_fav.triggered.connect(lambda: self._mover_a_favoritos(ca_id))

        # --- LÓGICA DE MENÚ POR PESTAÑA ---

        if nombre_objeto == "tab_unified": # Candidatas
            menu.addAction(accion_mover_fav)
            menu.addAction(accion_web)
            menu.addAction(accion_mover_ofer)
            menu.addSeparator()
            self._agregar_accion_roja(menu, "Ocultar de lista", FIF.DELETE, lambda: self._ocultar_de_candidatas(ca_id, nombre_ca))

        elif nombre_objeto == "tab_seguimiento": # Favoritas
            menu.addAction(accion_mover_ofer)
            act_unfav = QAction(FIF.UNPIN.icon(), "Dejar de seguir", self)
            act_unfav.triggered.connect(lambda: self._quitar_de_favoritos(ca_id))
            menu.addAction(act_unfav)
            menu.addSeparator()
            menu.addAction(accion_nota)
            menu.addAction(accion_borrar_nota)
            menu.addAction(accion_web)

        elif nombre_objeto == "tab_ofertadas": # Ofertadas
            menu.addAction(accion_mover_fav) # Regresar a favoritas
            act_unofer = QAction(FIF.REMOVE_FROM.icon(), "Quitar de ofertadas", self)
            act_unofer.triggered.connect(lambda: self._desmarcar_ofertada(ca_id))
            menu.addAction(act_unofer)
            menu.addSeparator()
            menu.addAction(accion_nota)
            menu.addAction(accion_borrar_nota)
            menu.addAction(accion_web)

        else:
            menu.addAction(accion_web)

        menu.exec(vista_origen.viewport().mapToGlobal(pos))

    def _agregar_accion_roja(self, menu, text, icon, slot):
        btn = QPushButton(f"  {text}")
        btn.setIcon(icon.icon())
        btn.setStyleSheet("QPushButton { text-align: left; color: #d9534f; background: transparent; border: none; padding: 6px 14px; font-weight: bold; border-radius: 4px; } QPushButton:hover { background-color: #ffe6e6; }")
        btn.clicked.connect(lambda: [menu.close(), slot()])
        act = QWidgetAction(menu); act.setDefaultWidget(btn); menu.addAction(act)

    def _abrir_web_por_id(self, ca_id): 
        self.start_task(self.db_service.obtener_licitacion_por_id, self._callback_abrir_url, task_args=(ca_id,))

    def _callback_abrir_url(self, lic): 
        if lic and lic.codigo_ca: 
            QDesktopServices.openUrl(QUrl(f"https://buscador.mercadopublico.cl/ficha?code={lic.codigo_ca}"))

    # Acciones con auto-refresh 
    def _mover_a_favoritos(self, cid): self.start_task(self.db_service.gestionar_favorito, on_finished=self.on_load_data_thread, task_args=(cid, True))
    def _quitar_de_favoritos(self, cid): self.start_task(self.db_service.gestionar_favorito, on_finished=self.on_load_data_thread, task_args=(cid, False))
    def _marcar_ofertada(self, cid): self.start_task(self.db_service.gestionar_ofertada, on_finished=self.on_load_data_thread, task_args=(cid, True))
    def _desmarcar_ofertada(self, cid): self.start_task(self.db_service.gestionar_ofertada, on_finished=self.on_load_data_thread, task_args=(cid, False))
    
    def _ocultar_de_candidatas(self, cid, nombre):
        if QMessageBox.question(self, "Ocultar", f"¿Ocultar esta licitación?\n{nombre}", QMessageBox.Yes|QMessageBox.No) == QMessageBox.Yes:
            self.start_task(self.db_service.ocultar_licitacion, on_finished=self.on_load_data_thread, task_args=(cid, True))

    def _dialogo_nota(self, cid):
        text, ok = QInputDialog.getMultiLineText(self, "Nota", "Escribe una nota:")
        if ok and text is not None:
            self.start_task(self.db_service.guardar_nota_usuario, on_finished=self.on_load_data_thread, task_args=(cid, text))

    def _borrar_nota(self, cid):
        if QMessageBox.question(self, "Borrar Nota", "¿Eliminar la nota asociada?", QMessageBox.Yes|QMessageBox.No) == QMessageBox.Yes:
            self.start_task(self.db_service.guardar_nota_usuario, on_finished=self.on_load_data_thread, task_args=(cid, ""))
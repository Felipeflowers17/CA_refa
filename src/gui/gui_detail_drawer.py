# -*- coding: utf-8 -*-
from collections import defaultdict
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QFrame
)
from PySide6.QtCore import Qt
from qfluentwidgets import (
    StrongBodyLabel, BodyLabel, SubtitleLabel, 
    CardWidget, TransparentToolButton, FluentIcon as FIF
)

from src.db.db_models import CaLicitacion

class DetailDrawer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.FixedWidth = 500
        
        self.setGeometry(0, 0, self.FixedWidth, parent.height())
        
        self.setStyleSheet("""
            DetailDrawer {
                background-color: #f3f3f3;
                border-left: 1px solid #d0d0d0;
            }
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QWidget#ContentWidget {
                background-color: transparent;
            }
            CardWidget#MainSheet {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
            }
        """)
        self.hide() 

        self.mainLayout = QVBoxLayout(self)
        self.mainLayout.setContentsMargins(0, 0, 0, 0)
        self.mainLayout.setSpacing(0)

        # Header
        self.headerFrame = QFrame()
        self.headerFrame.setStyleSheet("background-color: #ffffff; border-bottom: 1px solid #e5e5e5;")
        self.headerLayout = QHBoxLayout(self.headerFrame)
        self.headerLayout.setContentsMargins(20, 15, 20, 15)
        
        self.titleLabel = SubtitleLabel("Detalle de Licitación", self)
        self.btnClose = TransparentToolButton(FIF.CLOSE, self)
        self.btnClose.clicked.connect(self.close_drawer)
        
        self.headerLayout.addWidget(self.titleLabel)
        self.headerLayout.addStretch(1)
        self.headerLayout.addWidget(self.btnClose)
        
        self.mainLayout.addWidget(self.headerFrame)

        # Scroll
        self.scrollArea = QScrollArea()
        self.scrollArea.setWidgetResizable(True)
        
        self.contentWidget = QWidget()
        self.contentWidget.setObjectName("ContentWidget")
        self.contentLayout = QVBoxLayout(self.contentWidget)
        self.contentLayout.setContentsMargins(20, 20, 20, 20)
        
        self.scrollArea.setWidget(self.contentWidget)
        self.mainLayout.addWidget(self.scrollArea)

        self._init_unified_sheet()

    def _init_unified_sheet(self):
        self.mainSheet = CardWidget(self)
        self.mainSheet.setObjectName("MainSheet")
        self.sheetLayout = QVBoxLayout(self.mainSheet)
        self.sheetLayout.setContentsMargins(24, 24, 24, 24)
        self.sheetLayout.setSpacing(16)
        
        # Secciones
        self._add_section_title("Información General")
        self.lblCodigo = self._add_field("Código:", "", vertical=False)
        self.lblNombre = self._add_field("Nombre:", "", vertical=True)
        self.lblEstado = self._add_field("Estado:", "", vertical=False)
        
        self._add_separator()
        
        self._add_section_title("Plazos y Montos")
        self.lblFechaPub = self._add_field("Publicación:", "", vertical=False)
        self.lblFechaCierre = self._add_field("Cierre:", "", vertical=False)
        self.lblFechaCierre2 = self._add_field("Cierre 2° Llamado:", "", vertical=False)
        # Se movio Plazo de entrega a la siguiente sección
        self.lblMonto = self._add_field("Monto:", "", vertical=False)
        self.lblProveedores = self._add_field("Proveedores:", "", vertical=False)

        self._add_separator()

        self._add_section_title("Descripción y Entrega")
        self.lblOrganismo = self._add_field("Organismo:", "", vertical=True)
        self.lblDireccion = self._add_field("Dirección Entrega:", "", vertical=True)
        self.lblPlazoEntrega = self._add_field("Plazo de entrega:", "", vertical=False) # <--- AQUI ESTA AHORA
        
        self.sheetLayout.addWidget(StrongBodyLabel("Descripción completa:", self))
        self.lblDescTexto = BodyLabel("", self)
        self.lblDescTexto.setWordWrap(True)
        self.lblDescTexto.setStyleSheet("color: #333;")
        self.sheetLayout.addWidget(self.lblDescTexto)

        self._add_separator()

        self._add_section_title("Productos Solicitados")
        self.productsLayout = QVBoxLayout()
        self.productsLayout.setSpacing(8)
        self.sheetLayout.addLayout(self.productsLayout)

        self.contentLayout.addWidget(self.mainSheet)
        self.contentLayout.addStretch(1)

    def _add_section_title(self, title):
        lbl = StrongBodyLabel(title, self)
        lbl.setStyleSheet("font-size: 16px; color: #005fb8;")
        self.sheetLayout.addWidget(lbl)

    def _add_separator(self):
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        line.setStyleSheet("background-color: #e0e0e0; margin-top: 8px; margin-bottom: 8px;")
        self.sheetLayout.addWidget(line)

    def _add_field(self, label_text, value_text, vertical=False):
        container = QWidget()
        if vertical:
            layout = QVBoxLayout(container); layout.setSpacing(2)
        else:
            layout = QHBoxLayout(container); layout.setSpacing(10)
        layout.setContentsMargins(0, 0, 0, 0)
        
        lbl = BodyLabel(label_text, self)
        lbl.setStyleSheet("color: #666; font-weight: 500;")
        val = BodyLabel(value_text, self)
        val.setWordWrap(True)
        val.setStyleSheet("color: #000; font-weight: 400;")

        layout.addWidget(lbl)
        if not vertical: layout.addWidget(val); layout.addStretch(1)
        else: layout.addWidget(val)
        
        self.sheetLayout.addWidget(container)
        return val

    def _clear_products_layout(self):
        while self.productsLayout.count():
            child = self.productsLayout.takeAt(0)
            if child.widget(): child.widget().deleteLater()

    def _create_product_row(self, nombre, descripcion, cantidad, unidad):
        frame = QFrame()
        frame.setStyleSheet("background-color: #f9f9f9; border: 1px solid #e0e0e0; border-radius: 6px;")
        layout = QVBoxLayout(frame); layout.setContentsMargins(10, 10, 10, 10)
        
        topRow = QHBoxLayout()
        nameLbl = StrongBodyLabel(nombre, frame); nameLbl.setStyleSheet("border: none; font-size: 13px;"); nameLbl.setWordWrap(True)
        qtyLbl = StrongBodyLabel(f"{cantidad} {unidad}", frame); qtyLbl.setStyleSheet("background-color: #e0f2f1; color: #00695c; border: none; border-radius: 4px; padding: 2px 6px;")
        
        topRow.addWidget(nameLbl, stretch=1); topRow.addWidget(qtyLbl)
        layout.addLayout(topRow)
        
        if descripcion and descripcion.strip():
            descLbl = BodyLabel(descripcion, frame); descLbl.setWordWrap(True)
            descLbl.setStyleSheet("color: #555; border: none; font-size: 12px; margin-top: 4px;")
            layout.addWidget(descLbl)
        return frame

    def set_data(self, licitacion: CaLicitacion):
        self.lblCodigo.setText(licitacion.codigo_ca)
        self.lblNombre.setText(licitacion.nombre)
        
        est = licitacion.estado_ca_texto or "N/A"
        if licitacion.estado_convocatoria == 2: est += " (2° Llamado)"
        self.lblEstado.setText(est)
        
        f_pub = licitacion.fecha_publicacion.strftime("%d-%m-%Y %H:%M") if licitacion.fecha_publicacion else "-"
        f_cierre = licitacion.fecha_cierre.strftime("%d-%m-%Y %H:%M") if licitacion.fecha_cierre else "-"
        f_cierre2 = licitacion.fecha_cierre_segundo_llamado.strftime("%d-%m-%Y %H:%M") if licitacion.fecha_cierre_segundo_llamado else "No aplica"
        
        self.lblFechaPub.setText(f_pub)
        self.lblFechaCierre.setText(f_cierre)
        self.lblFechaCierre2.setText(f_cierre2)
        
        # Formato de dias
        if licitacion.plazo_entrega is not None: 
            if licitacion.plazo_entrega == 1:
                self.lblPlazoEntrega.setText("1 día")
            else:
                self.lblPlazoEntrega.setText(f"{licitacion.plazo_entrega} días")
        else: 
            self.lblPlazoEntrega.setText("No especificado")
        
        m = licitacion.monto_clp or 0
        self.lblMonto.setText(f"$ {int(m):,}".replace(",", "."))
        self.lblProveedores.setText(str(licitacion.proveedores_cotizando or 0))
        
        self.lblOrganismo.setText(licitacion.organismo.nombre if licitacion.organismo else "N/A")
        self.lblDireccion.setText(licitacion.direccion_entrega or "No especificada")
        self.lblDescTexto.setText(licitacion.descripcion or "Sin descripción.")
        
        self._clear_products_layout()
        prods = licitacion.productos_solicitados
        if prods and isinstance(prods, list):
            for p in prods:
                nm = (p.get('nombre') or 'Item').strip()
                ds = (p.get('descripcion') or '').strip()
                un = (p.get('unidad_medida') or 'unid').strip()
                try:
                    cv = float(p.get('cantidad', 0))
                    ct = f"{int(cv)}" if cv.is_integer() else f"{cv:.2f}"
                except: ct = "0"
                self.productsLayout.addWidget(self._create_product_row(nm, ds, ct, un))
        else:
            self.productsLayout.addWidget(BodyLabel("No hay detalle de productos.", self))

    def open_drawer(self): self.raise_(); self.show()
    def close_drawer(self): self.hide()
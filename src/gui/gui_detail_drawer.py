# -*- coding: utf-8 -*-
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QFrame
)
from PySide6.QtCore import Qt
from qfluentwidgets import (
    StrongBodyLabel, BodyLabel, SubtitleLabel, 
    CardWidget, TransparentToolButton, FluentIcon as FIF
)
from src.db.db_models import CaLicitacion

class PanelLateralDetalle(QWidget):
    """
    Panel deslizante lateral que muestra el detalle completo de una licitación.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.AnchoFijo = 500
        
        self.setGeometry(0, 0, self.AnchoFijo, parent.height())
        
        self.setStyleSheet("""
            PanelLateralDetalle {
                background-color: #f3f3f3;
                border-left: 1px solid #d0d0d0;
            }
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QWidget#WidgetContenido {
                background-color: transparent;
            }
            CardWidget#TarjetaPrincipal {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
            }
        """)
        self.hide() 

        self.layout_principal = QVBoxLayout(self)
        self.layout_principal.setContentsMargins(0, 0, 0, 0)
        self.layout_principal.setSpacing(0)

        # Encabezado
        self.frame_header = QFrame()
        self.frame_header.setStyleSheet("background-color: #ffffff; border-bottom: 1px solid #e5e5e5;")
        self.layout_header = QHBoxLayout(self.frame_header)
        self.layout_header.setContentsMargins(20, 15, 20, 15)
        
        self.lbl_titulo = SubtitleLabel("Ficha de Licitación", self)
        self.btn_cerrar = TransparentToolButton(FIF.CLOSE, self)
        self.btn_cerrar.clicked.connect(self.cerrar_panel)
        
        self.layout_header.addWidget(self.lbl_titulo)
        self.layout_header.addStretch(1)
        self.layout_header.addWidget(self.btn_cerrar)
        
        self.layout_principal.addWidget(self.frame_header)

        # Área de Scroll
        self.area_scroll = QScrollArea()
        self.area_scroll.setWidgetResizable(True)
        
        self.widget_contenido = QWidget()
        self.widget_contenido.setObjectName("WidgetContenido")
        self.layout_contenido = QVBoxLayout(self.widget_contenido)
        self.layout_contenido.setContentsMargins(20, 20, 20, 20)
        
        self.area_scroll.setWidget(self.widget_contenido)
        self.layout_principal.addWidget(self.area_scroll)

        self._inicializar_tarjeta_unica()

    def _inicializar_tarjeta_unica(self):
        self.tarjeta_info = CardWidget(self)
        self.tarjeta_info.setObjectName("TarjetaPrincipal")
        self.layout_tarjeta = QVBoxLayout(self.tarjeta_info)
        self.layout_tarjeta.setContentsMargins(24, 24, 24, 24)
        self.layout_tarjeta.setSpacing(16)
        
        # --- Secciones ---
        self._agregar_titulo_seccion("Información General")
        self.val_codigo = self._agregar_campo("Código:", "", vertical=False)
        self.val_nombre = self._agregar_campo("Nombre:", "", vertical=True)
        self.val_estado = self._agregar_campo("Estado:", "", vertical=False)
        
        self._agregar_separador()
        
        self._agregar_titulo_seccion("Plazos y Presupuesto")
        self.val_fecha_pub = self._agregar_campo("Publicación:", "", vertical=False)
        self.val_fecha_cierre = self._agregar_campo("Cierre:", "", vertical=False)
        self.val_fecha_cierre2 = self._agregar_campo("Cierre 2° Llamado:", "", vertical=False)
        self.val_monto = self._agregar_campo("Monto:", "", vertical=False)
        self.val_proveedores = self._agregar_campo("Proveedores:", "", vertical=False)

        self._agregar_separador()

        self._agregar_titulo_seccion("Entrega y Ubicación")
        self.val_organismo = self._agregar_campo("Organismo:", "", vertical=True)
        self.val_direccion = self._agregar_campo("Dirección:", "", vertical=True)
        self.val_plazo_entrega = self._agregar_campo("Plazo de entrega:", "", vertical=False)
        
        self.layout_tarjeta.addWidget(StrongBodyLabel("Descripción Técnica:", self))
        self.val_descripcion = BodyLabel("", self)
        self.val_descripcion.setWordWrap(True)
        self.val_descripcion.setStyleSheet("color: #333;")
        # Habilitar selección en descripción
        self.val_descripcion.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.layout_tarjeta.addWidget(self.val_descripcion)

        self._agregar_separador()

        self._agregar_titulo_seccion("Productos Requeridos")
        self.layout_productos = QVBoxLayout()
        self.layout_productos.setSpacing(8)
        self.layout_tarjeta.addLayout(self.layout_productos)

        self.layout_contenido.addWidget(self.tarjeta_info)
        self.layout_contenido.addStretch(1)

    def _agregar_titulo_seccion(self, texto):
        lbl = StrongBodyLabel(texto, self)
        lbl.setStyleSheet("font-size: 16px; color: #005fb8;")
        self.layout_tarjeta.addWidget(lbl)

    def _agregar_separador(self):
        linea = QFrame()
        linea.setFrameShape(QFrame.HLine)
        linea.setFrameShadow(QFrame.Sunken)
        linea.setStyleSheet("background-color: #e0e0e0; margin-top: 8px; margin-bottom: 8px;")
        self.layout_tarjeta.addWidget(linea)

    def _agregar_campo(self, etiqueta, valor, vertical=False):
        contenedor = QWidget()
        if vertical:
            l = QVBoxLayout(contenedor); l.setSpacing(2)
        else:
            l = QHBoxLayout(contenedor); l.setSpacing(10)
        l.setContentsMargins(0, 0, 0, 0)
        
        lbl = BodyLabel(etiqueta, self)
        lbl.setStyleSheet("color: #666; font-weight: 500;")
        val = BodyLabel(valor, self)
        val.setWordWrap(True)
        val.setStyleSheet("color: #000; font-weight: 400;")
        
        # HABILITAR SELECCIÓN DE TEXTO
        val.setTextInteractionFlags(Qt.TextSelectableByMouse)

        l.addWidget(lbl)
        if not vertical: 
            l.addWidget(val); l.addStretch(1)
        else: 
            l.addWidget(val)
        
        self.layout_tarjeta.addWidget(contenedor)
        return val

    def _limpiar_productos(self):
        while self.layout_productos.count():
            item = self.layout_productos.takeAt(0)
            if item.widget(): item.widget().deleteLater()

    def _crear_fila_producto(self, nombre, descripcion, cantidad, unidad):
        frame = QFrame()
        frame.setStyleSheet("background-color: #f9f9f9; border: 1px solid #e0e0e0; border-radius: 6px;")
        layout = QVBoxLayout(frame); layout.setContentsMargins(10, 10, 10, 10)
        
        fila_sup = QHBoxLayout()
        lbl_nom = StrongBodyLabel(nombre, frame); lbl_nom.setStyleSheet("border: none; font-size: 13px;"); lbl_nom.setWordWrap(True)
        # Habilitar selección en nombre producto
        lbl_nom.setTextInteractionFlags(Qt.TextSelectableByMouse)
        
        lbl_cant = StrongBodyLabel(f"{cantidad} {unidad}", frame); lbl_cant.setStyleSheet("background-color: #e0f2f1; color: #00695c; border: none; border-radius: 4px; padding: 2px 6px;")
        
        fila_sup.addWidget(lbl_nom, stretch=1); fila_sup.addWidget(lbl_cant)
        layout.addLayout(fila_sup)
        
        if descripcion and descripcion.strip():
            lbl_desc = BodyLabel(descripcion, frame); lbl_desc.setWordWrap(True)
            lbl_desc.setStyleSheet("color: #555; border: none; font-size: 12px; margin-top: 4px;")
            # Habilitar selección en descripción producto
            lbl_desc.setTextInteractionFlags(Qt.TextSelectableByMouse)
            layout.addWidget(lbl_desc)
        return frame

    def set_data(self, licitacion: CaLicitacion):
        """Puebla el panel con los datos de un objeto CaLicitacion."""
        self.val_codigo.setText(licitacion.codigo_ca)
        self.val_nombre.setText(licitacion.nombre)
        
        estado = licitacion.estado_ca_texto or "N/A"
        if licitacion.estado_convocatoria == 2: estado += " (2° Llamado)"
        self.val_estado.setText(estado)
        
        f_pub = licitacion.fecha_publicacion.strftime("%d-%m-%Y %H:%M") if licitacion.fecha_publicacion else "-"
        f_cierre = licitacion.fecha_cierre.strftime("%d-%m-%Y %H:%M") if licitacion.fecha_cierre else "-"
        f_cierre2 = licitacion.fecha_cierre_segundo_llamado.strftime("%d-%m-%Y %H:%M") if licitacion.fecha_cierre_segundo_llamado else "No aplica"
        
        self.val_fecha_pub.setText(f_pub)
        self.val_fecha_cierre.setText(f_cierre)
        self.val_fecha_cierre2.setText(f_cierre2)
        
        # Plazo entrega
        if licitacion.plazo_entrega is not None: 
            self.val_plazo_entrega.setText(f"{licitacion.plazo_entrega} días")
        else: 
            self.val_plazo_entrega.setText("No especificado")
        
        monto = licitacion.monto_clp or 0
        self.val_monto.setText(f"$ {int(monto):,}".replace(",", "."))
        self.val_proveedores.setText(str(licitacion.proveedores_cotizando or 0))
        
        self.val_organismo.setText(licitacion.organismo.nombre if licitacion.organismo else "N/A")
        self.val_direccion.setText(licitacion.direccion_entrega or "No especificada")
        self.val_descripcion.setText(licitacion.descripcion or "Sin descripción.")
        
        # Productos
        self._limpiar_productos()
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
                self.layout_productos.addWidget(self._crear_fila_producto(nm, ds, ct, un))
        else:
            self.layout_productos.addWidget(BodyLabel("No hay detalle de productos.", self))

    def open_drawer(self): self.raise_(); self.show()
    def cerrar_panel(self): self.hide()
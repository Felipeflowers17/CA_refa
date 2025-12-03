# -*- coding: utf-8 -*-
from PySide6.QtGui import QStandardItem, QBrush, QColor
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTableView, QHeaderView, QAbstractItemView

# Definición global de encabezados (Se agregó "Código")
COLUMN_HEADERS = [
    "Score", "Código", "Nombre", "Organismo", "Estado", 
    "Fecha Pub.", "Fecha Cierre", "Cierre 2°", "Monto", "Nota"
]

class MixinGestorTabla:
    def crear_tabla_view(self, model, object_name):
        table = QTableView(self)
        table.setObjectName(object_name)
        table.setModel(model)
        
        model.setHorizontalHeaderLabels(COLUMN_HEADERS)
        
        # Estilo y comportamiento
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        
        # Redimensionamiento interactivo
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        table.horizontalHeader().setStretchLastSection(True)
        
        # Anchos iniciales (Actualizados con nueva columna Código)
        table.setColumnWidth(0, 50)   # Score
        table.setColumnWidth(1, 110)  # Código (NUEVA)
        table.setColumnWidth(2, 280)  # Nombre
        table.setColumnWidth(3, 180)  # Organismo
        table.setColumnWidth(4, 90)   # Estado
        table.setColumnWidth(5, 80)   # Fecha Pub
        table.setColumnWidth(6, 100)  # Fecha Cierre
        table.setColumnWidth(7, 100)  # Fecha Cierre 2°
        table.setColumnWidth(8, 90)   # Monto
        table.setColumnWidth(9, 50)   # Nota
        
        table.setSortingEnabled(True)
        table.setContextMenuPolicy(Qt.CustomContextMenu)

        # Delegados para cortar texto largo (...)
        # IMPORTANTE: Los índices cambiaron al agregar la columna Código en index 1
        from src.gui.delegates import DelegadoTextoElidido
        table.setItemDelegateForColumn(2, DelegadoTextoElidido(table)) # Nombre ahora es 2
        table.setItemDelegateForColumn(3, DelegadoTextoElidido(table)) # Organismo ahora es 3

        return table

    def poblar_tabla_generica(self, model, lista_datos):
        """Llena un QStandardItemModel con objetos CaLicitacion."""
        model.removeRows(0, model.rowCount())
        
        for data in lista_datos:
            # 0. Score
            score = getattr(data, 'puntuacion_final', 0)
            item_score = QStandardItem(str(score))
            item_score.setData(score, Qt.DisplayRole)
            item_score.setData(getattr(data, 'ca_id', None), Qt.UserRole + 1)
            
            detalles = getattr(data, 'puntaje_detalle', [])
            if detalles and isinstance(detalles, list):
                item_score.setToolTip("\n".join(str(d) for d in detalles))
            
            bg_color = None
            if score >= 500: bg_color = QColor("#dff6dd") 
            elif score >= 10: bg_color = QColor("#e6f7ff") 
            elif score == 0: bg_color = QColor("#ffffff") 
            elif score < 0: bg_color = QColor("#ffe6e6") 
            
            if bg_color: item_score.setBackground(QBrush(bg_color))

            # 1. Código (NUEVA)
            codigo = getattr(data, 'codigo_ca', '') or ''
            item_codigo = QStandardItem(codigo)
            item_codigo.setToolTip(codigo)
            item_codigo.setData(codigo, Qt.UserRole)

            # 2. Nombre
            nombre = getattr(data, 'nombre', 'Sin Nombre') or 'Sin Nombre'
            item_nombre = QStandardItem(nombre)
            item_nombre.setToolTip(nombre)
            item_nombre.setData(nombre, Qt.UserRole)

            # 3. Organismo
            org_obj = getattr(data, 'organismo', None)
            org_nombre = org_obj.nombre if org_obj else 'N/A'
            item_org = QStandardItem(org_nombre)
            item_org.setToolTip(org_nombre)
            item_org.setData(org_nombre, Qt.UserRole) 

            # 4. Estado
            estado_txt = getattr(data, 'estado_ca_texto', 'N/A') or 'N/A'
            item_estado = QStandardItem(estado_txt)
            item_estado.setData(getattr(data, 'estado_convocatoria', 0), Qt.UserRole)
            item_estado.setData(estado_txt, Qt.UserRole + 2)

            # 5. Fecha Pub
            f_pub = getattr(data, 'fecha_publicacion', None)
            f_pub_str = f_pub.strftime("%d-%m") if f_pub else ""
            item_fpub = QStandardItem(f_pub_str)
            item_fpub.setData(f_pub, Qt.UserRole)

            # 6. Fecha Cierre
            f_cierre = getattr(data, 'fecha_cierre', None)
            f_cierre_str = f_cierre.strftime("%d-%m %H:%M") if f_cierre else ""
            item_fcierre = QStandardItem(f_cierre_str)
            item_fcierre.setData(f_cierre, Qt.UserRole)

            # 7. Fecha Cierre 2° Llamado
            f_cierre2 = getattr(data, 'fecha_cierre_segundo_llamado', None)
            f_cierre2_str = f_cierre2.strftime("%d-%m %H:%M") if f_cierre2 else "-"
            item_fcierre2 = QStandardItem(f_cierre2_str)
            item_fcierre2.setData(f_cierre2, Qt.UserRole)

            # 8. Monto
            monto = getattr(data, 'monto_clp', 0)
            monto_val = float(monto) if monto is not None else 0
            monto_str = f"${int(monto_val):,}".replace(",", ".") if monto is not None else "N/A"
            item_monto = QStandardItem(monto_str)
            item_monto.setData(monto_val, Qt.UserRole)

            # 9. Nota
            nota_texto = ""
            seguimiento = getattr(data, 'seguimiento', None)
            if seguimiento:
                nota_texto = getattr(seguimiento, 'notas', "") or ""
            
            display_nota = "📝" if nota_texto.strip() else ""
            item_nota = QStandardItem(display_nota)
            item_nota.setTextAlignment(Qt.AlignCenter)
            item_nota.setData(nota_texto, Qt.UserRole) 
            
            if nota_texto: 
                item_nota.setToolTip(f"Nota: {nota_texto}")

            # Fila final
            row_items = [
                item_score, item_codigo, item_nombre, item_org, item_estado, 
                item_fpub, item_fcierre, item_fcierre2, item_monto, item_nota
            ]
            
            model.appendRow(row_items)
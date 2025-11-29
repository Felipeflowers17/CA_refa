# -*- coding: utf-8 -*-
from PySide6.QtGui import QStandardItem, QBrush, QColor
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTableView, QHeaderView, QAbstractItemView

# Definición global de encabezados
COLUMN_HEADERS = [
    "Score", "Nombre", "Organismo", "Estado", 
    "Fecha Pub.", "Fecha Cierre", "Monto", "Nota"
]

class TableManagerMixin:
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
        
        # Anchos iniciales
        table.setColumnWidth(0, 60)   # Score
        table.setColumnWidth(1, 350)  # Nombre
        table.setColumnWidth(2, 200)  # Organismo
        table.setColumnWidth(3, 100)  # Estado
        table.setColumnWidth(4, 90)   # Fecha Pub
        table.setColumnWidth(5, 110)  # Fecha Cierre
        table.setColumnWidth(6, 100)  # Monto
        table.setColumnWidth(7, 60)   # Nota
        
        table.setSortingEnabled(True)
        table.setContextMenuPolicy(Qt.CustomContextMenu)

        # Importación tardía para evitar ciclos si 'delegates.py' importa algo de GUI
        from src.gui.delegates import ElidedTextDelegate
        table.setItemDelegateForColumn(1, ElidedTextDelegate(table))
        table.setItemDelegateForColumn(2, ElidedTextDelegate(table))
        
        return table

    def poblar_tabla(self, model, data_list):
        model.removeRows(0, model.rowCount())
        
        for data in data_list:
            # 1. Score
            score = getattr(data, 'puntuacion_final', 0)
            item_score = QStandardItem(str(score))
            item_score.setData(score, Qt.DisplayRole) # Para ordenamiento numérico
            item_score.setData(getattr(data, 'ca_id', None), Qt.UserRole + 1)
            
            # Detalle puntaje (Tooltip)
            detalles = getattr(data, 'puntaje_detalle', [])
            if detalles and isinstance(detalles, list):
                item_score.setToolTip("\n".join(str(d) for d in detalles))
            
            # Colores Condicionales
            bg_color = None
            if score >= 500: bg_color = QColor("#dff6dd") # Verde Muy Alto
            elif score >= 10: bg_color = QColor("#e6f7ff") # Azul Positivo
            elif score == 0: bg_color = QColor("#ffffff") # Blanco Neutro
            elif score < 0: bg_color = QColor("#ffe6e6") # Rojo Negativo
            
            if bg_color: item_score.setBackground(QBrush(bg_color))

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

            # 7. Monto
            monto = getattr(data, 'monto_clp', 0)
            monto_val = float(monto) if monto is not None else 0
            monto_str = f"${int(monto_val):,}".replace(",", ".") if monto is not None else "N/A"
            item_monto = QStandardItem(monto_str)
            item_monto.setData(monto_val, Qt.UserRole)

            # 8. Nota (Protegida)
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

            row_items = [
                item_score, item_nombre, item_org, item_estado, 
                item_fpub, item_fcierre, item_monto, item_nota
            ]
            
            model.appendRow(row_items)
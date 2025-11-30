# -*- coding: utf-8 -*-
from datetime import date, datetime
from PySide6.QtCore import QSortFilterProxyModel, Qt, QModelIndex

class ModeloProxyLicitacion(QSortFilterProxyModel):
    """
    Modelo Intermediario (Proxy) para filtrado y ordenamiento avanzado.
    Permite filtrar la tabla sin modificar los datos originales.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        # Estado de los filtros
        self.texto_filtro = ""
        self.monto_minimo = 0
        self.mostrar_ceros = False
        self.solo_segundo_llamado = False
        self.estados_seleccionados = []
        
        self.fecha_pub_desde = None
        self.fecha_pub_hasta = None
        self.fecha_cierre_desde = None
        self.fecha_cierre_hasta = None

        # Índices de columnas 
        self.IDX_SCORE = 0
        self.IDX_NOMBRE = 1
        self.IDX_ESTADO = 3
        self.IDX_PUB = 4
        self.IDX_CIERRE = 5
        self.IDX_MONTO = 6

    def establecer_parametros_filtro(self, texto, min_monto, mostrar_ceros, solo_2do, estados, p_desde, p_hasta, c_desde, c_hasta):
        """Actualiza todos los criterios de filtrado y refresca la vista."""
        self.texto_filtro = texto.lower()
        self.monto_minimo = min_monto
        self.mostrar_ceros = mostrar_ceros
        self.solo_segundo_llamado = solo_2do
        self.estados_seleccionados = estados
        self.fecha_pub_desde = p_desde
        self.fecha_pub_hasta = p_hasta
        self.fecha_cierre_desde = c_desde
        self.fecha_cierre_hasta = c_hasta
        
        self.invalidateFilter() # Fuerza el repintado de la tabla

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        """Lógica principal: Decide si una fila se muestra o se oculta."""
        model = self.sourceModel()
        if not model:
            return True

        # 1. Filtro de Puntaje Cero
        if not self.mostrar_ceros:
            idx_score = model.index(source_row, self.IDX_SCORE, source_parent)
            try:
                val_score = int(model.data(idx_score, Qt.DisplayRole) or 0)
                if val_score == 0:
                    return False
            except: pass

        # 2. Filtro de Texto (Búsqueda inteligente)
        if self.texto_filtro:
            idx_nombre = model.index(source_row, self.IDX_NOMBRE, source_parent)
            data_busqueda = str(model.data(idx_nombre, Qt.UserRole) or "").lower()
            if self.texto_filtro not in data_busqueda:
                return False

        # 3. Filtro de Estados Específicos
        idx_estado = model.index(source_row, self.IDX_ESTADO, source_parent)
        if self.estados_seleccionados:
            estado_fila = model.data(idx_estado, Qt.UserRole + 2) # Role personalizado para el texto exacto
            if estado_fila not in self.estados_seleccionados:
                return False

        # 4. Filtro Segundo Llamado
        if self.solo_segundo_llamado:
            estado_id = int(model.data(idx_estado, Qt.UserRole) or 0)
            if estado_id != 2: # 2 = Segundo llamado
                return False

        # 5. Filtro de Monto
        if self.monto_minimo > 0:
            idx_monto = model.index(source_row, self.IDX_MONTO, source_parent)
            try:
                val_monto = float(model.data(idx_monto, Qt.UserRole) or 0)
                if val_monto < self.monto_minimo:
                    return False
            except: return False

        # 6. Filtro Fecha Publicación
        if self.fecha_pub_desde or self.fecha_pub_hasta:
            idx_pub = model.index(source_row, self.IDX_PUB, source_parent)
            fecha_fila = model.data(idx_pub, Qt.UserRole) 
            if not fecha_fila:
                return False
            if isinstance(fecha_fila, datetime):
                fecha_fila = fecha_fila.date()
            
            if self.fecha_pub_desde and fecha_fila < self.fecha_pub_desde: return False
            if self.fecha_pub_hasta and fecha_fila > self.fecha_pub_hasta: return False

        # 7. Filtro Fecha Cierre
        if self.fecha_cierre_desde or self.fecha_cierre_hasta:
            idx_cierre = model.index(source_row, self.IDX_CIERRE, source_parent)
            fecha_fila_dt = model.data(idx_cierre, Qt.UserRole)
            if not fecha_fila_dt:
                return False
            fecha_solo_date = fecha_fila_dt.date() if isinstance(fecha_fila_dt, datetime) else fecha_fila_dt

            if self.fecha_cierre_desde and fecha_solo_date < self.fecha_cierre_desde: return False
            if self.fecha_cierre_hasta and fecha_solo_date > self.fecha_cierre_hasta: return False

        return True
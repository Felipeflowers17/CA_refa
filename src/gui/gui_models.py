# -*- coding: utf-8 -*-
from datetime import date, datetime
from PySide6.QtCore import QSortFilterProxyModel, Qt, QModelIndex

class LicitacionProxyModel(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.filter_text = ""
        self.min_amount = 0
        self.show_zeros = False
        self.only_2nd_call = False
        self.selected_states = []
        
        self.pub_date_from = None
        self.pub_date_to = None
        self.close_date_from = None
        self.close_date_to = None

        self.IDX_SCORE = 0
        self.IDX_NOMBRE = 1
        self.IDX_ESTADO = 3
        self.IDX_PUB = 4
        self.IDX_CIERRE = 5
        self.IDX_MONTO = 6

    def set_filter_parameters(self, text, min_amount, show_zeros, only_2nd, states, p_from, p_to, c_from, c_to):
        self.filter_text = text.lower()
        self.min_amount = min_amount
        self.show_zeros = show_zeros
        self.only_2nd_call = only_2nd
        self.selected_states = states
        self.pub_date_from = p_from
        self.pub_date_to = p_to
        self.close_date_from = c_from
        self.close_date_to = c_to
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        model = self.sourceModel()
        if not model:
            return True

        if not self.show_zeros:
            idx_score = model.index(source_row, self.IDX_SCORE, source_parent)
            try:
                score_val = int(model.data(idx_score, Qt.DisplayRole) or 0)
                if score_val == 0:
                    return False
            except: pass

        if self.filter_text:
            idx_nombre = model.index(source_row, self.IDX_NOMBRE, source_parent)
            search_data = str(model.data(idx_nombre, Qt.UserRole) or "").lower()
            if self.filter_text not in search_data:
                return False

        idx_estado = model.index(source_row, self.IDX_ESTADO, source_parent)
        if self.selected_states:
            estado_row = model.data(idx_estado, Qt.UserRole + 2)
            if estado_row not in self.selected_states:
                return False

        if self.only_2nd_call:
            estado_id = int(model.data(idx_estado, Qt.UserRole) or 0)
            if estado_id != 2:
                return False

        if self.min_amount > 0:
            idx_monto = model.index(source_row, self.IDX_MONTO, source_parent)
            try:
                monto_val = float(model.data(idx_monto, Qt.UserRole) or 0)
                if monto_val < self.min_amount:
                    return False
            except: return False

        if self.pub_date_from or self.pub_date_to:
            idx_pub = model.index(source_row, self.IDX_PUB, source_parent)
            row_date = model.data(idx_pub, Qt.UserRole) 
            if not row_date:
                return False
            if isinstance(row_date, datetime):
                row_date = row_date.date()
            
            if self.pub_date_from and row_date < self.pub_date_from: return False
            if self.pub_date_to and row_date > self.pub_date_to: return False

        if self.close_date_from or self.close_date_to:
            idx_cierre = model.index(source_row, self.IDX_CIERRE, source_parent)
            row_datetime = model.data(idx_cierre, Qt.UserRole)
            if not row_datetime:
                return False
            row_date_only = row_datetime.date() if isinstance(row_datetime, datetime) else row_datetime

            if self.close_date_from and row_date_only < self.close_date_from: return False
            if self.close_date_to and row_date_only > self.close_date_to: return False

        return True
# -*- coding: utf-8 -*-
"""
Modelos de la Base de Datos (SQLAlchemy ORM).
"""

import datetime
import enum  
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import (
    String, Integer, Float, Boolean, DateTime, JSON, ForeignKey, Enum, Text
)
from typing import Optional, List

class Base(DeclarativeBase):
    type_annotation_map = {
        dict[str, any]: JSON,
        list[dict[str, any]]: JSON,
        list[str]: JSON,  
    }

# --- Tablas de Jerarquía ---
class CaSector(Base):
    __tablename__ = "ca_sector"
    sector_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    organismos: Mapped[List["CaOrganismo"]] = relationship(back_populates="sector")

class CaOrganismo(Base):
    __tablename__ = "ca_organismo"
    organismo_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(1000), unique=True, index=True)
    sector_id: Mapped[int] = mapped_column(ForeignKey("ca_sector.sector_id"))
    sector: Mapped["CaSector"] = relationship(back_populates="organismos", lazy="joined")
    licitaciones: Mapped[List["CaLicitacion"]] = relationship(back_populates="organismo")

# --- Tablas de Aplicación ---
class CaLicitacion(Base):
    __tablename__ = "ca_licitacion"
    ca_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo_ca: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    nombre: Mapped[Optional[str]] = mapped_column(String(1000))
    monto_clp: Mapped[Optional[float]] = mapped_column(Float)
    fecha_publicacion: Mapped[Optional[datetime.date]] = mapped_column()
    fecha_cierre: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True))
    fecha_cierre_segundo_llamado: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    estado_ca_texto: Mapped[Optional[str]] = mapped_column(String(255))
    estado_convocatoria: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    proveedores_cotizando: Mapped[Optional[int]] = mapped_column(Integer)
    descripcion: Mapped[Optional[str]] = mapped_column(String)
    direccion_entrega: Mapped[Optional[str]] = mapped_column(String(1000))
    plazo_entrega: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Campos JSON
    productos_solicitados: Mapped[Optional[list[dict[str, any]]]] = mapped_column(JSON, nullable=True)
    puntaje_detalle: Mapped[Optional[list[str]]] = mapped_column(JSON, nullable=True)
    puntuacion_final: Mapped[int] = mapped_column(Integer, default=0, index=True)
    organismo_id: Mapped[Optional[int]] = mapped_column(ForeignKey("ca_organismo.organismo_id"))
    organismo: Mapped[Optional["CaOrganismo"]] = relationship(back_populates="licitaciones", lazy="joined")
    seguimiento: Mapped["CaSeguimiento"] = relationship(back_populates="licitacion", cascade="all, delete-orphan", lazy="joined")

class CaSeguimiento(Base):
    __tablename__ = "ca_seguimiento"
    ca_id: Mapped[int] = mapped_column(ForeignKey("ca_licitacion.ca_id", ondelete="CASCADE"), primary_key=True)
    es_favorito: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    es_ofertada: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    es_oculta: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    notas: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    licitacion: Mapped["CaLicitacion"] = relationship(back_populates="seguimiento")

# --- Tablas de Configuración ---

class CaKeyword(Base):
    __tablename__ = "ca_keyword"
    
    keyword_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    keyword: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    
    puntos_nombre: Mapped[int] = mapped_column(Integer, default=0)
    puntos_descripcion: Mapped[int] = mapped_column(Integer, default=0)
    puntos_productos: Mapped[int] = mapped_column(Integer, default=0)

    def __repr__(self):
        return f"<CaKeyword('{self.keyword}', N:{self.puntos_nombre}, D:{self.puntos_descripcion}, P:{self.puntos_productos})>"

class TipoReglaOrganismo(enum.Enum):
    PRIORITARIO = 'prioritario'
    NO_DESEADO = 'no_deseado'

class CaOrganismoRegla(Base):
    __tablename__ = "ca_organismo_regla"
    regla_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organismo_id: Mapped[int] = mapped_column(ForeignKey("ca_organismo.organismo_id", ondelete="CASCADE"), unique=True, index=True)
    tipo: Mapped[TipoReglaOrganismo] = mapped_column(Enum(TipoReglaOrganismo, name='tipo_regla_organismo_enum', native_enum=False), nullable=False, index=True)
    puntos: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    organismo: Mapped["CaOrganismo"] = relationship(lazy="joined")